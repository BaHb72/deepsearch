"""
Ollama HTTP 调用客户端

通过 httpx 异步调用本地 Ollama 服务的 /api/chat 端点。
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx
from core.config.models.ai import AiConfig
from loguru import logger


class AiClientError(Exception):
    """AI 客户端错误"""


class AiClient:
    """Ollama AI 客户端"""

    def __init__(self, config: AiConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout, connect=10.0),  # type: ignore[attr-defined]
        )

    async def chat(self, messages: list[dict]) -> str:
        """发送聊天请求，返回完整响应文本。"""
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }
        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()  # type: ignore[attr-defined]
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except httpx.HTTPStatusError as e:  # type: ignore[attr-defined]
            raise AiClientError(f"Ollama 返回错误状态码: {e.response.status_code}") from e
        except httpx.ConnectError as e:  # type: ignore[attr-defined]
            raise AiClientError(f"无法连接 Ollama 服务 ({self._config.base_url})") from e
        except Exception as e:
            raise AiClientError(f"AI 请求失败: {e}") from e

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """发送聊天请求，流式返回 token。"""
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:  # type: ignore[attr-defined]
                resp.raise_for_status()  # type: ignore[attr-defined]
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    import json

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done", False):
                        return
        except httpx.HTTPStatusError as e:  # type: ignore[attr-defined]
            raise AiClientError(f"Ollama 流式请求失败: {e.response.status_code}") from e
        except httpx.ConnectError as e:  # type: ignore[attr-defined]
            raise AiClientError(f"无法连接 Ollama 服务 ({self._config.base_url})") from e
        except Exception as e:
            raise AiClientError(f"AI 流式请求失败: {e}") from e

    async def health_check(self) -> bool:
        """检查 Ollama 服务是否可用且模型已加载。"""
        try:
            resp = await self._client.get("/api/tags", timeout=5.0)
            resp.raise_for_status()  # type: ignore[attr-defined]
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            # 检查目标模型是否存在（支持带标签和不带标签的匹配）
            target = self._config.model
            available = any(target in m or m.startswith(target) for m in models)
            if not available:
                logger.warning(f"Ollama 中未找到模型 {target}，可用模型: {models}")
            return available
        except Exception as e:
            logger.debug(f"Ollama 健康检查失败: {e}")
            return False

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        await self._client.aclose()
