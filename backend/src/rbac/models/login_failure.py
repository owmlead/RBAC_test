"""
登录失败记录模型。

替代内存字典，持久化到数据库，服务重启后锁定状态不丢失。
每条记录以 (username, ip) 维度统计失败次数，达到阈值后锁定账户。
锁定到期后自动解禁（由登录逻辑判断 locked_until 是否过期）。
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from src.rbac.db.base import Base


class LoginFailure(Base):
    """登录失败记录表——按用户名+IP 维度记录失败次数与锁定状态。

    锁定策略：
    1. 同一 (username, ip) 在窗口期内连续失败 N 次后触发锁定
    2. locked_until 记录锁定截止时间，期间禁止该 (username, ip) 登录
    3. 锁定到期后或登录成功后，失败计数重置
    """

    __tablename__ = "login_failure"

    # 自增主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 尝试登录的用户名，建立索引用于快速查找
    # 注意：这里是尝试登录时输入的用户名，即使账户不存在也会记录
    username: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="尝试登录的用户名（含不存在的账户）"
    )

    # 登录来源 IP，与 username 共同组成锁定维度
    # 同一 IP 的不同用户名互不影响；同一用户名的不同 IP 也互不影响
    ip: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="登录来源IP地址"
    )

    # 当前连续失败次数，每次失败 +1，成功后或锁定到期后重置为 0
    fail_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="连续失败次数"
    )

    # 锁定截止时间，NULL 表示未锁定
    # 登录验证时检查：若当前时间 < locked_until，则拒绝登录
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="锁定截止时间（NULL=未锁定）"
    )

    # 首次失败时间，用于审计和窗口期计算
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="首次失败时间"
    )

    # 最近失败时间，每次失败时更新，用于追踪最后攻击时间
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="最近失败时间"
    )
