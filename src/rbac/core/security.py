"""
安全工具模块。
提供密码哈希、JWT 令牌签发/解析、登录失败锁定、图形验证码和密码强度校验功能。
登录失败记录持久化到数据库，服务重启不丢失。

模块功能概览：
- 密码: BCrypt 哈希与验密
- 验证码: SVG 数学题生成与一次性验证
- JWT: 访问/刷新令牌签发、解析、JTI 提取、过期时间查询
- 密码强度: 长度与字符种类校验
"""
import random
import re
from base64 import b64encode
from datetime import timedelta, datetime, timezone
from typing import Any
from passlib.context import CryptContext
from sqlalchemy import select, update
import uuid
from jose import JWTError, jwt

from src.rbac.core.config import setting

# ── 密码哈希 ──

# BCrypt 上下文，schemes=["bcrypt"] 指定使用 bcrypt 算法，deprecated="auto" 自动升级旧算法
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    BCrypt 哈希密码。

    使用 bcrypt 算法对明文密码进行加盐哈希，生成的哈希字符串
    包含算法标识、盐值和摘要，可直接存入数据库。

    :param password: 明文密码
    :return: bcrypt 哈希后的密码字符串
    """
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    验证用户密码是否正确。

    从哈希字符串中自动提取盐值，对明文密码进行相同哈希后比较。

    :param plain: 用户输入的明文密码
    :param hashed: 数据库中存储的 bcrypt 哈希密码
    :return: True 正确 / False 错误
    """
    return _pwd_context.verify(plain, hashed)


# ── 图形验证码 ──

# 内存字典存储验证码，key 为验证码 ID，value 为正确答案
# 注意：生产环境建议迁移到 Redis 以支持分布式和多实例
_captcha_store: dict[str, str] = {}


def generate_captcha() -> dict[str, str]:
    """
    生成简单数学验证码（SVG 格式图片）。

    随机生成两位数四则运算，渲染为 SVG 图片后 Base64 编码，
    正确结果存入内存，验证时一次性消费（pop 取出后即销毁）。

    :return: {
        "captcha_id": 验证码唯一标识（12位十六进制），
        "captcha_text": 问题文本（如 "3 + 5 = ?"），
        "captcha_image": Base64 编码的 SVG 图片 data URI
    }
    """
    # 随机生成两个操作数
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    # 随机选择运算符
    op = random.choice(["+", "-", "*", "/"])
    result = 0
    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    elif op == "/":
        # 除法结果保留浮点数（如 3/2=1.5），用户需输入精确值
        result = a / b

    # 生成唯一验证码 ID（uuid4 hex 前12位）
    captcha_id = uuid.uuid4().hex[:12]
    text = f"{a} {op} {b} = ?"
    # 将正确答案存入内存
    _captcha_store[captcha_id] = str(result)

    # 构造 SVG 图像字符串
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="150" height="50">'
        f'<rect width="150" height="50" fill="#f0f0f0"/>'
        f'<text x="10" y="32" font-size="20" fill="#333">{text}</text>'
        f"</svg>"
    )
    # Base64 编码为 data URI，前端可直接用于 <img src="...">
    img_b64 = "data:image/svg+xml;base64," + b64encode(svg.encode()).decode()

    return {"captcha_id": captcha_id, "captcha_text": text, "captcha_image": img_b64}


def verify_captcha(captcha_id: str, user_input: str) -> bool:
    """
    验证验证码答案（一次性消费）。

    使用 pop 取出答案，验证后即销毁——每个验证码只能使用一次，
    防止重复提交攻击。

    :param captcha_id: 验证码 ID
    :param user_input: 用户输入的答案字符串
    :return: True 正确 / False 错误（ID 不存在或答案不匹配）
    """
    # pop 取出并删除，确保一次性消费
    expected = _captcha_store.pop(captcha_id, None)
    if expected is None:
        return False  # 验证码 ID 无效或已被使用
    return str(user_input).strip() == expected


# ── JWT ──

def create_jwt_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
        token_type: str = 'access',
) -> str:
    """
    签发 JWT 令牌。

    生成的令牌包含以下标准声明：
    - jti: 唯一标识符，用于黑名单/注销机制
    - type: 令牌类型（access / refresh）
    - exp: 过期时间（UTC）
    - iat: 签发时间（UTC）
    - 以及调用方传入的自定义数据（user_id, username 等）

    :param data: 令牌自定义载荷数据（如 {"user_id": 1, "username": "admin"}）
    :param expires_delta: 过期时间增量，为 None 则根据 token_type 使用默认配置
    :param token_type: 令牌类型，"access" 为访问令牌，"refresh" 为刷新令牌
    :return: 编码后的 JWT 字符串（三段式：header.payload.signature）
    """
    # 复制载荷数据，避免修改原始字典
    to_encode = data.copy()
    # 添加 JTI（唯一标识，用于注销）
    to_encode["jti"] = uuid.uuid4().hex
    # 添加令牌类型标记
    to_encode["type"] = token_type

    # 根据令牌类型选择默认过期时间
    if token_type == "access":
        delta = expires_delta or timedelta(minutes=setting.ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        delta = expires_delta or timedelta(days=setting.REFRESH_TOKEN_EXPIRE_DAYS)
    # 签发时间和过期时间使用 UTC
    time_utc = datetime.now(timezone.utc)
    to_encode.update({"exp": time_utc + delta, "iat": time_utc})
    # 编码为 JWT 字符串
    return jwt.encode(to_encode, setting.JWT_SECRET_KEY, algorithm=setting.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict[str, Any] | None:
    """
    解析并验证 JWT 令牌。

    验证签名、过期时间等声明，全部通过后返回载荷字典。
    任何验证失败（签名不匹配、已过期、格式错误等）均返回 None。

    :param token: JWT 令牌字符串
    :return: 令牌载荷字典，验证失败返回 None
    """
    try:
        payload = jwt.decode(token, setting.JWT_SECRET_KEY, algorithms=[setting.JWT_ALGORITHM])
        return payload
    except JWTError:
        # 捕获所有 JWT 相关异常（过期、签名错误、格式错误等）
        return None


def get_token_jti(token: str) -> str | None:
    """
    获取令牌的 JTI（唯一标识符），用于加入黑名单实现注销。

    解析时不验证过期时间（verify_exp=False），因为注销操作
    可能需要将尚未到期但已被主动退出的 Token 加入黑名单。

    :param token: JWT 令牌字符串
    :return: JTI 字符串，解析失败返回 None
    """
    try:
        payload = jwt.decode(
            token, setting.JWT_SECRET_KEY, algorithms=[setting.JWT_ALGORITHM],
            options={"verify_exp": False},  # 不验证过期，仅提取 JTI
        )
        return payload.get("jti")
    except JWTError:
        return None


def get_token_expire_time(token: str) -> datetime | None:
    """
    获取令牌的过期时间。

    不验证过期（verify_exp=False），仅提取 exp 声明并转为 datetime 对象，
    用于计算黑名单的 TTL（黑名单记录应在 Token 过期时自动清除）。

    :param token: JWT 令牌字符串
    :return: 过期时间 datetime 对象（带 UTC 时区），解析失败返回 None
    """
    try:
        payload = jwt.decode(
            token, setting.JWT_SECRET_KEY, algorithms=[setting.JWT_ALGORITHM],
            options={"verify_exp": False},  # 不验证过期，仅提取 exp
        )
        exp = payload.get("exp")
        # exp 为 Unix 时间戳（秒），转为带时区的 datetime
        return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
    except JWTError:
        return None


# ── 密码强度校验 ──

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    校验密码强度（长度 >= 8，且包含字母/数字/特殊字符中至少两种）。

    强度规则：
    1. 长度不小于 PASSWORD_MIN_LENGTH（默认 8）
    2. 至少包含以下三类字符中的两类：
       - 字母 (a-z, A-Z)
       - 数字 (0-9)
       - 特殊字符（非字母非数字）

    :param password: 待校验的明文密码
    :return: (是否通过, 失败原因描述) — 通过时原因为空字符串
    """
    # 规则1：长度校验
    if len(password) < setting.PASSWORD_MIN_LENGTH:
        return False, f"密码长度至少 {setting.PASSWORD_MIN_LENGTH} 位"
    # 规则2：字符种类统计
    categories = 0
    if re.search(r"[a-zA-Z]", password):
        categories += 1  # 包含字母
    if re.search(r"\d", password):
        categories += 1  # 包含数字
    if re.search(r"[^a-zA-Z\d]", password):
        categories += 1  # 包含特殊字符
    if categories < 2:
        return False, "密码须包含字母、数字、特殊字符中至少两种"
    return True, ""
