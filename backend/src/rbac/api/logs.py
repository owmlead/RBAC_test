"""
审计日志接口层。
提供日志分页查询和导出等 REST API。
"""
from fastapi import APIRouter, Depends, Query

from src.rbac.core.deps import require_permission, get_current_user, get_pagination
from src.rbac.crud.logs import get_audit_logs_paginated
from src.rbac.db.session import get_db
from datetime import datetime

router = APIRouter()


@router.get("/")
async def get_logs_api(
        start_time: str | None = Query(None, description="开始时间 ISO 8601"),
        end_time: str | None = Query(None, description="结束时间 ISO 8601"),
        username: str | None = None,
        operation: str | None = None,
        module: str | None = None,
        result: str | None = None,
        pagination=Depends(get_pagination),
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("audit:list"),
):
    """
    多条件分页查询审计日志
    :param start_time: 开始时间（ISO 8601格式），可选
    :param end_time: 结束时间（ISO 8601格式），可选
    :param username: 操作用户名筛选，可选
    :param operation: 操作类型筛选，可选
    :param module: 操作模块筛选，可选
    :param result: 操作结果筛选（SUCCESS/FAIL），可选
    :param pagination: 分页参数（自动注入）
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 audit:list 权限）
    :return: {"total": 总数, "list": [...]}
    """
    # 安全解析时间字符串：格式错误或空值时统一置为 None，不阻断查询
    try:
        st = datetime.fromisoformat(start_time) if start_time else None
    except (ValueError, TypeError):
        st = None
    try:
        et = datetime.fromisoformat(end_time) if end_time else None
    except (ValueError, TypeError):
        et = None
    logs, total = await get_audit_logs_paginated(
        db=db,
        page=pagination["page"],
        size=pagination["size"],
        start_time=st,
        end_time=et,
        username=username,
        operation=operation,
        module=module,
        result=result,
    )
    return {
        "code": 0, "message": "success",
        "data": {
            "total": total,
            "page": pagination["page"],
            "size": pagination["size"],
            "list": [
                {
                    "id": log.id, "username": log.username,
                    "operation": log.operation, "module": log.module,
                    "description": log.description,
                    "request_params": log.request_params,
                    "ip": log.ip, "result": log.result,
                    "create_time": log.create_time.isoformat() if log.create_time else None,
                }
                for log in logs
            ],
        },
    }


@router.get("/export")
async def download_logs(
        start_time: str | None = Query(None, description="开始时间 ISO 8601"),
        end_time: str | None = Query(None, description="结束时间 ISO 8601"),
        username: str | None = None,
        operation: str | None = None,
        module: str | None = None,
        result: str | None = None,
        db=Depends(get_db),
        current_user=Depends(get_current_user),
        _: bool = require_permission("audit:list"),
):
    """
    导出审计日志（返回最近1000条）
    :param start_time: 开始时间（ISO 8601格式），可选
    :param end_time: 结束时间（ISO 8601格式），可选
    :param username: 操作用户名筛选，可选
    :param operation: 操作类型筛选，可选
    :param module: 操作模块筛选，可选
    :param result: 操作结果筛选（SUCCESS/FAIL），可选
    :param db: 数据库会话（自动注入）
    :param current_user: 当前登录用户（自动注入）
    :param _: 权限校验（需要 audit:list 权限）
    :return: {"total": 总数, "list": [...]}
    """
    # 安全解析时间字符串：格式错误或空值时统一置为 None，不阻断查询
    try:
        st = datetime.fromisoformat(start_time) if start_time else None
    except (ValueError, TypeError):
        st = None
    try:
        et = datetime.fromisoformat(end_time) if end_time else None
    except (ValueError, TypeError):
        et = None

    logs, total = await get_audit_logs_paginated(
        db=db,
        page=1,
        size=1000,
        start_time=st,
        end_time=et,
        username=username,
        operation=operation,
        module=module,
        result=result,
    )
    return {
        "code": 0, "message": "success",
        "data": {
            "total": total,
            "list": [
                {
                    "id": log.id, "username": log.username,
                    "operation": log.operation, "module": log.module,
                    "description": log.description,
                    "ip": log.ip, "result": log.result,
                    "create_time": log.create_time.isoformat() if log.create_time else None,
                }
                for log in logs
            ],
        },
    }
