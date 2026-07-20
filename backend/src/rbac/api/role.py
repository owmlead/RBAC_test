"""
角色管理接口层。
提供角色 CRUD、角色树、复制、用户关联查询和移除等 REST API。
"""
from fastapi import APIRouter, Query, Depends, Request

from src.rbac.core.deps import get_client_ip, require_permission, get_current_user, get_pagination
from src.rbac.db.session import get_db
from src.rbac.schemas.role import RoleCreateRequest, RoleUpdateRequest, RoleCopyRequest, RoleRemoveUsersRequest
from src.rbac.service.role import build_all_role_tree, get_roles_paginated, get_role_by_id, create_role, update_role, \
    delete_role, copy_role, get_users_by_role_id, remove_users_from_role

router = APIRouter()


@router.get("/")
async def get_role_list_api(
        keyword: str | None = None,
        tree: bool = Query(False),
        pagination=Depends(get_pagination),
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:list"),
) -> dict:
    """
    查询角色列表（支持分页和角色树两种模式）
    :param keyword: 搜索关键字，可选
    :param tree: True返回角色树，False返回分页列表
    :param pagination: 分页参数（自动注入）
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:list 权限）
    :return: 角色树或分页列表
    """
    # 根据 tree 参数选择返回格式：树形结构 or 分页列表
    if tree:
        return {"code": 0, "message": "success",
                "data": await build_all_role_tree(db)}
    roles, total = await get_roles_paginated(db, keyword, pagination["page"], pagination["size"])
    return {"code": 0, "message": "success",
            "data": {"total": total, "page": pagination["page"],
                     "size": pagination["size"], "list": roles}}


@router.get("/{role_id}")
async def get_role_by_id_api(
        role_id: int,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:detail")
) -> dict:
    """
    查询角色详情（含完整权限树）
    :param role_id: 角色ID
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:detail 权限）
    :return: 角色详情（含挂载的权限树）
    """
    ip = get_client_ip(request)
    result = await get_role_by_id(db, role_id)
    return {"code": 0, "message": "success", "data": result}


@router.post("/")
async def create_role_api(
        req: RoleCreateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:create")
) -> dict:
    """
    新增角色
    :param req: 创建角色请求体（role_name, role_code, description, parent_role_ids, permissions）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:create 权限）
    :return: {"code": 0, "data": {"id": 新角色ID}}
    """
    ip = get_client_ip(request)
    # 将 Pydantic schema 的 permissions 列表转换为 service 层期望的字典格式
    permissions = [{"permission_id": p.permission_id, "is_deny": p.is_deny}
                   for p in req.permissions] if req.permissions else []
    result = await create_role(
        db, req.role_name, req.role_code, req.description,
        req.parent_role_ids, permissions,
        current_user.id, current_user.username, ip)
    return {"code": 0, "message": "角色创建成功", "data": result}


@router.put("/{role_id}")
async def update_role_api(
        role_id: int,
        req: RoleUpdateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:update")
) -> dict:
    """
    编辑角色
    :param role_id: 角色ID
    :param req: 更新请求体（None值不更新）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:update 权限）
    :return: {"code": 0, "message": "角色更新成功"}
    """
    ip = get_client_ip(request)
    # exclude_none=True 确保只传递用户实际填写的字段，未填字段不覆盖
    update_data = req.model_dump(exclude_none=True)
    # 如果传了 permissions，将列表中的字典标准化为固定键名
    if update_data.get("permissions") is not None:
        update_data["permissions"] = [
            {"permission_id": p["permission_id"], "is_deny": p.get("is_deny", False)}
            for p in update_data["permissions"]
        ]
    await update_role(db, role_id, update_data, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "角色更新成功", "data": None}


@router.delete("/{role_id}")
async def delete_role_api(
        role_id: int,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:delete")
) -> dict:
    """
    删除角色（有用户关联时禁止删除）
    :param role_id: 角色ID
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:delete 权限）
    :return: {"code": 0, "message": "角色删除成功"}
    """
    ip = get_client_ip(request)
    await delete_role(db, role_id, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "角色删除成功", "data": None}


@router.post("/{role_id}/copy")
async def copy_role_api(
        role_id: int,
        req: RoleCopyRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:create")
) -> dict:
    """
    复制角色（含权限和继承关系）
    :param role_id: 源角色ID
    :param req: 请求体（role_name, role_code）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:create 权限）
    :return: {"code": 0, "data": {"id": 新角色ID}}
    """
    ip = get_client_ip(request)
    result = await copy_role(db, role_id, req.role_name, req.role_code,
                             current_user.id, current_user.username, ip)
    return {"code": 0, "message": "角色复制成功", "data": result}


@router.get("/{role_id}/users")
async def get_users_by_role_id_api(
        role_id: int,
        pagination=Depends(get_pagination),
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:detail")
) -> dict:
    """
    分页查询角色关联的用户列表
    :param role_id: 角色ID
    :param pagination: 分页参数（自动注入）
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:detail 权限）
    :return: {"total": 总数, "list": [...]}
    """
    result = await get_users_by_role_id(db, role_id, pagination)
    return {"code": 0, "message": "success", "data": result}


@router.delete("/{role_id}/users")
async def remove_users_from_role_api(
        role_id: int,
        req: RoleRemoveUsersRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("role:assign-user")
) -> dict:
    """
    批量移除角色关联用户
    :param role_id: 角色ID
    :param req: 请求体（user_ids）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 role:assign-user 权限）
    :return: {"code": 0, "message": "已移除指定用户"}
    """
    ip = get_client_ip(request)
    await remove_users_from_role(db, role_id, req.user_ids,
                                 current_user.id, current_user.username, ip)
    return {"code": 0, "message": "已移除指定用户", "data": None}
