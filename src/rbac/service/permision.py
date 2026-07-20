"""
权限资源管理服务。
提供权限 CRUD、权限树构建、排序和批量导入等业务逻辑。
"""
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.core.exceptions import ConflictError, NotFoundError
from src.rbac.crud.permission import PermissionRepository
from src.rbac.service._audit import write_audit as _audit
from src.rbac.service.checker import invalidate_users_cache


def _build_tree(permissions: list) -> list[dict]:
    """
    根据权限列表构建权限树（用于前端菜单渲染）。
    每个节点只挂到一个父节点下（单继承的树形结构）。
    :param permissions: 权限ORM模型列表
    :return: 嵌套字典结构的权限树列表
    """
    # 第一遍遍历：为每个权限创建树节点字典
    node_map = {}
    for p in permissions:
        node_map[p.id] = {"id": p.id, "name": p.name, "code": p.code, "type": p.type,
                          "parent_id": p.parent_id, "path": p.path, "icon": p.icon,
                          "sort": p.sort, "status": p.status, "api_paths": p.api_paths,
                          "children": []}
    roots = []
    # 第二遍遍历：根据 parent_id 建立父子关系
    for p in permissions:
        node = node_map[p.id]
        if p.parent_id and p.parent_id in node_map:
            # 将当前节点挂载到其父节点的 children 列表中
            node_map[p.parent_id]["children"].append(node)
        elif p.parent_id is None:
            # 没有父节点的作为根节点
            roots.append(node)
    return roots


async def build_all_tree(db: AsyncSession) -> list[dict]:
    """
    查询所有权限并构建完整权限树
    :param db: 数据库异步会话
    :return: 嵌套字典结构的权限树列表
    """
    permissions_crud = PermissionRepository(db)
    all_perms = await permissions_crud.get_all()
    return _build_tree(all_perms)


async def create_permission(
        db: AsyncSession,
        name: str,
        code: str,
        ptype: str,
        parent_id: int | None,
        path: str | None,
        icon: str | None,
        sort: int,
        status: int,
        api_paths: list | None,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> dict:
    """
    创建权限资源
    :param db: 数据库异步会话
    :param name: 权限名称
    :param code: 权限编码（唯一标识）
    :param ptype: 权限类型（MENU 或 BUTTON）
    :param parent_id: 父权限ID，None表示根节点
    :param path: 前端路由路径（菜单专用），可选
    :param icon: 图标标识（菜单专用），可选
    :param sort: 排序号
    :param status: 状态（True启用/False禁用）
    :param api_paths: 关联API路径列表（按钮专用），可选
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: {"id": 新权限ID}
    """
    perm_crud = PermissionRepository(db)
    # 权限编码必须全局唯一
    existing = await perm_crud.get_permission_by_code(code)
    if existing:
        raise ConflictError("权限编码已存在")
    # 如果指定了父权限，验证父权限是否存在
    if parent_id and not await perm_crud.get_permission_by_id(parent_id):
        raise NotFoundError("父资源不存在")

    perm = await perm_crud.create_permission(name=name, code=code, type=ptype,
                                             parent_id=parent_id, path=path, icon=icon,
                                             sort=sort, status=status, api_paths=api_paths)

    await _audit(db, operator_id, operator_name, "CREATE", "PERMISSION",
                 f"创建资源 {perm.name} ({perm.code})", None, ip, "SUCCESS")
    return {"id": perm.id}


async def update_permission(
        db: AsyncSession,
        perm_id: int,
        data: dict | None,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    更新权限资源
    :param db: 数据库异步会话
    :param perm_id: 权限ID
    :param data: 需要更新的字段字典
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    perm_crud = PermissionRepository(db)
    perm = await perm_crud.get_permission_by_id(perm_id)
    if not perm:
        raise NotFoundError("资源不存在")
    await perm_crud.update_permission(perm, data)

    # 权限变更后，失效所有拥有此权限的用户的缓存
    affected = await perm_crud.get_user_ids_by_permission_id(perm_id)
    if affected:
        await invalidate_users_cache(affected)

    await _audit(db, operator_id, operator_name, "UPDATE", "PERMISSION",
                 f"编辑资源 {perm.name}", None, ip, "SUCCESS")


async def delete_permission(
        db: AsyncSession,
        perm_id: int,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    删除权限资源（级联删除子资源由数据库外键处理）
    :param db: 数据库异步会话
    :param perm_id: 权限ID
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    perm_crud = PermissionRepository(db)
    perm = await perm_crud.get_permission_by_id(perm_id)
    if not perm:
        raise NotFoundError("资源不存在")

    # 先找出受影响的用户，再执行删除（删除后关联记录消失，查不到受影响用户）
    affected = await perm_crud.get_user_ids_by_permission_id(perm_id)
    await perm_crud.delete_permission(perm)
    if affected:
        await invalidate_users_cache(affected)

    await _audit(db, operator_id, operator_name, "DELETE", "PERMISSION",
                 f"删除资源 {perm.name}", None, ip, "SUCCESS")


async def sort_permissions(
        db: AsyncSession,
        sorted_ids: list[int],
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    拖拽排序权限资源
    :param db: 数据库异步会话
    :param sorted_ids: 按新顺序排列的权限ID列表
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    perm_crud = PermissionRepository(db)
    await perm_crud.update_sort_orders(sorted_ids)
    await _audit(db, operator_id, operator_name, "UPDATE", "PERMISSION",
                 f"排序资源: {sorted_ids}", None, ip, "SUCCESS")


async def export_all_permissions(db: AsyncSession) -> list[dict]:
    """
    导出所有权限资源树
    :param db: 数据库异步会话
    :return: 嵌套权限资源树列表
    """
    return await build_all_tree(db)


async def import_permissions(
        db: AsyncSession,
        items: list[dict],
) -> None:
    """
    递归导入权限资源树（存在则更新，不存在则创建）
    :param db: 数据库异步会话
    :param items: 权限资源树列表（嵌套字典结构）
    :return: None
    """
    perm_crud = PermissionRepository(db)

    async def _import_nodes(nodes: list[dict], parent_id: int | None = None) -> None:
        """
        递归导入节点：存在则更新，不存在则创建，然后递归处理子节点。
        利用 code 字段唯一性做 upsert 判断。
        :param nodes: 当前层级节点列表
        :param parent_id: 父权限ID，根节点为 None
        :return: None
        """
        for item in nodes:
            # 按 code 查找是否已存在同编码权限
            existing = await perm_crud.get_permission_by_code(item.get("code", ""))
            if existing:
                # 已存在：更新全部可覆盖字段（含父节点归属、路由、图标等）
                await perm_crud.update_permission(existing, {
                    "name": item.get("name"),
                    "type": item.get("type", existing.type),
                    "parent_id": parent_id,
                    "path": item.get("path"),
                    "icon": item.get("icon"),
                    "sort": item.get("sort", 0),
                    "status": item.get("status", 1),
                    "api_paths": item.get("api_paths"),
                })
                new_id = existing.id
            else:
                # 不存在：新建权限节点
                new_perm = await perm_crud.create_permission(
                    name=item["name"], code=item.get("code", ""),
                    type=item.get("type", "MENU"), parent_id=parent_id,
                    path=item.get("path"), icon=item.get("icon"),
                    sort=item.get("sort", 0), api_paths=item.get("api_paths"),
                )
                new_id = new_perm.id
            # 递归处理子节点，将当前节点ID作为父节点ID传递
            if item.get("children"):
                await _import_nodes(item["children"], new_id)

    await _import_nodes(items)
