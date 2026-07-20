"""
RBAC 权限管理系统 — 应用入口。
启动 FastAPI 服务，注册中间件、异常处理器和路由。

功能流程：
1. 初始化数据库连接并自动建表
2. 初始化 Redis 连接池
3. 注册 CORS 跨域中间件
4. 注册基于 IP 的滑动窗口速率限制中间件
5. 注册全局异常处理器（统一 JSON 响应格式）
6. 挂载 API 路由（/api 前缀）
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.rbac.api.router import router
from src.rbac.core.exceptions import register_exception_handlers
from src.rbac.core.redis_client import init_redis, close_redis
from src.rbac.db.session import init_db, engine
from src.rbac.core.config import setting


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    FastAPI 生命周期管理：启动时建表和 Redis 连接，关闭时释放资源。

    启动阶段（yield 之前）：
    - init_db(): 创建数据库引擎并自动建表（开发环境，生产请用 Alembic）
    - init_redis(): 建立 Redis 异步连接池并检测可用性

    关闭阶段（yield 之后）：
    - close_redis(): 断开 Redis 连接池
    - engine.dispose(): 释放数据库引擎所有连接
    """
    # ── 启动：初始化数据库表结构 ──
    await init_db()
    # ── 启动：初始化 Redis 连接 ──
    await init_redis()
    # ── 应用运行中 ──
    yield
    # ── 关闭：释放 Redis 资源 ──
    await close_redis()
    # ── 关闭：释放数据库连接池 ──
    await engine.dispose()


# 创建 FastAPI 应用实例
app = FastAPI(
    title="RBAC 权限管理系统",
    version=setting.APP_VERSION,
    lifespan=lifespan,
)


# ── CORS 中间件 ──
# 从配置中以逗号分隔读取允许的来源域名列表
origins = [o.strip() for o in setting.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # 允许携带 Cookie 等凭证
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # 限制允许的 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)


# ── 简易速率限制中间件（基于内存，按 IP 计数） ──
import time
from collections import defaultdict

# 以 IP 为 key，存储最近一次滑动窗口内的请求时间戳列表
_rate_records: dict[str, list[float]] = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    简单的滑动窗口速率限制，每个 IP 每分钟最多 200 次请求。

    实现原理：
    - 以客户端 IP 为粒度，记录每次请求的时间戳
    - 每次请求时清理 60 秒窗口外的过期时间戳
    - 窗口内时间戳数量达到上限时返回 429

    :param request: FastAPI Request 对象
    :param call_next: 下一个中间件或路由处理器
    :return: Response 对象
    """
    # 获取客户端 IP 地址
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # 滑动窗口大小（秒）

    # 解析速率限制配置，格式为 "次数/时间单位"（如 "200/minute"）
    try:
        limit = int(setting.RATE_LIMIT.split("/")[0])
    except (ValueError, AttributeError):
        limit = 200  # 解析失败时的安全默认值

    # 清理过期记录：保留窗口内的请求时间戳
    _rate_records[client_ip] = [
        t for t in _rate_records[client_ip] if now - t < window
    ]

    # 超出限制则拒绝请求
    if len(_rate_records[client_ip]) >= limit:
        return JSONResponse(
            status_code=429,
            content={"code": 429, "message": "请求过于频繁，请稍后重试", "data": None},
        )

    # 记录本次请求时间戳后放行
    _rate_records[client_ip].append(now)
    return await call_next(request)


# ── 全局异常处理 → 统一响应格式 ──
# 将 AppError 及其子类、以及未捕获的 Exception 统一转为 JSON 响应
register_exception_handlers(app)

# ── 注册路由 ──
# 所有 API 路由统一添加 /api 前缀
app.include_router(router, prefix="/api")


def main() -> None:
    """
    启动 Uvicorn 服务器。
    监听 0.0.0.0:8111，允许外部访问。
    """
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8111)


if __name__ == "__main__":
    main()
