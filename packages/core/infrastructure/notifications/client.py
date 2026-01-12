"""虾推啥推送客户端。"""

from __future__ import annotations

import urllib.parse
from typing import Any, Optional

import httpx
from core.config.models.notifications import BarkServerConfig, NotificationBaseUrls
from loguru import logger


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
        """发送推送请求（向后兼容旧版单服务器方式）。"""
        if not token:
            raise ValueError("推送 token 不能为空")

        base_url = self._base_urls.get(channel).rstrip("/")

        # Bark 和微信使用不同的 API 格式
        if channel.lower() == "bark":
            # Bark 官方格式: /{key}/{title}/{body} 或 /{key}/{title}
            encoded_title = urllib.parse.quote(title, safe="")
            if content:
                encoded_content = urllib.parse.quote(content, safe="")
                url = f"{base_url}/{token}/{encoded_title}/{encoded_content}"
            else:
                url = f"{base_url}/{token}/{encoded_title}"
            params = {}
        else:
            # 虾推啥微信格式: /{token}.send?text=...&desp=...
            url = f"{base_url}/{token}.send"
            params = {"text": title}
            if content:
                params["desp"] = content

        logger.debug(
            "发送虾推啥通知",
            channel=channel,
            url=url,
            params_preview={k: v for k, v in params.items() if k != "desp"} if params else {},
        )
        response = await self._client.get(url, params=params if params else None)
        return response

    async def send_bark(
        self,
        server: BarkServerConfig,
        title: str,
        content: Optional[str] = None,
        *,
        # 完整 Bark API 参数
        subtitle: Optional[str] = None,
        url: Optional[str] = None,
        group: Optional[str] = None,
        icon: Optional[str] = None,
        image: Optional[str] = None,
        sound: Optional[str] = None,
        call: bool = False,
        level: Optional[str] = None,
        copy: Optional[str] = None,
        auto_copy: bool = False,
        is_archive: Optional[bool] = None,
        badge: Optional[int] = None,
        use_markdown: bool = False,
    ) -> httpx.Response:
        """发送 Bark 推送请求（支持完整 Bark API 参数）。

        Args:
            server: Bark 服务器配置
            title: 推送标题
            content: 推送内容
            subtitle: 副标题
            url: 点击跳转 URL
            group: 通知分组
            icon: 自定义图标 URL（iOS 15+）
            image: 通知配图 URL
            sound: 通知声音
            call: 是否持续响铃直到用户操作
            level: 通知级别 (active/timeSensitive/passive/critical)
            copy: 复制内容
            auto_copy: 是否自动复制
            is_archive: 是否归档
            badge: App 角标数字
            use_markdown: 是否使用 Markdown 格式
        """
        base_url = server.base_url.rstrip("/")

        # 检测是否是虾推啥托管的 Bark 服务器
        # 虾推啥使用 WeChat 风格的 API: /{token}.send?text=...&desp=...
        # 官方 Bark 使用路径风格或 POST JSON
        is_xtuis = "xtuis.cn" in base_url.lower()

        if is_xtuis:
            # 虾推啥需要 token（设备 key）
            if not server.token:
                raise ValueError("虾推啥 Bark 服务器需要填写设备 Key")

            # 虾推啥需要先注册设备才能发送
            register_url = f"{base_url}?xia={server.token}"
            logger.debug("注册虾推啥 Bark 设备", url=register_url)
            try:
                await self._client.get(register_url)
            except Exception as e:
                logger.warning("虾推啥 Bark 设备注册失败（可能已注册）", error=str(e))

            # 虾推啥 Bark 发送格式: /{token}.send?text=...&desp=...
            request_url = f"{base_url}/{server.token}.send"
            params: dict[str, str] = {"text": title}
            if content:
                params["desp"] = content

            logger.debug("发送虾推啥 Bark 通知", server=server.name, url=request_url)
            response = await self._client.get(request_url, params=params)
            return response

        # 官方 Bark：使用 POST JSON 格式支持完整参数
        # 构建 POST JSON body
        body: dict[str, Any] = {
            "title": title,
        }

        # 确定 device_key：从 token 或 URL 路径提取
        if server.token:
            body["device_key"] = server.token
        else:
            # 从 URL 路径提取 key，如 https://api.day.app/YOUR_KEY
            path_parts = base_url.split("/")
            if len(path_parts) > 3:
                body["device_key"] = path_parts[-1]
                base_url = "/".join(path_parts[:-1])

        # Markdown 或普通 body
        if use_markdown and content:
            body["markdown"] = content
        elif content:
            body["body"] = content

        # 其他参数（优先使用传入参数，回退到服务器默认配置）
        if subtitle:
            body["subtitle"] = subtitle
        if url:
            body["url"] = url
        if group or server.group:
            body["group"] = group or server.group
        if icon or server.icon:
            body["icon"] = icon or server.icon
        if image:
            body["image"] = image
        if sound or server.sound:
            body["sound"] = sound or server.sound
        if call:
            body["call"] = "1"
        if level or server.level:
            body["level"] = level or server.level
        if copy:
            body["copy"] = copy
        if auto_copy:
            body["autoCopy"] = "1"
        if is_archive is not None:
            body["isArchive"] = "1" if is_archive else "0"
        if badge is not None:
            body["badge"] = badge

        # POST 到 /push 端点
        push_url = f"{base_url}/push"

        logger.debug(
            "发送 Bark 通知 (POST)",
            server=server.name,
            url=push_url,
            body_keys=list(body.keys()),
        )

        response = await self._client.post(
            push_url, json=body, headers={"Content-Type": "application/json; charset=utf-8"}
        )
        return response

    async def aclose(self) -> None:
        """关闭底层 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "XtuisClient":  # pragma: no cover - 方便 with 使用
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        await self.aclose()
