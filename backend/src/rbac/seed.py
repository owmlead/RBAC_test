"""
测试数据种子脚本。
运行方式: python -m src.rbac.seed
"""
import asyncio
from sqlalchemy import delete, select

from src.rbac.core.security import hash_password
from src.rbac.db.session import AsyncSessionLocal, init_db
from src.rbac.models.permission import Permission
from src.rbac.models.role import Role
from src.rbac.models.role_permission import RolePermission
from src.rbac.models.user import User
from src.rbac.models.user_role import UserRole


# ── 权限树数据结构 ──
# (name, code, type, parent_key, path, icon, api_paths)
PERMISSIONS = [
    # ── 系统管理 ──
    ("系统管理", "system", "MENU", None, "/system", "SettingOutlined", None),
    # 用户管理
    ("用户管理", "user:manage", "MENU", "system", "/system/user", "UserOutlined", None),
    ("用户列表", "user:list", "BUTTON", "user:manage", None, None, ["GET /api/v1/user/"]),
    ("用户详情", "user:detail", "BUTTON", "user:manage", None, None, ["GET /api/v1/user/{user_id}"]),
    ("新增用户", "user:create", "BUTTON", "user:manage", None, None, ["POST /api/v1/user/"]),
    ("编辑用户", "user:update", "BUTTON", "user:manage", None, None, ["PUT /api/v1/user/{user_id}"]),
    ("删除用户", "user:delete", "BUTTON", "user:manage", None, None, ["DELETE /api/v1/user/{user_id}"]),
    ("分配角色", "user:assign-role", "BUTTON", "user:manage", None, None, ["PUT /api/v1/user/{user_id}/roles"]),
    ("踢人下线", "user:kick", "BUTTON", "user:manage", None, None, ["POST /api/v1/auth/kick-out"]),
    # 角色管理
    ("角色管理", "role:manage", "MENU", "system", "/system/role", "TeamOutlined", None),
    ("角色列表", "role:list", "BUTTON", "role:manage", None, None, ["GET /api/v1/role/"]),
    ("角色详情", "role:detail", "BUTTON", "role:manage", None, None, ["GET /api/v1/role/{role_id}"]),
    ("新增角色", "role:create", "BUTTON", "role:manage", None, None, ["POST /api/v1/role/"]),
    ("编辑角色", "role:update", "BUTTON", "role:manage", None, None, ["PUT /api/v1/role/{role_id}"]),
    ("删除角色", "role:delete", "BUTTON", "role:manage", None, None, ["DELETE /api/v1/role/{role_id}"]),
    ("角色分配用户", "role:assign-user", "BUTTON", "role:manage", None, None, ["DELETE /api/v1/role/{role_id}/users"]),
    # 权限管理
    ("资源管理", "permission:manage", "MENU", "system", "/system/permission", "ApartmentOutlined", None),
    ("资源列表", "permission:list", "BUTTON", "permission:manage", None, None, ["GET /api/v1/permission/tree"]),
    ("新增资源", "permission:create", "BUTTON", "permission:manage", None, None, ["POST /api/v1/permission/"]),
    ("编辑资源", "permission:update", "BUTTON", "permission:manage", None, None, ["PUT /api/v1/permission/{perm_id}"]),
    ("删除资源", "permission:delete", "BUTTON", "permission:manage", None, None, ["DELETE /api/v1/permission/{perm_id}"]),
    # ── 审计日志 ──
    ("审计日志", "audit:manage", "MENU", None, "/audit", "FileTextOutlined", None),
    ("日志列表", "audit:list", "BUTTON", "audit:manage", None, None, ["GET /api/v1/logs/"]),
]

# ── 角色定义 ──
# (role_name, role_code, description, parent_role_ids)
ROLES = [
    ("超级管理员", "SUPER_ADMIN", "拥有系统所有权限", None),
    ("管理员", "ADMIN", "可管理用户和角色，不可管理资源", None),
    ("编辑者", "EDITOR", "可查看并编辑用户", None),
    ("只读用户", "VIEWER", "仅可查看列表", None),
]

# ── 角色权限映射 ──
# role_code -> {"grant": [permission_codes], "deny": [permission_codes]}
ROLE_PERMS = {
    "SUPER_ADMIN": {
        "grant": [p[1] for p in PERMISSIONS],  # 所有权限
        "deny": [],
    },
    "ADMIN": {
        "grant": [
            "system", "user:manage", "user:list", "user:detail",
            "user:create", "user:update", "user:delete", "user:assign-role",
            "role:manage", "role:list", "role:detail", "role:create",
            "role:update", "role:delete", "role:assign-user",
            "audit:manage", "audit:list",
        ],
        "deny": [],
    },
    "EDITOR": {
        "grant": [
            "system", "user:manage", "user:list", "user:detail", "user:update",
            "role:manage", "role:list", "role:detail",
            "audit:manage", "audit:list",
        ],
        "deny": ["user:delete"],  # 演示 deny 优先
    },
    "VIEWER": {
        "grant": [
            "system", "user:manage", "user:list", "user:detail",
            "role:manage", "role:list", "role:detail",
            "audit:manage", "audit:list",
        ],
        "deny": [],
    },
}

# ── 用户定义 ──
# (username, password, real_name, gender, email, phone, role_codes)
USERS = [
    ("admin", "admin123", "系统管理员", 1, "admin@example.com", "13800000001", ["SUPER_ADMIN"]),
    ("editor", "editor123", "编辑小王", 2, "editor@example.com", "13800000002", ["EDITOR"]),
    ("viewer", "viewer123", "访客小李", 1, "viewer@example.com", "13800000003", ["VIEWER"]),
    ("multi", "multi123", "多角色用户", 1, "multi@example.com", "13800000004", ["EDITOR", "VIEWER"]),
]


async def seed():
    """写入测试数据（幂等：先清再插）。"""
    print("=" * 50)
    print("  开始写入测试数据...")
    print("=" * 50)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # ── 1. 清空数据（逆序处理外键依赖）──
            print("\n[1/5] 清空旧数据...")
            for table in [UserRole, RolePermission, User, Role, Permission]:
                await db.execute(delete(table))
            await db.flush()

            # ── 2. 插入权限 ──
            print("[2/5] 插入权限...")
            perm_map: dict[str, int] = {}  # code -> id
            for name, code, ptype, parent_key, path, icon, api_paths in PERMISSIONS:
                parent_id = perm_map.get(parent_key) if parent_key else None
                perm = Permission(
                    name=name, code=code, type=ptype,
                    parent_id=parent_id, path=path, icon=icon,
                    api_paths=api_paths, status=True,
                )
                db.add(perm)
                await db.flush()
                perm_map[code] = perm.id
            print(f"   [OK] 已插入 {len(PERMISSIONS)} 条权限")

            # ── 3. 插入角色 ──
            print("[3/5] 插入角色...")
            role_map: dict[str, int] = {}  # code -> id
            for role_name, role_code, desc, parent_ids in ROLES:
                is_sys = role_code == "SUPER_ADMIN"
                role = Role(
                    role_name=role_name, role_code=role_code,
                    description=desc, parent_role_ids=parent_ids,
                    is_system=is_sys, status=True,
                )
                db.add(role)
                await db.flush()
                role_map[role_code] = role.id
            print(f"   [OK] 已插入 {len(ROLES)} 个角色")

            # ── 4. 分配角色权限 ──
            print("[4/5] 分配角色权限...")
            rp_count = 0
            for role_code, perms in ROLE_PERMS.items():
                role_id = role_map[role_code]
                for code in perms["grant"]:
                    if code not in perm_map:
                        continue
                    db.add(RolePermission(
                        role_id=role_id,
                        permission_id=perm_map[code],
                        is_deny=False,
                    ))
                    rp_count += 1
                for code in perms["deny"]:
                    if code not in perm_map:
                        continue
                    db.add(RolePermission(
                        role_id=role_id,
                        permission_id=perm_map[code],
                        is_deny=True,
                    ))
                    rp_count += 1
            print(f"   [OK] 已分配 {rp_count} 条角色-权限关系")

            # ── 5. 插入用户并分配角色 ──
            print("[5/5] 插入用户并分配角色...")
            for username, pwd, real_name, gender, email, phone, role_codes in USERS:
                user = User(
                    username=username, password=hash_password(pwd),
                    real_name=real_name, gender=gender,
                    email=email, phone=phone, status=True,
                )
                db.add(user)
                await db.flush()
                for rc in role_codes:
                    if rc in role_map:
                        db.add(UserRole(user_id=user.id, role_id=role_map[rc]))
            print(f"   [OK] 已插入 {len(USERS)} 个用户")

        # 事务自动提交
        print("\n" + "=" * 50)
        print("  测试数据写入完成！")
        print("=" * 50)
        print("""
   ┌──────────┬──────────────┬──────────────────────┐
   │ 用户名   │ 密码         │ 角色                 │
   ├──────────┼──────────────┼──────────────────────┤
   │ admin    │ admin123     │ 超级管理员（全权限） │
   │ editor   │ editor123    │ 编辑者（user:delete 被 deny）│
   │ viewer   │ viewer123    │ 只读用户             │
   │ multi    │ multi123     │ 编辑者 + 只读        │
   └──────────┴──────────────┴──────────────────────┘
        """)


if __name__ == "__main__":
    asyncio.run(seed())
