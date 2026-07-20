"""
角色 ORM 模型。

role 表存储 RBAC 系统的角色定义，角色是权限的集合，通过
role_permission 关联表与 permission 建立多对多关系，
通过 user_role 关联表与 user 建立多对多关系。

角色支持继承：parent_role_ids 用 JSON 数组存储父角色 ID 列表，
子角色自动继承父角色的所有权限（前端/后端递归计算）。

字段说明：
    id              bigint       主键ID（自增）
    role_name       varchar(50)  角色名称（如"超级管理员"、"普通用户"）
    role_code       varchar(50)  角色编码（如"SUPER_ADMIN"，全局唯一）
    description     varchar(255) 角色描述
    status          tinyint      状态：True-启用，False-禁用
    parent_role_ids json        父角色ID列表（JSON数组），如 [1, 2]，实现角色继承
    is_system       tinyint      是否系统内置：True-内置（不可删除），False-自定义（可删除）
    sort            int          排序号（用于前端列表展示顺序）
    create_time     datetime     创建时间
    update_time     datetime     更新时间
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.rbac.db.base import Base


class Role(Base):
    """角色模型——RBAC 系统的权限分组核心。

    设计要点：
    - 角色编码（role_code）全局唯一，用于后端代码中的权限判断（@require_role("ADMIN")）
    - 角色继承：通过 parent_role_ids JSON 字段实现，子角色自动拥有父角色的所有权限
      继承关系由前端或业务层递归展开，数据库仅存储关系
    - 系统保护：is_system=True 的角色不可删除，防止误删核心角色
    - 排序：sort 字段控制前端列表的展示顺序
    """

    __tablename__ = "role"

    # ---------- 核心字段 ----------
    # 自增主键
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    # 角色显示名称，如"超级管理员"、"内容编辑"
    role_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="角色名称（界面显示）")
    # 角色编码，全局唯一，用于代码中的权限标识
    # 建议格式：大写英文+下划线，如 SUPER_ADMIN、CONTENT_EDITOR
    role_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="角色编码（全局唯一标识）")
    # 角色描述，说明该角色的职责和权限范围
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="角色描述")

    # ---------- 状态 ----------
    # 禁用角色后，拥有该角色的用户将不获得对应权限
    # 用于临时冻结某个角色而不删除
    status: Mapped[bool] = mapped_column(Boolean, default=True, comment="状态 True-启用 False-禁用")

    # ---------- 继承（JSON存储父角色ID列表） ----------
    # 使用 List[int] 类型提示，SQLAlchemy 会自动处理 JSON 序列化/反序列化
    # 例如：[1, 3] 表示该角色继承自 id=1 和 id=3 的角色
    # 权限计算时递归展开：自身权限 ∪ 所有父角色权限（去重，拒绝优先）
    parent_role_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON, nullable=True, comment="父角色ID列表（JSON数组），实现角色权限继承"
    )

    # ---------- 系统保护 ----------
    # 系统内置角色（如"超级管理员"）标记为 True，前端不显示删除按钮
    # 自定义角色可自由删除
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="系统内置角色 True=不可删除 False=可删除"
    )
    # 排序号，值越小越靠前，用于前端角色列表的展示顺序
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序号（前端展示顺序）")

    # ---------- 时间戳 ----------
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,  # 每次更新自动刷新
        comment="更新时间"
    )

    # ---------- ORM 关系 ----------
    # 多对多反向：拥有该角色的用户列表
    # 通过 user_role 中间表关联，back_populates 指向 User.roles
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_role",
        lazy="selectin",  # 一次 JOIN 查出所有关联用户，避免 N+1
        back_populates="roles"
    )

    # 多对多：该角色拥有的权限列表
    # 通过 role_permission 中间表关联，back_populates 指向 Permission.roles
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary="role_permission",
        lazy="selectin",
        back_populates="roles"
    )

    # ---------- 表级约束（索引） ----------
    __table_args__ = (
        # 加速按状态筛选角色（如查询所有启用角色）
        Index('idx_status', 'status'),
        # 加速按排序号排序（前端列表展示）
        Index('idx_sort', 'sort'),
    )

    def __repr__(self):
        return f"<Role(id={self.id}, role_code='{self.role_code}', role_name='{self.role_name}')>"
