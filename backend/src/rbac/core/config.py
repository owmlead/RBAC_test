"""
应用配置模块。
优先级：环境变量 > .env 文件 > 默认值。
pydantic-settings 自动从项目根目录 .env 文件加载配置项。

使用方式：
    from src.rbac.core.config import setting
    print(setting.DATABASE_URL)
"""
from pydantic_settings import BaseSettings


class Setting(BaseSettings):
    """
    应用配置类。

    所有配置项通过类属性声明，pydantic-settings 自动从 .env 文件
    和环境变量中读取同名参数覆盖默认值。敏感项建议通过环境变量注入。

    配置分组：
    - 数据库连接
    - JWT 认证参数
    - 密码策略与登录安全
    - 验证码与速率限制
    - CORS 跨域白名单
    - Redis 连接
    """

    # 从 .env 文件加载配置，编码为 UTF-8，忽略未声明的额外字段
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── 数据库 ──
    # MySQL 异步连接字符串，使用 aiomysql 驱动
    DATABASE_URL: str = "mysql+aiomysql://root:root@localhost:3306/rbac_db"

    # ── 应用版本 ──
    APP_VERSION: str = "0.1.0"

    # ── 调试 ──
    # 开启后 FastAPI 自动重载，并输出详细错误信息
    DEBUG: bool = False

    # ── JWT ──
    JWT_SECRET_KEY: str = "rbac-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"  # 签名算法
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 访问令牌有效期（分钟）
    REFRESH_TOKEN_EXPIRE_DAYS: int = 1  # 刷新令牌有效期（天）

    # ── 密码策略 ──
    PASSWORD_MIN_LENGTH: int = 8  # 密码最小长度
    MAX_LOGIN_ATTEMPTS: int = 5  # 最大连续登录失败次数
    LOGIN_LOCK_MINUTES: int = 30  # 触发锁定后的锁定时长（分钟）

    # ── 验证码 ──
    # 连续登录失败达到该次数后要求输入验证码
    CAPTCHA_THRESHOLD: int = 3

    # ── CORS ──
    # 允许的前端域名，多个用逗号分隔
    CORS_ORIGINS: str = "http://localhost:5173"

    # ── Redis ──
    # Redis 连接地址，用于缓存、黑名单、登录失败计数等
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── 速率限制 ──
    # 格式为 "次数/时间单位"，如 "200/minute"
    RATE_LIMIT: str = "200/minute"


setting = Setting()
"""全局配置单例，供各模块导入使用。"""
