"""
角色-权限关联表 ORM 模型。

role_permission 是角色与权限之间的多对多中间表，
使用 (role_id, permission_id) 复合主键，不设独立 ID。
额外包含 is_deny 字段用于实现"拒绝优先"的权限控制策略：
- is_deny=False 表示授予该权限
- is_deny=True 表示拒绝该权限（拒绝优先级高于授予）
"""
from sqlalchemy import BigInteger, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.rbac.db.base import Base


class RolePermission(Base):
    """角色-权限关联表——记录角色被授予或拒绝了哪些权限。"""

    __tablename__ = "role_permission"

    # ---------- 联合主键（多对多关系核心） ----------
    # 注意：这里没有单独的 id 字段，直接使用 (role_id, permission_id) 作为复合主键
    # 好处：天然保证同一角色的同一权限不会被重复分配
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("role.id", ondelete="CASCADE"),  # 角色被删除时，关联记录自动清除
        primary_key=True,
        comment="角色ID（关联 role 表主键）"
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("permission.id", ondelete="CASCADE"),  # 权限被删除时，关联记录自动清除
        primary_key=True,
        comment="权限ID（关联 permission 表主键）"
    )

    # ---------- 权限遮盖字段 ----------
    # 核心设计：支持"拒绝优先"策略
    # - 当 is_deny=False（默认）：角色拥有该权限
    # - 当 is_deny=True：角色被明确拒绝该权限，即使其他角色授予了也会被拒绝
    # 典型场景：管理员拥有所有权限，但某个管理员角色被明确拒绝了"删除用户"按钮
    is_deny: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否拒绝：False-授予，True-拒绝（拒绝优先级高于授予）"
    )

    # ---------- 表级约束 ----------
    __table_args__ = (
        # 反向查询索引：当需要查询"某个权限分配给了哪些角色"时使用
        # 例如：审计某个敏感权限（如 DELETE 操作）被分配给了哪些角色
        Index('idx_permission_id', 'permission_id'),
    )

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id}, is_deny={self.is_deny})>"
