"""
角色管理服务。
提供角色 CRUD、角色树构建、复制和用户关联等业务逻辑。
"""
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.core.exceptions import NotFoundError, ConflictError
from src.rbac.crud.permission import PermissionRepository
from src.rbac.crud.role import RoleRepository
from src.rbac.models.role import Role
from src.rbac.service.checker import check_cycle_on_update, get_users_id_by_role_id, invalidate_users_cache


from src.rbac.service._audit import write_audit as _audit


def _build_role_tree(all_roles: list[Role]) -> list[dict]:
    """
    根据角色列表构建角色树（用于前端展示）。
    一个角色可以有多个父角色（parent_role_ids 是数组），
    因此同一节点可能出现在多个父节点下。
    :param all_roles: 所有角色ORM模型列表
    :return: 嵌套字典结构的角色树列表
    """
    # 第一遍遍历：为每个角色创建树节点字典（含空的 children 列表）
    role_map = {}
    for r in all_roles:
        role_map[r.id] = {"id": r.id, "role_name": r.role_name,
                          "role_code": r.role_code, "description": r.description,
                          "status": r.status, "children": []}
    roots = []
    # 第二遍遍历：根据 parent_role_ids 建立父子关系
    for r in all_roles:
        node = role_map[r.id]
        is_child = False
        if r.parent_role_ids:
            for pid in r.parent_role_ids:
                if pid in role_map:
                    # 同一节点可挂载到多个父节点下（多继承）
                    role_map[pid]["children"].append(node)
                    is_child = True
        if not is_child:
            # 没有父节点引用的角色作为根节点
            roots.append(node)
    return roots


async def build_all_role_tree(db: AsyncSession) -> list[dict]:
    """
    查询所有角色并构建完整角色树
    :param db: 数据库异步会话
    :return: 嵌套字典结构的角色树列表
    """
    role_crud = RoleRepository(db)
    result = _build_role_tree(await role_crud.get_all_roles())
    return result


async def get_roles_paginated(
        db: AsyncSession,
        keyword: str | None,
        page: int,
        size: int
) -> tuple[list[dict], int]:
    """
    分页查询角色列表（含用户数统计）
    :param db: 数据库异步会话
    :param keyword: 搜索关键字，为None则不筛选
    :param page: 页码（从1开始）
    :param size: 每页条数
    :return: (角色字典列表, 总条数) 元组
    """
    role_crud = RoleRepository(db)
    result = await role_crud.get_roles_paginated(keyword, page, size)
    return result


async def get_role_by_id(
        db: AsyncSession,
        role_id: int,
) -> dict:
    """
    查询角色详情（含完整权限树）
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :return: 角色详情字典（含挂载的权限树）
    """
    role_crud = RoleRepository(db)
    role = await role_crud.get_role_by_id(role_id)
    if not role:
        raise NotFoundError("角色不存在")
    # 获取角色直接分配的权限记录，构建 deny 映射表
    perms_db = await role_crud.get_role_permission_records(role_id)
    # key=权限ID, value=是否为拒绝
    perm_deny_map = {p["permission_id"]: p.get("is_deny", False) for p in perms_db}
    # 所有已分配权限（含授予和拒绝），用于前端 checked 状态
    perm_assigned = set(perm_deny_map.keys())

    # 加载全部权限资源，构建带角色授权状态的权限树
    perm_crud = PermissionRepository(db)
    all_perms = await perm_crud.get_all()
    perm_map = {}
    for p in all_perms:
        perm_map[p.id] = {"id": p.id, "name": p.name, "code": p.code, "type": p.type,
                          "checked": p.id in perm_assigned,
                          "is_deny": perm_deny_map.get(p.id, False),
                          "partial": False, "children": []}
    # 构建树形结构：子节点挂到父节点的 children 下
    roots = []
    for p in all_perms:
        node = perm_map[p.id]
        if p.parent_id and p.parent_id in perm_map:
            perm_map[p.parent_id]["children"].append(node)
        elif p.parent_id is None:
            roots.append(node)

    return {"id": role.id, "role_name": role.role_name, "role_code": role.role_code,
            "description": role.description, "status": role.status,
            "parent_role_ids": role.parent_role_ids,
            "create_time": role.create_time.isoformat() if role.create_time else None,
            "permissions": roots}


async def create_role(
        db: AsyncSession,
        role_name: str,
        role_code: str,
        description: str | None,
        parent_role_ids: list[int] | None,
        permissions: list[dict],
        operator_id: int,
        operator_name: str,
        ip: str | None) -> dict:
    """
    创建角色（含权限分配和循环依赖检测）
    :param db: 数据库异步会话
    :param role_name: 角色名称
    :param role_code: 角色编码（唯一标识）
    :param description: 角色描述，可选
    :param parent_role_ids: 父角色ID列表，可选
    :param permissions: 权限分配列表 [{permission_id, is_deny}, ...]
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: {"id": 新角色ID}
    """
    role_crud = RoleRepository(db)
    # 检查角色编码唯一性
    existing = await role_crud.get_role_by_code(role_code)
    if existing:
        raise ConflictError("角色编码已存在")
    # 检查继承关系是否存在循环依赖（role_id=0 表示新建，非已有角色）
    if parent_role_ids and await check_cycle_on_update(db, 0, parent_role_ids):
        raise ConflictError("角色继承关系存在循环")
    # 创建角色并设置父角色继承关系
    role = await role_crud.create_role(role_name=role_name, role_code=role_code,
                                       description=description,
                                       parent_role_ids=parent_role_ids or None)
    # 如果指定了权限，建立角色-权限关联
    if permissions:
        await role_crud.set_role_permissions(role.id, permissions)

    await _audit(db, operator_id, operator_name, "CREATE", "ROLE",
                 f"新增角色 {role.role_name}", None, ip, "SUCCESS")
    return {"id": role.id}


async def update_role(db: AsyncSession,
                      role_id: int,
                      update_data: dict,
                      operator_id: int,
                      operator_name: str,
                      ip: str | None) -> None:
    """
    更新角色（含权限覆盖、循环检测和受影响用户缓存失效）
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :param update_data: 需要更新的字段字典
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    role_crud = RoleRepository(db)
    role = await role_crud.get_role_by_id(role_id)
    if not role:
        raise NotFoundError("角色不存在")

    # 将 permissions 从 update_data 中弹出单独处理（需要批量覆盖写入）
    permissions_data = update_data.pop("permissions", None)
    parent_ids = update_data.get("parent_role_ids")
    # 检查父角色设置是否导致循环依赖
    if parent_ids is not None and await check_cycle_on_update(db, role_id, parent_ids):
        raise ConflictError("角色继承关系存在循环")

    # 先更新角色基本信息
    await role_crud.update_role(role, update_data)

    # 如果传了权限数据，则全量覆盖角色权限并失效受影响用户的缓存
    if permissions_data is not None:
        await role_crud.set_role_permissions(role_id, permissions_data)
        # 找出所有受此角色影响的用户（含子角色继承），使其权限缓存失效
        affected = await get_users_id_by_role_id(db, role_id)
        await invalidate_users_cache(affected)

    await _audit(db, operator_id, operator_name, "UPDATE", "ROLE",
                 f"编辑角色 {role.role_name}", None, ip, "SUCCESS")


async def delete_role(
        db: AsyncSession,
        role_id: int,
        operator_id: int,
        operator_name: str,
        ip: str | None
) -> None:
    """
    删除角色（含关联用户检查和缓存失效）
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    role_crud = RoleRepository(db)
    role = await role_crud.get_role_by_id(role_id)
    if not role:
        raise NotFoundError("角色不存在")
    if await role_crud.get_role_user_count(role_id) > 0:
        raise ConflictError("角色下尚有用户关联，请先移除")
    affected = await get_users_id_by_role_id(db, role_id)
    await invalidate_users_cache(affected)
    await role_crud.delete_role(role)

    await _audit(db, operator_id, operator_name, "DELETE", "ROLE",
                 f"删除角色 {role.role_name}", None, ip, "SUCCESS")


async def copy_role(
        db: AsyncSession,
        source_id: int,
        new_name: str,
        new_code: str,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> dict:
    """
    复制角色（含权限和继承关系）
    :param db: 数据库异步会话
    :param source_id: 源角色ID
    :param new_name: 新角色名称
    :param new_code: 新角色编码
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: {"id": 新角色ID}
    """
    role_crud = RoleRepository(db)
    source = await role_crud.get_role_by_id(source_id)
    if not source:
        raise NotFoundError("源角色不存在")
    if await role_crud.get_role_by_code(new_code):
        raise ConflictError("角色编码已存在")

    new_role = await role_crud.create_role(role_name=new_name, role_code=new_code,
                                           description=source.description,
                                           parent_role_ids=source.parent_role_ids)
    perms = await role_crud.get_role_permission_records(source_id)
    if perms:
        await role_crud.set_role_permissions(new_role.id, perms)

    await _audit(db, operator_id, operator_name, "CREATE", "ROLE",
                 f"复制角色 {source.role_name} → {new_role.role_name}", None, ip, "SUCCESS")
    return {"id": new_role.id}


async def get_users_by_role_id(
        db: AsyncSession,
        role_id: int,
        pagination: dict[str, int],
) -> dict:
    """
    分页查询角色关联的用户列表
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :param pagination: {"page": 页码, "size": 每页条数}
    :return: {"total": 总数, "page": 页码, "size": 每页条数, "list": [...]}
    """
    role_crud = RoleRepository(db)
    if not await role_crud.get_role_by_id(role_id):
        raise NotFoundError("角色不存在")
    users, total = await role_crud.get_role_users_paginated(
        role_id, pagination["page"], pagination["size"])
    return {"total": total, "page": pagination["page"], "size": pagination["size"],
            "list": [{"id": u.id, "username": u.username, "real_name": u.real_name}
                     for u in users]}


async def remove_users_from_role(
        db: AsyncSession,
        role_id: int,
        user_ids: list[int],
        operator_id: int,
        operator_name: str,
        ip: str | None
) -> None:
    """
    批量移除角色关联用户（含缓存失效）
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :param user_ids: 待移除的用户ID列表
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    role_crud = RoleRepository(db)
    role = await role_crud.get_role_by_id(role_id)
    if not role:
        raise NotFoundError("角色不存在")
    await role_crud.remove_users_from_role(role_id, user_ids)
    await invalidate_users_cache(set(user_ids))

    await _audit(db, operator_id, operator_name, "DELETE", "ROLE",
                 f"从角色 {role.role_name} 移除用户: {user_ids}", None, ip, "SUCCESS")
