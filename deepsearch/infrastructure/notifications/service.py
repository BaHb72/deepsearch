"""通知推送服务实现。"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from loguru import logger

from deepsearch.config.models.notifications import NotificationCategoryConfig, NotificationsConfig

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
    ) -> NotificationResult:
        """发送通知。"""
        if not self.enabled:
            raise NotificationError("通知推送功能未启用")

        if not title:
            raise ValueError("通知标题不能为空")

        normalized_channel = (channel or self._config.default_channel or "wechat").lower()
        normalized_category = (category or "default").lower()

        if normalized_channel == "wechat" and len(title) > WECHAT_TITLE_MAX_LENGTH:
            raise NotificationValidationError(
                f"微信推送标题长度需不超过 {WECHAT_TITLE_MAX_LENGTH} 个字符"
            )

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

        attempts = max(1, int(self._config.retry_attempts) + 1)
        last_error: Optional[str] = None
        response: Optional[httpx.Response] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.send(
                    channel=normalized_channel,
                    token=token,
                    title=title,
                    content=content,
                )
                if response.status_code < 400:
                    result = NotificationResult(
                        success=True,
                        channel=normalized_channel,
                        category=normalized_category,
                        status_code=response.status_code,
                        response_data=self._extract_response_payload(response),
                        quota=quota_decision,
                    )
                    self._logger.info(
                        "通知发送成功",
                        channel=normalized_channel,
                        category=normalized_category,
                        status=response.status_code,
                    )
                    return result

                last_error = f"HTTP {response.status_code}"
                self._logger.warning(
                    "通知发送失败",
                    channel=normalized_channel,
                    category=normalized_category,
                    status=response.status_code,
                )
            except httpx.RequestError as exc:
                last_error = str(exc)
                self._logger.warning(
                    "通知发送异常",
                    channel=normalized_channel,
                    category=normalized_category,
                    attempt=attempt,
                    error=str(exc),
                )

            if attempt < attempts:
                await asyncio.sleep(self._config.retry_delay)

        raise NotificationDispatchError(normalized_channel, last_error or "未知错误")

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
