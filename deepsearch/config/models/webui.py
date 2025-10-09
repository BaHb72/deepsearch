"""
WebUI 配置模型定义。

本模块定义了 WebUI 前后端服务的配置模型。
"""

from typing import Optional

from pydantic import BaseModel, Field


class WebUIConfig(BaseModel):
    """WebUI 配置。"""

    # 组件启用状态
    enabled: bool = Field(default=True, description="是否启用WebUI组件")

    # 后端 API 服务配置
    backend_host: str = Field(default="127.0.0.1", description="后端服务监听地址")
    backend_port: int = Field(default=8000, description="后端服务端口")

    # 前端开发服务器配置
    frontend_enabled: bool = Field(default=True, description="是否启动前端开发服务器")
    frontend_host: str = Field(default="localhost", description="前端服务监听地址")
    frontend_port: int = Field(default=3000, description="前端服务端口")

    # 通用配置
    enable_cors: bool = Field(default=True, description="是否启用跨域资源共享")
    reload: bool = Field(default=False, description="是否启用热重载")
    workers: Optional[int] = Field(default=None, description="工作进程数量，None 表示使用默认值")

    class Config:
        """Pydantic 配置。"""

        extra = "forbid"
