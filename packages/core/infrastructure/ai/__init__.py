"""
AI 分析服务模块

提供基于本地 DeepSeek 模型（通过 Ollama）的智能分析能力。
"""

from .ai_analysis_service import AiAnalysisService
from .ai_client import AiClient

__all__ = ["AiClient", "AiAnalysisService"]
