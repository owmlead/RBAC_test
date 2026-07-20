"""
角色数据访问层（CRUD）。

提供角色表的所有数据库操作，包括查询、新增、修改、删除和角色-权限关联管理。
同时提供角色与用户关联的查询和移除功能。
"""
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update, insert

from src.rbac.models.role import Role
from src.rbac.models.role_permission import RolePermission
from src.rbac.models.user import User
from src.rbac.models.user_role import UserRole


class RoleRepository:
    """角色仓储类，封装角色相关的数据库操作。

    提供角色 CRUD、角色-权限关联管理、角色-用户关联查询等功能。
    角色删除支持硬删除（物理删除），但系统内置角色受 is_system 保护，业务层需先校验。
    """

    def __init__(self, db: AsyncSession):
        """
        初始化角色仓储
        :param db: 数据库异步会话（由依赖注入提供）
        """
        self.db = db

    # ── 查询 ──

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """
        通过角色ID查询启用的角色
        :param role_id: 角色ID
        :return: 角色ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.status == True,  # 仅查启用角色
            )
        )
        return result.scalar_one_or_none()

    async def get_role_by_role_name(self, role_name: str) -> Role | None:
        """
        通过角色名称查询启用的角色（用于创建时重名检查）
        :param role_name: 角色名称
        :return: 角色ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Role).where(
                Role.role_name == role_name,
                Role.status == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_role_by_code(self, role_code: str) -> Role | None:
        """
        通过角色编码查询角色（不限制状态，编码全局唯一）
        :param role_code: 角色编码（唯一标识）
        :return: 角色ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Role).where(Role.role_code == role_code)
        )
        return result.scalar_one_or_none()

    async def get_all_roles(self) -> list[Role]:
        """
        获取全部角色（按ID排序，用于构建角色树）
        :return: 角色ORM模型列表
        """
        result = await self.db.execute(
            select(Role).order_by(Role.id)
        )
        return list(result.scalars().all())

    async def get_all_role(self) -> list[Role]:
        """
        获取全部角色（不排序，用于简单列表场景）
        :return: 角色ORM模型列表
        """
        result = await self.db.execute(select(Role))
        return result.scalars().all()

    async def get_roles_paginated(self, keyword: str | None, page: int, size: int) -> tuple[list[dict], int]:
        """
        分页查询角色列表，支持关键字筛选，返回字典列表（包含 user_count）
        :param keyword: 搜索关键字（匹配角色名称或编码），为None则不筛选
        :param page: 页码（从1开始）
        :param size: 每页条数
        :return: (角色字典列表, 总条数) 元组，每个字典包含 user_count 字段
        """
        q = select(Role)
        # 关键字模糊搜索：同时在角色名称和编码中匹配
        if keyword:
            like = f"%{keyword}%"
            q = q.where((Role.role_name.like(like)) | (Role.role_code.like(like)))

        # 统计总数
        total0 = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total0.scalar() or 0
        # 分页查询角色列表
        roles0 = await self.db.execute(q.order_by(Role.id).offset((page - 1) * size).limit(size))
        roles = roles0.scalars().all()

        # 构造返回字典，附加 user_count（通过 len(r.users) 利用 ORM 关系获取）
        result = []
        for r in roles:
            d = {
                "id": r.id, "role_name": r.role_name, "role_code": r.role_code,
                "description": r.description, "status": r.status,
                "parent_role_ids": r.parent_role_ids, "user_count": len(r.users),
                "create_time": r.create_time,
            }
            result.append(d)
        return result, total

    async def get_id_by_parent_ids(self, parent_ids: List[int]) -> List[int]:
        """
        通过父角色ID列表查询其中启用的角色ID（用于验证继承关系的有效性）
        :param parent_ids: 父角色ID列表
        :return: 启用的父角色ID列表（过滤掉已禁用的）
        """
        result = await self.db.execute(
            select(Role.id).where(
                Role.id.in_(parent_ids),
                Role.status == True,  # 仅返回启用的父角色
            )
        )
        return list(result.scalars().all())

    async def get_role_permission_records(self, role_id: int) -> list[dict]:
        """
        根据角色ID获取权限分配记录（含 deny 标记，用于权限编辑回显）
        :param role_id: 角色ID
        :return: 权限记录列表 [{permission_id, is_deny}, ...]
        """
        result = await self.db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        records = result.scalars().all()
        # 将 ORM 对象转为简单字典，is_deny 转为 bool 确保 JSON 序列化兼容
        return [{"permission_id": r.permission_id, "is_deny": bool(r.is_deny)} for r in records]

    async def get_role_user_count(self, role_id: int) -> int:
        """
        获取角色关联的用户数量（用于删除前验证）
        :param role_id: 角色ID
        :return: 用户数量
        """
        result = await self.db.execute(
            select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
        )
        return result.scalar() or 0

    async def get_role_users_paginated(
            self, role_id: int, page: int, size: int
    ) -> tuple[list[User], int]:
        """
        分页查询某角色下的用户（通过 user_role 关联表 JOIN）
        :param role_id: 角色ID
        :param page: 页码（从1开始）
        :param size: 每页条数
        :return: (用户列表, 总条数) 元组
        """
        # JOIN user_role 和 user 表，关联出该角色的所有用户
        base = (
            select(User)
            .join(UserRole, User.id == UserRole.user_id)
            .where(UserRole.role_id == role_id, User.deleted_at.is_(None))
        )
        tot = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = tot.scalar() or 0
        us = await self.db.execute(base.offset((page - 1) * size).limit(size))
        users = us.scalars().all()
        return list(users), total

    async def get_user_by_role_id(self, role_id: int) -> list:
        """
        获取直接拥有某角色的所有用户ID（不含通过父角色继承的用户）
        :param role_id: 角色ID
        :return: 用户ID列表（result.rows 格式，每个元素是一个单值元组）
        """
        result = await self.db.execute(
            select(UserRole.user_id).where(UserRole.role_id == role_id)
        )
        return result.all()

    async def get_user_by_role_ids(self, role_ids: set[int]) -> list:
        """
        批量获取拥有指定角色集合的用户ID（用于权限范围内的用户筛选）
        :param role_ids: 角色ID集合
        :return: 用户ID列表（去重需业务层处理）
        """
        result = await self.db.execute(
            select(UserRole.user_id).where(
                UserRole.role_id.in_(role_ids)
            )
        )
        return result.all()

    # ── 新增 ──

    async def create_role(self, **kwargs) -> Role:
        """
        新增角色
        :param kwargs: 角色字段键值对（role_name, role_code, description 等）
        :return: 创建成功的角色ORM模型（已 flush 但未 commit）
        """
        role = Role(**kwargs)
        self.db.add(role)
        await self.db.flush()
        return role

    async def set_role_permissions(self, role_id: int, permissions: list[dict]) -> None:
        """
        全量覆盖角色权限（先删后插，确保权限列表与传入数据一致）
        :param role_id: 角色ID
        :param permissions: 权限列表 [{permission_id, is_deny}, ...]
        :return: None
        """
        # 第一步：删除该角色的所有现有权限关联
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        # 第二步：批量插入新的权限关联
        if permissions:
            await self.db.execute(
                insert(RolePermission),
                [{"role_id": role_id, "permission_id": p["permission_id"], "is_deny": p.get("is_deny", False)}
                 for p in permissions],
            )
        await self.db.flush()

    # ── 修改 ──

    async def update_role(self, role: Role, update_data: dict) -> Role:
        """
        按字典更新角色字段（仅更新非 None 字段）
        :param role: 待更新的角色ORM对象
        :param update_data: 需要更新的字段字典，None值会被跳过
        :return: 更新后的角色ORM模型
        """
        for k, v in update_data.items():
            if v is not None:
                setattr(role, k, v)
        await self.db.flush()
        return role

    # ── 删除 ──

    async def delete_role(self, role: Role) -> None:
        """
        硬删除角色（物理删除），并清理所有子角色 parent_role_ids 中对该角色的引用。
        业务层需先校验关联用户数量。
        :param role: 待删除的角色ORM对象
        :return: None
        """
        deleted_id = role.id

        # 第一步：清理所有子角色 parent_role_ids 中对被删除角色的引用
        all_roles_result = await self.db.execute(
            select(Role.id, Role.parent_role_ids)
        )
        for rid, parent_ids in all_roles_result.all():
            if parent_ids and deleted_id in parent_ids:
                new_parents = [pid for pid in parent_ids if pid != deleted_id]
                await self.db.execute(
                    update(Role)
                    .where(Role.id == rid)
                    .values(parent_role_ids=new_parents if new_parents else None)
                )

        # 第二步：删除 role_permission 关联记录
        await self.db.execute(
            delete(RolePermission).where(RolePermission.role_id == deleted_id)
        )
        # 第三步：删除角色主记录
        await self.db.execute(
            delete(Role).where(Role.id == deleted_id)
        )
        await self.db.flush()

    async def remove_users_from_role(self, role_id: int, user_ids: list[int]) -> None:
        """
        批量移除角色下的用户（删除 user_role 关联记录，不影响用户本身）
        :param role_id: 角色ID
        :param user_ids: 待移除的用户ID列表
        :return: None
        """
        await self.db.execute(
            delete(UserRole).where(
                UserRole.role_id == role_id,
                UserRole.user_id.in_(user_ids),
            )
        )
        await self.db.flush()
