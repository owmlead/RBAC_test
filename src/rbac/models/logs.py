"""
审计日志模型。

对应 logs 表，只增不删（append-only），记录系统中所有关键操作。
每条日志包含操作人、操作类型、所属模块、操作描述、请求参数（脱敏后）
和操作结果，用于安全审计、问题溯源和操作回溯。

日志策略：
    - 只增不删：日志数据不可篡改或删除，确保审计完整性
    - 请求参数脱敏：敏感字段（如密码）在写入前由业务层脱敏处理
    - 用户快照：username 存储操作时的用户名快照，即使用户后被删除也能追溯
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.rbac.db.base import Base


class Logs(Base):
    """系统审计日志表——记录所有关键操作，只增不删。

    使用方式：
    1. 在各 API 端点处理完成后调用 create_audit_log() 写入
    2. 查询时按时间范围、用户、操作类型等维度筛选
    3. 长期存储策略：可定期将旧日志归档到其他存储
    """

    __tablename__ = "logs"

    # 自增主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 操作用户ID，可为 NULL（如未登录的登录尝试）
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="操作用户ID（NULL=未登录操作）")

    # 操作时用户名的快照，即使用户后续被删除/改名也能追溯
    # 不同于关联 user 表查实时用户名，快照保留了操作发生时的真实信息
    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作时用户名快照（防用户变更后无法追溯）")

    # 操作类型枚举，用于日志分类筛选
    # 常见值：LOGIN, LOGOUT, CREATE, UPDATE, DELETE, QUERY, BATCH, ASSIGN 等
    operation: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="操作类型: LOGIN, CREATE, UPDATE, DELETE 等"
    )

    # 操作所属模块，用于按功能区域筛选日志
    # 常见值：AUTH（认证）, USER（用户管理）, ROLE（角色管理）, PERMISSION（权限管理）
    module: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="操作模块: USER, ROLE, PERMISSION, AUTH 等"
    )

    # 操作描述，人类可读的操作说明，如"管理员 admin 创建了用户 zhangsan"
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="操作描述（人类可读）"
    )

    # 请求参数 JSON，已由业务层脱敏处理（密码等敏感字段替换为 ***）
    # 用于问题排查时还原操作上下文
    request_params: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="请求参数JSON（脱敏后，用于溯源）"
    )

    # 操作来源 IP，用于安全审计和异常检测（如异地操作告警）
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="操作来源IP地址")

    # 操作结果，SUCCESS=成功，FAIL=失败
    # 失败操作也需要记录，用于发现攻击尝试或系统异常
    result: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="操作结果: SUCCESS-成功, FAIL-失败"
    )

    # 操作时间，日志的核心时间戳，用于按时间范围查询和排序
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="操作时间（日志时间戳）"
    )
