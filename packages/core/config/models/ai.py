"""
AI 分析服务配置模型
"""

from pydantic import BaseModel, Field


class AiConfig(BaseModel):
    """AI 分析服务配置"""

    enabled: bool = Field(default=False, description="是否启用 AI 分析服务")
    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama 服务地址",
    )
    model: str = Field(default="deepseek-v3", description="使用的模型名称")
    timeout: float = Field(default=120.0, gt=0, description="请求超时时间（秒）")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=4096, gt=0, description="最大生成 token 数")
    system_prompt: str = Field(
        default="你是一位专业的量化投资分析师，擅长解读投资者互动问答和时事新闻，为决策者提供客观、严谨的投资建议。",
        description="系统提示词",
    )
