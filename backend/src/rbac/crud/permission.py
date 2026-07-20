"""
权限数据访问层（CRUD）。

提供权限表的所有数据库操作，包括查询、新增、修改、删除和排序。
权限支持树形结构（通过 parent_id 自关联），排序通过 sort 字段控制同级顺序。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case, update

from src.rbac.models.permission import Permission
from src.rbac.models.role_permission import RolePermission


class PermissionRepository:
    """权限仓储类，封装权限相关的数据库操作。

    权限分为菜单（MENU）和按钮（BUTTON）两种类型，通过 parent_id 形成树形层级。
    所有查询默认过滤禁用权限。
    """

    def __init__(self, db: AsyncSession):
        """
        初始化权限仓储
        :param db: 数据库异步会话（由依赖注入提供）
        """
        self.db = db

    # ── 查询 ──

    async def get_all(self) -> list[Permission]:
        """
        查询全部权限（含禁用，按排序号升序）。
        用于权限管理页面和角色编辑页面——管理员需要看到禁用权限以重新启用。
        :return: 权限ORM模型列表
        """
        result = await self.db.execute(
            select(Permission).order_by(Permission.sort)
        )
        return result.scalars().all()

    async def get_permission_by_id(self, perm_id: int) -> Permission | None:
        """
        通过权限ID查询权限（含禁用，管理员可能需要对其操作）
        :param perm_id: 权限ID
        :return: 权限ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Permission).where(Permission.id == perm_id)
        )
        return result.scalar_one_or_none()

    async def get_permission_by_name(self, name: str) -> Permission | None:
        """
        通过权限名称查询启用的权限（用于创建时重名检查）
        :param name: 权限名称
        :return: 权限ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Permission).where(
                Permission.name == name,
                Permission.status == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_permission_by_code(self, code: str) -> Permission | None:
        """
        通过权限编码查询权限（不限制状态，编码全局唯一）
        :param code: 权限编码（唯一标识）
        :return: 权限ORM模型，未找到返回None
        """
        result = await self.db.execute(
            select(Permission).where(Permission.code == code)
        )
        return result.scalar_one_or_none()

    async def get_perms_code_by_role_ids(self, role_ids: list[int]) -> list[tuple[str, bool]]:
        """
        通过角色ID列表批量查询权限编码和拒绝标记（用于权限校验的核心查询）
        :param role_ids: 角色ID列表
        :return: [(权限编码, 是否拒绝), ...] 列表
                 调用方需处理拒绝优先逻辑：若任一角色拒绝了某权限，则用户无权
        """
        result = await self.db.execute(
            select(Permission.code, RolePermission.is_deny)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id.in_(role_ids),
                Permission.status == True,  # 仅返回启用权限的编码
            )
        )
        return result.all()

    async def get_user_ids_by_permission_id(self, perm_id: int) -> set[int]:
        """
        查询拥有指定权限的所有用户ID（用于权限变更后失效缓存）。

        处理两层关联：
        1. 直接关联：角色通过 role_permission 直接持有该权限的用户
        2. 间接继承：子角色通过 parent_role_ids 继承该权限的用户

        :param perm_id: 权限ID
        :return: 受影响的用户ID集合（已去重）
        """
        from sqlalchemy import select as _select
        from src.rbac.models.role import Role
        from src.rbac.models.user_role import UserRole

        # 第一步：找出直接关联此权限的角色ID
        role_result = await self.db.execute(
            _select(RolePermission.role_id).where(RolePermission.permission_id == perm_id)
        )
        direct_role_ids = {r[0] for r in role_result.all()}
        if not direct_role_ids:
            return set()

        # 第二步：加载所有角色，构建 role_id → parent_role_ids 的映射
        all_roles_result = await self.db.execute(_select(Role.id, Role.parent_role_ids))
        role_parent_map: dict[int, list[int]] = {}
        for role_id, parent_ids in all_roles_result.all():
            role_parent_map[role_id] = parent_ids or []

        # 第三步：递归展开每个角色的完整祖先链
        def get_all_ancestors(rid: int, visited: set[int] | None = None) -> set[int]:
            """递归向上追溯所有祖先角色ID"""
            if visited is None:
                visited = set()
            if rid in visited:
                return set()
            visited.add(rid)
            ancestors = set()
            for pid in role_parent_map.get(rid, []):
                ancestors.add(pid)
                ancestors |= get_all_ancestors(pid, visited)
            return ancestors

        affected_role_ids = set(direct_role_ids)
        for role_id in role_parent_map:
            if role_id in affected_role_ids:
                continue
            if get_all_ancestors(role_id) & direct_role_ids:
                affected_role_ids.add(role_id)

        # 第三步：找出拥有这些受影响角色的所有用户ID
        user_result = await self.db.execute(
            _select(UserRole.user_id).where(UserRole.role_id.in_(list(affected_role_ids)))
        )
        return {u[0] for u in user_result.all()}

    # ── 新增 ──

    async def create_permission(self, **kwargs) -> Permission:
        """
        新增权限
        :param kwargs: 权限字段键值对（name, code, type, parent_id 等）
        :return: 创建成功的权限ORM模型（已 flush 但未 commit）
        """
        perm = Permission(**kwargs)
        self.db.add(perm)
        await self.db.flush()
        return perm

    # ── 修改 ──

    async def update_permission(self, perm: Permission, update_data: dict) -> Permission:
        """
        按字典更新权限字段（仅更新非 None 字段）
        :param perm: 待更新的权限ORM对象
        :param update_data: 需要更新的字段字典，None值会被跳过
        :return: 更新后的权限ORM模型
        """
        for key, value in update_data.items():
            if value is not None:
                setattr(perm, key, value)
        await self.db.flush()
        return perm

    async def update_sort_orders(self, sorted_ids: list[int]) -> None:
        """
        批量更新排序值：每个 ID 按其在新列表中的位置 + 1 赋值。
        前端按同 parent_id 分组后拼接发送，保证同级节点的 sort 连续递增。
        使用 SQL CASE WHEN 一条 UPDATE 语句完成，避免逐条更新。

        :param sorted_ids: 按新顺序排列的权限ID列表
        :return: None
        """
        if not sorted_ids:
            return
        stmt = (
            update(Permission)
            .where(Permission.id.in_(sorted_ids))
            .values(
                sort=case(
                    {perm_id: idx + 1 for idx, perm_id in enumerate(sorted_ids)},
                    value=Permission.id
                )
            )
        )
        await self.db.execute(stmt)

    # ── 删除 ──

    async def delete_permission(self, perm: Permission) -> None:
        """
        级联删除权限及其所有子孙节点。
        先递归收集要删除的权限ID，再清理关联的 role_permission，最后批量删除权限记录。
        :param perm: 待删除的权限ORM对象（根节点）
        :return: None
        """
        from sqlalchemy import delete as sql_delete
        from src.rbac.models.permission import Permission as PermModel
        from src.rbac.models.role_permission import RolePermission

        # 第一步：递归收集所有子孙权限ID
        all_ids: list[int] = []

        async def collect_ids(parent_id: int) -> None:
            """递归收集 parent_id 的所有子孙权限ID"""
            result = await self.db.execute(
                select(PermModel.id).where(PermModel.parent_id == parent_id)
            )
            child_ids = [r[0] for r in result.all()]
            for cid in child_ids:
                all_ids.append(cid)
                await collect_ids(cid)

        all_ids.append(perm.id)
        await collect_ids(perm.id)

        # 第二步：清理所有受影响权限的 role_permission 关联记录
        await self.db.execute(
            sql_delete(RolePermission).where(RolePermission.permission_id.in_(all_ids))
        )
        # 第三步：批量删除权限主记录
        await self.db.execute(
            sql_delete(PermModel).where(PermModel.id.in_(all_ids))
        )
        await self.db.flush()
