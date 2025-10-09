"""虾推啥推送客户端。"""

from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from deepsearch.config.models.notifications import NotificationBaseUrls


class XtuisClient:
    """封装虾推啥推送所需的 HTTP 请求。"""

    def __init__(
        self,
        base_urls: Optional[NotificationBaseUrls] = None,
        timeout: float = 5.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_urls = base_urls or NotificationBaseUrls()
        self._timeout = timeout
        self._client = http_client or httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": "DeepSearch-Notifier/1.0"}
        )
        self._owns_client = http_client is None

    async def send(
        self,
        channel: str,
        token: str,
        title: str,
        content: Optional[str] = None,
    ) -> httpx.Response:
        """发送推送请求。"""
        if not token:
            raise ValueError("推送 token 不能为空")

        base_url = self._base_urls.get(channel).rstrip("/")
        url = f"{base_url}/{token}.send"
        params = {"text": title}
        if content:
            params["desp"] = content

        logger.debug(
            "发送虾推啥通知",
            channel=channel,
            url=url,
            params_preview={k: v for k, v in params.items() if k != "desp"},
        )
        response = await self._client.get(url, params=params)
        return response

    async def aclose(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "XtuisClient":  # pragma: no cover - 方便 with 使用
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        await self.aclose()
