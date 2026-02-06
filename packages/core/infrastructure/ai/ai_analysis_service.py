"""
AI 分析服务

负责从数据层获取数据、组装 Prompt、调用 AI 模型，返回分析结果。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from loguru import logger

from .prompt_templates import (
    GENERAL_ANALYSIS_TEMPLATE,
    INVESTOR_QA_TEMPLATE,
    NEWS_ANALYSIS_TEMPLATE,
)

if TYPE_CHECKING:
    from core.config.models.ai import AiConfig

    from .ai_client import AiClient


class AiAnalysisService:
    """AI 分析服务"""

    def __init__(self, ai_client: AiClient, config: AiConfig) -> None:
        self._client = ai_client
        self._config = config

    def _build_messages(self, user_content: str) -> list[dict]:
        """构建包含系统提示词的消息列表。"""
        return [
            {"role": "system", "content": self._config.system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def analyze_investor_qa(
        self,
        symbol: str,
        qa_data: str,
        query: str,
    ) -> str:
        """解读投资者互动问答（非流式）。"""
        prompt = INVESTOR_QA_TEMPLATE.format(
            symbol=symbol,
            qa_data=qa_data,
            query=query,
        )
        messages = self._build_messages(prompt)
        logger.info(f"AI 分析投资者互问: symbol={symbol}")
        return await self._client.chat(messages)

    async def analyze_investor_qa_stream(
        self,
        symbol: str,
        qa_data: str,
        query: str,
    ) -> AsyncIterator[str]:
        """解读投资者互动问答（流式）。"""
        prompt = INVESTOR_QA_TEMPLATE.format(
            symbol=symbol,
            qa_data=qa_data,
            query=query,
        )
        messages = self._build_messages(prompt)
        logger.info(f"AI 流式分析投资者互问: symbol={symbol}")
        async for token in self._client.chat_stream(messages):
            yield token

    async def analyze_news(
        self,
        keywords: list[str],
        news_data: str,
        query: str,
    ) -> str:
        """解读时事新闻对投资的影响（非流式）。"""
        prompt = NEWS_ANALYSIS_TEMPLATE.format(
            keywords=", ".join(keywords),
            news_data=news_data,
            query=query,
        )
        messages = self._build_messages(prompt)
        logger.info(f"AI 分析新闻: keywords={keywords}")
        return await self._client.chat(messages)

    async def analyze_news_stream(
        self,
        keywords: list[str],
        news_data: str,
        query: str,
    ) -> AsyncIterator[str]:
        """解读时事新闻对投资的影响（流式）。"""
        prompt = NEWS_ANALYSIS_TEMPLATE.format(
            keywords=", ".join(keywords),
            news_data=news_data,
            query=query,
        )
        messages = self._build_messages(prompt)
        logger.info(f"AI 流式分析新闻: keywords={keywords}")
        async for token in self._client.chat_stream(messages):
            yield token

    async def analyze_general(
        self,
        context: str,
        query: str,
    ) -> str:
        """通用分析（非流式）。"""
        prompt = GENERAL_ANALYSIS_TEMPLATE.format(context=context, query=query)
        messages = self._build_messages(prompt)
        return await self._client.chat(messages)

    async def analyze_general_stream(
        self,
        context: str,
        query: str,
    ) -> AsyncIterator[str]:
        """通用分析（流式）。"""
        prompt = GENERAL_ANALYSIS_TEMPLATE.format(context=context, query=query)
        messages = self._build_messages(prompt)
        async for token in self._client.chat_stream(messages):
            yield token
