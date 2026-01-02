"""通知推送服务实现。"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from deepsearch.config.models.notifications import (
    BarkServerConfig,
    NotificationCategoryConfig,
    NotificationsConfig,
)

from .client import XtuisClient
from .exceptions import (
    CategoryNotAllowedError,
    ChannelNotConfiguredError,
    NotificationDispatchError,
    NotificationError,
    NotificationValidationError,
    QuotaExceededContext,
    QuotaExceededError,
)
from .models import NotificationResult, QuotaDecision
from .quota import NotificationQuotaGuard

WECHAT_TITLE_MAX_LENGTH = 32


class NotificationService:
    """面向业务的通知推送服务。"""

    def __init__(
        self,
        config: NotificationsConfig,
        client: Optional[XtuisClient] = None,
        quota_guard: Optional[NotificationQuotaGuard] = None,
    ) -> None:
        self._config = config
        self._client = client or XtuisClient(
            base_urls=config.base_urls,
            timeout=config.request_timeout,
        )
        self._quota_guard = quota_guard or NotificationQuotaGuard()
        self._logger = logger.bind(component="NotificationService")

    @property
    def enabled(self) -> bool:
        return bool(self._config.enabled)

    async def send(
        self,
        title: str,
        content: Optional[str] = None,
        *,
        channel: Optional[str] = None,
        category: str = "default",
        bypass_quota: bool = False,
        # Bark 专用参数
        url: Optional[str] = None,
        group: Optional[str] = None,
        icon: Optional[str] = None,
        sound: Optional[str] = None,
        call: bool = False,
        level: Optional[str] = None,
        bark_server_names: Optional[list[str]] = None,
        # 新增 Bark 参数
        subtitle: Optional[str] = None,
        image: Optional[str] = None,
        copy: Optional[str] = None,
        auto_copy: bool = False,
        is_archive: Optional[bool] = None,
        badge: Optional[int] = None,
        use_markdown: bool = False,
        # 模板参数
        bark_template_name: Optional[str] = None,
    ) -> NotificationResult:
        """发送通知。

        Args:
            title: 通知标题
            content: 通知内容
            channel: 推送渠道 (wechat/bark)，None 时使用默认渠道列表的第一个
            category: 额度类别
            bypass_quota: 是否绕过额度限制
            url: Bark - 点击跳转 URL
            group: Bark - 通知分组
            icon: Bark - 自定义图标 URL
            sound: Bark - 通知声音
            call: Bark - 是否重复响铃 30 秒
            level: Bark - 通知级别 (active/timeSensitive/passive/critical)
            bark_server_names: 指定要推送的 Bark 服务器名称列表，None 表示所有已启用
        """
        if not self.enabled:
            raise NotificationError("通知推送功能未启用")

        if not title:
            raise ValueError("通知标题不能为空")

        # 处理默认渠道（可能是列表或字符串）
        default_ch_raw = self._config.default_channel
        default_ch_str: str = "wechat"
        if isinstance(default_ch_raw, list):
            default_ch_str = default_ch_raw[0] if default_ch_raw else "wechat"
        elif isinstance(default_ch_raw, str):
            default_ch_str = default_ch_raw
        normalized_channel = (channel or default_ch_str).lower()
        normalized_category = (category or "default").lower()

        if normalized_channel == "wechat" and len(title) > WECHAT_TITLE_MAX_LENGTH:
            raise NotificationValidationError(
                f"微信推送标题长度需不超过 {WECHAT_TITLE_MAX_LENGTH} 个字符"
            )

        # 检查渠道是否配置
        if normalized_channel == "bark":
            bark_servers = self._config.get_enabled_bark_servers()
            if not bark_servers and not self._config.bark_token:
                raise ChannelNotConfiguredError(normalized_channel)
        else:
            token = self._config.get_token(normalized_channel)
            if not token:
                raise ChannelNotConfiguredError(normalized_channel)

        category_config = self._resolve_category_config(normalized_category)
        if (
            category_config
            and category_config.channels
            and normalized_channel not in category_config.channels
        ):
            raise CategoryNotAllowedError(normalized_category, normalized_channel)

        quota_decision: Optional[QuotaDecision] = None
        if not bypass_quota:
            quota_decision = await self._quota_guard.check_and_consume(
                normalized_channel,
                normalized_category,
                category_config,
            )
            if not quota_decision.allowed:
                context = QuotaExceededContext(
                    channel=normalized_channel,
                    category=normalized_category,
                    max_per_window=quota_decision.max_per_window,
                    current_count=quota_decision.current_count,
                    window_seconds=quota_decision.window_seconds,
                    reset_seconds=quota_decision.reset_seconds,
                )
                raise QuotaExceededError(context)

        # Bark 渠道：发送到所有启用的服务器或指定服务器
        if normalized_channel == "bark":
            # 应用 Bark 模板（如果指定）
            effective_title = title
            effective_content = content
            effective_subtitle = subtitle
            effective_use_markdown = use_markdown
            effective_level = level
            effective_sound = sound
            effective_icon = icon
            effective_image = image
            effective_group = group
            effective_url = url
            effective_copy = copy
            effective_auto_copy = auto_copy
            effective_is_archive = is_archive
            effective_call = call
            effective_badge = badge

            # 查找并应用模板
            template_name = bark_template_name or self._config.templates.default_bark
            if template_name:
                template = self._config.templates.get_bark_template(template_name)
                if template:
                    # 应用模板的标题和内容模板
                    if template.title_template:
                        effective_title = template.title_template.replace("{title}", title).replace(
                            "{content}", content or ""
                        )
                    if template.body_template:
                        effective_content = template.body_template.replace(
                            "{title}", title
                        ).replace("{content}", content or "")
                    if template.subtitle_template:
                        effective_subtitle = template.subtitle_template.replace(
                            "{title}", title
                        ).replace("{content}", content or "")
                    # 应用模板的其他参数（模板参数优先，除非已显式传入）
                    if template.use_markdown and not use_markdown:
                        effective_use_markdown = template.use_markdown
                    if template.level and not level:
                        effective_level = template.level
                    if template.sound and not sound:
                        effective_sound = template.sound
                    if template.icon and not icon:
                        effective_icon = template.icon
                    if template.image and not image:
                        effective_image = template.image
                    if template.group and not group:
                        effective_group = template.group
                    if template.url and not url:
                        effective_url = template.url
                    if template.copy_content and not copy:
                        effective_copy = template.copy_content
                    if template.auto_copy and not auto_copy:
                        effective_auto_copy = template.auto_copy
                    if template.is_archive is not None and is_archive is None:
                        effective_is_archive = template.is_archive
                    if template.call and not call:
                        effective_call = template.call
                    if template.badge is not None and badge is None:
                        effective_badge = template.badge

                    self._logger.debug(
                        "应用 Bark 模板",
                        template=template_name,
                        title=effective_title[:50] if effective_title else None,
                    )

            return await self._send_bark_multi(
                title=effective_title,
                content=effective_content,
                category=normalized_category,
                quota_decision=quota_decision,
                url=effective_url,
                group=effective_group,
                icon=effective_icon,
                sound=effective_sound,
                call=effective_call,
                level=effective_level,
                server_names=bark_server_names,
                subtitle=effective_subtitle,
                image=effective_image,
                copy=effective_copy,
                auto_copy=effective_auto_copy,
                is_archive=effective_is_archive,
                badge=effective_badge,
                use_markdown=effective_use_markdown,
            )

        # 其他渠道（微信）：使用原有逻辑
        return await self._send_single(
            channel=normalized_channel,
            token=self._config.get_token(normalized_channel) or "",
            title=title,
            content=content,
            category=normalized_category,
            quota_decision=quota_decision,
        )

    async def _send_bark_multi(
        self,
        title: str,
        content: Optional[str],
        category: str,
        quota_decision: Optional[QuotaDecision],
        url: Optional[str] = None,
        group: Optional[str] = None,
        icon: Optional[str] = None,
        sound: Optional[str] = None,
        call: bool = False,
        level: Optional[str] = None,
        server_names: Optional[list[str]] = None,
        # 新增 Bark 参数
        subtitle: Optional[str] = None,
        image: Optional[str] = None,
        copy: Optional[str] = None,
        auto_copy: bool = False,
        is_archive: Optional[bool] = None,
        badge: Optional[int] = None,
        use_markdown: bool = False,
    ) -> NotificationResult:
        """向所有启用的 Bark 服务器发送通知。

        Args:
            server_names: 如果提供，仅向这些名称的服务器发送；None = 所有已启用
        """
        bark_servers = self._config.get_enabled_bark_servers()

        # 如果指定了服务器名称，过滤
        if server_names is not None:
            bark_servers = [s for s in bark_servers if s.name in server_names]

        # 向后兼容：如果没有配置 bark_servers 但有 bark_token
        if not bark_servers and self._config.bark_token:
            legacy_server = BarkServerConfig(
                name="默认 Bark",
                base_url=self._config.base_urls.bark,
                token=self._config.bark_token,
                enabled=True,
            )
            bark_servers = [legacy_server]

        if not bark_servers:
            raise ChannelNotConfiguredError("bark")

        results: List[Dict[str, Any]] = []
        last_success_response: Optional[httpx.Response] = None
        success_count = 0
        fail_count = 0

        for server in bark_servers:
            try:
                response = await self._send_bark_to_server(
                    server=server,
                    title=title,
                    content=content,
                    subtitle=subtitle,
                    url=url,
                    group=group,
                    icon=icon,
                    image=image,
                    sound=sound,
                    call=call,
                    level=level,
                    copy=copy,
                    auto_copy=auto_copy,
                    is_archive=is_archive,
                    badge=badge,
                    use_markdown=use_markdown,
                )
                if response.status_code < 400:
                    success_count += 1
                    last_success_response = response
                    results.append(
                        {
                            "server": server.name,
                            "success": True,
                            "status_code": response.status_code,
                        }
                    )
                    self._logger.info(
                        "Bark 通知发送成功",
                        server=server.name,
                        status=response.status_code,
                    )
                else:
                    fail_count += 1
                    results.append(
                        {
                            "server": server.name,
                            "success": False,
                            "status_code": response.status_code,
                            "error": f"HTTP {response.status_code}",
                        }
                    )
                    self._logger.warning(
                        "Bark 通知发送失败",
                        server=server.name,
                        status=response.status_code,
                    )
            except Exception as exc:
                fail_count += 1
                results.append(
                    {
                        "server": server.name,
                        "success": False,
                        "error": str(exc),
                    }
                )
                self._logger.warning(
                    "Bark 通知发送异常",
                    server=server.name,
                    error=str(exc),
                )

        if success_count == 0:
            raise NotificationDispatchError("bark", f"所有 {len(bark_servers)} 个服务器均发送失败")

        return NotificationResult(
            success=True,
            channel="bark",
            category=category,
            status_code=last_success_response.status_code if last_success_response else None,
            response_data={
                "servers": results,
                "success_count": success_count,
                "fail_count": fail_count,
            },
            quota=quota_decision,
        )

    async def _send_bark_to_server(
        self,
        server: BarkServerConfig,
        title: str,
        content: Optional[str],
        url: Optional[str] = None,
        group: Optional[str] = None,
        icon: Optional[str] = None,
        sound: Optional[str] = None,
        call: bool = False,
        level: Optional[str] = None,
        # 新增 Bark 参数
        subtitle: Optional[str] = None,
        image: Optional[str] = None,
        copy: Optional[str] = None,
        auto_copy: bool = False,
        is_archive: Optional[bool] = None,
        badge: Optional[int] = None,
        use_markdown: bool = False,
    ) -> httpx.Response:
        """向单个 Bark 服务器发送通知（带重试）。"""
        attempts = max(1, int(self._config.retry_attempts) + 1)
        last_error: Optional[str] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.send_bark(
                    server=server,
                    title=title,
                    content=content,
                    subtitle=subtitle,
                    url=url,
                    group=group,
                    icon=icon,
                    image=image,
                    sound=sound,
                    call=call,
                    level=level,
                    copy=copy,
                    auto_copy=auto_copy,
                    is_archive=is_archive,
                    badge=badge,
                    use_markdown=use_markdown,
                )
                return response
            except httpx.RequestError as exc:
                last_error = str(exc)
                if attempt < attempts:
                    await asyncio.sleep(self._config.retry_delay)

        raise httpx.RequestError(last_error or "未知错误")

    async def _send_single(
        self,
        channel: str,
        token: str,
        title: str,
        content: Optional[str],
        category: str,
        quota_decision: Optional[QuotaDecision],
    ) -> NotificationResult:
        """发送到单个渠道（微信等）。"""
        attempts = max(1, int(self._config.retry_attempts) + 1)
        last_error: Optional[str] = None
        response: Optional[httpx.Response] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.send(
                    channel=channel,
                    token=token,
                    title=title,
                    content=content,
                )
                if response.status_code < 400:
                    result = NotificationResult(
                        success=True,
                        channel=channel,
                        category=category,
                        status_code=response.status_code,
                        response_data=self._extract_response_payload(response),
                        quota=quota_decision,
                    )
                    self._logger.info(
                        "通知发送成功",
                        channel=channel,
                        category=category,
                        status=response.status_code,
                    )
                    return result

                last_error = f"HTTP {response.status_code}"
                self._logger.warning(
                    "通知发送失败",
                    channel=channel,
                    category=category,
                    status=response.status_code,
                )
            except httpx.RequestError as exc:
                last_error = str(exc)
                self._logger.warning(
                    "通知发送异常",
                    channel=channel,
                    category=category,
                    attempt=attempt,
                    error=str(exc),
                )

            if attempt < attempts:
                await asyncio.sleep(self._config.retry_delay)

        raise NotificationDispatchError(channel, last_error or "未知错误")

    async def get_quota_status(self) -> dict:
        """返回当前额度状态。"""
        return await self._quota_guard.snapshot()

    async def reset_quotas(self) -> None:
        """清空额度计数。"""
        await self._quota_guard.reset()

    async def shutdown(self) -> None:
        """释放资源。"""
        await self._client.aclose()

    def _resolve_category_config(self, category: str) -> Optional[NotificationCategoryConfig]:
        return self._config.get_category(category)

    @staticmethod
    def _extract_response_payload(response: httpx.Response):
        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text[:512]}
        return data
