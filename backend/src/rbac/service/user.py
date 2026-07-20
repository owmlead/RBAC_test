"""
用户管理服务。
提供用户创建、更新、删除、批量操作和角色分配等业务逻辑。
"""
import json
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.core.exceptions import AppError, ConflictError, NotFoundError
from src.rbac.core.security import validate_password_strength, hash_password
from src.rbac.crud.user import UserRepository
from src.rbac.service.checker import invalidate_user_cache, get_user_permissions, get_user_menu_tree
from src.rbac.service._audit import write_audit as _audit


async def create_user(
        db: AsyncSession,
        username: str,
        password: str,
        real_name: str,
        gender: int,
        email: str | None,
        phone: str | None,
        avatar: str | None,
        role_ids: list[int],
        operator_id: int,
        operator_name: str,
        ip: str | None
) -> dict:
    """
    创建用户（含可选角色分配和审计日志）
    :param db: 数据库异步会话
    :param username: 用户名
    :param password: 明文密码（将自动哈希）
    :param real_name: 真实姓名
    :param gender: 性别（0未知/1男/2女）
    :param email: 邮箱，可选
    :param phone: 手机号，可选
    :param avatar: 头像URL，可选
    :param role_ids: 初始角色ID列表
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: {"id": 新用户ID}
    """
    user_crud = UserRepository(db)
    # 检查用户名唯一性
    existing = await user_crud.get_user_by_username(username)
    if existing:
        raise ConflictError("用户名已存在")
    # 密码强度校验（长度、复杂度等）
    ok, msg = validate_password_strength(password)
    if not ok:
        raise AppError(msg, code=400, status_code=400)

    # 创建用户（密码已经过哈希处理）
    user = await user_crud.create_user(username=username, password=hash_password(password), real_name=real_name,
                                       gender=gender, email=email, phone=phone, avatar=avatar)
    # 如果指定了初始角色，建立用户-角色关联
    if role_ids:
        await user_crud.set_user_roles(user.id, role_ids)

    # 记录操作审计日志，params 以 JSON 形式存储
    await _audit(db, operator_id, operator_name, "CREATE", "USER",
                 f"新增用户 {user.username}",
                 json.dumps({"username": username, "real_name": real_name}), ip, "SUCCESS")
    return {"id": user.id}


async def update_user(
        db: AsyncSession,
        user_id: int,
        update_data: dict,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    更新用户信息
    :param db: 数据库异步会话
    :param user_id: 待更新用户ID
    :param update_data: 需要更新的字段字典
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    await user_crud.update_user_by_data(user=user, update_data=update_data)
    await _audit(db, operator_id, operator_name, "UPDATE", "USER",
                 f"编辑用户 {user.username}", None, ip, "SUCCESS")


async def delete_user(
        db: AsyncSession,
        user_id: int,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    逻辑删除用户
    :param db: 数据库异步会话
    :param user_id: 待删除用户ID
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    # 防止操作者误删自己
    if user.id == operator_id:
        raise ConflictError("不能删除自己")

    # 逻辑删除（软删除），不物理删除数据库记录
    await user_crud.soft_delete_user(user)
    # 删除后使该用户的权限缓存失效
    await invalidate_user_cache(user_id=user_id)
    await _audit(db, operator_id, operator_name, "DELETE", "USER",
                 f"删除用户 {user.username}", None, ip, "SUCCESS")


async def batch_status(
        db: AsyncSession,
        ids: list[int],
        status: int,
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    批量启用/禁用用户
    :param db: 数据库异步会话
    :param ids: 用户ID列表
    :param status: 目标状态（True启用/False禁用）
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    # 批量更新用户状态（启用/禁用）
    await user_crud.batch_status(ids, status)
    # 状态变更后逐个失效权限缓存
    for uid in ids:
        await invalidate_user_cache(uid)
    await _audit(db, operator_id, operator_name, "UPDATE", "USER",
                 f"批量更新用户状态: ids={ids}, status={status}", None, ip, "SUCCESS")


async def batch_delete(
        db: AsyncSession,
        ids: list[int],
        operator_id: int,
        operator_name: str,
        ip: str | None,
) -> None:
    """
    批量逻辑删除用户
    :param db: 数据库异步会话
    :param ids: 用户ID列表
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    await user_crud.batch_delete(ids)
    await _audit(db, operator_id, operator_name, "DELETE", "USER",
                 f"批量删除用户: ids={ids}", None, ip, "SUCCESS")


async def assign_roles(
        db: AsyncSession,
        user_id: int,
        role_ids: list[int],
        operator_id: int,
        operator_name: str,
        ip: str | None
) -> None:
    """
    全量覆盖用户角色（含缓存失效和审计）
    :param db: 数据库异步会话
    :param user_id: 目标用户ID
    :param role_ids: 角色ID列表
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    await user_crud.set_user_roles(user_id, role_ids)
    await invalidate_user_cache(user_id)
    await _audit(db, operator_id, operator_name, "UPDATE", "USER",
                 f"分配用户 {user.username} 角色: {role_ids}", None, ip, "SUCCESS")


async def reset_user_password(
        db: AsyncSession,
        user_id: int,
        new_password: str,
        operator_id: int,
        operator_name: str,
        ip: str | None
) -> None:
    """
    重置用户密码（含密码强度校验、哈希和审计日志）
    :param db: 数据库异步会话
    :param user_id: 目标用户ID
    :param new_password: 新密码（明文）
    :param operator_id: 操作者ID
    :param operator_name: 操作者用户名
    :param ip: 操作者IP
    :return: None
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    ok, msg = validate_password_strength(new_password)
    if not ok:
        raise ConflictError(msg)

    await user_crud.update_user_by_data(user, {"password": hash_password(new_password)})
    await invalidate_user_cache(user_id)
    await _audit(db, operator_id, operator_name, "UPDATE", "USER",
                 f"重置用户 {user.username} 的密码", None, ip, "SUCCESS")


async def update_user_roles(
        db: AsyncSession,
        user_id: int,
) -> dict:
    """
    查看用户最终权限列表和菜单树
    :param db: 数据库异步会话
    :param user_id: 用户ID
    :return: {"menus": [...], "permissions": [...]}
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    result = {}
    result["menus"] = await get_user_menu_tree(db, user_id)
    result["permissions"] = sorted(await get_user_permissions(db, user_id))
    return result
