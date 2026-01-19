"""
超时配置模型

定义数据源状态枚举和超时配置数据类。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class DataSourceState(Enum):
    """数据源工作状态"""

    IDLE = "idle"
    """空闲状态 - 没有正在进行的操作"""

    CONNECTING = "connecting"
    """连接中 - 正在建立连接或登录（如 AmazingData SDK 首次调用）"""

    FETCHING = "fetching"
    """获取数据中 - 正常的单次数据请求"""

    BATCH_FETCHING = "batch_fetching"
    """批量获取中 - 正在下载大量数据（如 AkShare 获取 557 条股票列表）"""

    ERROR = "error"
    """错误状态 - 上次操作失败"""


@dataclass
class TimeoutConfig:
    """
    数据源超时配置

    不同状态下使用不同的超时值，避免"一刀切"导致的误判。
    """

    idle_timeout: float = 5.0
    """空闲时的快速超时 - 用于检测数据源是否响应"""

    connect_timeout: float = 90.0
    """连接/登录超时 - 首次调用可能需要较长时间初始化"""

    fetch_timeout: float = 30.0
    """单次获取超时 - 正常的数据请求"""

    batch_timeout: float = 300.0
    """批量获取超时 - 下载大量数据时允许更长时间（5分钟）"""

    fallback_timeout: float = 10.0
    """备用数据源超时 - 切换到备用数据源时的超时"""


# 预定义的数据源超时配置
DEFAULT_TIMEOUT_CONFIGS: Dict[str, TimeoutConfig] = {
    "akshare": TimeoutConfig(
        idle_timeout=5.0,
        connect_timeout=30.0,  # AkShare 无需登录，连接较快
        fetch_timeout=15.0,  # 单条请求
        batch_timeout=300.0,  # 批量下载（如 557 条股票）
        fallback_timeout=10.0,
    ),
    "amazingdata": TimeoutConfig(
        idle_timeout=5.0,
        connect_timeout=90.0,  # SDK 首次登录需要较长时间
        fetch_timeout=45.0,  # Actor 调用
        batch_timeout=120.0,  # 批量查询
        fallback_timeout=15.0,
    ),
    "miniqmt": TimeoutConfig(
        idle_timeout=5.0,
        connect_timeout=60.0,  # QMT 连接
        fetch_timeout=30.0,
        batch_timeout=180.0,
        fallback_timeout=10.0,
    ),
}


@dataclass
class SourceStateInfo:
    """数据源状态详细信息"""

    state: DataSourceState = DataSourceState.IDLE
    """当前状态"""

    operation: str = ""
    """当前操作描述（如 "get_stock_list", "login"）"""

    started_at: float = 0.0
    """操作开始时间戳（用于计算已耗时）"""

    expected_items: int = 0
    """预期处理的数据条数（用于批量操作）"""

    processed_items: int = 0
    """已处理的数据条数"""

    extra: Dict[str, object] = field(default_factory=dict)
    """额外的状态信息"""
