"""
用户数据访问层（CRUD）。

提供用户表的所有数据库操作，包括查询、新增、修改、逻辑删除和角色关联。
所有方法均使用 SQLAlchemy 异步会话，调用后需在业务层执行 commit。
"""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, insert, delete

from src.rbac.models.user import User
from src.rbac.models.user_role import UserRole


class UserRepository:
    """用户仓储类，封装用户相关的数据库操作。

    所有查询默认过滤已软删除（deleted_at IS NOT NULL）的用户，
    查询函数根据业务场景选择是否过滤禁用用户。
    """

    def __init__(self, db: AsyncSession):
        """
        初始化用户仓储
        :param db: 数据库异步会话（由依赖注入提供）
        """
        self.db = db

    # ── 查询 ──

    async def get_user_by_username(self, username: str) -> User | None:
        """
        通过用户名查询用户（仅查启用且未删除的用户，用于登录认证）
        :param username: 用户名
        :return: 用户ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(User).where(
                User.username == username,
                User.deleted_at.is_(None),  # 排除已软删除的用户
                User.status == True,  # 仅查启用用户，禁用账户不可登录
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        """
        通过用户ID查询用户（含禁用用户，管理员可能需要对其操作）
        :param user_id: 用户ID
        :return: 用户ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.deleted_at.is_(None),  # 排除已软删除的用户
            )
        )
        return result.scalar_one_or_none()

    async def get_users_paginated(
            self, keyword: str | None, status: int | None, page: int, size: int
    ) -> tuple[list[User], int]:
        """
        分页查询用户列表，支持关键字和状态筛选
        :param keyword: 搜索关键字（匹配用户名、邮箱、真实姓名），为None则不筛选
        :param status: 用户状态筛选（True启用/False禁用），为None则查全部
        :param page: 页码（从1开始）
        :param size: 每页条数
        :return: (用户列表, 总条数) 元组
        """
        # 基础查询：排除已软删除的用户
        sql = select(User).where(User.deleted_at.is_(None))
        # 关键字模糊搜索：同时在用户名、邮箱、真实姓名三个字段中匹配
        if keyword:
            like = f"%{keyword}%"
            sql = sql.where(User.username.like(like) | User.email.like(like) | User.real_name.like(like))
        # 状态筛选（True=仅启用, False=仅禁用, None=全部）
        if status is not None:
            sql = sql.where(User.status == status)

        # 先统计总数（基于筛选条件）
        result = await self.db.execute(select(func.count()).select_from(sql.subquery()))
        total = result.scalar() or 0
        # 再查分页数据：按ID倒序（最新在前）、偏移、限数
        result = await self.db.execute(sql.order_by(User.id.desc()).offset((page - 1) * size).limit(size))
        users = result.scalars().all()
        return list(users), total

    # ── 新增 ──

    async def create_user(self, **kwargs) -> User:
        """
        新增用户
        :param kwargs: 用户字段键值对（username, password, real_name 等）
        :return: 创建成功的用户ORM模型（已 flush 但未 commit）
        """
        user = User(**kwargs)
        self.db.add(user)
        await self.db.flush()  # flush 生成 ID，但仍需业务层 commit
        return user

    # ── 修改 ──

    async def update_user_by_data(self, user: User, update_data: dict) -> User:
        """
        按字典更新用户字段（仅更新非 None 字段，保护原有数据不被覆盖）
        :param user: 待更新的用户ORM对象（必须是已 tracked 对象）
        :param update_data: 需要更新的字段字典，None值会被跳过
        :return: 更新后的用户ORM模型
        """
        for kay, val in update_data.items():
            if val is not None:  # None 字段跳过，实现部分更新
                setattr(user, kay, val)
        await self.db.flush()
        return user

    # ── 删除 ──

    async def soft_delete_user(self, user: User) -> None:
        """
        逻辑删除用户（标记 deleted_at，并清除角色关联）
        :param user: 待删除的用户ORM对象
        :return: None
        """
        user.deleted_at = datetime.now()
        # 清除用户-角色关联记录
        from sqlalchemy import delete as sql_delete
        await self.db.execute(
            sql_delete(UserRole).where(UserRole.user_id == user.id)
        )

    async def batch_status(self, ids: list[int], status: int) -> None:
        """
        批量启用/禁用用户（SQL UPDATE 直接操作，避免逐条查询）
        :param ids: 用户ID列表
        :param status: 目标状态（True启用/False禁用）
        :return: None
        """
        await self.db.execute(
            update(User)
            .where(User.id.in_(ids), User.deleted_at.is_(None))  # 仅操作未删除用户
            .values(status=status)
        )

    async def batch_delete(self, ids: list[int]) -> None:
        """
        批量逻辑删除用户（设置 deleted_at 并清除角色关联）
        :param ids: 用户ID列表
        :return: None
        """
        await self.db.execute(
            update(User)
            .where(User.id.in_(ids), User.deleted_at.is_(None))  # 仅操作未删除用户
            .values(deleted_at=datetime.now())
        )
        # 清除批量删除用户的角色关联
        from sqlalchemy import delete as sql_delete
        await self.db.execute(
            sql_delete(UserRole).where(UserRole.user_id.in_(ids))
        )

    # ── 角色关联 ──

    async def set_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        """
        全量覆盖用户角色（先删后插，确保角色列表与传入的 role_ids 完全一致）
        :param user_id: 用户ID
        :param role_ids: 角色ID列表（空列表表示清空所有角色）
        :return: None
        """
        # 第一步：删除该用户的所有现有角色关联
        await self.db.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        # 第二步：插入新的角色关联（如果 role_ids 非空）
        if role_ids:
            await self.db.execute(
                insert(UserRole),
                [{"user_id": user_id, "role_id": rid} for rid in role_ids],
            )
        await self.db.flush()
