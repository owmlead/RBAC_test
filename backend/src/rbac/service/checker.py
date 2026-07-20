"""
权限校验核心服务。
提供用户权限计算、内存缓存、权限校验和菜单树构建功能。
核心规则：
1. 角色继承：用户通过角色继承获得祖先角色的所有权限
2. deny 优先：任一角色拒绝某项权限（is_deny=True），则最终结果为拒绝
3. 通配符匹配：如 user:* 可以匹配 user:create、user:update 等子权限
4. 菜单过滤：无权限的按钮不展示，无内容的菜单自动隐藏
"""
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.crud.permission import PermissionRepository
from src.rbac.crud.role import RoleRepository
from src.rbac.crud.user import UserRepository
from src.rbac.core.redis_client import (
    cache_user_permissions, get_cached_permissions, invalidate_permission_cache,
    _available as _redis_available,
)

# 内存降级缓存（Redis 不可用时使用）
_permission_cache: dict[int, set[str]] = {}


async def _get_ancestor_role_ids(db: AsyncSession, role_ids: list[int]) -> set[int]:
    """
    使用 BFS（广度优先搜索）递归获取所有祖先角色 ID，用于角色继承链展开。
    遍历每个角色的 parent_role_ids，逐层向上收集所有祖先。
    :param db: 数据库异步会话
    :param role_ids: 起始角色ID列表
    :return: 所有祖先角色ID集合（含自身）
    """
    role_crud = RoleRepository(db)
    all_ids = set(role_ids)
    queue = list(role_ids)
    visited = set()  # 防止重复访问造成死循环
    while queue:
        rid = queue.pop(0)  # BFS：取出队首元素
        if rid in visited:
            continue
        visited.add(rid)
        role = await role_crud.get_role_by_id(rid)
        if role and role.parent_role_ids:
            for pid in role.parent_role_ids:
                if pid not in visited:
                    all_ids.add(pid)
                    queue.append(pid)  # 将父角色入队，继续向上追溯
    return all_ids


async def resolve_user_permissions(db: AsyncSession, user_id: int) -> set[str]:
    """
    计算用户最终权限集合：展开角色继承链，按 deny 优先规则合并权限。
    处理流程：
    1. 获取用户启用的角色列表
    2. BFS 展开所有祖先角色
    3. 查询所有角色关联的权限及其 is_deny 标记
    4. deny 优先合并：任一角色拒绝则该权限最终拒绝
    :param db: 数据库异步会话
    :param user_id: 用户ID
    :return: 用户最终拥有的权限编码集合
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    perms_crud = PermissionRepository(db)

    # 展开用户所有启用的角色及其祖先角色
    all_role_ids = await _get_ancestor_role_ids(db, [r.id for r in user.roles if r.status])

    # 批量查询所有角色关联的权限（含 is_deny 标记）
    if all_role_ids:
        result = await perms_crud.get_perms_code_by_role_ids(list(all_role_ids))
        rows: list[tuple[str, bool]] = result
    else:
        rows = []

    # deny 优先合并规则：任一角色拒绝该权限即为拒绝
    # 如果多个角色中既有允许又有拒绝，最终结果以拒绝为准
    perm_map: dict[str, bool] = {}
    for code, is_deny in rows:
        current = perm_map.get(code)
        if current is None:
            # 首次遇到该权限，直接记录其 deny 状态
            perm_map[code] = is_deny
        elif is_deny:
            # 已有记录但新来源是拒绝 → 覆盖为拒绝（deny 优先）
            perm_map[code] = True

    # 过滤掉被拒绝的权限，只返回最终允许的权限编码
    perms = set([code for code, is_denied in perm_map.items() if not is_denied])
    return perms


async def get_user_permissions(db: AsyncSession, user_id: int) -> set[str]:
    """
    获取用户权限集合（Redis 优先 -> 内存降级 -> DB 计算）。
    :param db: 数据库异步会话
    :param user_id: 用户ID
    :return: 权限编码集合
    """
    if _redis_available:
        cached = await get_cached_permissions(user_id)
        if cached is not None:
            return cached
    if user_id in _permission_cache:
        return _permission_cache[user_id]
    perms = await resolve_user_permissions(db, user_id)
    if _redis_available:
        await cache_user_permissions(user_id, perms)
    else:
        _permission_cache[user_id] = perms
    return perms


async def check_user_has_permission(db: AsyncSession, user_id: int, required_code: str) -> bool:
    """
    检查用户是否拥有指定权限。支持三级匹配策略：
    1. 超级通配符 "*"：拥有全部权限
    2. 精确匹配：权限编码完全一致
    3. 前缀通配符：如 "user:*" 匹配 "user:create"、"user:update" 等
    :param db: 数据库异步会话
    :param user_id: 用户ID
    :param required_code: 需要校验的权限编码
    :return: True拥有权限 / False无权限
    """
    perms = await get_user_permissions(db, user_id)
    # 超级管理员：拥有 "*" 权限则放行一切
    if "*" in perms:
        return True
    # 精确匹配
    if required_code in perms:
        return True
    # 通配符前缀匹配：如 user:* 匹配 user:create
    for p in perms:
        if p.endswith(":*") and required_code.startswith(p[:-1]):
            return True
    return False


async def invalidate_user_cache(user_id: int) -> None:
    """
    使指定用户的权限缓存失效（角色/权限变更后调用）。
    同时清除内存缓存和 Redis 缓存，确保下次请求重新计算权限。
    :param user_id: 用户ID
    :return: None
    """
    _permission_cache.pop(user_id, None)
    await invalidate_permission_cache(user_id)


async def invalidate_users_cache(user_ids: set[int]) -> None:
    """
    批量失效多个用户的权限缓存。
    用于角色或权限变更后，一次性清理所有受影响用户的缓存。
    同时清除内存缓存和 Redis 缓存。
    :param user_ids: 用户ID集合
    :return: None
    """
    for uid in user_ids:
        _permission_cache.pop(uid, None)
        await invalidate_permission_cache(uid)


async def get_user_menu_tree(db: AsyncSession, user_id: int) -> list[dict]:
    """
    构建用户可见的菜单树。
    处理流程：
    1. 加载所有权限资源和用户权限集合
    2. 按钮权限过滤：无权限的按钮不展示
    3. 构建树形结构：按 parent_id 组装父子关系
    4. 递归过滤：移除无子节点的空菜单节点
    :param db: 数据库异步会话
    :param user_id: 用户ID
    :return: 菜单树列表（嵌套字典结构）
    """
    perms_curd = PermissionRepository(db)
    all_perms = await perms_curd.get_all()
    perms = await get_user_permissions(db, user_id)

    # 构建节点映射：按钮类型需要权限校验，非按钮类型直接加入
    # 禁用的权限不出现在菜单中
    node_map: dict[int, dict] = {}
    for p in all_perms:
        if not p.status:
            continue  # 跳过禁用的权限
        if p.type == "BUTTON":
            # 无权限的按钮直接跳过（除非用户拥有超级通配符 "*"）
            if p.code not in perms and "*" not in perms:
                continue
            node_map[p.id] = {
                "id": p.id, "name": p.name, "code": p.code,
                "type": p.type, "sort": p.sort, "children": []
            }
        else:
            # 菜单/目录节点始终加入，后续通过 filter_empty_menus 过滤空菜单
            node_map[p.id] = {
                "id": p.id, "name": p.name, "code": p.code,
                "type": p.type, "path": p.path, "icon": p.icon,
                "sort": p.sort, "children": []
            }

    # 按 parent_id 组装树形结构
    roots: list[dict] = []
    for p in all_perms:
        if p.id not in node_map:
            continue  # 被过滤掉的按钮跳过
        node = node_map[p.id]
        if p.parent_id and p.parent_id in node_map:
            # 有父节点且在映射中存在 → 挂到父节点下
            node_map[p.parent_id]["children"].append(node)
        elif p.parent_id is None:
            # 根节点
            roots.append(node)

    def filter_empty_menus(nodes: list[dict]) -> list[dict]:
        """
        递归过滤：移除没有子节点的 MENU 类型节点。
        如果目录下所有内容都因权限不足被过滤，则目录本身也不展示。
        """
        result = []
        for n in nodes:
            # 先递归过滤子节点
            n["children"] = filter_empty_menus(n["children"])
            # MENU 节点如果没有子内容则移除
            if n["type"] == "MENU" and not n["children"]:
                continue
            result.append(n)
        return result

    return filter_empty_menus(roots)


async def check_cycle_on_update(db: AsyncSession, role_id: int, parent_role_ids: list[int]) -> bool:
    """
    编辑角色时检查 parent_role_ids 是否会导致循环继承。
    检查逻辑：遍历每个候选父角色，展开其祖先链，如果当前角色
    出现在祖先链中，则说明会产生循环依赖。
    :param db: 数据库异步会话
    :param role_id: 当前角色ID（新建时传0，0不会匹配任何已有角色的ID）
    :param parent_role_ids: 待设置的父角色ID列表
    :return: True存在循环 / False无循环
    """
    for pid in parent_role_ids:
        # 展开该父角色的所有祖先，检查是否包含当前角色
        ancestors = await _get_ancestor_role_ids(db, [pid])
        if role_id in ancestors:
            return True  # 发现循环：自身出现在祖先链中
    return False


async def get_users_id_by_role_id(db: AsyncSession, role_id: int) -> set[int]:
    """
    获取拥有某角色的所有用户ID（含通过子角色间接继承的用户）。
    用于角色变更后批量失效受影响用户的权限缓存。
    处理流程：
    1. 直接关联：查询 user_role 表中直接分配该角色的用户
    2. 间接关联：找出 parent_role_ids 包含该角色的子角色，
       再递归展开子角色的祖先链，最后查询这些角色的用户
    :param db: 数据库异步会话
    :param role_id: 角色ID
    :return: 所有受影响的用户ID集合
    """
    role_curd = RoleRepository(db)
    # 步骤1：直接拥有该角色的用户
    rows = await role_curd.get_user_by_role_id(role_id)
    user_ids = {r[0] for r in rows}

    # 步骤2：查找 parent_role_ids 中包含该角色的子角色（即继承该角色的角色）
    all_roles = await role_curd.get_all_role()
    child_role_ids: set[int] = set()
    for r in all_roles:
        if r.parent_role_ids and role_id in r.parent_role_ids:
            child_role_ids.add(r.id)

    # 展开子角色的祖先链（包含子角色本身及其所有祖先）
    for child_id in list(child_role_ids):
        child_role_ids.update(await _get_ancestor_role_ids(db, [child_id]))

    # 步骤3：查询所有子角色关联的用户
    if child_role_ids:
        rows = await role_curd.get_user_by_role_ids(child_role_ids)
        user_ids.update(r[0] for r in rows)

    return user_ids
