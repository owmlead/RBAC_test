"""
用户 ORM 模型。

user 表是 RBAC 系统的核心实体表，存储所有用户的基本信息、
登录凭证、联系方式、审计字段和软删除标记。
通过 user_role 关联表与 role 建立多对多关系。

字段说明：
    id              bigint      主键ID（自增）
    username        varchar(50) 用户名（登录凭证，与 deleted_at 组成联合唯一键）
    password        varchar(255) Bcrypt 加密密码（不可逆，验证时使用哈希比对）
    real_name       varchar(50) 真实姓名（用于界面显示）
    gender          tinyint     性别：0-未知，1-男，2-女
    email           varchar(100) 邮箱（与 deleted_at 组成联合唯一键，用于找回密码/通知）
    phone           varchar(20)  手机号（与 deleted_at 组成联合唯一键，用于短信验证）
    avatar          varchar(255) 头像 URL
    status          tinyint      账户状态：True-启用，False-禁用（管理员手动管控）
    remark          varchar(500) 备注信息（运营/管理员标注）
    last_login_time datetime     最近一次登录时间（用于运营分析和安全审计）
    last_login_ip   varchar(50)  最近一次登录 IP（用于安全审计）
    deleted_at      datetime     软删除时间（NULL=正常，非NULL=已注销/已删除）
    create_time     datetime     创建时间（自动设置）
    update_time     datetime     更新时间（自动更新）
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, UniqueConstraint, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.rbac.db.base import Base


class User(Base):
    """用户模型——RBAC 系统的核心实体，存储用户所有信息。

    设计要点：
    - 软删除：不物理删除数据，通过 deleted_at 标记删除，保留数据可恢复
    - 唯一约束：username/email/phone 分别与 deleted_at 组成联合唯一键，
      允许已删除用户使用相同的用户名/邮箱/手机号重新注册
    - 密码安全：使用 Bcrypt 单向加密，数据库不存明文
    """

    __tablename__ = "user"

    # ---------- 核心字段 ----------
    # 主键，自增 BigInteger，支持海量用户
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    # 登录凭证，与 deleted_at 组成联合唯一键
    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="用户名（登录凭证）")
    # Bcrypt 加密后的密码哈希，验证时用 bcrypt 比对
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="Bcrypt 加密密码")
    # 界面展示名称，如"张三"
    real_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="真实姓名（界面显示）")
    # 性别枚举，0=未知（默认），1=男，2=女
    gender: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="性别 0-未知 1-男 2-女")

    # ---------- 联系方式 ----------
    # 邮箱，用于找回密码和系统通知
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="邮箱（找回密码/通知）")
    # 手机号，用于短信验证码登录
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="手机号（短信验证）")
    # 头像图片地址，支持远程 URL
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="头像URL")

    # ---------- 状态与备注 ----------
    # 账户启停开关，管理员可禁用违规账户
    status: Mapped[bool] = mapped_column(Boolean, default=True, comment="状态 True-启用 False-禁用")
    # 运营备注，如"该用户为 VIP 客户"
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注（运营/管理员标注）")

    # ---------- 登录审计 ----------
    # 最近登录时间，用于分析用户活跃度
    last_login_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近登录时间")
    # 最近登录 IP，用于安全风控（异地登录检测等）
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="最近登录IP")

    # ---------- 软删除（关键） ----------
    # NULL=正常用户，非NULL=已删除用户
    # 软删除保护数据完整性：关联的角色、日志等不会因删除用户而丢失
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="软删除时间(NULL=未删除)")

    # ---------- 自动时间戳 ----------
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,  # 注意：这里传函数引用，不要加括号，否则会是固定时间
        comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,  # 每次 UPDATE 自动刷新为当前时间
        comment="更新时间"
    )

    # ---------- ORM 关系 ----------
    # 多对多关系：用户拥有的角色
    # lazy="selectin" 比默认的 lazy="select" 更高效——一次性 JOIN 查出所有关联角色，避免 N+1 查询
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_role",  # 关联表名
        lazy="selectin",
        back_populates="users"  # 双向关联，反向在 Role 模型中定义
    )

    # ---------- 表级约束（索引/唯一键） ----------
    __table_args__ = (
        # 1. 核心唯一索引：允许删除后同名重新注册
        #    实现方式：username + deleted_at 联合唯一，已删除用户不同 deleted_at 可重复注册
        UniqueConstraint('username', 'deleted_at', name='uk_username_deleted'),
        # 2. 邮箱/手机号同理：防止同一邮箱绑定多个活跃账户，但允许注销后重新注册
        UniqueConstraint('email', 'deleted_at', name='uk_email_deleted'),
        UniqueConstraint('phone', 'deleted_at', name='uk_phone_deleted'),
        # 3. 普通索引：加速"查询所有启用且未删除的用户"这类常见筛选
        Index('idx_status_deleted', 'status', 'deleted_at'),
        # 4. 登录时间索引：运营看板按最近登录时间排序时加速
        Index('idx_last_login', 'last_login_time'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', real_name='{self.real_name}')>"
