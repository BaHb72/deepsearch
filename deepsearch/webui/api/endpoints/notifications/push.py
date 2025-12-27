"""Notification related API endpoints"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from deepsearch.config import get_config, reload_config
from deepsearch.config.models.notifications import (
    BarkServerConfig,
    MessageTemplates,
    NotificationBaseUrls,
    NotificationCategoryConfig,
    NotificationsConfig,
)
from deepsearch.constants import YAML_ENCODING
from deepsearch.core.runtime.context import get_context
from deepsearch.infrastructure.notifications import (
    CategoryNotAllowedError,
    ChannelNotConfiguredError,
    NotificationDispatchError,
    NotificationError,
    NotificationQuotaGuard,
    NotificationService,
    NotificationValidationError,
    QuotaExceededError,
)
from deepsearch.webui.dependencies import get_notification_service

router = APIRouter(prefix="/api/notification", tags=["Notification"])


class NotificationBaseUrlsPayload(BaseModel):
    """Base urls for Xtuis channels"""

    model_config = ConfigDict(populate_by_name=True)

    wechat: str = Field(default="https://wx.xtuis.cn", description="Wechat push base url")
    bark: str = Field(
        default="https://bark.xtuis.cn", description="Bark push base url (deprecated)"
    )


class BarkServerPayload(BaseModel):
    """Bark server configuration payload"""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Server display name", min_length=1)
    base_url: str = Field(..., alias="baseUrl", description="Server URL", min_length=1)
    token: str = Field(
        default="", description="Device key (optional for official Bark with key in URL)"
    )
    enabled: bool = Field(default=True, description="Whether this server is enabled")
    group: Optional[str] = Field(default=None, description="Default notification group")
    icon: Optional[str] = Field(default=None, description="Default icon URL (iOS 15+)")
    sound: Optional[str] = Field(default=None, description="Default notification sound")
    level: Optional[str] = Field(
        default=None,
        description="Default notification level: active/timeSensitive/passive/critical",
    )


class NotificationCategoryPayload(BaseModel):
    """Notification category payload definition"""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Category identifier", min_length=1)
    enabled: bool = Field(default=True, description="Whether the category is active")
    max_per_window: Optional[int] = Field(
        default=None,
        alias="maxPerWindow",
        ge=0,
        description="Maximum number of notifications per window",
    )
    window_seconds: Optional[int] = Field(
        default=None,
        alias="windowSeconds",
        gt=0,
        description="Length of the quota window in seconds",
    )
    channels: List[str] = Field(
        default_factory=list, description="Allowed delivery channels for the category"
    )

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Category name cannot be empty")
        return normalized

    @field_validator("channels", mode="after")
    @classmethod
    def _normalize_channels(cls, value: List[str]) -> List[str]:
        normalized: List[str] = []
        seen: set[str] = set()
        for channel in value:
            channel_str = str(channel).strip().lower()
            if channel_str and channel_str not in seen:
                seen.add(channel_str)
                normalized.append(channel_str)
        return normalized


class NotificationConfigUpdate(BaseModel):
    """Notification config update payload"""

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(..., description="Whether notification service is enabled")
    default_channel: List[str] = Field(..., alias="defaultChannel", description="Default channels")
    wechat_token: Optional[str] = Field(None, alias="wechatToken", description="Wechat token")
    bark_token: Optional[str] = Field(None, alias="barkToken", description="Bark token")
    request_timeout: float = Field(
        ..., alias="requestTimeout", gt=0, description="Request timeout in seconds"
    )
    retry_attempts: int = Field(..., alias="retryAttempts", ge=0, description="Retry attempts")
    retry_delay: float = Field(..., alias="retryDelay", ge=0, description="Retry delay in seconds")
    title_template: Optional[str] = Field(
        None, alias="titleTemplate", min_length=1, description="Notification title template"
    )
    body_template: Optional[str] = Field(
        None, alias="bodyTemplate", min_length=1, description="Notification body template"
    )
    base_urls: Optional[NotificationBaseUrlsPayload] = Field(
        None, alias="baseUrls", description="Channel base urls"
    )
    bark_servers: List[BarkServerPayload] = Field(
        default_factory=list, alias="barkServers", description="Bark server configurations"
    )
    categories: List[NotificationCategoryPayload] = Field(
        default_factory=list, alias="categories", description="Quota categories"
    )
    templates: Optional[Dict[str, Any]] = Field(
        default=None, description="Message templates configuration"
    )


class NotificationPayload(BaseModel):
    """Send notification request"""

    title: str = Field(..., description="Notification title", min_length=1)
    content: Optional[str] = Field(None, description="Notification body")
    channel: Optional[str] = Field(default=None, description="Target channel")
    category: str = Field(default="default", description="Quota category")
    bypass_quota: bool = Field(default=False, description="Bypass quota guard")
    # Bark specific parameters
    url: Optional[str] = Field(default=None, description="Bark: click to open URL")
    group: Optional[str] = Field(default=None, description="Bark: notification group")
    icon: Optional[str] = Field(default=None, description="Bark: custom icon URL")
    sound: Optional[str] = Field(default=None, description="Bark: notification sound")
    call: bool = Field(default=False, description="Bark: repeat sound for 30s")
    level: Optional[str] = Field(
        default=None, description="Bark: notification level (active/timeSensitive/passive/critical)"
    )
    bark_server_names: Optional[List[str]] = Field(
        default=None,
        alias="barkServerNames",
        description="Specific Bark servers to push (names). None = all enabled",
    )
    bark_template_name: Optional[str] = Field(
        default=None, alias="barkTemplateName", description="Bark template name to use"
    )


# ==================== Helpers ====================


def _config_dir() -> Path:
    base = Path(__file__).parent.parent.parent.parent.parent
    return base / "config"


def _get_config_path() -> Path:
    settings = get_config()
    if settings is None:
        raise HTTPException(status_code=500, detail="Settings not initialised")
    env = getattr(settings.app, "env", "dev")
    cfg_path = _config_dir() / f"settings.{env}.yaml"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"Config file not found: {cfg_path}")
    return cfg_path


def _notifications_from_settings() -> NotificationsConfig:
    settings = get_config()
    if settings is None:
        return NotificationsConfig()
    notifications = getattr(settings, "notifications", None)
    if notifications is None:
        return NotificationsConfig()
    if isinstance(notifications, NotificationsConfig):
        return notifications
    return NotificationsConfig.model_validate(notifications)


def _build_notification_response(config: NotificationsConfig) -> Dict[str, Any]:
    categories: List[Dict[str, Any]] = []
    for name, item in sorted((config.categories or {}).items(), key=lambda kv: kv[0]):
        if not isinstance(item, NotificationCategoryConfig):
            item = NotificationCategoryConfig.model_validate(item)
        categories.append(
            {
                "name": name,
                "enabled": item.enabled,
                "maxPerWindow": item.max_per_window,
                "windowSeconds": item.window_seconds,
                "channels": item.channels or [],
            }
        )

    base_urls = (
        config.base_urls
        if isinstance(config.base_urls, NotificationBaseUrls)
        else NotificationBaseUrls()
    )

    # default_channel 可能是字符串或列表，统一返回列表格式
    default_ch = config.default_channel or ["wechat"]
    if isinstance(default_ch, str):
        default_ch = [default_ch]

    # 构建 bark_servers 响应 - 返回明文 token
    bark_servers_data: List[Dict[str, Any]] = []
    for server in config.bark_servers:
        bark_servers_data.append(
            {
                "name": server.name,
                "baseUrl": server.base_url,
                "token": server.token or "",  # 明文显示
                "enabled": server.enabled,
                "group": server.group,
                "icon": server.icon,
                "sound": server.sound,
                "level": server.level,
            }
        )

    return {
        "enabled": bool(config.enabled),
        "defaultChannel": default_ch,
        "wechatToken": config.wechat_token or "",  # 明文显示
        "barkToken": config.bark_token or "",  # 明文显示
        "hasWechatToken": bool(config.wechat_token),
        "hasBarkToken": bool(config.bark_token) or bool(config.bark_servers),
        "barkServers": bark_servers_data,
        "requestTimeout": config.request_timeout,
        "retryAttempts": config.retry_attempts,
        "retryDelay": config.retry_delay,
        "titleTemplate": config.title_template,
        "bodyTemplate": config.body_template,
        "baseUrls": {
            "wechat": base_urls.wechat,
            "bark": base_urls.bark,
        },
        "categories": categories,
        # 消息模板
        "templates": {
            "wechat": [
                {
                    "name": t.name,
                    "titleTemplate": t.title_template,
                    "bodyTemplate": t.body_template,
                }
                for t in config.templates.wechat
            ],
            "bark": [
                {
                    "name": t.name,
                    "titleTemplate": t.title_template,
                    "bodyTemplate": t.body_template,
                    "subtitleTemplate": t.subtitle_template,
                    "useMarkdown": t.use_markdown,
                    "level": t.level,
                    "sound": t.sound,
                    "icon": t.icon,
                    "image": t.image,
                    "group": t.group,
                    "url": t.url,
                    "copy": t.copy,
                    "autoCopy": t.auto_copy,
                    "isArchive": t.is_archive,
                    "call": t.call,
                    "badge": t.badge,
                }
                for t in config.templates.bark
            ],
            "defaultWechat": config.templates.default_wechat,
            "defaultBark": config.templates.default_bark,
        },
    }


def _normalize_token(new_value: Optional[str], existing: Optional[str]) -> Optional[str]:
    if new_value is None or new_value == "***":
        return existing
    stripped = new_value.strip()
    if not stripped:
        return None
    return stripped


def _categories_to_dict(
    items: Sequence[NotificationCategoryPayload], default_channels: List[str]
) -> Dict[str, NotificationCategoryConfig]:
    defaults = NotificationCategoryConfig()
    result: Dict[str, NotificationCategoryConfig] = {}
    for item in items:
        channels = item.channels or default_channels
        result[item.name] = NotificationCategoryConfig(
            enabled=item.enabled,
            max_per_window=(
                item.max_per_window if item.max_per_window is not None else defaults.max_per_window
            ),
            window_seconds=(
                item.window_seconds if item.window_seconds is not None else defaults.window_seconds
            ),
            channels=channels,
        )
    return result


def _write_notifications_config(cfg_path: Path, data: Dict[str, Any]) -> None:
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        source_data = yaml.safe_load(cfg_path.read_text(encoding=YAML_ENCODING)) or {}
    else:
        source_data = {}
    source_data["notifications"] = data
    with cfg_path.open("w", encoding=YAML_ENCODING) as fh:
        yaml.safe_dump(source_data, fh, allow_unicode=True, sort_keys=False)


# ==================== Config endpoints ====================


@router.get("/config")
async def get_notification_config() -> Dict[str, Any]:
    """Return current notification configuration"""
    config = _notifications_from_settings()
    return _build_notification_response(config)


@router.put("/config")
async def update_notification_config(payload: NotificationConfigUpdate) -> Dict[str, Any]:
    """Persist notification configuration"""
    cfg_path = _get_config_path()
    existing_config = _notifications_from_settings()
    defaults = NotificationsConfig()

    # 默认渠道列表
    default_channels = payload.default_channel
    if not default_channels:
        existing_ch = existing_config.default_channel
        if isinstance(existing_ch, str):
            default_channels = [existing_ch] if existing_ch else ["wechat"]
        else:
            default_channels = existing_ch or ["wechat"]
    default_channel_value = [ch.lower() for ch in default_channels]

    base_urls_data = payload.base_urls or NotificationBaseUrlsPayload(
        wechat=(
            existing_config.base_urls.wechat
            if existing_config.base_urls
            else NotificationBaseUrls().wechat
        ),
        bark=(
            existing_config.base_urls.bark
            if existing_config.base_urls
            else NotificationBaseUrls().bark
        ),
    )

    if payload.categories:
        categories_payload: Sequence[NotificationCategoryPayload] = payload.categories
    else:
        categories_payload = [
            NotificationCategoryPayload.model_validate(
                {
                    "name": name,
                    "enabled": item.enabled,
                    "maxPerWindow": item.max_per_window,
                    "windowSeconds": item.window_seconds,
                    "channels": item.channels or [],
                }
            )
            for name, item in (existing_config.categories or {}).items()
        ]

    categories_dict: Dict[str, NotificationCategoryConfig] = _categories_to_dict(
        categories_payload,
        default_channel_value,
    )

    title_template = (
        payload.title_template.strip()
        if payload.title_template
        else (existing_config.title_template or defaults.title_template)
    )
    body_template = (
        payload.body_template.strip()
        if payload.body_template
        else (existing_config.body_template or defaults.body_template)
    )

    # 处理 bark_servers
    bark_servers_list: List[BarkServerConfig] = []
    if payload.bark_servers:
        for srv in payload.bark_servers:
            bark_servers_list.append(
                BarkServerConfig(
                    name=srv.name,
                    base_url=srv.base_url,
                    token=(
                        srv.token
                        if srv.token != "***"
                        else next(
                            (s.token for s in existing_config.bark_servers if s.name == srv.name),
                            srv.token,
                        )
                    ),
                    enabled=srv.enabled,
                    group=srv.group,
                    icon=srv.icon,
                    sound=srv.sound,
                    level=srv.level,
                )
            )
    else:
        bark_servers_list = list(existing_config.bark_servers)

    # 处理 templates
    templates_config = existing_config.templates
    if payload.templates:
        try:
            templates_config = MessageTemplates.model_validate(payload.templates)
        except Exception:
            # 如果验证失败，保持现有配置
            pass

    new_config = NotificationsConfig(
        enabled=payload.enabled,
        default_channel=default_channel_value,
        wechat_token=_normalize_token(payload.wechat_token, existing_config.wechat_token),
        bark_token=_normalize_token(payload.bark_token, existing_config.bark_token),
        bark_servers=bark_servers_list,
        base_urls=NotificationBaseUrls(
            wechat=base_urls_data.wechat,
            bark=base_urls_data.bark,
        ),
        request_timeout=payload.request_timeout,
        retry_attempts=payload.retry_attempts,
        retry_delay=payload.retry_delay,
        title_template=title_template,
        body_template=body_template,
        categories=categories_dict,
        templates=templates_config,
    )

    backup = cfg_path.read_text(encoding=YAML_ENCODING) if cfg_path.exists() else None
    try:
        _write_notifications_config(cfg_path, new_config.model_dump(exclude_none=True))
        reload_config()
        refreshed = _notifications_from_settings()

        context = get_context()
        if context.has_service("notifications"):
            service = context.get_service("notifications")
            if isinstance(service, NotificationService):
                await service.shutdown()
        service_instance = NotificationService(refreshed, quota_guard=NotificationQuotaGuard())
        context.register_service("notifications", service_instance)

        return _build_notification_response(refreshed)
    except Exception as exc:
        if backup is not None:
            cfg_path.write_text(backup, encoding=YAML_ENCODING)
            reload_config()
        raise HTTPException(status_code=500, detail=f"保存通知配置失败: {exc}") from exc


# ==================== Send & quota endpoints ====================


class NotificationResponse(BaseModel):
    success: bool
    channel: str
    category: str
    status_code: Optional[int] = None
    quota: Optional[Dict[str, Any]] = None
    response: Optional[Any] = None


class QuotaSnapshotResponse(BaseModel):
    success: bool
    data: Dict[str, Dict[str, Dict[str, Any]]]


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    payload: NotificationPayload,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    try:
        result = await service.send(
            title=payload.title,
            content=payload.content,
            channel=payload.channel,
            category=payload.category,
            bypass_quota=payload.bypass_quota,
            # Bark specific parameters
            url=payload.url,
            group=payload.group,
            icon=payload.icon,
            sound=payload.sound,
            call=payload.call,
            level=payload.level,
            bark_server_names=payload.bark_server_names,
            bark_template_name=payload.bark_template_name,
        )
    except ChannelNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except CategoryNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except NotificationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except QuotaExceededError as exc:
        ctx = exc.context
        detail = {
            "message": str(exc),
            "quota": {
                "channel": ctx.channel,
                "category": ctx.category,
                "max_per_window": ctx.max_per_window,
                "current_count": ctx.current_count,
                "window_seconds": ctx.window_seconds,
                "reset_seconds": ctx.reset_seconds,
            },
        }
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail) from exc
    except NotificationDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail or str(exc)
        ) from exc
    except NotificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    quota_info: Optional[Dict[str, Any]] = None
    if result.quota:
        quota_info = {
            "max_per_window": result.quota.max_per_window,
            "current_count": result.quota.current_count,
            "remaining": result.quota.remaining,
            "window_seconds": result.quota.window_seconds,
            "reset_seconds": result.quota.reset_seconds,
        }

    return NotificationResponse(
        success=True,
        channel=result.channel,
        category=result.category,
        status_code=result.status_code,
        quota=quota_info,
        response=result.response_data,
    )


@router.get("/quotas", response_model=QuotaSnapshotResponse)
async def get_quota_status(
    service: NotificationService = Depends(get_notification_service),
) -> QuotaSnapshotResponse:
    data = await service.get_quota_status()
    return QuotaSnapshotResponse(success=True, data=data)


@router.post("/quotas/reset", response_model=Dict[str, bool])
async def reset_quota_status(
    service: NotificationService = Depends(get_notification_service),
) -> Dict[str, bool]:
    await service.reset_quotas()
    return {"success": True}
