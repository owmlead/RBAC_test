"""
认证鉴权服务。
提供登录、刷新令牌、登出、强制下线和权限检查等业务逻辑。
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.core.config import setting
from src.rbac.core.exceptions import LockedError, UnauthorizedError, ConflictError
from src.rbac.core.redis_client import incr_login_failure as _redis_incr_fail, \
    get_login_failure_count as _redis_get_fail, reset_login_failure as _redis_reset_fail, \
    add_to_blacklist as _redis_blacklist, set_kicked_out as _redis_set_kicked, \
    get_kicked_out_time as _redis_get_kicked, is_blacklisted as _redis_is_blacklisted
from src.rbac.core.security import verify_captcha, verify_password, \
    create_jwt_token, decode_jwt_token, get_token_jti, get_token_expire_time, \
    hash_password, validate_password_strength
from src.rbac.crud.user import UserRepository
from src.rbac.models.token_blacklist import TokenBlacklist
from src.rbac.models.user import User
from src.rbac.models.login_failure import LoginFailure
from src.rbac.service.checker import check_user_has_permission, resolve_user_permissions, invalidate_user_cache


# ── 登录失败追踪（Redis 优先，数据库降级） ──

_lock_ttl = setting.LOGIN_LOCK_MINUTES * 60


async def _record_login_failure(db: AsyncSession, username: str, ip: str) -> int:
    """
    记录登录失败，返回当前失败次数。
    采用 Redis 优先策略：Redis 可用时使用 Redis 计数器（支持 TTL 自动过期），
    Redis 不可用时降级到数据库记录。两级存储保证高可用。
    :param db: 数据库异步会话
    :param username: 用户名
    :param ip: 客户端IP
    :return: 当前累计失败次数
    """
    count = await _redis_incr_fail(username, _lock_ttl)
    if count >= 0:
        return count  # Redis 正常返回
    # Redis 不可用 → DB 降级：查询或创建失败记录
    result = await db.execute(select(LoginFailure).where(LoginFailure.username == username))
    record = result.scalars().first()
    if record:
        record.fail_count += 1
        # 达到最大尝试次数时设置锁定截止时间
        if record.fail_count >= setting.MAX_LOGIN_ATTEMPTS:
            record.locked_until = datetime.now(timezone.utc) + timedelta(minutes=setting.LOGIN_LOCK_MINUTES)
    else:
        record = LoginFailure(username=username, ip=ip, fail_count=1)
        db.add(record)
    await db.flush()
    return record.fail_count


async def _check_login_locked(db: AsyncSession, username: str) -> tuple[bool, str]:
    """检查是否锁定。Redis 优先。"""
    fail_count = await _redis_get_fail(username)
    if fail_count >= 0:
        if fail_count >= setting.MAX_LOGIN_ATTEMPTS:
            return True, f"账号异常，请 {setting.LOGIN_LOCK_MINUTES} 分钟后重试"
        return False, ""
    # DB 降级
    result = await db.execute(select(LoginFailure).where(LoginFailure.username == username))
    record = result.scalars().first()
    if not record:
        return False, ""
    if record.fail_count >= setting.MAX_LOGIN_ATTEMPTS:
        if record.locked_until and datetime.now(timezone.utc) < record.locked_until:
            remaining = int((record.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            return True, f"账号异常，请 {remaining} 分钟后重试"
        await db.delete(record)
        await db.flush()
    return False, ""


async def _get_login_failure_count(db: AsyncSession, username: str) -> int:
    """获取失败次数。Redis 优先。"""
    count = await _redis_get_fail(username)
    if count >= 0:
        return count
    result = await db.execute(select(LoginFailure).where(LoginFailure.username == username))
    record = result.scalars().first()
    return record.fail_count if record else 0


async def _reset_login_failures(db: AsyncSession, username: str) -> None:
    """清除失败记录。Redis 优先。"""
    await _redis_reset_fail(username)
    result = await db.execute(select(LoginFailure).where(LoginFailure.username == username))
    record = result.scalars().first()
    if record:
        await db.delete(record)
        await db.flush()


from src.rbac.service._audit import write_audit as _audit


async def _blacklist_token(db: AsyncSession, token: str) -> None:
    """
    将 Token 加入黑名单，使其立即失效。
    采用 Redis + DB 双写策略：Redis 优先（利用 TTL 自动过期），DB 作为持久化兜底。
    :param db: 数据库异步会话
    :param token: 待加入黑名单的 JWT token
    :return: None
    """
    jti = get_token_jti(token)
    exp = get_token_expire_time(token)
    if not jti or not exp:
        return  # 无法提取 jti 或过期时间则跳过（防御性处理）
    # 计算剩余有效时间，至少保留 1 秒
    ttl = max(1, int((exp - datetime.now(timezone.utc)).total_seconds()))
    # Redis 写入（TTL 到期后自动清除，无需手动清理过期黑名单）
    await _redis_blacklist(jti, ttl)
    # DB 同时写入：Redis 不可用时降级，同时也作为持久化备份
    db.add(TokenBlacklist(jti=jti, expire_time=exp))
    await db.flush()


async def login(
        db: AsyncSession,
        username: str,
        password: str,
        captcha_id: str | None,
        captcha: str | None,
        ip: str | None
) -> dict:
    """
    用户登录：校验凭证 → 签发JWT → 返回Token和用户信息
    :param db: 数据库异步会话
    :param username: 用户名
    :param password: 明文密码
    :param captcha_id: 验证码ID（失败超过阈值时必填）
    :param captcha: 验证码答案（失败超过阈值时必填）
    :param ip: 客户端IP
    :return: 包含access_token, refresh_token和user_info的字典
    """
    # 第一步：检查账号是否被锁定（连续失败次数超限）
    locked, msg = await _check_login_locked(db, username)
    if locked:
        raise LockedError(msg)

    # 第二步：失败次数超过验证码阈值时，必须校验验证码
    fail_count = await _get_login_failure_count(db, username)
    if fail_count >= setting.CAPTCHA_THRESHOLD:
        if not captcha_id or not captcha:
            raise UnauthorizedError("请输入验证码")
        if not verify_captcha(captcha_id, captcha):
            raise UnauthorizedError("验证码错误")

    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_username(username=username)

    # 第三步：校验密码。防用户名枚举——不论用户是否存在，统一响应
    if not user or not verify_password(password, user.password):
        # 记录登录失败次数（用于锁定和验证码判断）
        await _record_login_failure(db, username, ip or "unknown")
        # 审计日志不记录不存在的用户名，防止通过日志枚举用户
        if user:
            await _audit(db, user.id, username, "LOGIN", "AUTH",
                         "登录失败: 密码错误", None, ip, "FAIL")
        raise UnauthorizedError("用户名或密码错误")

    # 第四步：检查用户是否被禁用
    if not user.status:
        raise UnauthorizedError("用户已被禁用")

    # 第五步：登录成功——清除失败记录，更新最后登录时间
    await _reset_login_failures(db, username)
    user.last_login_time = datetime.now()
    await db.flush()

    # 提取用户角色编码列表，用于前端展示和权限判断
    role_objs = user.roles
    role_codes = [r.role_code for r in role_objs]

    # 解析用户最终权限集合（含角色继承和 deny 优先）
    perms = sorted(await resolve_user_permissions(db, user.id))

    # 签发双 Token：access_token（短时效，用于 API 鉴权） + refresh_token（长时效，用于续期）
    access_token = create_jwt_token(
        {"user_id": user.id, "username": user.username}, token_type="access"
    )
    refresh_token = create_jwt_token(
        {"user_id": user.id, "username": user.username}, token_type="refresh"
    )

    await _audit(db, user.id, user.username, "LOGIN", "AUTH",
                 f"登录成功: {user.username}", None, ip, "SUCCESS")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": setting.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_info": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "roles": role_codes,
            "permissions": perms,
        },
    }


async def refresh(db: AsyncSession, token: str) -> dict:
    """
    刷新access_token（旧的refresh_token立即失效）
    :param db: 数据库异步会话
    :param token: 有效的refresh_token
    :return: 包含新access_token和refresh_token的字典
    """
    # 解码并校验 token：必须是 refresh 类型
    payload = decode_jwt_token(token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("token无效或已过期")

    # 检查 token 是否已被加入黑名单（防止重放攻击）
    jti = payload.get("jti")
    if jti:
        result = await db.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        blacklisted = result.scalar_one_or_none()
        if blacklisted:
            raise UnauthorizedError("token已被注销")

    # 校验用户状态：必须存在且未被禁用
    user_id = payload.get("user_id")
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user or not user.status:
        raise UnauthorizedError("用户不存在或已被禁用")

    # 校验用户是否被管理员强制下线（token 签发时间 < 踢出时间）
    kicked_at = await _redis_get_kicked(user_id)
    if kicked_at:
        iat = payload.get("iat", 0)
        if iat < kicked_at:
            raise UnauthorizedError("您已被管理员强制下线，请重新登录")

    # 旧的 refresh_token 立即加入黑名单，防止被滥用（实现 refresh token rotation）
    await _blacklist_token(db, token)

    new_access = create_jwt_token(
        {"user_id": user.id, "username": user.username}, token_type="access"
    )
    new_refresh = create_jwt_token(
        {"user_id": user.id, "username": user.username}, token_type="refresh"
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "expires_in": setting.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def logout(db: AsyncSession, token: str, ip: str | None = None) -> None:
    """
    用户登出：将当前access_token加入黑名单
    :param db: 数据库异步会话
    :param token: 待注销的access_token
    :param ip: 客户端IP
    :return: None
    """
    payload = decode_jwt_token(token)
    if payload:
        await _blacklist_token(db, token)
        await _audit(db, payload.get("user_id"), payload.get("username", "unknown"),
                     "LOGOUT", "AUTH", f"登出: {payload.get('username')}", None, ip, "SUCCESS")


async def kick_out(db: AsyncSession, operator: User, target_user_id: int, ip: str | None = None) -> None:
    """
    管理员强制下线某用户（使目标用户权限缓存失效）
    :param db: 数据库异步会话
    :param operator: 执行操作的当前用户
    :param target_user_id: 被强制下线的目标用户ID
    :param ip: 客户端IP
    :return: None
    """
    user_crud = UserRepository(db)
    target = await user_crud.get_user_by_id(target_user_id)
    if not target:
        raise UnauthorizedError("目标用户不存在")

    # 清除权限缓存
    await invalidate_user_cache(target_user_id)
    # 记录踢出时间戳，该时间之前签发的 token 全部失效
    await _redis_set_kicked(target_user_id)
    await _audit(db, operator.id, operator.username,
                 "KICK_OUT", "AUTH", f"强制下线用户: {target.username}", None, ip, "SUCCESS")


async def change_password(
        db: AsyncSession,
        user: User,
        old_password: str,
        new_password: str,
        ip: str | None,
) -> None:
    """
    当前用户修改自己的登录密码。

    校验流程：
    1. 验证旧密码是否正确
    2. 新密码不能与旧密码相同
    3. 新密码需满足强度要求
    4. 哈希后写入数据库
    5. 踢出所有旧设备（设置 kicked_at 时间戳使所有旧 token 失效）
    6. 清除权限缓存
    7. 记录审计日志

    :param db: 数据库异步会话
    :param user: 当前登录用户
    :param old_password: 当前密码（用于身份验证）
    :param new_password: 新密码
    :param ip: 客户端IP
    :return: None
    """
    # 1. 验证旧密码
    if not verify_password(old_password, user.password):
        raise UnauthorizedError("当前密码错误")

    # 2. 新密码不能与旧密码相同
    if old_password == new_password:
        raise ConflictError("新密码不能与当前密码相同")

    # 3. 密码强度校验
    ok, msg = validate_password_strength(new_password)
    if not ok:
        raise ConflictError(msg)

    # 4. 更新密码
    user_crud = UserRepository(db)
    await user_crud.update_user_by_data(user, {"password": hash_password(new_password)})

    # 5. 清除权限缓存
    await invalidate_user_cache(user.id)

    # 6. 记录踢出时间戳，该时间之前签发的所有 token 全部失效
    #    （包括当前设备——前端收到 401 后会跳转登录页）
    await _redis_set_kicked(user.id)

    # 7. 审计日志
    await _audit(db, user.id, user.username,
                 "CHANGE_PASSWORD", "AUTH",
                 f"修改密码: {user.username}", None, ip, "SUCCESS")


async def verify_token(db: AsyncSession, token: str) -> dict:
    """
    验证 token 有效性并返回用户信息（供外部服务调用）。

    校验流程与 get_current_user 一致：
    1. 解码 JWT 获取载荷
    2. 检查 token 黑名单（Redis 优先，DB 降级）
    3. 查询用户并校验状态（存在、未删除、未禁用、未被踢下线）

    :param db: 数据库异步会话
    :param token: JWT token 字符串
    :return: {"user_id": ..., "username": ..., "real_name": ..., "roles": [...], "permissions": [...]}
    """
    from src.rbac.service.checker import get_user_permissions

    # 1. 解码 token
    payload = decode_jwt_token(token)
    if not payload:
        raise UnauthorizedError("token 无效或已过期")

    # 2. 检查黑名单
    jti = payload.get("jti")
    if jti:
        if await _redis_is_blacklisted(jti):
            raise UnauthorizedError("token 已被注销")
        result = await db.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        if result.scalars().first():
            raise UnauthorizedError("token 已被注销")

    # 3. 查询用户
    user_id = payload.get("user_id")
    if not user_id:
        raise UnauthorizedError("token 内容无效")

    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user or user.deleted_at:
        raise UnauthorizedError("用户不存在或已删除")
    if not user.status:
        raise UnauthorizedError("用户已被禁用")

    # 4. 检查是否被踢下线
    kicked_at = await _redis_get_kicked(user_id)
    if kicked_at:
        iat = payload.get("iat", 0)
        if iat < kicked_at:
            raise UnauthorizedError("您已被管理员强制下线，请重新登录")

    # 5. 返回用户信息
    role_codes = [r.role_code for r in user.roles]
    perms = sorted(await get_user_permissions(db, user_id))

    return {
        "user_id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "roles": role_codes,
        "permissions": perms,
    }


async def check_permission(db: AsyncSession, user: User, permission_code: str) -> dict:
    """
    鉴权检查：当前用户是否拥有指定权限
    :param db: 数据库异步会话
    :param user: 当前用户
    :param permission_code: 需要检查的权限编码
    :return: {"allowed": True/False}
    """
    allowed = await check_user_has_permission(db, user.id, permission_code)
    return {"allowed": allowed}
