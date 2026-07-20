"""
权限管理相关的 Pydantic 请求模型。

定义权限资源的 CRUD 操作（创建、更新、拖拽排序等）的请求体结构。
权限资源分为菜单（MENU）和按钮（BUTTON）两种类型。
"""
from pydantic import BaseModel, Field


class PermissionCreateRequest(BaseModel):
    """创建权限请求——新增菜单或按钮资源。

    区分菜单和按钮：
    - MENU（菜单）：需设置 name, code, path（可选）, icon（可选）
    - BUTTON（按钮）：需设置 name, code, api_paths（可选，关联后端API）
    两者的 type 字段决定了前端渲染方式。
    """

    name: str = Field(..., min_length=1, max_length=50, description='资源名称（如「用户管理」、「新增用户」）')
    code: str = Field(..., min_length=1, max_length=100, description="权限编码（全局唯一，建议格式：模块:操作）")
    type: str = Field(..., description="资源类型：MENU-菜单（侧边栏），BUTTON-按钮（页面内操作）")
    parent_id: int | None = Field(None, description="父资源ID（NULL=顶级菜单，非NULL=子菜单/子按钮）")
    path: str | None = Field(None, max_length=200, description="前端路由路径（菜单专用，如 /system/user）")
    icon: str | None = Field(None, max_length=50, description="图标标识（菜单专用）")
    sort: int = Field(0, description="排序号（同级节点显示顺序，值越小越靠前）")
    status: int = Field(1, description="状态：1-启用，0-禁用")
    api_paths: list[str] | None = Field(None, description="关联的API路径列表（按钮专用），如 [\"POST /api/v1/users\"]")


class PermissionUpdateRequest(BaseModel):
    """编辑权限资源请求——修改已有权限的属性。

    code 不可修改（唯一标识），其余字段均为可选，仅更新提交的非 None 字段。
    """

    name: str | None = Field(None, min_length=1, max_length=50, description="新的资源名称")
    parent_id: int | None = Field(None, description="新的父资源ID（移动节点到其他父节点下）")
    path: str | None = Field(None, max_length=200, description="新的前端路由路径")
    icon: str | None = Field(None, max_length=50, description="新的图标标识")
    sort: int | None = Field(None, description="新的排序号")
    status: int | None = Field(None, description="新的状态：1-启用，0-禁用")
    api_paths: list[str] | None = Field(None, description="新的API路径列表（None=不修改，空列表=清空）")


class PermissionSortRequest(BaseModel):
    """拖拽排序请求——重新排列同级节点的显示顺序。

    sorted_ids 按新顺序排列，后端将其映射为 sort 字段值（1,2,3...）。
    例如：sorted_ids=[3,1,2] 表示 id=3 排第1，id=1 排第2，id=2 排第3。
    """

    sorted_ids: list[int] = Field(..., description="按新顺序排列的权限ID列表，索引对应新的排序号")
