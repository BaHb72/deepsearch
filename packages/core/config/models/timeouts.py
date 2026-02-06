"""
统一超时配置模型

将散落在代码各处的硬编码超时值集中到 YAML 配置文件管理，
支持按环境（dev/prod）调整，避免同一超时概念出现多个不一致的值。
"""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field


class ProviderTimeoutProfile(BaseModel):
    """单个数据源的操作超时配置

    与 packages/core/utils/timeout/config.py 中的 TimeoutConfig 对齐，
    提供 Pydantic 模型以便从 YAML 加载。
    """

    idle: float = Field(default=5.0, gt=0, description="空闲时的快速超时（秒）")
    connect: float = Field(default=90.0, gt=0, description="连接/登录超时（秒）")
    fetch: float = Field(default=30.0, gt=0, description="单次获取超时（秒）")
    batch: float = Field(default=300.0, gt=0, description="批量获取超时（秒）")
    fallback: float = Field(default=10.0, gt=0, description="备用数据源超时（秒）")


class DaskTimeoutsConfig(BaseModel):
    """Dask 分布式计算相关超时"""

    worker_ready: float = Field(default=30.0, gt=0, description="等待 Worker 就绪（秒）")
    amazingdata_init: float = Field(
        default=60.0, gt=0, description="等待 AmazingData Dask 代理初始化（秒）"
    )
    shutdown: float = Field(default=15.0, gt=0, description="关闭 Dask 集群超时（秒）")
    circuit_breaker_recovery: float = Field(default=60.0, gt=0, description="熔断器恢复超时（秒）")


class AmazingDataTimeoutsConfig(BaseModel):
    """AmazingData 专用超时（Dask Adapter 层）"""

    normal_call: float = Field(default=45.0, gt=0, description="普通 Actor 调用超时（秒）")
    first_call: float = Field(default=90.0, gt=0, description="首次调用超时（含 SDK 登录，秒）")
    sdk_login: float = Field(default=30.0, gt=0, description="SDK 登录超时（秒）")
    actor_create: float = Field(default=60.0, gt=0, description="Actor 创建超时（秒）")
    calendar_preload: float = Field(default=30.0, gt=0, description="交易日历预加载超时（秒）")


class ShutdownTimeoutsConfig(BaseModel):
    """关闭流程超时"""

    server: float = Field(default=3.0, gt=0, description="服务器关闭超时（秒）")
    runner_stop: float = Field(default=5.0, gt=0, description="Runner 停止超时（秒）")
    runner_stop_outer: float = Field(default=8.0, gt=0, description="Runner 停止外层保护超时（秒）")
    cache_writer: float = Field(default=5.0, gt=0, description="缓存写入器关闭超时（秒）")
    provider_stop: float = Field(default=5.0, gt=0, description="数据源提供器停止超时（秒）")
    task_cancel: float = Field(default=2.0, gt=0, description="任务取消超时（秒）")


class TimeoutsConfig(BaseModel):
    """统一超时配置

    将系统中所有超时值集中管理，支持从 YAML 配置文件加载。

    配置示例（infrastructure.dev.yaml）:
        timeouts:
          dask:
            worker_ready: 30.0
            amazingdata_init: 60.0
          amazingdata:
            normal_call: 45.0
            first_call: 90.0
          shutdown:
            server: 3.0
          providers:
            akshare:
              connect: 30.0
              fetch: 15.0
    """

    dask: DaskTimeoutsConfig = Field(
        default_factory=DaskTimeoutsConfig, description="Dask 相关超时"
    )
    amazingdata: AmazingDataTimeoutsConfig = Field(
        default_factory=AmazingDataTimeoutsConfig, description="AmazingData 专用超时"
    )
    shutdown: ShutdownTimeoutsConfig = Field(
        default_factory=ShutdownTimeoutsConfig, description="关闭流程超时"
    )
    providers: Dict[str, ProviderTimeoutProfile] = Field(
        default_factory=lambda: {
            "akshare": ProviderTimeoutProfile(
                idle=5.0, connect=30.0, fetch=15.0, batch=300.0, fallback=10.0
            ),
            "amazingdata": ProviderTimeoutProfile(
                idle=5.0, connect=90.0, fetch=45.0, batch=120.0, fallback=15.0
            ),
            "miniqmt": ProviderTimeoutProfile(
                idle=5.0, connect=60.0, fetch=30.0, batch=180.0, fallback=10.0
            ),
        },
        description="各数据源的操作超时配置",
    )
