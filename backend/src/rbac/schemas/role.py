"""
角色管理相关的 Pydantic 请求模型。

定义角色的 CRUD 操作（创建、更新、复制、移除用户等）的请求体结构。
包含 PermissionAssignment 子模型，用于角色-权限关联的数据传递。
"""
from pydantic import BaseModel, Field


class PermissionAssignment(BaseModel):
    """权限分配项——角色创建/更新时传递的单个权限绑定。

    每个绑定包含权限ID和是否拒绝标记：
    - is_deny=False（默认）：授予该权限
    - is_deny=True：明确拒绝该权限（拒绝优先于授予）

    典型用法：[
        {"permission_id": 1, "is_deny": false},  // 授予"用户管理"权限
        {"permission_id": 5, "is_deny": true},   // 但拒绝"删除用户"按钮
    ]
    """

    permission_id: int = Field(..., description="权限ID")
    is_deny: bool = Field(False, description="是否拒绝：False-授予，True-拒绝（拒绝优先级高于授予）")


class RoleCreateRequest(BaseModel):
    """新增角色请求——创建新角色时的数据结构。

    role_code 建议使用大写英文+下划线格式（如 CONTENT_EDITOR），
    全局唯一，创建时校验重复。
    """

    role_name: str = Field(..., min_length=1, max_length=50, description='角色名称（如「内容编辑」）')
    role_code: str = Field(..., min_length=1, max_length=50, description="角色编码（建议大写+下划线，全局唯一）")
    description: str | None = Field(None, max_length=255, description="角色描述（可选）")
    parent_role_ids: list[int] = Field(default_factory=list, description="继承的父角色ID列表（权限继承）")
    permissions: list[PermissionAssignment] = Field(default_factory=list, description="直接分配的权限列表")


class RoleUpdateRequest(BaseModel):
    """编辑角色请求——修改已有角色的信息。

    所有字段可选，仅更新提交的非 None 字段。
    注意：role_code 不可修改（唯一标识，修改会导致关联混乱）。
    """

    role_name: str | None = Field(None, max_length=50, description="新的角色名称")
    description: str | None = Field(None, max_length=255, description="新的角色描述")
    parent_role_ids: list[int] | None = Field(None, description="新的父角色ID列表（None=不修改，空列表=清空继承）")
    permissions: list[PermissionAssignment] | None = Field(None, description="新的权限列表（None=不修改，空列表=清空权限）")


class RoleCopyRequest(BaseModel):
    """复制角色请求——基于已有角色创建新角色。

    复制时需提供新的名称和编码，权限和父角色关系从源角色继承。
    """

    role_name: str = Field(..., max_length=50, description="新角色的名称")
    role_code: str = Field(..., max_length=50, description="新角色的编码（必须全局唯一）")


class RoleRemoveUsersRequest(BaseModel):
    """批量移除角色关联用户请求——将指定用户从当前角色中移除。

    不影响用户本身，仅删除 user_role 关联记录。
    """

    user_ids: list[int] = Field(..., description="要移除的用户ID列表")
