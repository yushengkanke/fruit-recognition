"""密码哈希与登录令牌工具。

安全约定：
- 数据库只保存 bcrypt 哈希，不再保存明文密码；
- 登录成功后签发 HS256 JWT，默认 12 小时过期；
- 签名密钥优先读环境变量 ``AUTH_SECRET``；没有配置时自动生成并保存到
  ``data/.auth_secret``（Docker 中 data 目录已挂载，容器重启后令牌仍有效）。

生产环境建议显式设置 ``AUTH_SECRET``（例如 ``openssl rand -hex 32``），
并保证 ``data/.auth_secret`` 或环境变量不会进入 Git。
"""
from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
_secret_cache: str | None = None


def is_password_hash(value: object) -> bool:
    """判断一个字符串是否已经是 bcrypt 哈希。"""
    return isinstance(value, str) and value.startswith(_BCRYPT_PREFIXES)


def hash_password(password: str) -> str:
    """bcrypt 加盐哈希。bcrypt 的输入上限是 72 字节。"""
    raw = (password or "").encode("utf-8")
    if len(raw) > 72:
        raise ValueError("密码过长：最多 72 字节（中文约 24 个字符）")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored: str | None) -> bool:
    """校验密码；兼容历史明文数据，方便 init_db/login 做平滑迁移。"""
    if not stored:
        return False
    raw = (password or "").encode("utf-8")
    if is_password_hash(stored):
        if len(raw) > 72:
            return False
        try:
            return bcrypt.checkpw(raw, stored.encode("ascii"))
        except (ValueError, TypeError):
            return False
    # 旧库中的明文密码。init_db 会批量升级，login 也会在成功登录后补升级。
    if not isinstance(stored, str):
        return False
    return hmac.compare_digest(stored, password or "")


def _secret_file() -> Path:
    configured = (os.getenv("AUTH_SECRET_FILE") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent / "data" / ".auth_secret"


def get_auth_secret() -> str:
    """返回 JWT 签名密钥；未配置时生成并持久化。"""
    global _secret_cache
    if _secret_cache:
        return _secret_cache

    env_secret = (os.getenv("AUTH_SECRET") or "").strip()
    if env_secret:
        _secret_cache = env_secret
        return _secret_cache

    path = _secret_file()
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        secret = ""

    if not secret:
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_urlsafe(48)
        path.write_text(secret, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows 等平台可能不支持 POSIX 权限位，忽略即可
            pass

    _secret_cache = secret
    return secret


def token_ttl_seconds() -> int:
    try:
        hours = float(os.getenv("TOKEN_TTL_HOURS", "12"))
    except ValueError:
        hours = 12.0
    return int(max(1.0, hours) * 3600)


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=token_ttl_seconds()),
    }
    return jwt.encode(payload, get_auth_secret(), algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    """校验 JWT，成功时返回用户 ID；失败返回 None。"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_auth_secret(), algorithms=["HS256"])
    except (jwt.PyJWTError, TypeError):
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject
