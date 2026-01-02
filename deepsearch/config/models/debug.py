"""
调试配置模型。
"""

from pydantic import BaseModel


class DebugConfig(BaseModel):
    """调试配置。"""

    enable_profiling: bool = False
    enable_tracing: bool = False
    log_sql: bool = False
