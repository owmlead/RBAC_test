"""
数据库会话管理模块。

核心职责：
- 创建异步 SQLAlchemy 引擎和会话工厂
- 启动时自动建表（开发/测试环境）
- 为每个 HTTP 请求提供独立的数据库会话（通过 FastAPI 依赖注入）

会话生命周期：
1. 请求进入 → get_db() 创建会话
2. 路由处理中 → 使用注入的会话执行 CRUD
3. 请求成功 → 自动 commit
4. 请求异常 → 自动 rollback 并向上传播异常
5. 请求结束 → 会话关闭并归还连接池
"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from typing import AsyncGenerator
from src.rbac.core.config import setting
from src.rbac.db.base import Base
# 确保所有 ORM 模型在建表前被 SQLAlchemy 注册到 Base.metadata
# noqa 注释防止 linter 报 "未使用导入" 的警告
import src.rbac.models.user  # noqa
import src.rbac.models.role  # noqa
import src.rbac.models.permission  # noqa
import src.rbac.models.user_role  # noqa
import src.rbac.models.role_permission  # noqa
import src.rbac.models.token_blacklist  # noqa
import src.rbac.models.logs  # noqa
import src.rbac.models.login_failure  # noqa


# 数据库连接地址（从配置中读取）
DB_URL = setting.DATABASE_URL


# 创建异步数据库引擎
engine = create_async_engine(
    DB_URL,
    pool_size=20,       # 连接池大小：最大保持 20 个空闲连接
    max_overflow=10,    # 池满后允许额外创建的连接数（峰值可达 30）
    pool_pre_ping=True, # 连接前发送 ping 检测可用性，避免使用已断开的连接
    pool_recycle=3600,  # 连接回收时间（秒），超过 1 小时强制回收
)

# 异步会话工厂：每次调用创建新的 AsyncSession 实例
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=True,        # 查询前自动 flush 挂起的变更，保持数据一致性
    expire_on_commit=False, # 提交后不使对象过期，避免异步下隐式懒加载
)


async def init_db() -> None:
    """
    异步建表（仅开发/测试环境，生产请用 Alembic 迁移）。

    从 Base.metadata 读取所有已注册的 ORM 模型，
    在数据库中创建对应的表结构（如果表已存在则跳过）。

    :return: None
    """
    async with engine.begin() as conn:
        # run_sync 在异步连接上同步执行 metadata.create_all
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：每次请求提供一个独立的数据库会话。

    会话管理策略：
    - 请求处理成功 → 自动提交事务
    - 请求处理中抛出异常 → 自动回滚事务，异常继续向上传播
    - 无论成功或失败 → 会话在上下文退出时自动关闭

    用法示例:
        @router.get("/users")
        async def list_users(db = Depends(get_db)):
            result = await db.execute(select(User))
            ...

    :yield: AsyncSession 实例
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session  # 交给请求处理器
            # 请求处理成功，提交事务
            await session.commit()
        except Exception:
            # 请求处理失败，回滚事务
            await session.rollback()
            raise  # 重新抛出异常，让上层异常处理器捕获
