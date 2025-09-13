"""
数据源验证器

用于检查和管理可用的数据源
"""
import time
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

from loguru import logger
from deepsearch.data_providers.interfaces.base import DataSourceType
    

@dataclass
class DataSourceStatus:
    """数据源状态"""
    source_type: DataSourceType
    is_available: bool
    last_check: float
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None


class DataSourceValidator:
    """数据源验证器"""
    
    def __init__(self):
        self._status_cache: Dict[DataSourceType, DataSourceStatus] = {}
        self._cache_ttl = 30  # 缓存30秒
        
    def check_akshare(self) -> DataSourceStatus:
        """检查AKShare数据源"""
        start_time = time.time()
        
        try:
            import akshare as ak
            # 尝试获取一个简单的数据来测试连接
            test_data = ak.stock_zh_a_spot_em()
            
            if test_data is not None and not test_data.empty:
                latency = (time.time() - start_time) * 1000
                return DataSourceStatus(
                    source_type=DataSourceType.AKSHARE,
                    is_available=True,
                    last_check=time.time(),
                    latency_ms=latency
                )
        except Exception as e:
            logger.debug(f"AKShare不可用: {e}")
            
        return DataSourceStatus(
            source_type=DataSourceType.AKSHARE,
            is_available=False,
            last_check=time.time(),
            error_message="AKShare数据源不可用"
        )
        
    def check_qmt(self) -> DataSourceStatus:
        """检查QMT数据源"""
        try:
            from deepsearch.core.runtime.context import get_context
            context = get_context()
            
            # 获取QMT网关
            try:
                manager = context.get_component_manager()
                component = manager.get_component('qmt_gateway')
                
                if component and hasattr(component, 'is_qmt_connected'):
                    if component.is_qmt_connected():
                        return DataSourceStatus(
                            source_type=DataSourceType.QMT,
                            is_available=True,
                            last_check=time.time()
                        )
            except Exception as e:
                logger.debug(f"检查QMT状态失败: {e}")
                
        except Exception as e:
            logger.debug(f"QMT组件不可用: {e}")
            
        return DataSourceStatus(
            source_type=DataSourceType.QMT,
            is_available=False,
            last_check=time.time(),
            error_message="QMT采集器未连接"
        )
        
    def check_database(self) -> DataSourceStatus:
        """检查数据库数据源"""
        try:
            from deepsearch.config import get_config
            config = get_config()
            
            if config.database.main.enabled:
                # 这里可以添加实际的数据库连接测试
                return DataSourceStatus(
                    source_type=DataSourceType.DATABASE,
                    is_available=True,
                    last_check=time.time()
                )
        except Exception as e:
            logger.debug(f"数据库不可用: {e}")
            
        return DataSourceStatus(
            source_type=DataSourceType.DATABASE,
            is_available=False,
            last_check=time.time(),
            error_message="数据库未配置或不可用"
        )
        
    def get_available_sources(self, force_check: bool = False) -> List[DataSourceType]:
        """获取可用的数据源列表"""
        available = []
        
        # 检查各个数据源
        for source_type in DataSourceType:
            status = self.get_source_status(source_type, force_check)
            if status and status.is_available:
                available.append(source_type)
                
        return available
        
    def get_source_status(self, source_type: DataSourceType, 
                         force_check: bool = False) -> Optional[DataSourceStatus]:
        """获取数据源状态"""
        # 检查缓存
        if not force_check and source_type in self._status_cache:
            cached = self._status_cache[source_type]
            if time.time() - cached.last_check < self._cache_ttl:
                return cached
                
        # 执行检查
        if source_type == DataSourceType.AKSHARE:
            status = self.check_akshare()
        elif source_type == DataSourceType.QMT:
            status = self.check_qmt()
        elif source_type == DataSourceType.DATABASE:
            status = self.check_database()
        else:
            return None
            
        # 更新缓存
        self._status_cache[source_type] = status
        return status
        
    def get_best_source(self, preferred_order: Optional[List[DataSourceType]] = None) -> Optional[DataSourceType]:
        """获取最佳可用数据源"""
        if preferred_order is None:
            preferred_order = [DataSourceType.QMT, DataSourceType.AKSHARE, DataSourceType.DATABASE]
            
        available = self.get_available_sources()
        
        # 按优先级返回第一个可用的
        for source in preferred_order:
            if source in available:
                return source
                
        # 如果优先级列表中没有可用的，返回任意一个可用的
        return available[0] if available else None
        
    def get_status_report(self) -> Dict:
        """获取所有数据源的状态报告"""
        report = {}
        
        for source_type in DataSourceType:
            status = self.get_source_status(source_type)
            if status:
                report[source_type.value] = {
                    'available': status.is_available,
                    'last_check': status.last_check,
                    'error': status.error_message,
                    'latency_ms': status.latency_ms
                }
                
        return report


# 全局验证器实例
data_source_validator = DataSourceValidator()


def get_available_data_sources() -> List[str]:
    """获取可用的数据源列表（简化接口）"""
    sources = data_source_validator.get_available_sources()
    return [s.value for s in sources]


def is_data_source_available(source: str) -> bool:
    """检查特定数据源是否可用"""
    try:
        source_type = DataSourceType(source)
        status = data_source_validator.get_source_status(source_type)
        return status.is_available if status else False
    except ValueError:
        return False