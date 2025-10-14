from __future__ import annotations

"""
数据库连接配置的 Pydantic 模型。

用于校验和序列化 database_connections.<env>.yaml 中的连接条目。
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConnectionConfigModel(BaseModel):
    """单个数据库连接配置条目。"""

    id: Optional[int] = Field(default=None, description="连接唯一标识")
    name: Optional[str] = Field(default=None, description="连接名称")
    type: Optional[str] = Field(default=None, description="连接类型")
    host: Optional[str] = Field(default=None, description="主机地址")
    port: Optional[int] = Field(default=None, description="端口")
    database: Optional[str] = Field(default=None, description="数据库名称或路径")
    username: Optional[str] = Field(default=None, description="登录用户名")
    password: Optional[str] = Field(default=None, description="登录密码（可能为加密串或掩码）")
    enabled: Optional[bool] = Field(default=True, description="是否启用该连接")
    status: Optional[str] = Field(default=None, description="当前状态")
    options: Dict[str, Any] = Field(default_factory=dict, description="额外的连接配置")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="最近更新时间")
    last_test_time: Optional[datetime] = Field(default=None, description="最近一次测试时间")
    last_test_result: Optional[str] = Field(default=None, description="最近一次测试结果")

    model_config = ConfigDict(extra="allow", populate_by_name=True)
