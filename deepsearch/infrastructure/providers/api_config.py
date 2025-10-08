"""
API配置模块

定义不同API的超时、重试和性能参数
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class APICategory(Enum):
    """API分类"""

    SPOT = "spot"  # 实时行情（全市场）
    INDIVIDUAL = "individual"  # 个股数据
    HISTORICAL = "historical"  # 历史K线
    INFO = "info"  # 基础信息
    ORDERBOOK = "orderbook"  # 盘口数据
    BOARD = "board"  # 板块数据
    ANOMALY = "anomaly"  # 异动数据
    HSGT = "hsgt"  # 沪深港通


@dataclass
class APIConfig:
    """API配置"""

    category: APICategory
    timeout: float  # 超时时间（秒）
    max_retries: int  # 最大重试次数
    batch_size: Optional[int]  # 批量大小
    cache_ttl: Optional[int]  # 缓存时间（秒）
    priority: int  # 优先级（1-10）


class APIConfigManager:
    """API配置管理器"""

    # API配置映射
    API_CONFIGS = {
        # 实时行情类
        "stock_zh_a_spot_em": APIConfig(
            category=APICategory.SPOT,
            timeout=15.0,  # 全市场数据需要更长时间
            max_retries=2,
            batch_size=None,
            cache_ttl=None,  # 使用动态缓存
            priority=1,
        ),
        "stock_individual_info_em": APIConfig(
            category=APICategory.INDIVIDUAL,
            timeout=5.0,  # 个股数据快速返回
            max_retries=3,
            batch_size=10,
            cache_ttl=None,
            priority=2,
        ),
        # 历史数据类
        "stock_zh_a_hist": APIConfig(
            category=APICategory.HISTORICAL,
            timeout=20.0,  # 历史数据可能需要较长时间
            max_retries=3,
            batch_size=5,
            cache_ttl=None,
            priority=3,
        ),
        "stock_zh_a_hist_min_em": APIConfig(
            category=APICategory.HISTORICAL,
            timeout=25.0,  # 分钟数据更多，需要更长时间
            max_retries=2,
            batch_size=3,
            cache_ttl=None,
            priority=3,
        ),
        # 基础信息类
        "stock_info_a_code_name": APIConfig(
            category=APICategory.INFO,
            timeout=10.0,
            max_retries=3,
            batch_size=None,
            cache_ttl=3600,  # 基础信息缓存1小时
            priority=5,
        ),
        # 盘口数据
        "stock_bid_ask_em": APIConfig(
            category=APICategory.ORDERBOOK,
            timeout=3.0,  # 盘口数据需要快速响应
            max_retries=2,
            batch_size=20,
            cache_ttl=None,
            priority=1,
        ),
        # 板块数据
        "stock_board_industry_name_em": APIConfig(
            category=APICategory.BOARD,
            timeout=8.0,
            max_retries=3,
            batch_size=None,
            cache_ttl=600,  # 板块数据缓存10分钟
            priority=4,
        ),
        "stock_board_concept_name_em": APIConfig(
            category=APICategory.BOARD,
            timeout=8.0,
            max_retries=3,
            batch_size=None,
            cache_ttl=600,
            priority=4,
        ),
        # 异动数据
        "stock_zt_pool_em": APIConfig(
            category=APICategory.ANOMALY,
            timeout=10.0,
            max_retries=2,
            batch_size=None,
            cache_ttl=60,  # 异动数据缓存1分钟
            priority=2,
        ),
        "stock_zt_pool_dtgc_em": APIConfig(
            category=APICategory.ANOMALY,
            timeout=10.0,
            max_retries=2,
            batch_size=None,
            cache_ttl=60,
            priority=2,
        ),
        # 沪深港通
        "stock_em_hsgt_north_net_flow_in": APIConfig(
            category=APICategory.HSGT,
            timeout=12.0,
            max_retries=3,
            batch_size=None,
            cache_ttl=120,  # 北向资金缓存2分钟
            priority=3,
        ),
        # 分时数据
        "stock_intraday_em": APIConfig(
            category=APICategory.INDIVIDUAL,
            timeout=5.0,
            max_retries=3,
            batch_size=10,
            cache_ttl=None,
            priority=2,
        ),
    }

    # 默认配置（未定义的API使用）
    DEFAULT_CONFIG = APIConfig(
        category=APICategory.INFO,
        timeout=10.0,
        max_retries=3,
        batch_size=None,
        cache_ttl=None,
        priority=5,
    )

    @classmethod
    def get_config(cls, api_name: str) -> APIConfig:
        """
        获取API配置

        Args:
            api_name: API函数名

        Returns:
            API配置
        """
        # 标准化API名称
        api_name = api_name.replace("/", "_").replace("-", "_")

        # 返回配置，如果没有则使用默认配置
        return cls.API_CONFIGS.get(api_name, cls.DEFAULT_CONFIG)

    @classmethod
    def get_timeout(cls, api_name: str) -> float:
        """
        获取API超时时间

        Args:
            api_name: API函数名

        Returns:
            超时时间（秒）
        """
        config = cls.get_config(api_name)
        return config.timeout

    @classmethod
    def get_max_retries(cls, api_name: str) -> int:
        """
        获取最大重试次数

        Args:
            api_name: API函数名

        Returns:
            最大重试次数
        """
        config = cls.get_config(api_name)
        return config.max_retries

    @classmethod
    def get_batch_size(cls, api_name: str) -> Optional[int]:
        """
        获取批量大小

        Args:
            api_name: API函数名

        Returns:
            批量大小，None表示不支持批量
        """
        config = cls.get_config(api_name)
        return config.batch_size

    @classmethod
    def get_priority(cls, api_name: str) -> int:
        """
        获取API优先级

        Args:
            api_name: API函数名

        Returns:
            优先级（1-10）
        """
        config = cls.get_config(api_name)
        return config.priority

    @classmethod
    def supports_batch(cls, api_name: str) -> bool:
        """
        判断API是否支持批量请求

        Args:
            api_name: API函数名

        Returns:
            是否支持批量
        """
        config = cls.get_config(api_name)
        return config.batch_size is not None

    @classmethod
    def get_category_timeout(cls, category: APICategory) -> float:
        """
        根据API类别获取建议超时时间

        Args:
            category: API类别

        Returns:
            超时时间（秒）
        """
        category_timeouts = {
            APICategory.SPOT: 15.0,
            APICategory.INDIVIDUAL: 5.0,
            APICategory.HISTORICAL: 20.0,
            APICategory.INFO: 10.0,
            APICategory.ORDERBOOK: 3.0,
            APICategory.BOARD: 8.0,
            APICategory.ANOMALY: 10.0,
            APICategory.HSGT: 12.0,
        }

        return category_timeouts.get(category, 10.0)
