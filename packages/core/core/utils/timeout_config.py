"""
超时配置管理模块

统一管理系统中所有的超时配置，避免硬编码，提高可维护性。
"""

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class TimeoutCategory(Enum):
    """超时类别"""

    # 网络请求
    NETWORK_REALTIME = "network_realtime"  # 实时数据请求
    NETWORK_HISTORICAL = "network_historical"  # 历史数据请求
    NETWORK_BATCH = "network_batch"  # 批量数据请求
    NETWORK_HEALTH = "network_health"  # 健康检查请求

    # 数据库操作
    DB_CONNECT = "db_connect"  # 数据库连接
    DB_QUERY = "db_query"  # 数据库查询
    DB_TRANSACTION = "db_transaction"  # 数据库事务
    DB_HEALTH = "db_health"  # 数据库健康检查

    # 缓存操作
    CACHE_GET = "cache_get"  # 缓存读取
    CACHE_SET = "cache_set"  # 缓存写入
    CACHE_DELETE = "cache_delete"  # 缓存删除
    CACHE_FLUSH = "cache_flush"  # 缓存清空

    # 消息总线
    MSG_PUBLISH = "msg_publish"  # 消息发布
    MSG_SUBSCRIBE = "msg_subscribe"  # 消息订阅
    MSG_CONSUME = "msg_consume"  # 消息消费

    # 组件生命周期
    COMPONENT_INIT = "component_init"  # 组件初始化
    COMPONENT_START = "component_start"  # 组件启动
    COMPONENT_STOP = "component_stop"  # 组件停止
    COMPONENT_HEALTH = "component_health"  # 组件健康检查


@dataclass
class TimeoutConfig:
    """超时配置"""

    default: float  # 默认超时（秒）
    min: float  # 最小超时（秒）
    max: float  # 最大超时（秒）
    retry_multiplier: float = 1.5  # 重试时的超时倍数

    def get_timeout(self, attempt: int = 0) -> float:
        """
        获取超时时间

        Args:
            attempt: 重试次数（0表示首次尝试）

        Returns:
            超时时间（秒）
        """
        # 处理负数尝试次数，当作0处理
        if attempt <= 0:
            return self.default

        # 指数退避，但不超过最大值
        timeout = min(self.default * (self.retry_multiplier**attempt), self.max)
        return timeout


class TimeoutManager:
    """超时管理器"""

    # 默认超时配置
    DEFAULT_CONFIGS: Dict[TimeoutCategory, TimeoutConfig] = {
        # 网络请求 - 根据数据类型设置不同超时
        TimeoutCategory.NETWORK_REALTIME: TimeoutConfig(default=10.0, min=5.0, max=30.0),
        TimeoutCategory.NETWORK_HISTORICAL: TimeoutConfig(default=30.0, min=10.0, max=120.0),
        TimeoutCategory.NETWORK_BATCH: TimeoutConfig(default=60.0, min=30.0, max=300.0),
        TimeoutCategory.NETWORK_HEALTH: TimeoutConfig(default=5.0, min=2.0, max=10.0),
        # 数据库操作 - 相对较短的超时
        TimeoutCategory.DB_CONNECT: TimeoutConfig(default=10.0, min=5.0, max=30.0),
        TimeoutCategory.DB_QUERY: TimeoutConfig(default=30.0, min=5.0, max=120.0),
        TimeoutCategory.DB_TRANSACTION: TimeoutConfig(default=60.0, min=10.0, max=300.0),
        TimeoutCategory.DB_HEALTH: TimeoutConfig(default=5.0, min=2.0, max=10.0),
        # 缓存操作 - 应该很快
        TimeoutCategory.CACHE_GET: TimeoutConfig(default=5.0, min=1.0, max=10.0),
        TimeoutCategory.CACHE_SET: TimeoutConfig(default=5.0, min=1.0, max=10.0),
        TimeoutCategory.CACHE_DELETE: TimeoutConfig(default=5.0, min=1.0, max=10.0),
        TimeoutCategory.CACHE_FLUSH: TimeoutConfig(default=10.0, min=5.0, max=30.0),
        # 消息总线 - 取决于消息处理复杂度
        TimeoutCategory.MSG_PUBLISH: TimeoutConfig(default=5.0, min=1.0, max=30.0),
        TimeoutCategory.MSG_SUBSCRIBE: TimeoutConfig(default=5.0, min=1.0, max=30.0),
        TimeoutCategory.MSG_CONSUME: TimeoutConfig(default=30.0, min=5.0, max=120.0),
        # 组件生命周期 - 给予足够时间
        TimeoutCategory.COMPONENT_INIT: TimeoutConfig(default=30.0, min=10.0, max=120.0),
        TimeoutCategory.COMPONENT_START: TimeoutConfig(default=30.0, min=10.0, max=120.0),
        TimeoutCategory.COMPONENT_STOP: TimeoutConfig(default=30.0, min=10.0, max=120.0),
        TimeoutCategory.COMPONENT_HEALTH: TimeoutConfig(default=5.0, min=2.0, max=10.0),
    }

    def __init__(self, custom_configs: Optional[Dict[TimeoutCategory, TimeoutConfig]] = None):
        """
        初始化超时管理器

        Args:
            custom_configs: 自定义超时配置，会覆盖默认配置
        """
        # 使用深拷贝避免默认配置在不同管理器实例之间共享同一个 TimeoutConfig 对象
        # 浅拷贝会导致调用方修改返回的配置对象时污染全局默认值
        self.configs = deepcopy(self.DEFAULT_CONFIGS)
        if custom_configs:
            self.configs.update(custom_configs)

    def get_timeout(self, category: TimeoutCategory, attempt: int = 0) -> float:
        """
        获取指定类别的超时时间

        Args:
            category: 超时类别
            attempt: 重试次数

        Returns:
            超时时间（秒）
        """
        # 处理None类别或不存在的类别
        if category is None or category not in self.configs:
            # 如果没有配置，返回默认30秒
            return 30.0

        config = self.configs[category]
        # 处理负数尝试次数
        if attempt < 0:
            attempt = 0

        return config.get_timeout(attempt)

    def get_config(self, category: TimeoutCategory) -> Optional[TimeoutConfig]:
        """
        获取指定类别的超时配置

        Args:
            category: 超时类别

        Returns:
            超时配置对象
        """
        return self.configs.get(category)

    def update_config(self, category: TimeoutCategory, config: TimeoutConfig) -> None:
        """
        更新指定类别的超时配置

        Args:
            category: 超时类别
            config: 新的超时配置
        """
        self.configs[category] = config

    def get_timeout_for_api(self, api_name: str, is_batch: bool = False) -> float:
        """
        根据API名称智能获取超时时间

        Args:
            api_name: API名称
            is_batch: 是否是批量请求

        Returns:
            超时时间（秒）
        """
        # 批量请求使用更长的超时
        if is_batch:
            return self.get_timeout(TimeoutCategory.NETWORK_BATCH)

        # 根据API名称判断数据类型
        realtime_keywords = ["realtime", "spot", "tick", "orderbook", "quote"]
        if any(keyword in api_name.lower() for keyword in realtime_keywords):
            return self.get_timeout(TimeoutCategory.NETWORK_REALTIME)

        historical_keywords = ["hist", "daily", "weekly", "monthly", "kline"]
        if any(keyword in api_name.lower() for keyword in historical_keywords):
            return self.get_timeout(TimeoutCategory.NETWORK_HISTORICAL)

        # 默认使用历史数据的超时
        return self.get_timeout(TimeoutCategory.NETWORK_HISTORICAL)


# 全局超时管理器实例
_timeout_manager: Optional[TimeoutManager] = None


def get_timeout_manager() -> TimeoutManager:
    """
    获取全局超时管理器实例

    Returns:
        超时管理器实例
    """
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager


def configure_timeouts(custom_configs: Dict[TimeoutCategory, TimeoutConfig]) -> None:
    """
    配置全局超时设置

    Args:
        custom_configs: 自定义超时配置
    """
    global _timeout_manager
    _timeout_manager = TimeoutManager(custom_configs)
