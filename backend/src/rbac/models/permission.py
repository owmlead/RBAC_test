"""
权限表 ORM 模型。

permission 表存储 RBAC 系统的权限资源定义，支持菜单（MENU）和按钮（BUTTON）
两种资源类型，通过 parent_id 自关联形成树形层级结构。通过
role_permission 关联表与 role 建立多对多关系。

树形结构说明：
    - parent_id=NULL 的节点为根菜单
    - 菜单（MENU）节点可有子菜单或子按钮
    - 按钮（BUTTON）节点通常是叶子节点，关联具体的 API 路径

字段说明：
    id          bigint       主键ID（自增）
    name        varchar(50)  资源名称（如"用户管理"、"新增用户"）
    code        varchar(100) 权限编码（如 user:list、user:create），全局唯一
    type        varchar(10)  资源类型：MENU-菜单（展示在侧边栏），BUTTON-按钮（页面内操作）
    parent_id   bigint       父资源ID，NULL 表示根节点（顶级菜单）
    path        varchar(200) 前端路由路径（菜单专用，如 /system/user）
    icon        varchar(50)  图标标识（菜单专用，如 user、setting）
    sort        int          排序号（同级节点的显示顺序，值越小越靠前）
    status      tinyint      状态：True-启用，False-禁用
    api_paths   json         关联的API路径列表（按钮专用），如 ["POST /api/v1/users", "GET /api/v1/users"]
    create_time datetime     创建时间
    update_time datetime     更新时间
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, BigInteger, Integer, Boolean, DateTime, JSON, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.rbac.db.base import Base


class Permission(Base):
    """权限模型——RBAC 系统的权限资源定义，支持菜单/按钮树形结构。

    设计要点：
    - 两种资源类型：MENU（侧边栏菜单项）和 BUTTON（页面内的操作按钮）
    - 树形自关联：通过 parent_id 外键指向自身，形成菜单->子菜单->按钮的层级
    - 菜单路由：菜单类型通过 path 字段指定前端路由，icon 指定显示图标
    - API 绑定：按钮类型通过 api_paths JSON 数组关联后端 API，用于接口级鉴权
    - 排序：sort 字段控制同级节点的展示顺序，支持拖拽排序
    """

    __tablename__ = "permission"

    # ---------- 核心字段 ----------
    # 主键，自增 BigInteger
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )
    # 资源名称，如"用户管理"、"新增用户"按钮
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="资源名称（界面显示）"
    )
    # 权限编码，全局唯一，格式建议：模块:操作，如 user:list、user:create、user:delete
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="权限编码（全局唯一，如 user:create）"
    )
    # 资源类型，MENU=侧边栏菜单项，BUTTON=页面操作按钮
    type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="资源类型：MENU-菜单（侧边栏显示），BUTTON-按钮（页面内操作）"
    )

    # ---------- 树形结构 ----------
    # 父节点ID，自关联外键，删除父节点时子节点 parent_id 设为 NULL
    # NULL 表示该节点为根菜单（顶级导航项）
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("permission.id", ondelete="SET NULL"),
        nullable=True,
        comment="父资源ID（NULL=根节点，自关联形成菜单树）"
    )
    # 前端 Vue Router 路径，仅 MENU 类型使用
    # 例如：/system/user 对应用户管理页面
    path: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="前端路由路径（菜单专用，如 /system/user）"
    )
    # 图标名称，对应前端图标库的图标标识，仅 MENU 类型使用
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="图标标识（菜单专用，如 user、setting）"
    )
    # 排序号，同级节点按此字段升序排列，支持拖拽排序
    sort: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序号（同级节点显示顺序，值越小越靠前）"
    )

    # ---------- 状态 ----------
    # 禁用后该权限失效，对应菜单不显示、按钮不渲染、API 拒绝访问
    status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="状态：True-启用，False-禁用"
    )

    # ---------- API路径（按钮专用） ----------
    # JSON 数组，存储按钮关联的 API 端点
    # 例如：["POST /api/v1/users", "GET /api/v1/users/:id", "DELETE /api/v1/users"]
    # 鉴权时匹配请求的 method+path 是否在授权列表中
    api_paths: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="关联的API路径列表（按钮专用），如 [\"POST /api/v1/users\"]"
    )

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
    # 多对多反向：拥有该权限的角色列表
    # 通过 role_permission 中间表关联
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="role_permission",
        lazy="selectin",
        back_populates="permissions"
    )

    # ---------- 自关联树形关系（菜单/按钮层级） ----------
    # 父节点：指向自身的 Permission 对象
    # remote_side=[id] 是关键参数，告诉 SQLAlchemy 外键指向自身的主键
    parent: Mapped[Optional["Permission"]] = relationship(
        "Permission",
        remote_side=[id],  # 指向自身主键，形成自引用
        back_populates="children"
    )
    # 子节点列表：该节点下的所有子菜单/子按钮
    children: Mapped[List["Permission"]] = relationship(
        "Permission",
        back_populates="parent"
    )

    # ---------- 表级约束 ----------
    __table_args__ = (
        # 加速按父节点查询子节点（构建菜单树时频繁使用）
        Index('idx_parent_id', 'parent_id'),
        # 加速按排序号排序（同级节点排序）
        Index('idx_sort', 'sort'),
        # 加速按状态筛选（查询所有启用权限）
        Index('idx_status', 'status'),
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, code='{self.code}', name='{self.name}', type='{self.type}')>"
