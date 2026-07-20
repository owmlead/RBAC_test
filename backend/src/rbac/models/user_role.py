"""
用户-角色关联表 ORM 模型。

user_role 是用户与角色之间的多对多中间表，
使用 (user_id, role_id) 复合主键，不设独立 ID。
删除用户或角色时，对应的关联记录级联删除（CASCADE）。
"""
from sqlalchemy import ForeignKey, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.rbac.db.base import Base


class UserRole(Base):
    """用户-角色关联表——记录用户被分配了哪些角色。"""

    __tablename__ = "user_role"

    # ---------- 联合主键（多对多关系核心） ----------
    # 注意：这里没有单独的 id 字段，直接使用 (user_id, role_id) 作为复合主键
    # 好处：天然保证同一用户不会被重复分配同一角色
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),  # 用户被删除时，关联记录自动清除
        primary_key=True,
        comment="用户ID（关联 user 表主键）"
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("role.id", ondelete="CASCADE"),  # 角色被删除时，关联记录自动清除
        primary_key=True,
        comment="角色ID（关联 role 表主键）"
    )

    # ---------- 表级约束 ----------
    __table_args__ = (
        # 反向查询索引：当需要查询"某个角色下有哪些用户"时，这个索引能大幅提速
        # 例如：查询"管理员"角色的所有成员
        Index('idx_role_id', 'role_id'),
    )

    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"
