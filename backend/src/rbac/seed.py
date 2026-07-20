"""
测试数据种子脚本。

提供丰富的演示数据：多级菜单权限、角色继承（含 deny 优先）、
多角色用户、禁用角色/用户、分页测试等场景。

运行方式: cd backend && python -m src.rbac.seed
"""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

from src.rbac.core.security import hash_password
from src.rbac.db.session import AsyncSessionLocal
from src.rbac.models.permission import Permission
from src.rbac.models.role import Role
from src.rbac.models.role_permission import RolePermission
from src.rbac.models.user import User
from src.rbac.models.user_role import UserRole

# ════════════════════════════════════════════════════════════════
# 权限资源树
# (name, code, type, parent_key, path, icon, api_paths)
# parent_key 引用同组权限的 code，用作插入时查找父节点 ID
# ════════════════════════════════════════════════════════════════
PERMISSIONS: list[tuple] = [
    # ── 仪表盘 ──
    ("仪表盘", "dashboard", "MENU", None, "/dashboard", "HomeFilled", None),
    ("首页概览", "dashboard:view", "BUTTON", "dashboard", None, None,
     ["GET /api/v1/dashboard/stats"]),

    # ── 系统管理 ──
    ("系统管理", "system", "MENU", None, "/system", "Setting", None),

    # ── 用户管理 ──
    ("用户管理", "user:manage", "MENU", "system", "/system/user", "User", None),
    ("用户列表", "user:list", "BUTTON", "user:manage", None, None,
     ["GET /api/v1/user/"]),
    ("用户详情", "user:detail", "BUTTON", "user:manage", None, None,
     ["GET /api/v1/user/{user_id}"]),
    ("新增用户", "user:create", "BUTTON", "user:manage", None, None,
     ["POST /api/v1/user/"]),
    ("编辑用户", "user:update", "BUTTON", "user:manage", None, None,
     ["PUT /api/v1/user/{user_id}"]),
    ("删除用户", "user:delete", "BUTTON", "user:manage", None, None,
     ["DELETE /api/v1/user/{user_id}"]),
    ("分配角色", "user:assign-role", "BUTTON", "user:manage", None, None,
     ["PUT /api/v1/user/{user_id}/roles"]),
    ("重置密码", "user:reset-password", "BUTTON", "user:manage", None, None,
     ["PUT /api/v1/user/{user_id}/reset-password"]),
    ("踢人下线", "user:kick", "BUTTON", "user:manage", None, None,
     ["POST /api/v1/auth/kick-out"]),

    # ── 角色管理 ──
    ("角色管理", "role:manage", "MENU", "system", "/system/role", "Avatar", None),
    ("角色列表", "role:list", "BUTTON", "role:manage", None, None,
     ["GET /api/v1/role/"]),
    ("角色详情", "role:detail", "BUTTON", "role:manage", None, None,
     ["GET /api/v1/role/{role_id}"]),
    ("新增角色", "role:create", "BUTTON", "role:manage", None, None,
     ["POST /api/v1/role/"]),
    ("编辑角色", "role:update", "BUTTON", "role:manage", None, None,
     ["PUT /api/v1/role/{role_id}"]),
    ("删除角色", "role:delete", "BUTTON", "role:manage", None, None,
     ["DELETE /api/v1/role/{role_id}"]),
    ("角色分配用户", "role:assign-user", "BUTTON", "role:manage", None, None,
     ["DELETE /api/v1/role/{role_id}/users"]),
    ("复制角色", "role:copy", "BUTTON", "role:manage", None, None,
     ["POST /api/v1/role/{role_id}/copy"]),

    # ── 资源管理 ──
    ("资源管理", "permission:manage", "MENU", "system", "/system/permission", "Menu", None),
    ("资源列表", "permission:list", "BUTTON", "permission:manage", None, None,
     ["GET /api/v1/permission/tree"]),
    ("新增资源", "permission:create", "BUTTON", "permission:manage", None, None,
     ["POST /api/v1/permission/"]),
    ("编辑资源", "permission:update", "BUTTON", "permission:manage", None, None,
     ["PUT /api/v1/permission/{perm_id}"]),
    ("删除资源", "permission:delete", "BUTTON", "permission:manage", None, None,
     ["DELETE /api/v1/permission/{perm_id}"]),
    ("导出资源", "permission:export", "BUTTON", "permission:manage", None, None,
     ["GET /api/v1/permission/export"]),
    ("导入资源", "permission:import", "BUTTON", "permission:manage", None, None,
     ["POST /api/v1/permission/import"]),

    # ── 部门管理 ──
    ("部门管理", "dept:manage", "MENU", "system", "/system/dept", "OfficeBuilding", None),
    ("部门列表", "dept:list", "BUTTON", "dept:manage", None, None,
     ["GET /api/v1/dept/"]),
    ("新增部门", "dept:create", "BUTTON", "dept:manage", None, None,
     ["POST /api/v1/dept/"]),
    ("编辑部门", "dept:update", "BUTTON", "dept:manage", None, None,
     ["PUT /api/v1/dept/{dept_id}"]),
    ("删除部门", "dept:delete", "BUTTON", "dept:manage", None, None,
     ["DELETE /api/v1/dept/{dept_id}"]),

    # ── 内容管理 ──
    ("内容管理", "content", "MENU", None, "/content", "Document", None),

    # ── 文章管理 ──
    ("文章管理", "article:manage", "MENU", "content", "/content/article", "Notebook", None),
    ("文章列表", "article:list", "BUTTON", "article:manage", None, None,
     ["GET /api/v1/article/"]),
    ("查看文章", "article:detail", "BUTTON", "article:manage", None, None,
     ["GET /api/v1/article/{id}"]),
    ("新增文章", "article:create", "BUTTON", "article:manage", None, None,
     ["POST /api/v1/article/"]),
    ("编辑文章", "article:update", "BUTTON", "article:manage", None, None,
     ["PUT /api/v1/article/{id}"]),
    ("删除文章", "article:delete", "BUTTON", "article:manage", None, None,
     ["DELETE /api/v1/article/{id}"]),
    ("发布文章", "article:publish", "BUTTON", "article:manage", None, None,
     ["PUT /api/v1/article/{id}/publish"]),

    # ── 分类管理 ──
    ("分类管理", "category:manage", "MENU", "content", "/content/category", "Collection", None),
    ("分类列表", "category:list", "BUTTON", "category:manage", None, None,
     ["GET /api/v1/category/"]),
    ("新增分类", "category:create", "BUTTON", "category:manage", None, None,
     ["POST /api/v1/category/"]),
    ("编辑分类", "category:update", "BUTTON", "category:manage", None, None,
     ["PUT /api/v1/category/{id}"]),
    ("删除分类", "category:delete", "BUTTON", "category:manage", None, None,
     ["DELETE /api/v1/category/{id}"]),

    # ── 审计日志 ──
    ("审计日志", "audit:manage", "MENU", None, "/audit", "Tickets", None),
    ("日志列表", "audit:list", "BUTTON", "audit:manage", None, None,
     ["GET /api/v1/logs/"]),
    ("日志详情", "audit:detail", "BUTTON", "audit:manage", None, None,
     ["GET /api/v1/logs/{id}"]),
    ("导出日志", "audit:export", "BUTTON", "audit:manage", None, None,
     ["GET /api/v1/logs/export"]),
    ("清空日志", "audit:clear", "BUTTON", "audit:manage", None, None,
     ["DELETE /api/v1/logs/"]),
]

# ════════════════════════════════════════════════════════════════
# 角色定义
# (role_name, role_code, description, parent_role_ids, is_system, sort)
# ════════════════════════════════════════════════════════════════
ROLES: list[tuple] = [
    ("超级管理员", "SUPER_ADMIN",
     "系统内置角色，拥有全部权限，不可删除",
     None, True, 10),

    ("系统管理员", "ADMIN",
     "管理用户、角色和查看审计日志，但不可管理资源权限",
     None, True, 20),

    ("部门主管", "DEPT_MANAGER",
     "继承编辑者全部权限，额外拥有部门管理和用户角色分配能力",
     None, False, 30),

    ("内容主编", "CONTENT_EDITOR",
     "继承编辑者全部权限，额外拥有内容管理（文章/分类）完整权限",
     None, False, 40),

    ("编辑者", "EDITOR",
     "可查看用户/角色列表、编辑用户信息，可管理文章和分类（不能删除）",
     None, False, 50),

    ("文章编辑", "ARTICLE_EDITOR",
     "仅可管理文章和分类，无法访问系统管理",
     None, False, 60),

    ("只读用户", "VIEWER",
     "仅可查看仪表盘、用户、角色、日志列表，无任何修改权限",
     None, False, 70),

    ("禁用演示", "DISABLED_DEMO",
     "该角色已被禁用，用于测试禁用角色在编辑/权限计算中的表现",
     None, False, 80),
]

# ════════════════════════════════════════════════════════════════
# 角色继承关系（parent_role_ids，在角色创建后单独更新）
# role_code → [父角色 code...]
# ════════════════════════════════════════════════════════════════
ROLE_INHERITANCE: dict[str, list[str]] = {
    "DEPT_MANAGER": ["EDITOR"],
    "CONTENT_EDITOR": ["EDITOR"],
    "EDITOR": ["VIEWER"],
    "ARTICLE_EDITOR": ["VIEWER"],
}

# ════════════════════════════════════════════════════════════════
# 角色权限映射  role_code → {"grant": [...], "deny": [...]}
# ════════════════════════════════════════════════════════════════
ROLE_PERMS: dict[str, dict] = {
    "SUPER_ADMIN": {
        "grant": [p[1] for p in PERMISSIONS],
        "deny": [],
    },
    "ADMIN": {
        "grant": [
            "dashboard", "dashboard:view",
            "system",
            "user:manage", "user:list", "user:detail",
            "user:create", "user:update", "user:delete",
            "user:assign-role", "user:reset-password", "user:kick",
            "role:manage", "role:list", "role:detail",
            "role:create", "role:update", "role:delete",
            "role:assign-user", "role:copy",
            "dept:manage", "dept:list", "dept:create",
            "dept:update", "dept:delete",
            "audit:manage", "audit:list", "audit:detail",
            "audit:export", "audit:clear",
        ],
        "deny": [],
    },
    "DEPT_MANAGER": {
        "grant": [
            "dept:manage", "dept:list", "dept:create",
            "dept:update", "dept:delete",
            "user:assign-role", "user:kick",
        ],
        "deny": ["user:delete"],
    },
    "CONTENT_EDITOR": {
        "grant": [
            "content",
            "article:manage", "article:list", "article:detail",
            "article:create", "article:update", "article:delete",
            "article:publish",
            "category:manage", "category:list", "category:create",
            "category:update", "category:delete",
        ],
        "deny": [],
    },
    "EDITOR": {
        "grant": [
            "system",
            "user:manage", "user:list", "user:detail", "user:update",
            "role:manage", "role:list", "role:detail",
            "audit:manage", "audit:list",
            "content",
            "article:manage", "article:list", "article:detail",
            "article:create", "article:update",
            "category:manage", "category:list", "category:create",
            "category:update",
        ],
        "deny": [
            "user:delete",          # 典型 deny 场景：可编辑用户但不可删除
            "article:delete",       # 可编辑文章但不可删除
            "category:delete",      # 可编辑分类但不可删除
        ],
    },
    "ARTICLE_EDITOR": {
        "grant": [
            "dashboard", "dashboard:view",
            "content",
            "article:manage", "article:list", "article:detail",
            "article:create", "article:update",
            "category:manage", "category:list", "category:detail",
            "category:create", "category:update",
            "audit:manage", "audit:list",
        ],
        "deny": [
            "article:delete",
            "category:delete",
        ],
    },
    "VIEWER": {
        "grant": [
            "dashboard", "dashboard:view",
            "system",
            "user:manage", "user:list", "user:detail",
            "role:manage", "role:list", "role:detail",
            "audit:manage", "audit:list",
        ],
        "deny": [],
    },
    "DISABLED_DEMO": {
        "grant": [
            "dashboard", "dashboard:view",
            "system", "user:manage", "user:list", "user:detail",
        ],
        "deny": [],
    },
}

# ════════════════════════════════════════════════════════════════
# 用户定义
# (username, password, real_name, gender, email, phone, status, remark, role_codes)
# gender: 0=未知, 1=男, 2=女
# ════════════════════════════════════════════════════════════════
USERS: list[tuple] = [
    # ── 核心测试账号 ──
    ("admin", "admin123", "超级管理员", 1, "admin@rbac.local",
     "13800000001", True, "系统内置超级管理员，拥有全部权限",
     ["SUPER_ADMIN"]),

    ("zhangsan", "Admin@123", "张三", 1, "zhangsan@rbac.local",
     "13800000002", True, "系统管理员，可管理用户和角色",
     ["ADMIN"]),

    ("lisi", "Admin@123", "李四", 1, "lisi@rbac.local",
     "13800000003", True, "部门主管，继承编辑者权限并额外管理用户角色",
     ["DEPT_MANAGER"]),

    ("wangwu", "Admin@123", "王五", 2, "wangwu@rbac.local",
     "13800000004", True, "内容主编，继承编辑者权限并额外管理内容",
     ["CONTENT_EDITOR"]),

    ("zhaoliu", "Admin@123", "赵六", 2, "zhaoliu@rbac.local",
     "13800000005", True, "普通编辑，可编辑用户和内容，不可删除",
     ["EDITOR"]),

    ("sunqi", "Admin@123", "孙七", 1, "sunqi@rbac.local",
     "13800000006", True, "文章编辑，仅能管理文章和分类",
     ["ARTICLE_EDITOR"]),

    ("zhouba", "Admin@123", "周八", 1, "zhouba@rbac.local",
     "13800000007", True, "只读用户，仅可查看各模块列表",
     ["VIEWER"]),

    ("wujiu", "Admin@123", "吴九", 2, "wujiu@rbac.local",
     "13800000008", True, "多角色用户：同时拥有编辑者和只读权限",
     ["EDITOR", "VIEWER"]),

    # ── 边界场景 ──
    ("liuqian", "Admin@123", "刘千", 1, "liuqian@rbac.local",
     "13800000009", False, "此账号已被管理员禁用，无法登录",
     ["EDITOR"]),

    ("chenmo", "Admin@123", "陈墨", 2, "chenmo@rbac.local",
     "13800000010", True, "仅拥有已禁用的角色，实际权限为空",
     ["DISABLED_DEMO"]),

    # ── 批量测试数据（分页、批量操作演示用）──
    ("test01", "Test@123", "测试用户01", 0, "test01@rbac.local",
     "13800000101", True, "批量测试账号", ["VIEWER"]),
    ("test02", "Test@123", "测试用户02", 0, "test02@rbac.local",
     "13800000102", True, "批量测试账号", ["VIEWER"]),
    ("test03", "Test@123", "测试用户03", 0, "test03@rbac.local",
     "13800000103", True, "批量测试账号", ["VIEWER"]),
    ("test04", "Test@123", "测试用户04", 0, "test04@rbac.local",
     "13800000104", True, "批量测试账号", ["VIEWER"]),
    ("test05", "Test@123", "测试用户05", 0, "test05@rbac.local",
     "13800000105", True, "批量测试账号", ["VIEWER"]),
    ("test06", "Test@123", "测试用户06", 0, "test06@rbac.local",
     "13800000106", True, "批量测试账号", ["VIEWER"]),
    ("test07", "Test@123", "测试用户07", 0, "test07@rbac.local",
     "13800000107", True, "批量测试账号", ["VIEWER"]),
    ("test08", "Test@123", "测试用户08", 0, "test08@rbac.local",
     "13800000108", True, "批量测试账号", ["VIEWER"]),
    ("test09", "Test@123", "测试用户09", 0, "test09@rbac.local",
     "13800000109", True, "批量测试账号", ["VIEWER"]),
    ("test10", "Test@123", "测试用户10", 0, "test10@rbac.local",
     "13800000110", True, "批量测试账号", ["VIEWER"]),
    ("test11", "Test@123", "测试用户11", 0, "test11@rbac.local",
     "13800000111", True, "批量测试账号", ["VIEWER"]),
    ("test12", "Test@123", "测试用户12", 0, "test12@rbac.local",
     "13800000112", True, "批量测试账号", ["VIEWER"]),
    ("test13", "Test@123", "测试用户13", 0, "test13@rbac.local",
     "13800000113", False, "已禁用的批量测试账号", ["VIEWER"]),
    ("test14", "Test@123", "测试用户14", 0, "test14@rbac.local",
     "13800000114", False, "已禁用的批量测试账号", ["VIEWER"]),
    ("test15", "Test@123", "测试用户15", 0, "test15@rbac.local",
     "13800000115", True, "批量测试账号", ["VIEWER"]),
]


async def seed() -> None:
    """写入演示数据（幂等：先清再插）。"""
    print("=" * 60)
    print("  RBAC 权限管理系统 — 测试数据初始化")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # ── 1. 清空旧数据 ──
            print("\n[1/6] 清空旧数据...")
            for table in [UserRole, RolePermission, User, Role, Permission]:
                await db.execute(delete(table))
            await db.flush()
            print("   [OK] 数据已清空")

            # ── 2. 插入权限资源 ──
            print("[2/6] 插入权限资源...")
            perm_map: dict[str, int] = {}
            idx = 0
            for name, code, ptype, parent_key, path, icon, api_paths in PERMISSIONS:
                idx += 1
                parent_id = perm_map.get(parent_key) if parent_key else None
                perm = Permission(
                    name=name, code=code, type=ptype,
                    parent_id=parent_id, path=path, icon=icon,
                    api_paths=api_paths, status=True, sort=idx,
                )
                db.add(perm)
                await db.flush()
                perm_map[code] = perm.id
            print(f"   [OK] 已插入 {len(PERMISSIONS)} 条权限资源")

            # ── 3. 插入角色 ──
            print("[3/6] 插入角色...")
            role_map: dict[str, int] = {}
            for role_name, role_code, desc, _, is_sys, sort in ROLES:
                disabled = (role_code == "DISABLED_DEMO")
                role = Role(
                    role_name=role_name, role_code=role_code,
                    description=desc, parent_role_ids=None,
                    is_system=is_sys, sort=sort, status=not disabled,
                )
                db.add(role)
                await db.flush()
                role_map[role_code] = role.id
            print(f"   [OK] 已插入 {len(ROLES)} 个角色")

            # ── 3.5 回写角色继承关系 ──
            print("[3.5/6] 设置角色继承关系...")
            inh_count = 0
            for child_code, parent_codes in ROLE_INHERITANCE.items():
                if child_code in role_map:
                    child_role = await db.get(Role, role_map[child_code])
                    if child_role:
                        child_role.parent_role_ids = [
                            role_map[pc] for pc in parent_codes if pc in role_map
                        ]
                        await db.flush()
                        inh_count += 1
            print(f"   [OK] 已设置 {inh_count} 条角色继承关系")

            # ── 4. 分配角色权限 ──
            print("[4/6] 分配角色权限...")
            grant_count = 0
            deny_count = 0
            for role_code, perms in ROLE_PERMS.items():
                if role_code not in role_map:
                    continue
                role_id = role_map[role_code]
                for code in perms["grant"]:
                    if code not in perm_map:
                        continue
                    db.add(RolePermission(
                        role_id=role_id, permission_id=perm_map[code],
                        is_deny=False,
                    ))
                    grant_count += 1
                for code in perms["deny"]:
                    if code not in perm_map:
                        continue
                    db.add(RolePermission(
                        role_id=role_id, permission_id=perm_map[code],
                        is_deny=True,
                    ))
                    deny_count += 1
            print(f"   [OK] 已授权 {grant_count} 条, 拒绝 {deny_count} 条")

            # ── 5. 插入用户并分配角色 ──
            print("[5/6] 插入用户并分配角色...")
            ur_count = 0
            for (username, pwd, real_name, gender,
                 email, phone, status, remark, role_codes) in USERS:
                # 模拟一些用户的最近登录时间
                last_login = None
                if status and username in ("admin", "zhangsan", "lisi"):
                    last_login = datetime.now(timezone.utc) - timedelta(
                        hours=hash(username) % 72
                    )

                user = User(
                    username=username,
                    password=hash_password(pwd),
                    real_name=real_name,
                    gender=gender,
                    email=email,
                    phone=phone,
                    status=status,
                    remark=remark,
                    last_login_time=last_login,
                )
                db.add(user)
                await db.flush()
                for rc in role_codes:
                    if rc in role_map:
                        db.add(UserRole(
                            user_id=user.id, role_id=role_map[rc],
                        ))
                        ur_count += 1
            print(f"   [OK] 已插入 {len(USERS)} 个用户, "
                  f"分配 {ur_count} 条角色关联")

            # ── 6. 插入一些审计日志（模拟历史操作） ──
            print("[6/6] 插入示例审计日志...")
            from src.rbac.models.logs import Logs
            sample_logs = [
                ("系统初始化完成，种子数据已加载", "SYSTEM"),
                ("超级管理员登录成功", "AUTH"),
                ("创建角色「编辑者」并分配权限", "ROLE"),
                ("新增用户「张三」并分配系统管理员角色", "USER"),
            ]
            for i, (desc, module) in enumerate(sample_logs):
                db.add(Logs(
                    user_id=1, username="admin", module=module,
                    operation="CREATE" if i > 0 else "SYSTEM",
                    description=desc, request_params=None,
                    ip="127.0.0.1", result="SUCCESS",
                ))
            print(f"   [OK] 已插入 {len(sample_logs)} 条审计日志")

        # 事务自动提交
        print("\n" + "=" * 60)
        print("  初始化完成！")
        print("=" * 60)

        # ── 打印账号密码表 ──
        print(f"""
   ┌──────────────┬──────────────┬──────────────────────────────┐
   │ 用户名       │ 密码         │ 角色 / 说明                  │
   ├──────────────┼──────────────┼──────────────────────────────┤
   │ admin        │ admin123     │ 超级管理员（全部权限）       │
   │ zhangsan     │ Admin@123    │ 系统管理员                   │
   │ lisi         │ Admin@123    │ 部门主管（继承编辑者+部门）  │
   │ wangwu       │ Admin@123    │ 内容主编（继承编辑者+内容）  │
   │ zhaoliu      │ Admin@123    │ 编辑者（user:delete 被 deny）│
   │ sunqi        │ Admin@123    │ 文章编辑（仅文章/分类）      │
   │ zhouba       │ Admin@123    │ 只读用户                     │
   │ wujiu        │ Admin@123    │ 多角色：编辑者 + 只读        │
   │ liuqian      │ Admin@123    │ [!] 账号已禁用，无法登录     │
   │ chenmo       │ Admin@123    │ [!] 拥有已禁用的角色         │
   │ test01~test15│ Test@123     │ 批量测试（含禁用、分页用）   │
   └──────────────┴──────────────┴──────────────────────────────┘

   [角色继承] DEPT_MANAGER -> EDITOR -> VIEWER
             CONTENT_EDITOR -> EDITOR -> VIEWER
             ARTICLE_EDITOR -> VIEWER
   [deny演示] EDITOR 拥有 article:delete / user:delete 的 deny 标记
   [禁用场景] liuqian（账号禁用）、chenmo（角色禁用）、
             test13/test14（批量测试中的禁用账号）
   [分页测试] 共 {len(USERS)} 个用户，默认每页 20 条
   [权限资源] 共 {len(PERMISSIONS)} 个权限节点，{len(ROLES)} 个角色
        """)


if __name__ == "__main__":
    asyncio.run(seed())
