"""
WebUI 认证 API 路由。

提供统一的登录入口 `/api/auth/login`，返回 JWT 令牌供前端使用。
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional

from core.config import get_config
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    """登录请求体"""

    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginUser(BaseModel):
    """登录返回用户信息"""

    name: str = Field(..., description="用户名")
    role: str = Field("user", description="角色")


class LoginResponse(BaseModel):
    """登录响应体"""

    token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="令牌过期秒数")
    auth_enabled: bool = Field(..., description="服务端是否启用严格认证")
    user: LoginUser


def _is_auth_enabled() -> bool:
    config = get_config()
    return bool(getattr(config.webui, "auth_enabled", False))


def _expected_username() -> str:
    """解析登录用户名，优先环境变量，其次配置，最后默认 admin。"""

    env_username = (os.getenv("DEEPSEARCH_AUTH_USERNAME") or "").strip()
    if env_username:
        return env_username

    config = get_config()
    cfg_username = getattr(config.webui, "auth_username", None)
    if isinstance(cfg_username, str) and cfg_username.strip():
        return cfg_username.strip()

    return "admin"


def _expected_password() -> Optional[str]:
    """解析登录密码，优先环境变量，其次配置。"""

    env_password = os.getenv("DEEPSEARCH_AUTH_PASSWORD")
    if env_password:
        return env_password

    config = get_config()
    cfg_password = getattr(config.webui, "auth_password", None)
    if isinstance(cfg_password, str) and cfg_password:
        return cfg_password

    return None


@router.post("/login", response_model=LoginResponse, summary="WebUI 登录")
async def login(payload: LoginRequest) -> LoginResponse:
    """
    WebUI 通用登录接口。

    - `auth_enabled=true` 时：严格校验用户名和密码（来源：环境变量/配置）。
    - `auth_enabled=false` 时：允许本地登录并签发 JWT，避免前端走硬编码 token。
    """

    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")

    auth_enabled = _is_auth_enabled()
    expected_username = _expected_username()
    expected_password = _expected_password()

    if auth_enabled:
        if not expected_password:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "认证已启用但未配置密码。"
                    "请设置环境变量 DEEPSEARCH_AUTH_PASSWORD（可选 DEEPSEARCH_AUTH_USERNAME）。"
                ),
            )

        if username != expected_username or payload.password != expected_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

    role = "admin" if username == expected_username else "user"
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={
            "sub": username,
            "role": role,
        },
        expires_delta=expires_delta,
    )

    return LoginResponse(
        token=token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds()),
        auth_enabled=auth_enabled,
        user=LoginUser(name=username, role=role),
    )
