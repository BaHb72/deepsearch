"""
WebUI 认证模块

提供可选的JWT认证功能
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping, Optional, cast

from core.config import get_config
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger

# JWT配置
SECRET_KEY = os.getenv("DEEPSEARCH_JWT_SECRET", "deepsearch-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HTTP Bearer认证
security = HTTPBearer(auto_error=False)


Payload = Dict[str, Any]


def _decode_token(token: str) -> Payload:
    """解码 JWT 并确保得到字典结果。"""
    decoded: Any = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if not isinstance(decoded, dict):
        raise JWTError("解码结果不是字典类型")
    return cast(Payload, decoded)


def create_access_token(data: Mapping[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间间隔

    Returns:
        JWT令牌字符串
    """
    to_encode: Dict[str, Any] = dict(data)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return cast(str, encoded_jwt)


def verify_token(credentials: HTTPAuthorizationCredentials) -> Payload:
    """
    验证JWT令牌

    Args:
        credentials: HTTP认证凭据

    Returns:
        解码后的令牌数据

    Raises:
        HTTPException: 令牌无效或过期
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return _decode_token(credentials.credentials)
    except JWTError as e:
        logger.debug(f"JWT验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[Payload]:
    """
    可选的认证依赖

    如果提供了令牌则验证，否则返回None

    Args:
        credentials: HTTP认证凭据（可选）

    Returns:
        解码后的令牌数据或None
    """
    config = get_config()

    # 检查是否启用了认证
    auth_enabled = getattr(config.webui, "auth_enabled", False)

    if not auth_enabled:
        # 认证未启用，直接通过
        return None

    if credentials:
        return verify_token(credentials)

    return None


def require_auth(credentials: HTTPAuthorizationCredentials = Security(security)) -> Payload:
    """
    强制认证依赖

    必须提供有效的令牌

    Args:
        credentials: HTTP认证凭据

    Returns:
        解码后的令牌数据

    Raises:
        HTTPException: 未提供令牌或令牌无效
    """
    config = get_config()

    # 检查是否启用了认证
    auth_enabled = getattr(config.webui, "auth_enabled", False)

    if not auth_enabled:
        # 认证未启用，但端点要求认证，记录警告
        logger.warning("端点要求认证但系统认证未启用")
        return cast(Payload, {})

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(credentials)


def check_admin_role(token_data: Dict[str, Any]) -> None:
    """
    检查管理员角色

    Args:
        token_data: 令牌数据

    Raises:
        HTTPException: 无管理员权限
    """
    if not token_data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")

    role = token_data.get("role", "user")
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


# WebSocket认证
def verify_websocket_token(token: str) -> Optional[Payload]:
    """
    验证WebSocket连接的令牌

    Args:
        token: JWT令牌字符串

    Returns:
        解码后的令牌数据或None
    """
    config = get_config()
    auth_enabled = getattr(config.webui, "auth_enabled", False)

    if not auth_enabled:
        return None

    if not token:
        return None

    try:
        return _decode_token(token)
    except JWTError:
        return None
