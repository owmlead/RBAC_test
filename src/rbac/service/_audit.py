"""
审计日志写入模块 — 所有 service 模块共享调用。
提供统一的审计日志写入入口，封装底层 CRUD 调用。
审计日志是系统安全审计的核心数据源，记录所有关键操作（增删改、登录、登出等）。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from src.rbac.crud.logs import create_audit_log


async def write_audit(
    db: AsyncSession,
    user_id: int | None,
    username: str,
    operation: str,
    module: str,
    desc: str,
    params: str | None = None,
    ip: str | None = None,
    result: str = "SUCCESS",
) -> None:
    """
    写入一条审计日志到数据库。
    用于记录用户的所有关键操作，包括增删改查、登录登出、权限变更等。
    :param db: 数据库异步会话
    :param user_id: 操作者用户ID，可为None（如登录失败时用户尚未确定）
    :param username: 操作者用户名
    :param operation: 操作类型，如 LOGIN / LOGOUT / CREATE / UPDATE / DELETE
    :param module: 操作模块，如 AUTH / USER / ROLE / PERMISSION
    :param desc: 操作描述文本
    :param params: 请求参数（JSON字符串），可选
    :param ip: 操作者IP地址，可选
    :param result: 操作结果，默认 "SUCCESS"，可传 "FAIL"
    :return: None
    """
    # 调用底层 CRUD 将日志写入数据库
    await create_audit_log(
        db, user_id=user_id, username=username, operation=operation,
        module=module, description=desc, request_params=params,
        ip=ip, result=result,
    )
