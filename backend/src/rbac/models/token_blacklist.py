"""
JWT Token 黑名单模型。

对应 token_blacklist 表，存储已失效的 JWT 的 jti（JWT ID）。
当用户主动登出或管理员踢人下线时，将 token 的 jti 加入此表，
后续请求即使 token 未过期也会被拦截。expire_time 字段用于
定时清理已自然过期的记录，防止表无限增长。
"""

from datetime import datetime

from sqlalchemy import DateTime, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.rbac.db.base import Base


class TokenBlacklist(Base):
    """Token 黑名单表——存储已失效 JWT 的 jti。

    工作机制：
    1. 用户登出/被踢下线时，将当前 token 的 jti 和过期时间写入此表
    2. 后续请求在验证 token 时，先查此表是否存在对应 jti
    3. 定时任务根据 expire_time 清理已过期的记录，避免表膨胀
    """

    __tablename__ = "token_blacklist"

    # 自增主键，仅用于记录标识
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # JWT 的唯一标识符（jti），由签发 token 时生成
    # 每个 token 的 jti 全局唯一，用于精确失效某个 token
    jti: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="JWT 唯一标识符（jti），全局唯一"
    )

    # Token 的原始过期时间戳，用于定时任务清理
    # 当 expire_time 已过期时，该记录已无存在意义——token 本身也不会被接受了
    expire_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="Token 原始过期时间，用于定时清理已失效记录"
    )

    # 加入黑名单的时间，用于审计追踪
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="加入黑名单时间（登出/踢人时间）"
    )
