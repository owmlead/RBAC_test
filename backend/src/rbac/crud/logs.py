"""
审计日志数据访问层。

提供日志表的写入和分页查询操作。日志表只增不删，
所有方法为模块级函数（非类），由业务层直接调用。
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.rbac.models.logs import Logs


async def create_audit_log(db: AsyncSession, **kwargs) -> Logs:
    """
    写入一条审计日志（只增不删，记录用户的关键操作）
    :param db: 数据库异步会话
    :param kwargs: 日志字段键值对（user_id, username, operation, module, description 等）
    :return: 创建成功的日志ORM模型（已 flush 但未 commit）
    """
    log = Logs(**kwargs)
    db.add(log)
    await db.flush()
    return log


async def get_audit_logs_paginated(
    db: AsyncSession,
    page: int,
    size: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    username: str | None = None,
    operation: str | None = None,
    module: str | None = None,
    result: str | None = None,
) -> tuple[list[Logs], int]:
    """
    多条件分页查询审计日志，支持按时间范围、用户、操作类型、模块、结果筛选。
    所有筛选条件均为可选，不传则不筛选。

    :param db: 数据库异步会话
    :param page: 页码（从1开始）
    :param size: 每页条数
    :param start_time: 日志开始时间筛选（create_time >= start_time），为None则不筛选
    :param end_time: 日志结束时间筛选（create_time <= end_time），为None则不筛选
    :param username: 操作用户名筛选（精确匹配），为None则不筛选
    :param operation: 操作类型筛选（LOGIN, CREATE, UPDATE 等），为None则不筛选
    :param module: 操作模块筛选（USER, ROLE, PERMISSION, AUTH 等），为None则不筛选
    :param result: 操作结果筛选（SUCCESS/FAIL），为None则不筛选
    :return: (日志列表, 总条数) 元组，日志按创建时间倒序排列
    """
    # 构建基础查询
    q = select(Logs)
    # 逐步追加筛选条件（使用链式 WHERE，SQLAlchemy 自动以 AND 连接）
    if start_time:
        q = q.where(Logs.create_time >= start_time)
    if end_time:
        q = q.where(Logs.create_time <= end_time)
    if username:
        q = q.where(Logs.username == username)
    if operation:
        q = q.where(Logs.operation == operation)
    if module:
        q = q.where(Logs.module == module)
    if result:
        q = q.where(Logs.result == result)

    # 统计符合条件的总数
    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar() or 0
    # 分页查询：按ID倒序（最新日志在前）
    list_result = await db.execute(
        q.order_by(Logs.id.desc()).offset((page - 1) * size).limit(size)
    )
    logs = list_result.scalars().all()
    return list(logs), total
