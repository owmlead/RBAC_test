"""
全局路由聚合模块。
将各子模块（用户、角色、权限、认证、日志）的路由统一注册到顶层 APIRouter，
形成完整的 API 路由树。FastAPI 会根据 prefix + path 最终拼接出完整 URL。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from src.rbac.api import user, role, permission, auth, logs
from src.rbac.core.deps import get_current_user
from src.rbac.db.session import get_db
from src.rbac.models.user import User
from src.rbac.models.role import Role
from src.rbac.models.permission import Permission as PermModel
from src.rbac.models.logs import Logs

router = APIRouter()

# ── 仪表盘统计（仅需登录，不需要特定权限）──
@router.get("/dashboard/stats")
async def dashboard_stats(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取仪表盘统计数据：用户/角色/权限/日志总数。"""
    user_total = (await db.execute(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))).scalar() or 0
    role_total = (await db.execute(select(func.count()).select_from(Role))).scalar() or 0
    perm_total = (await db.execute(select(func.count()).select_from(PermModel))).scalar() or 0
    log_total = (await db.execute(select(func.count()).select_from(Logs))).scalar() or 0
    return {
        "code": 0,
        "data": {
            "userCount": user_total,
            "roleCount": role_total,
            "permCount": perm_total,
            "logCount": log_total,
        }
    }

# 用户管理模块：prefix="/user"，最终路径形如 /user/、/user/{id}
router.include_router(user.router, prefix="/user", tags=["用户管理"])

# 角色管理模块：prefix="/role"，最终路径形如 /role/、/role/{id}
router.include_router(role.router, prefix="/role", tags=["角色管理"])

# 权限管理模块：prefix="/permission"，最终路径形如 /permission/tree、/permission/{id}
router.include_router(permission.router, prefix="/permission", tags=["权限管理"])

# 认证鉴权模块：prefix="/auth"，最终路径形如 /auth/login、/auth/refresh、/auth/logout
router.include_router(auth.router, prefix="/auth", tags=["认证鉴权"])

# 审计日志模块：prefix="/logs"，最终路径形如 /logs/、/logs/export
router.include_router(logs.router, prefix="/logs", tags=["日志"])