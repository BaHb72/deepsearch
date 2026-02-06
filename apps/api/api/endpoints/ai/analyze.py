"""
AI 分析端点

提供投资者互问解读、时事新闻分析、通用流式分析和健康检查。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ── Request / Response 模型 ──────────────────────────────────


class InvestorQaRequest(BaseModel):
    symbol: str = Field(..., description="股票代码")
    qa_data: str = Field(..., description="投资者互动问答原始数据")
    query: str = Field(..., description="用户问题")
    stream: bool = Field(default=False, description="是否使用流式响应")


class NewsAnalysisRequest(BaseModel):
    keywords: List[str] = Field(..., description="新闻关键词列表")
    news_data: str = Field(..., description="新闻原始数据")
    query: str = Field(..., description="用户问题")
    stream: bool = Field(default=False, description="是否使用流式响应")


class GeneralAnalysisRequest(BaseModel):
    context: str = Field(..., description="上下文数据")
    query: str = Field(..., description="用户问题")


class AnalysisResponse(BaseModel):
    result: str = Field(..., description="分析结果")
    model: str = Field(..., description="使用的模型")


# ── 辅助函数 ─────────────────────────────────────────────────


def _get_ai_service(request: Request):
    """从 app.state 获取 AI 分析服务实例。"""
    service = getattr(request.app.state, "ai_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="AI 分析服务未启用或不可用")
    return service


def _get_ai_config(request: Request):
    """从 app.state 获取 AI 配置。"""
    config = getattr(request.app.state, "ai_config", None)
    if config is None:
        raise HTTPException(status_code=503, detail="AI 配置不可用")
    return config


async def _sse_generator(stream_iter):
    """将异步迭代器包装为 SSE 格式。"""
    try:
        async for token in stream_iter:
            data = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


# ── 端点 ─────────────────────────────────────────────────────


@router.post("/analyze/investor-qa", response_model=AnalysisResponse)
async def analyze_investor_qa(body: InvestorQaRequest, request: Request):
    """解读投资者互动问答"""
    service = _get_ai_service(request)
    config = _get_ai_config(request)

    if body.stream:
        stream = service.analyze_investor_qa_stream(
            symbol=body.symbol,
            qa_data=body.qa_data,
            query=body.query,
        )
        return StreamingResponse(
            _sse_generator(stream),
            media_type="text/event-stream",
        )

    result = await service.analyze_investor_qa(
        symbol=body.symbol,
        qa_data=body.qa_data,
        query=body.query,
    )
    return AnalysisResponse(result=result, model=config.model)


@router.post("/analyze/news", response_model=AnalysisResponse)
async def analyze_news(body: NewsAnalysisRequest, request: Request):
    """解读时事新闻对投资的影响"""
    service = _get_ai_service(request)
    config = _get_ai_config(request)

    if body.stream:
        stream = service.analyze_news_stream(
            keywords=body.keywords,
            news_data=body.news_data,
            query=body.query,
        )
        return StreamingResponse(
            _sse_generator(stream),
            media_type="text/event-stream",
        )

    result = await service.analyze_news(
        keywords=body.keywords,
        news_data=body.news_data,
        query=body.query,
    )
    return AnalysisResponse(result=result, model=config.model)


@router.post("/analyze/stream")
async def analyze_stream(body: GeneralAnalysisRequest, request: Request):
    """通用流式分析（SSE）"""
    service = _get_ai_service(request)

    stream = service.analyze_general_stream(
        context=body.context,
        query=body.query,
    )
    return StreamingResponse(
        _sse_generator(stream),
        media_type="text/event-stream",
    )


@router.get("/health")
async def ai_health(request: Request) -> Dict[str, Any]:
    """AI 服务健康检查"""
    ai_client = getattr(request.app.state, "ai_client", None)
    ai_config = getattr(request.app.state, "ai_config", None)

    if ai_client is None or ai_config is None:
        return {"status": "disabled", "message": "AI 服务未启用"}

    healthy = await ai_client.health_check()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "model": ai_config.model,
        "base_url": ai_config.base_url,
    }
