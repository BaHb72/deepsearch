"""
数据源配置管理模块

提供实盘数据访问速度的动态配置
支持用户通过前端面板调节各种参数
"""
import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import asyncio
from pathlib import Path

from loguru import logger


class AccessMode(Enum):
    """访问模式"""
    CONSERVATIVE = "conservative"  # 保守模式（稳定优先）
    BALANCED = "balanced"          # 均衡模式（默认）
    AGGRESSIVE = "aggressive"      # 激进模式（速度优先）
    CUSTOM = "custom"              # 自定义模式


class DataType(Enum):
    """数据类型"""
    REALTIME = "realtime"      # 实时行情
    ORDERBOOK = "orderbook"    # 盘口数据
    MINUTE = "minute"          # 分钟数据
    DAILY = "daily"            # 日线数据
    INFO = "info"              # 基础信息


@dataclass
class DataTypeConfig:
    """单个数据类型的配置"""
    cache_ttl: int                    # 缓存TTL（秒）
    request_timeout: float            # 请求超时（秒）
    rate_limit: float                 # 速率限制（请求/秒）
    max_retries: int                  # 最大重试次数
    batch_size: Optional[int] = None  # 批量大小
    priority: int = 5                 # 优先级（1-10）


@dataclass
class DataSourceConfig:
    """数据源配置"""
    # 基础配置
    mode: AccessMode = AccessMode.BALANCED
    enabled: bool = True
    
    # 全局配置
    global_rate_limit: float = 20.0      # 全局速率限制
    global_timeout_multiplier: float = 1.0  # 超时倍数
    global_cache_multiplier: float = 1.0    # 缓存时间倍数
    
    # 批量处理配置
    batch_enabled: bool = True
    batch_timeout: float = 0.2
    max_batch_size: int = 20
    
    # 重试配置
    retry_enabled: bool = True
    retry_base_delay: float = 1.0
    retry_max_delay: float = 10.0
    
    # 熔断器配置
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    
    # 各数据类型的具体配置
    data_types: Dict[str, DataTypeConfig] = field(default_factory=dict)
    
    # 自动调节配置
    auto_adjust: bool = False             # 是否自动调节
    target_success_rate: float = 0.95     # 目标成功率
    target_latency_p99: float = 2.0       # 目标P99延迟
    
    # 元数据
    last_updated: Optional[str] = None
    updated_by: Optional[str] = None
    version: int = 1


class DataSourceConfigManager:
    """数据源配置管理器"""
    
    # 预设配置
    PRESETS = {
        AccessMode.CONSERVATIVE: {
            "global_rate_limit": 10.0,
            "global_timeout_multiplier": 1.5,
            "global_cache_multiplier": 2.0,
            "batch_timeout": 0.5,
            "retry_max_delay": 20.0,
            "data_types": {
                DataType.REALTIME.value: DataTypeConfig(
                    cache_ttl=10, request_timeout=8.0, rate_limit=5.0, max_retries=3
                ),
                DataType.ORDERBOOK.value: DataTypeConfig(
                    cache_ttl=5, request_timeout=5.0, rate_limit=3.0, max_retries=2
                ),
                DataType.MINUTE.value: DataTypeConfig(
                    cache_ttl=120, request_timeout=15.0, rate_limit=2.0, max_retries=3
                ),
                DataType.DAILY.value: DataTypeConfig(
                    cache_ttl=600, request_timeout=20.0, rate_limit=1.0, max_retries=3
                ),
                DataType.INFO.value: DataTypeConfig(
                    cache_ttl=3600, request_timeout=10.0, rate_limit=0.5, max_retries=3
                ),
            }
        },
        AccessMode.BALANCED: {
            "global_rate_limit": 20.0,
            "global_timeout_multiplier": 1.0,
            "global_cache_multiplier": 1.0,
            "batch_timeout": 0.2,
            "retry_max_delay": 10.0,
            "data_types": {
                DataType.REALTIME.value: DataTypeConfig(
                    cache_ttl=5, request_timeout=5.0, rate_limit=15.0, max_retries=2
                ),
                DataType.ORDERBOOK.value: DataTypeConfig(
                    cache_ttl=3, request_timeout=3.0, rate_limit=10.0, max_retries=2
                ),
                DataType.MINUTE.value: DataTypeConfig(
                    cache_ttl=60, request_timeout=10.0, rate_limit=5.0, max_retries=3
                ),
                DataType.DAILY.value: DataTypeConfig(
                    cache_ttl=300, request_timeout=15.0, rate_limit=3.0, max_retries=3
                ),
                DataType.INFO.value: DataTypeConfig(
                    cache_ttl=1800, request_timeout=8.0, rate_limit=2.0, max_retries=3
                ),
            }
        },
        AccessMode.AGGRESSIVE: {
            "global_rate_limit": 50.0,
            "global_timeout_multiplier": 0.7,
            "global_cache_multiplier": 0.5,
            "batch_timeout": 0.1,
            "retry_max_delay": 5.0,
            "data_types": {
                DataType.REALTIME.value: DataTypeConfig(
                    cache_ttl=2, request_timeout=3.0, rate_limit=30.0, max_retries=1
                ),
                DataType.ORDERBOOK.value: DataTypeConfig(
                    cache_ttl=1, request_timeout=2.0, rate_limit=20.0, max_retries=1
                ),
                DataType.MINUTE.value: DataTypeConfig(
                    cache_ttl=30, request_timeout=5.0, rate_limit=10.0, max_retries=2
                ),
                DataType.DAILY.value: DataTypeConfig(
                    cache_ttl=180, request_timeout=10.0, rate_limit=5.0, max_retries=2
                ),
                DataType.INFO.value: DataTypeConfig(
                    cache_ttl=900, request_timeout=5.0, rate_limit=3.0, max_retries=2
                ),
            }
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 默认配置路径
            self.config_path = Path("data/config/data_source_config.json")
        
        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 当前配置
        self.config: DataSourceConfig = self._load_config()
        
        # 配置变更回调
        self.change_callbacks: List[callable] = []
        
        # 性能统计（用于自动调节）
        self.stats = {
            'success_count': 0,
            'failure_count': 0,
            'total_latency': 0.0,
            'request_count': 0
        }
        
        # 启动自动调节任务
        if self.config.auto_adjust:
            asyncio.create_task(self._auto_adjust_task())
    
    def _load_config(self) -> DataSourceConfig:
        """加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 转换数据类型配置
                if 'data_types' in data:
                    data_types = {}
                    for key, value in data['data_types'].items():
                        data_types[key] = DataTypeConfig(**value)
                    data['data_types'] = data_types
                
                # 转换枚举
                if 'mode' in data:
                    data['mode'] = AccessMode(data['mode'])
                
                config = DataSourceConfig(**data)
                logger.info(f"加载数据源配置: {config.mode.value}模式")
                return config
                
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
        
        # 使用默认配置
        logger.info("使用默认数据源配置")
        return self._create_default_config()
    
    def _create_default_config(self) -> DataSourceConfig:
        """创建默认配置"""
        config = DataSourceConfig(mode=AccessMode.BALANCED)
        preset = self.PRESETS[AccessMode.BALANCED]
        
        # 应用预设
        for key, value in preset.items():
            if key != 'data_types':
                setattr(config, key, value)
            else:
                config.data_types = value
        
        return config
    
    def save_config(self):
        """保存配置"""
        try:
            # 准备数据
            data = asdict(self.config)
            
            # 转换枚举为字符串
            data['mode'] = self.config.mode.value
            
            # 添加元数据
            data['last_updated'] = datetime.now().isoformat()
            data['version'] = self.config.version + 1
            
            # 保存到文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("数据源配置已保存")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def apply_preset(self, mode: AccessMode):
        """
        应用预设配置
        
        Args:
            mode: 访问模式
        """
        if mode not in self.PRESETS:
            logger.error(f"未知的预设模式: {mode}")
            return
        
        preset = self.PRESETS[mode]
        
        # 更新配置
        self.config.mode = mode
        for key, value in preset.items():
            setattr(self.config, key, value)
        
        # 保存并通知
        self.save_config()
        self._notify_change()
        
        logger.info(f"应用预设配置: {mode.value}")
    
    def update_config(self, updates: Dict[str, Any]):
        """
        更新配置
        
        Args:
            updates: 更新的配置项
        """
        try:
            # 更新配置
            for key, value in updates.items():
                if hasattr(self.config, key):
                    # 特殊处理数据类型配置
                    if key == 'data_types' and isinstance(value, dict):
                        for dt_key, dt_value in value.items():
                            if dt_key in self.config.data_types:
                                for field_key, field_value in dt_value.items():
                                    setattr(self.config.data_types[dt_key], field_key, field_value)
                            else:
                                self.config.data_types[dt_key] = DataTypeConfig(**dt_value)
                    else:
                        setattr(self.config, key, value)
            
            # 如果不是预设值，标记为自定义
            if not self._matches_preset():
                self.config.mode = AccessMode.CUSTOM
            
            # 保存并通知
            self.save_config()
            self._notify_change()
            
            logger.info("数据源配置已更新")
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
    
    def _matches_preset(self) -> bool:
        """检查当前配置是否匹配某个预设"""
        for mode, preset in self.PRESETS.items():
            if self._config_equals_preset(preset):
                return True
        return False
    
    def _config_equals_preset(self, preset: dict) -> bool:
        """比较配置与预设是否相等"""
        for key, value in preset.items():
            if key == 'data_types':
                continue  # 暂时跳过复杂比较
            if getattr(self.config, key, None) != value:
                return False
        return True
    
    def get_data_type_config(self, data_type: str) -> DataTypeConfig:
        """
        获取数据类型配置
        
        Args:
            data_type: 数据类型
            
        Returns:
            数据类型配置
        """
        if data_type in self.config.data_types:
            return self.config.data_types[data_type]
        
        # 返回默认配置
        return DataTypeConfig(
            cache_ttl=60,
            request_timeout=10.0,
            rate_limit=5.0,
            max_retries=3
        )
    
    def register_change_callback(self, callback: callable):
        """注册配置变更回调"""
        self.change_callbacks.append(callback)
    
    def _notify_change(self):
        """通知配置变更"""
        for callback in self.change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(self.config))
                else:
                    callback(self.config)
            except Exception as e:
                logger.error(f"配置变更回调失败: {e}")
    
    def record_request(self, success: bool, latency: float):
        """
        记录请求统计（用于自动调节）
        
        Args:
            success: 是否成功
            latency: 延迟时间
        """
        self.stats['request_count'] += 1
        if success:
            self.stats['success_count'] += 1
        else:
            self.stats['failure_count'] += 1
        self.stats['total_latency'] += latency
    
    async def _auto_adjust_task(self):
        """自动调节任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                
                if not self.config.auto_adjust:
                    continue
                
                # 计算成功率和平均延迟
                if self.stats['request_count'] > 100:  # 至少100个请求
                    success_rate = self.stats['success_count'] / self.stats['request_count']
                    avg_latency = self.stats['total_latency'] / self.stats['request_count']
                    
                    # 根据目标调节
                    adjusted = False
                    
                    if success_rate < self.config.target_success_rate:
                        # 成功率太低，放宽限制
                        self.config.global_rate_limit *= 0.9
                        self.config.global_timeout_multiplier *= 1.1
                        adjusted = True
                        logger.info(f"自动调节：降低速率限制到 {self.config.global_rate_limit:.1f}")
                    
                    elif avg_latency > self.config.target_latency_p99:
                        # 延迟太高，减少并发
                        self.config.global_rate_limit *= 0.95
                        self.config.batch_timeout *= 1.1
                        adjusted = True
                        logger.info(f"自动调节：降低并发以减少延迟")
                    
                    elif success_rate > 0.98 and avg_latency < self.config.target_latency_p99 * 0.7:
                        # 表现良好，可以提速
                        self.config.global_rate_limit *= 1.05
                        self.config.global_timeout_multiplier *= 0.95
                        adjusted = True
                        logger.info(f"自动调节：提高速率限制到 {self.config.global_rate_limit:.1f}")
                    
                    if adjusted:
                        self.save_config()
                        self._notify_change()
                    
                    # 重置统计
                    self.stats = {
                        'success_count': 0,
                        'failure_count': 0,
                        'total_latency': 0.0,
                        'request_count': 0
                    }
                
            except Exception as e:
                logger.error(f"自动调节失败: {e}")
    
    def get_recommendation(self) -> Dict[str, Any]:
        """
        获取配置推荐
        
        Returns:
            推荐信息
        """
        # 获取当前时间
        from deepsearch.utils.time.market_time import MarketTimeUtil
        
        session = MarketTimeUtil.get_current_session()
        is_trading = MarketTimeUtil.is_trading_time()
        
        recommendation = {
            'current_mode': self.config.mode.value,
            'recommended_mode': AccessMode.BALANCED.value,
            'reason': '',
            'tips': []
        }
        
        if is_trading:
            recommendation['recommended_mode'] = AccessMode.AGGRESSIVE.value
            recommendation['reason'] = '当前为交易时段，建议使用激进模式以获得更快的数据更新'
            recommendation['tips'] = [
                '可适当降低缓存时间以获得更实时的数据',
                '提高速率限制以支持更多并发请求',
                '减少超时时间以快速失败和重试'
            ]
        else:
            recommendation['recommended_mode'] = AccessMode.CONSERVATIVE.value
            recommendation['reason'] = '当前为非交易时段，建议使用保守模式以节省资源'
            recommendation['tips'] = [
                '可增加缓存时间减少不必要的请求',
                '降低速率限制避免触发限流',
                '增加超时时间提高成功率'
            ]
        
        # 根据最近的性能统计给出建议
        if self.stats['request_count'] > 50:
            success_rate = self.stats['success_count'] / self.stats['request_count']
            if success_rate < 0.9:
                recommendation['tips'].append('当前成功率较低，建议降低请求频率或增加超时时间')
        
        return recommendation


# 全局配置管理器实例
_config_manager: Optional[DataSourceConfigManager] = None

def get_config_manager() -> DataSourceConfigManager:
    """获取全局配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = DataSourceConfigManager()
    return _config_manager