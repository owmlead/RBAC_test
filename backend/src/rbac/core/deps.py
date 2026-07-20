"""
FastAPI 依赖注入模块。
提供当前用户解析、权限校验、分页参数等可复用的依赖项。

核心依赖项：
- get_current_user: 从 JWT Token 解析并验证当前登录用户
- require_permission: 依赖工厂函数，校验用户是否拥有指定权限
- get_pagination: 从查询参数中提取分页信息
"""
from fastapi import Depends, Header, Query, Request
from sqlalchemy import select

from src.rbac.core.exceptions import UnauthorizedError, ForbiddenError
from src.rbac.core.redis_client import is_blacklisted as _redis_is_blacklisted, \
    get_kicked_out_time as _redis_get_kicked
from src.rbac.core.security import decode_jwt_token
from src.rbac.crud.user import UserRepository
from src.rbac.db.session import get_db
from src.rbac.models.token_blacklist import TokenBlacklist
from src.rbac.models.user import User
from src.rbac.service.checker import get_user_permissions


async def get_current_user(
        db=Depends(get_db),
        authorization: str = Header(None, description="Bearer <token>")
) -> User:
    """
    从请求头 Authorization 解析 JWT 并返回当前用户。

    校验流程：
    1. 检查 Authorization 请求头是否存在且格式正确
    2. 解析 JWT Token 获取载荷
    3. 检查 Token JTI 是否在黑名单中（Redis 优先，DB 降级）
    4. 根据载荷中的 user_id 查询用户
    5. 校验用户是否存在、是否被软删除、是否被禁用

    :param db: 数据库异步会话（自动注入）
    :param authorization: Authorization 请求头，格式为 "Bearer <token>"
    :return: 当前登录用户的 User ORM 对象
    :raises UnauthorizedError: Token 缺失、格式错误、无效/过期、已注销、用户不存在或已禁用
    """
    # 1. 检查 Authorization 请求头是否存在
    if not authorization:
        raise UnauthorizedError("缺少认证令牌")
    # 2. 校验 Bearer Token 格式
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误")
    # 3. 提取 Token 字符串（去掉 "Bearer " 前缀）
    token = authorization[len("Bearer "):]
    # 4. 解析并验证 JWT Token
    payload = decode_jwt_token(token)
    if payload is None:
        raise UnauthorizedError("token 无效或已过期")
    # 5. 检查 Token 黑名单（Redis 优先，DB 作为降级方案）
    jti = payload.get("jti")
    if jti:
        # Redis 优先（O(1) 查询 + TTL 自动过期），不可用时降级到 DB
        if await _redis_is_blacklisted(jti):
            raise UnauthorizedError("token 已被注销，请重新登录")
        # DB 降级：当 Redis 不可用时，从数据库确认黑名单状态
        result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
        blacklisted = result.scalars().first()
        if blacklisted:
            raise UnauthorizedError("token 已被注销，请重新登录")

    # 6. 从载荷中提取用户 ID
    user_id = payload.get("user_id")
    if not user_id:
        raise UnauthorizedError("token 内容无效")
    # 7. 查询用户并校验状态
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    # 7a. 用户不存在或已被软删除
    if not user or user.deleted_at:
        raise UnauthorizedError("用户不存在或已删除")
    # 7b. 用户被管理员禁用
    if not user.status:
        raise UnauthorizedError("用户已被禁用")
    # 7c. 用户被管理员强制下线（token 签发时间 < 踢出时间）
    kicked_at = await _redis_get_kicked(user_id)
    if kicked_at:
        iat = payload.get("iat", 0)
        if iat < kicked_at:
            raise UnauthorizedError("您已被管理员强制下线，请重新登录")

    return user


def require_permission(permission_code: str):
    """
    权限校验依赖工厂：返回一个 Depends 校验当前用户是否拥有指定权限。

    权限匹配规则（从高到低）：
    - 超级管理员通配符 "*" → 直接放行
    - 精确匹配 permission_code
    - 通配符匹配：如用户有 "user:*" 则可通过 "user:list"、 "user:create" 等

    用法示例:
        @router.get("/users")
        async def list_users(_: bool = require_permission("user:list")):
            ...

    :param permission_code: 需要校验的权限编码（如 "user:list"、"role:create"）
    :return: Depends 可调用对象，注入后返回 True
    :raises ForbiddenError: 用户缺少指定权限
    """
    async def _check(
            current_user=Depends(get_current_user),
            db=Depends(get_db),
    ) -> bool:
        """
        内部校验函数：检查当前用户是否拥有指定权限。

        执行流程：
        1. 获取当前用户的所有有效权限编码集合
        2. 超级管理员通配符 "*" 直接放行
        3. 精确匹配目标权限编码
        4. 通配符前缀匹配（如 "user:*" 匹配 "user:list"）

        :param current_user: 当前用户（通过 Depends 自动注入）
        :param db: 数据库会话（通过 Depends 自动注入）
        :return: True
        :raises ForbiddenError: 权限不足
        """
        # 获取当前用户拥有的所有权限编码集合
        perms = await get_user_permissions(db, current_user.id)
        # 超级管理员拥有通配符 "*"，直接放行
        if "*" in perms:
            return True

        # 精确匹配：用户权限集合中包含目标权限编码
        if permission_code not in perms:
            # 通配符匹配：检查用户是否有上级资源的通配权限
            # 例如用户有 "user:*" 则自动拥有 "user:list"、"user:create" 等
            for p in perms:
                if p.endswith(":*") and permission_code.startswith(p[:-1]):
                    return True
            # 所有匹配规则均未通过，抛出权限不足异常
            raise ForbiddenError(f"缺少权限: {permission_code}")
        return True

    return Depends(_check)


def get_pagination(
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(20, ge=1, le=100, description="每页条数"),
) -> dict[str, int]:
    """
    分页参数依赖：从查询参数中提取 page 和 size。

    参数约束：
    - page: 页码，最小值为 1
    - size: 每页条数，范围 1～100，默认 20

    用法示例:
        @router.get("/list")
        async def list_data(pg: dict = Depends(get_pagination)):
            offset = (pg["page"] - 1) * pg["size"]
            ...

    :param page: 页码（≥1）
    :param size: 每页条数（1-100）
    :return: {"page": 页码, "size": 每页条数}
    """
    return {"page": page, "size": size}


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP。
    优先从代理头 X-Forwarded-For / X-Real-IP 中提取，
    兜底使用 request.client.host（直连场景）。
    """
    # X-Forwarded-For 格式: "client, proxy1, proxy2"，取第一个
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # X-Real-IP 通常只包含一个 IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # 直连场景
    return request.client.host if request.client else "unknown"
