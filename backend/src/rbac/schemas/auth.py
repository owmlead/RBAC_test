"""
认证/授权相关的 Pydantic 请求模型。

定义登录、登出、踢人下线、权限校验等认证流程中的请求体结构。
所有模型均使用 Pydantic v2 的 Field 进行字段验证和文档描述。
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求——用户提交登录表单的数据结构。

    支持验证码模式：当系统开启验证码时，需同时提交 captcha_id 和 captcha；
    未开启时可留空。
    """

    username: str = Field(..., description="用户名（登录凭证）")
    password: str = Field(..., description="密码（明文，服务端进行 Bcrypt 比对）")
    captcha_id: str | None = Field(None, description="验证码 ID（图形验证码的唯一标识）")
    captcha: str | None = Field(None, description="验证码文本（用户输入的验证码内容）")


class KickOutRequest(BaseModel):
    """踢人下线请求——管理员强制使指定用户的所有 token 失效。

    实现方式：将该用户的 token 加入黑名单表，后续请求被拦截。
    """

    user_id: int = Field(..., description="要强制下线的用户ID")


class ChangePasswordRequest(BaseModel):
    """修改密码请求——当前用户修改自己的登录密码。

    必须提供当前密码进行身份验证，新密码需满足强度要求。
    """

    old_password: str = Field(..., description="当前密码（用于身份验证）")
    new_password: str = Field(..., description="新密码（需满足强度要求：至少8位，含字母/数字/特殊字符中至少两种）")


class CheckPermissionRequest(BaseModel):
    """权限校验请求——检查当前用户是否拥有指定权限。

    用于前端按钮/菜单的显隐控制，或后端接口的权限拦截。
    """

    permission_code: str = Field(..., description="要检查的权限编码，如 user:delete")
