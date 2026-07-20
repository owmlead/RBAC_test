"""
认证鉴权接口层。
提供登录、刷新令牌、登出、强制下线和权限检查等 REST API。
"""
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.rbac.core.deps import get_client_ip, get_current_user, require_permission
from src.rbac.db.session import get_db
from src.rbac.schemas.auth import LoginRequest, KickOutRequest, CheckPermissionRequest, ChangePasswordRequest
from src.rbac.core.security import generate_captcha
from src.rbac.core.exceptions import UnauthorizedError
from src.rbac.service.auth import login, refresh, logout, kick_out, change_password, verify_token, check_permission

router = APIRouter()


@router.get(path="/verify")
async def verify_api(
        authorization: str = Header(..., description="Bearer <token>"),
        db=Depends(get_db),
) -> dict:
    """
    验证 token 有效性并返回用户信息（供外部服务调用）。
    外部后端拿到用户请求中的 token 后，调此接口确认身份并获取权限列表。

    :param authorization: Authorization 请求头（Bearer token）
    :param db: 数据库会话（自动注入）
    :return: {"user_id": ..., "username": ..., "real_name": ..., "roles": [...], "permissions": [...]}
    """
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误")
    data = await verify_token(db, authorization[len("Bearer "):])
    return {"code": 0, "message": "success", "data": data}


@router.get(path="/captcha")
async def get_captcha(_request: Request):
    """
    获取图形验证码
    :param _request: HTTP请求对象
    :return: {"code": 0, "data": {"captcha_id": ..., "captcha_image": ...}}
    """
    data = generate_captcha()
    return {
        "code": 0,
        "message": "success",
        "data": {
            "captcha_id": data["captcha_id"],
            "captcha_image": data["captcha_image"],
        },
    }


@router.post(path="/login")
async def login_api(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    用户登录，返回 JWT Token 和用户信息
    :param req: 登录请求体（username, password, captcha_id, captcha）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :return: {"access_token": ..., "refresh_token": ..., "user_info": {...}}
    """
    # 从 request 中提取客户端 IP，用于审计日志和登录失败追踪
    ip = get_client_ip(request)
    result = await login(db, req.username, req.password,
                         req.captcha_id, req.captcha, ip)
    return {"code": 0, "message": "success", "data": result}


@router.post(path="/refresh")
async def refresh_api(
        authorization: str = Header(..., description="Bearer <refresh_token>"),
        db=Depends(get_db),
):
    """
    刷新令牌：用 refresh_token 换取新的 access_token 和 refresh_token
    :param authorization: Authorization 请求头（Bearer refresh_token）
    :param db: 数据库会话（自动注入）
    :return: {"access_token": ..., "refresh_token": ...}
    """
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误")
    # 去掉 "Bearer " 前缀，提取实际 token 字符串
    result = await refresh(db, authorization[len("Bearer "):])
    return {"code": 0, "message": "success", "data": result}


@router.post(path="/logout")
async def logout_api(
        request: Request,
        authorization: str = Header(..., description="Bearer <access_token>"),
        db=Depends(get_db),
):
    """
    用户登出：将当前 access_token 加入黑名单使其失效
    :param authorization: Authorization 请求头（Bearer access_token）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :return: {"code": 0, "message": "已登出"}
    """
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误")
    ip = get_client_ip(request)
    await logout(db, authorization[len("Bearer "):], ip)
    return {"code": 0, "message": "已登出", "data": None}


@router.post(path="/kick-out")
async def kick_out_api(
        req: KickOutRequest,
        request: Request,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
        _: bool = require_permission("user:kick"),
):
    """
    管理员强制下线指定用户（使目标用户权限缓存失效）
    :param req: 踢人请求体（user_id）
    :param request: HTTP请求对象
    :param current_user: 当前登录用户（自动注入）
    :param db: 数据库会话（自动注入）
    :param _: 权限校验（需要 user:kick 权限）
    :return: {"code": 0, "message": "用户已强制下线"}
    """
    ip = get_client_ip(request)
    await kick_out(db, current_user, req.user_id, ip)
    return {"code": 0, "message": "用户已强制下线", "data": None}


@router.put(path="/change-password")
async def change_password_api(
        req: ChangePasswordRequest,
        request: Request,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
) -> dict:
    """
    当前用户修改自己的登录密码（需验证旧密码）。
    修改成功后所有已登录设备将被强制下线，需用新密码重新登录。

    :param req: 请求体（old_password, new_password）
    :param request: HTTP请求对象
    :param current_user: 当前登录用户（自动注入）
    :param db: 数据库会话（自动注入）
    :return: {"code": 0, "message": "密码修改成功，请重新登录"}
    """
    ip = get_client_ip(request)
    await change_password(db, current_user, req.old_password, req.new_password, ip)
    return {"code": 0, "message": "密码修改成功，请重新登录", "data": None}


@router.post(path="/check-permission")
async def check_permission_api(
        req: CheckPermissionRequest,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
):
    """
    鉴权检查：当前用户是否拥有指定权限
    :param req: 请求体（permission_code）
    :param current_user: 当前登录用户（自动注入）
    :param db: 数据库会话（自动注入）
    :return: {"code": 0, "data": {"allowed": true/false}}
    """
    result = await check_permission(db, current_user, req.permission_code)
    return {"code": 0, "message": "success", "data": result}
