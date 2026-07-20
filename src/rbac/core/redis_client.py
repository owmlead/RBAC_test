"""
Redis 客户端模块。
提供异步连接池和带降级的 Redis 操作封装。

设计要点：
- 使用 redis.asyncio 异步连接池，支持高并发
- 所有操作方法都带有降级策略：Redis 不可用时静默返回安全默认值
- 不阻塞业务主流程，Redis 仅作为缓存/加速层

提供的功能：
- 登录失败计数与重置（登录安全）
- Token 黑名单管理（注销机制）
"""
import os
os.environ.setdefault("REDIS_RESP3_DISABLE", "1")  # Redis 5.x 不支持 RESP3/HELLO
import redis.asyncio as aioredis
from src.rbac.core.config import setting

# Redis 连接池（全局单例）
_pool: aioredis.ConnectionPool | None = None
# 连接可用性标记：True 表示 Redis 已连接且可用
_available: bool = False


async def init_redis() -> None:
    """
    初始化 Redis 连接池。

    在 FastAPI lifespan 启动阶段调用，创建异步连接池并发送 ping 测试连通性。
    如果连接失败，_available 保持为 False，后续所有操作静默降级。

    :return: None
    """
    global _pool, _available
    try:
        # 创建异步连接池，最大连接数 10
        _pool = aioredis.ConnectionPool.from_url(setting.REDIS_URL, max_connections=10)
        # 发送 PING 命令测试连接是否可用（protocol="RESP2" 兼容 Redis 5.x）
        r = aioredis.Redis(connection_pool=_pool)
        await r.ping()
        _available = True  # 连接成功，标记可用
        print(f"[Redis] 连接成功: {setting.REDIS_URL}")
    except Exception as e:
        _available = False  # 连接失败，标记不可用，后续操作降级
        print(f"[Redis] 连接失败: {e}")


async def close_redis() -> None:
    """
    关闭 Redis 连接池。

    在 FastAPI lifespan 关闭阶段调用，断开所有连接并重置状态。

    :return: None
    """
    global _pool, _available
    if _pool:
        await _pool.disconnect()  # 断开连接池中所有连接
        _pool = None
    _available = False


def _client() -> aioredis.Redis:
    """
    获取 Redis 客户端实例。

    内部辅助函数，从连接池创建新的 Redis 客户端。
    必须在 init_redis() 成功之后调用，否则会因 _pool 为 None 而异常。
    强制使用 RESP2 协议以兼容 Redis 5.x。

    :return: Redis 异步客户端实例
    """
    return aioredis.Redis(connection_pool=_pool)


# ── 登录失败计数 ──

async def incr_login_failure(username: str, ttl_seconds: int) -> int:
    """
    递增登录失败次数。

    每次登录失败时调用，使用 Redis INCR 命令原子递增计数，
    并设置 key 的 TTL 为锁定窗口时长（过期自动清零）。

    :param username: 登录用户名，用于构造 Redis key
    :param ttl_seconds: key 的过期时间（秒），通常为锁定窗口时长
    :return: 当前失败次数；Redis 不可用时返回 -1（降级）
    """
    if not _available:
        return -1  # 降级：Redis 不可用时返回 -1
    # Redis key 格式：login_fail:<username>
    key = f"login_fail:{username}"
    r = _client()
    # INCR 原子递增（key 不存在时自动初始化为 0 再递增）
    count = await r.incr(key)
    # 设置/重置过期时间
    await r.expire(key, ttl_seconds)
    return count


async def get_login_failure_count(username: str) -> int:
    """
    获取当前登录失败次数。

    查询指定用户当前的连续登录失败计数。

    :param username: 登录用户名
    :return: 失败次数（0 表示无记录或已过期）；Redis 不可用时返回 -1
    """
    if not _available:
        return -1
    key = f"login_fail:{username}"
    r = _client()
    val = await r.get(key)
    return int(val) if val else 0


async def reset_login_failure(username: str) -> None:
    """
    登录成功后清除失败记录。

    用户登录成功后调用，重置该用户的登录失败计数器。
    防止用户因历史失败记录在下次登录时被误限。

    :param username: 登录用户名
    :return: None
    """
    if not _available:
        return  # 降级：Redis 不可用时静默跳过
    key = f"login_fail:{username}"
    r = _client()
    await r.delete(key)


# ── Token 黑名单 ──

async def add_to_blacklist(jti: str, ttl_seconds: int) -> None:
    """
    将 Token 加入黑名单。

    用户主动退出登录时调用，黑名单记录在 TTL 到期后自动清除，
    TTL 通常设置为 Token 的剩余有效时间（避免无限增长）。

    :param jti: Token 唯一标识符（JWT ID）
    :param ttl_seconds: 黑名单记录的存活时间（秒），与 Token 剩余有效期一致
    :return: None
    """
    if not _available:
        return  # 降级：Redis 不可用时跳过（注销不完全，但可接受）
    # Redis key 格式：bl:<jti>，bl 前缀表示 blacklist
    key = f"bl:{jti}"
    r = _client()
    # SETEX：设置值并指定过期时间，原子操作
    await r.setex(key, ttl_seconds, "1")


async def is_blacklisted(jti: str) -> bool:
    """
    检查 Token 是否在黑名单中。

    每次请求鉴权时调用，检查 Token 是否已被主动注销。
    采用宽松策略：Redis 不可用时返回 False（假设不在黑名单中），
    避免因 Redis 故障导致所有用户认证失败。

    :param jti: Token 唯一标识符
    :return: True 已注销 / False 未注销或 Redis 不可用
    """
    if not _available:
        return False  # 降级：不可用时放宽策略，不阻塞认证
    key = f"bl:{jti}"
    r = _client()
    # EXISTS 返回存在的 key 数量（0 或 1）
    return await r.exists(key) > 0


# ── 踢人下线 ──

async def set_kicked_out(user_id: int) -> None:
    """记录用户被强制下线的时间戳（token.iat < 此值 则拒绝）。"""
    if not _available:
        return
    key = f"kicked:{user_id}"
    r = _client()
    import time
    await r.set(key, str(int(time.time())))
    # 踢出记录保留 7 天（超过 token 最大有效期）
    await r.expire(key, 7 * 86400)


async def get_kicked_out_time(user_id: int) -> int | None:
    """获取用户被踢出的时间戳（秒），不可用时返回 None。"""
    if not _available:
        return None
    key = f"kicked:{user_id}"
    r = _client()
    val = await r.get(key)
    return int(val) if val else None


# ── 权限缓存 ──

_PERM_TTL = 30 * 60  # 权限缓存 30 分钟（与 access_token 有效期一致）


async def cache_user_permissions(user_id: int, perms: set[str]) -> None:
    """缓存用户的权限集合到 Redis Set。"""
    if not _available or not perms:
        return
    key = f"perm:{user_id}"
    r = _client()
    await r.delete(key)
    await r.sadd(key, *perms)
    await r.expire(key, _PERM_TTL)


async def get_cached_permissions(user_id: int) -> set[str] | None:
    """从 Redis 获取缓存的权限集合，不可用时返回 None。"""
    if not _available:
        return None
    key = f"perm:{user_id}"
    r = _client()
    members = await r.smembers(key)
    return {m.decode() for m in members} if members else None


async def invalidate_permission_cache(user_id: int) -> None:
    """清除指定用户的权限缓存。"""
    if not _available:
        return
    key = f"perm:{user_id}"
    r = _client()
    await r.delete(key)
