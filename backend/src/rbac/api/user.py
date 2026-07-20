"""
用户管理接口层。
提供用户 CRUD、批量操作、角色分配和权限查询等 REST API。
"""
from fastapi import APIRouter, Depends, Request

from src.rbac.core.deps import get_client_ip, get_pagination, require_permission, get_current_user
from src.rbac.core.exceptions import NotFoundError
from src.rbac.crud.user import UserRepository
from src.rbac.db.session import get_db
from src.rbac.schemas.user import UserCreateRequest, UserUpdateRequest, UserBatchStatusRequest, BatchDeleteRequest, \
    ResetPasswordRequest, AssignRoleRequest
from src.rbac.service.checker import get_user_permissions
from src.rbac.service.user import create_user, update_user, delete_user, batch_status, batch_delete, assign_roles, \
    update_user_roles, reset_user_password

router = APIRouter()


@router.get("/")
async def list_users(
        keyword: str | None = None,
        status: int | None = None,
        pagination=Depends(get_pagination),
        db=Depends(get_db),
        _: bool = require_permission("user:list"),
) -> dict:
    """
    分页查询用户列表，支持关键字和状态筛选
    :param keyword: 搜索关键字，可选
    :param status: 用户状态筛选，可选
    :param pagination: 分页参数（自动注入，含page和size）
    :param db: 数据库会话（自动注入）
    :param _: 权限校验（需要 user:list 权限）
    :return: {"total": 总数, "page": 页码, "size": 每页条数, "list": [...]}
    """
    user_crud = UserRepository(db)
    users, total = await user_crud.get_users_paginated(keyword, status,
                                                       pagination["page"], pagination["size"])

    # 构建响应列表，对时间字段做 isoformat 序列化以避免 JSON 序列化报错
    return {"code": 0, "message": "success",
            "data": {"total": total, "page": pagination["page"],
                     "size": pagination["size"],
                     "list": [{"id": u.id, "username": u.username, "real_name": u.real_name,
                               "email": u.email, "phone": u.phone, "status": u.status,
                               "last_login_time": u.last_login_time.isoformat() if u.last_login_time else None,
                               "create_time": u.create_time.isoformat() if u.create_time else None}
                              for u in users]}}


@router.post("/")
async def create_user_api(
        req: UserCreateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:create")
) -> dict:
    """
    新建用户
    :param req: 创建用户请求体（username, password, real_name, gender, email等）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:create 权限）
    :return: {"code": 0, "data": {"id": 新用户ID}}
    """
    ip = get_client_ip(request)
    result = await create_user(db, req.username, req.password, req.real_name, req.gender,
                               req.email, req.phone, req.avatar, req.role_ids,
                               current_user.id, current_user.username, ip)
    return {"code": 0, "message": "用户创建成功", "data": result}


# ── 批量操作（必须在 /{user_id} 前注册以避路由冲突）──

@router.put("/batch-status")
async def batch_status_api(
        req: UserBatchStatusRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:update")
) -> dict:
    """
    批量启用/禁用用户
    :param req: 请求体（ids, status）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:update 权限）
    :return: {"code": 0, "message": "用户操作成功"}
    """
    # 获取客户端IP用于审计日志记录
    ip = get_client_ip(request)
    await batch_status(db, req.ids, req.status, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "用户操作成功", "data": None}


@router.delete("/batch")
async def batch_delete_api(
        req: BatchDeleteRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:delete")
) -> dict:
    """
    批量逻辑删除用户
    :param req: 请求体（ids）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:delete 权限）
    :return: {"code": 0, "message": "批量删除成功"}
    """
    ip = get_client_ip(request)
    await batch_delete(db, req.ids, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "批量删除成功", "data": None}


# ── /{user_id} 参数化路径 ──

@router.get("/{user_id}")
async def get_user(
        user_id: int,
        db=Depends(get_db),
        _: bool = require_permission("user:detail"),
) -> dict:
    """
    通过用户ID查询用户详情（含角色和权限列表）
    :param user_id: 用户ID
    :param db: 数据库会话（自动注入）
    :param _: 权限校验（需要 user:detail 权限）
    :return: 用户详细信息（含roles和permissions）
    """
    user_crud = UserRepository(db)
    user = await user_crud.get_user_by_id(user_id)
    if not user:
        raise NotFoundError("用户不存在")
    roles = user.roles
    perms = await get_user_permissions(db, user_id)
    return {"code": 0, "message": "success",
            "data": {"id": user.id, "username": user.username, "real_name": user.real_name,
                     "email": user.email, "phone": user.phone, "status": user.status,
                     "last_login_time": user.last_login_time.isoformat() if user.last_login_time else None,
                     "create_time": user.create_time.isoformat() if user.create_time else None,
                     "roles": [{"id": r.id, "role_name": r.role_name, "role_code": r.role_code} for r in roles],
                     "permissions": sorted(perms)}}


@router.put("/{user_id}")
async def update_user_api(
        user_id: int,
        req: UserUpdateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:update"),
) -> dict:
    """
    编辑用户信息
    :param user_id: 用户ID
    :param req: 更新请求体（real_name, email, phone, status等，None不更新）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:update 权限）
    :return: {"code": 0, "message": "用户修改成功"}
    """
    ip = get_client_ip(request)
    await update_user(db, user_id, req.model_dump(exclude_none=True), current_user.id, current_user.username, ip)
    return {"code": 0, "message": "用户修改成功", "data": None}


@router.delete("/{user_id}")
async def delete_user_api(
        user_id: int,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:delete")
) -> dict:
    """
    逻辑删除用户
    :param user_id: 用户ID
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:delete 权限）
    :return: {"code": 0, "message": "用户删除成功"}
    """
    ip = get_client_ip(request)
    await delete_user(db, user_id, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "用户删除成功", "data": None}


@router.put("/{user_id}/reset-password")
async def reset_password_api(
        user_id: int,
        req: ResetPasswordRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:update")
) -> dict:
    """
    重置用户密码
    :param user_id: 用户ID
    :param req: 请求体（new_password）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:update 权限）
    :return: {"code": 0, "message": "密码重置成功，用户需重新登录"}
    """
    ip = get_client_ip(request)
    await reset_user_password(db, user_id, req.new_password,
                              current_user.id, current_user.username, ip)
    return {"code": 0, "message": "密码重置成功，用户需重新登录", "data": None}


@router.put("/{user_id}/roles")
async def update_user_roles_api(
        user_id: int,
        req: AssignRoleRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:assign-role")
) -> dict:
    """
    全量覆盖分配用户角色
    :param user_id: 用户ID
    :param req: 请求体（role_ids）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:assign-role 权限）
    :return: {"code": 0, "message": "角色分配成功"}
    """
    ip = get_client_ip(request)
    await assign_roles(db, user_id, req.role_ids,
                       current_user.id, current_user.username, ip)
    return {"code": 0, "message": "角色分配成功", "data": None}


@router.get("/{user_id}/permissions")
async def get_user_permissions_api(
        user_id: int,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("user:detail")
) -> dict:
    """
    查看用户最终权限列表和菜单树
    :param user_id: 用户ID
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 user:detail 权限）
    :return: {"menus": [...], "permissions": [...]}
    """
    result = await update_user_roles(db, user_id)
    return {"code": 0, "message": "success",
            "data": {"menus": result.get("menus", []),
                     "permissions": sorted(result.get("permissions", []))
                     }
            }
