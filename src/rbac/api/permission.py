"""
权限资源管理接口层。
提供权限树查询、CRUD、排序和批量导入等 REST API。
"""
from fastapi import APIRouter, Depends, Request

from src.rbac.core.deps import get_client_ip, get_current_user, require_permission
from src.rbac.db.session import get_db
from src.rbac.schemas.permission import PermissionCreateRequest, PermissionUpdateRequest, PermissionSortRequest
from src.rbac.service.permision import build_all_tree, create_permission, update_permission, delete_permission, \
    sort_permissions, import_permissions, export_all_permissions

router = APIRouter()


@router.get("/tree")
async def get_tree_api(
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:list"),
) -> dict:
    """
    获取完整权限资源树
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:list 权限）
    :return: 嵌套字典结构的权限树
    """
    result = await build_all_tree(db)
    return {"code": 0, "message": "success", "data": result}


@router.post("/")
async def create_perm_api(
        req: PermissionCreateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:create"),
) -> dict:
    """
    创建权限资源
    :param req: 创建权限请求体（name, code, type, parent_id, path, icon, sort, status, api_paths）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:create 权限）
    :return: {"code": 0, "data": {"id": 新权限ID}}
    """
    ip = get_client_ip(request)
    result = await create_permission(
        db, req.name, req.code, req.type, req.parent_id,
        req.path, req.icon, req.sort, req.status, req.api_paths,
        current_user.id, current_user.username, ip)
    return {"code": 0, "message": "资源创建成功", "data": result}


# ── 具体路径（必须在 /{perm_id} 前）──

@router.put("/sort")
async def sort_perm_api(
        req: PermissionSortRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:update"),
):
    """
    拖拽排序权限资源
    :param req: 排序请求体（sorted_ids）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:update 权限）
    :return: {"code": 0, "message": "排序成功"}
    """
    ip = get_client_ip(request)
    await sort_permissions(db, req.sorted_ids, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "排序成功", "data": None}


@router.post("/import")
async def import_perm_api(
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:create"),
):
    """
    递归导入权限资源树（存在则更新，不存在则创建）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:create 权限）
    :return: {"code": 0, "message": "导入成功"}
    """
    # 兼容两种请求格式：直接传数组 or 包裹在 {"data": [...]} 中
    body = await request.json()
    items = body if isinstance(body, list) else body.get("data", [])
    await import_permissions(db, items)
    return {"code": 0, "message": "导入成功", "data": None}


@router.get("/export")
async def export_perm_api(
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:list"),
):
    """
    导出所有权限资源树
    :param db: 数据库异步会话
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:list 权限）
    :return: 权限资源树
    """
    result = await export_all_permissions(db)
    return {"code": 0, "message": "success", "data": result}


# ── /{perm_id} 参数化路径 ──

@router.put("/{perm_id}")
async def update_perm_api(
        perm_id: int,
        req: PermissionUpdateRequest,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:update"),
):
    """
    编辑权限资源
    :param perm_id: 权限ID
    :param req: 更新请求体（None值不更新）
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:update 权限）
    :return: {"code": 0, "message": "资源修改成功"}
    """
    ip = get_client_ip(request)
    result = await update_permission(
        db, perm_id, req.model_dump(exclude_none=True),
        current_user.id, current_user.username, ip)
    return {"code": 0, "message": "资源修改成功", "data": result}


@router.delete("/{perm_id}")
async def delete_perm_api(
        perm_id: int,
        request: Request,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("permission:delete"),
):
    """
    删除权限资源（级联删除子资源由数据库外键处理）
    :param perm_id: 权限ID
    :param request: HTTP请求对象
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 permission:delete 权限）
    :return: {"code": 0, "message": "资源已删除"}
    """
    ip = get_client_ip(request)
    await delete_permission(db, perm_id, current_user.id, current_user.username, ip)
    return {"code": 0, "message": "资源已删除", "data": None}
