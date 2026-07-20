"""
用户管理相关的 Pydantic 请求模型。

定义用户的 CRUD 操作（创建、更新、批量操作、分配角色等）的请求体结构。
包含字段级验证规则，如用户名长度限制、密码最小长度、性别取值范围等。
"""
from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    """创建用户请求——管理员新增用户时提交的数据。

    必填字段：username, password, real_name, gender
    可选字段：email, phone, avatar, role_ids（初始角色分配）
    """

    username: str = Field(..., min_length=4, max_length=20, description="用户名（登录凭证，4-20字符）")
    password: str = Field(..., min_length=8, description="初始密码（至少8位，存储时 Bcrypt 加密）")
    real_name: str = Field(..., min_length=1, max_length=50, description="真实姓名（用于界面显示）")
    gender: int = Field(..., ge=0, le=2, description="性别：0-未知，1-男，2-女")
    email: str | None = Field(None, max_length=100, description="邮箱（可选，用于通知和找回密码）")
    phone: str | None = Field(None, max_length=20, description="手机号（可选，用于短信验证）")
    avatar: str | None = Field(None, max_length=100, description="头像URL（可选）")
    role_ids: list[int] = Field(default_factory=list, description="初始分配的角色ID列表（创建时一并设置）")


class UserUpdateRequest(BaseModel):
    """更新用户请求——编辑用户信息时的数据结构。

    所有字段均为可选，仅更新提交的非 None 字段。
    注意：password 不在此处更新，走独立的 ResetPasswordRequest。
    """

    real_name: str = Field(None, max_length=50, description="真实姓名")
    email: str | None = Field(None, max_length=100, description="邮箱")
    phone: str | None = Field(None, max_length=20, description="手机号")
    status: int = Field(None, description="账户状态：1-启用，0-禁用")


class UserBatchStatusRequest(BaseModel):
    """批量启用/禁用用户请求——支持同时操作多个用户的状态。

    典型场景：批量封禁违规用户或批量恢复误封用户。
    """

    ids: list[int] = Field(..., description="要操作的用户ID列表")
    status: int = Field(..., description="目标状态：1-启用，0-禁用")


class BatchDeleteRequest(BaseModel):
    """批量删除请求——软删除多个用户（标记 deleted_at）。

    删除后数据保留，可通过数据库层面恢复。
    """

    ids: list[int] = Field(..., description="要删除的用户ID列表")


class ResetPasswordRequest(BaseModel):
    """重置密码请求——管理员为用户设置新密码。

    与修改密码不同，重置不需要旧密码验证。
    """

    new_password: str = Field(..., min_length=8, description="新密码（至少8位）")


class AssignRoleRequest(BaseModel):
    """分配角色请求——全量覆盖用户的角色列表。

    处理方式：先删除用户的所有角色关联，再插入新的角色列表。
    传入空列表表示清空用户的所有角色。
    """

    role_ids: list[int] = Field(default_factory=list, description="新的角色ID列表（全量替换，空列表=清空角色）")
