"""
统一数据源管理器

根据配置的优先级自动选择最佳数据源
支持故障转移和负载均衡
"""
import asyncio
import time
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from collections import defaultdict

from loguru import logger

from deepsearch.config import get_config
from deepsearch.data_providers.interfaces import DataProviderAdapter
from deepsearch.data_providers.interfaces.base import DataSourceType


@dataclass
class DataSourceInfo:
    """数据源信息"""
    name: str
    type: DataSourceType
    enabled: bool
    priority: int  # 数字越小优先级越高
    instance: Optional[Any] = None
    initialized: bool = False
    last_success: float = 0
    last_failure: float = 0
    failure_count: int = 0
    success_count: int = 0


class DataSourceManager:
    """
    统一数据源管理器
    
    功能：
    1. 根据优先级自动选择数据源
    2. 故障自动切换
    3. 负载均衡
    4. 统计和监控
    """
    
    def __init__(self):
        """初始化数据源管理器"""
        self.config = get_config()
        self.data_sources: Dict[str, DataSourceInfo] = {}
        self.initialized = False
        
        # 请求统计
        self.stats = defaultdict(lambda: {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'total_time': 0,
            'last_request': None
        })
        
        # 断路器配置
        self.circuit_breaker = {
            'failure_threshold': 5,  # 连续失败次数阈值
            'recovery_time': 60,  # 恢复时间（秒）
            'half_open_requests': 3  # 半开状态测试请求数
        }
        
        # 健康监控
        self._health_monitor_task = None
        self._health_check_interval = 30  # 健康检查间隔（秒）
        self._health_metrics = {}
        
        # 初始化数据源配置
        self._load_data_source_config()
    
    def _load_data_source_config(self):
        """加载数据源配置"""
        providers_config = self.config.data_providers
        
        # AmazingData
        if hasattr(providers_config, 'amazingdata') and providers_config.amazingdata.enabled:
            self.data_sources['amazingdata'] = DataSourceInfo(
                name='amazingdata',
                type=DataSourceType.AMAZINGDATA,
                enabled=True,
                priority=providers_config.amazingdata.priority
            )
        
        # QMT
        if hasattr(providers_config, 'qmt') and providers_config.qmt.enabled:
            self.data_sources['qmt'] = DataSourceInfo(
                name='qmt',
                type=DataSourceType.QMT,
                enabled=True,
                priority=providers_config.qmt.priority
            )
        
        # CloudFlare代理（应该优先于直连）
        if hasattr(providers_config, 'cloudflare_proxy'):
            self.data_sources['cloudflare'] = DataSourceInfo(
                name='cloudflare',
                type=DataSourceType.CLOUDFLARE,
                enabled=providers_config.cloudflare_proxy.get('enabled', False),
                priority=providers_config.cloudflare_proxy.get('priority', 10)
            )
        
        # AkShare代理
        if hasattr(providers_config, 'akshare_proxy'):
            self.data_sources['akshare_proxy'] = DataSourceInfo(
                name='akshare_proxy',
                type=DataSourceType.AKSHARE_PROXY,
                enabled=providers_config.akshare_proxy.get('enabled', False),
                priority=providers_config.akshare_proxy.get('priority', 20)
            )
        
        # AkShare直连（最低优先级）
        self.data_sources['akshare_direct'] = DataSourceInfo(
            name='akshare_direct',
            type=DataSourceType.AKSHARE_DIRECT,
            enabled=True,  # 作为最后的备用方案
            priority=100  # 最低优先级
        )
        
        logger.info(f"加载了 {len(self.data_sources)} 个数据源配置")
    
    async def initialize(self):
        """初始化所有数据源 - 优化版本，并行执行带超时控制"""
        if self.initialized:
            return
        
        logger.info("开始初始化数据源管理器...")
        start_time = time.time()
        
        # 按优先级排序
        sorted_sources = sorted(
            self.data_sources.values(),
            key=lambda x: x.priority
        )
        
        # 创建带超时的初始化任务
        tasks = []
        for source in sorted_sources:
            if source.enabled:
                # 为每个数据源创建带超时的任务（5秒超时）
                task = asyncio.create_task(
                    asyncio.wait_for(
                        self._initialize_data_source(source),
                        timeout=5.0
                    )
                )
                tasks.append((source.name, source, task))
        
        # 并行等待所有任务完成
        if tasks:
            # 等待所有任务，保留任务与源的对应关系
            for name, source, task in tasks:
                try:
                    result = await task
                    source.initialized = result
                    if result:
                        logger.info(f"✅ 数据源 {source.name} 初始化成功")
                    else:
                        logger.warning(f"⚠️ 数据源 {source.name} 初始化失败")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ 数据源 {source.name} 初始化超时（5秒）")
                    source.initialized = False
                except Exception as e:
                    logger.error(f"❌ 数据源 {source.name} 初始化异常: {e}")
                    source.initialized = False
        
        self.initialized = True
        elapsed = time.time() - start_time
        
        # 打印初始化结果摘要
        active_sources = [s for s in self.data_sources.values() if s.initialized]
        logger.info(f"数据源管理器初始化完成（耗时: {elapsed:.2f}s）")
        logger.info(f"可用数据源: {[s.name for s in active_sources]}")
        logger.info(f"初始化成功率: {len(active_sources)}/{len([s for s in self.data_sources.values() if s.enabled])}")
        
        # 启动健康监控
        if not self._health_monitor_task:
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("健康监控已启动")
    
    async def _initialize_data_source(self, source: DataSourceInfo) -> bool:
        """初始化单个数据源"""
        try:
            logger.info(f"初始化数据源: {source.name} (优先级: {source.priority})")
            
            if source.type == DataSourceType.AMAZINGDATA:
                from deepsearch.data_providers.implementations.amazingdata.amazingdata import AmazingDataProvider, AmazingDataConfig
                config = AmazingDataConfig(
                    username=self.config.amazingdata.connection.username,
                    password=self.config.amazingdata.connection.password,
                    host=self.config.amazingdata.connection.host,
                    port=self.config.amazingdata.connection.port
                )
                provider = AmazingDataProvider(config)
                await provider.initialize()
                source.instance = DataProviderAdapter(provider)
                
            elif source.type == DataSourceType.QMT:
                # QMT通过组件管理器获取
                from deepsearch.core.managers.component_manager import ComponentManager
                cm = ComponentManager()
                if "qmt_gateway" in cm._components:
                    source.instance = cm._components["qmt_gateway"]
                else:
                    logger.warning("QMT网关组件未找到")
                    return False
                    
            elif source.type == DataSourceType.CLOUDFLARE:
                from deepsearch.data_providers.implementations.cloudflare.cloudflare import ProxyDataProvider
                provider = ProxyDataProvider()
                await provider.initialize()
                source.instance = DataProviderAdapter(provider)
                
            elif source.type == DataSourceType.AKSHARE_DIRECT:
                from deepsearch.data_providers.implementations.akshare.akshare_direct import AKShareDirectProvider
                provider = AKShareDirectProvider()
                result = await provider.initialize()
                if result:
                    source.instance = DataProviderAdapter(provider)
                return result
            
            return source.instance is not None
            
        except Exception as e:
            logger.error(f"初始化数据源 {source.name} 失败: {e}")
            return False
    
    def _is_circuit_open(self, source: DataSourceInfo) -> bool:
        """检查断路器是否打开"""
        if source.failure_count < self.circuit_breaker['failure_threshold']:
            return False
        
        # 检查是否过了恢复时间
        time_since_failure = time.time() - source.last_failure
        if time_since_failure > self.circuit_breaker['recovery_time']:
            # 重置失败计数，进入半开状态
            source.failure_count = 0
            return False
        
        return True
    
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情（自动选择最佳数据源）
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据
        """
        if not self.initialized:
            await self.initialize()
        
        # 按优先级排序的可用数据源
        available_sources = sorted(
            [s for s in self.data_sources.values() 
             if s.enabled and s.initialized and not self._is_circuit_open(s)],
            key=lambda x: x.priority
        )
        
        last_error = None
        for source in available_sources:
            try:
                start_time = time.time()
                logger.debug(f"尝试从 {source.name} 获取 {symbol} 实时行情")
                
                # 调用数据源
                if source.instance:
                    result = await source.instance.get_realtime_quote(symbol)
                    
                    # 检查结果
                    if result and not result.get('error'):
                        # 更新统计
                        elapsed = time.time() - start_time
                        source.success_count += 1
                        source.last_success = time.time()
                        source.failure_count = 0  # 重置失败计数
                        
                        self.stats[source.name]['requests'] += 1
                        self.stats[source.name]['successes'] += 1
                        self.stats[source.name]['total_time'] += elapsed
                        self.stats[source.name]['last_request'] = time.time()
                        
                        logger.info(f"成功从 {source.name} 获取数据 (耗时: {elapsed:.2f}s)")
                        
                        # 添加数据源标识
                        result['_source'] = source.name
                        result['_priority'] = source.priority
                        
                        return result
                
            except Exception as e:
                last_error = e
                source.failure_count += 1
                source.last_failure = time.time()
                
                self.stats[source.name]['requests'] += 1
                self.stats[source.name]['failures'] += 1
                
                logger.warning(f"从 {source.name} 获取数据失败: {e}")
                continue
        
        # 所有数据源都失败
        error_msg = f"所有数据源获取 {symbol} 失败"
        if last_error:
            error_msg += f": {last_error}"
        
        logger.error(error_msg)
        return {"error": error_msg}
    
    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500
    ) -> Dict[str, Any]:
        """
        获取K线数据（自动选择最佳数据源）
        
        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            limit: 数据条数
            
        Returns:
            K线数据
        """
        if not self.initialized:
            await self.initialize()
        
        # 按优先级尝试各个数据源
        available_sources = sorted(
            [s for s in self.data_sources.values() 
             if s.enabled and s.initialized and not self._is_circuit_open(s)],
            key=lambda x: x.priority
        )
        
        for source in available_sources:
            try:
                logger.debug(f"尝试从 {source.name} 获取 {symbol} K线数据")
                
                if source.instance:
                    # 根据不同数据源调用不同方法
                    if hasattr(source.instance, 'get_kline_data'):
                        result = await source.instance.get_kline_data(
                            symbol, period, start_date, end_date
                        )
                    elif hasattr(source.instance, 'get_stock_hist'):
                        result = await source.instance.get_stock_hist(
                            symbol, period, start_date, end_date
                        )
                    else:
                        continue
                    
                    if result and not isinstance(result, dict) or not result.get('error'):
                        logger.info(f"成功从 {source.name} 获取K线数据")
                        return result
                        
            except Exception as e:
                logger.warning(f"从 {source.name} 获取K线数据失败: {e}")
                continue
        
        return {"error": "所有数据源获取K线数据失败"}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据源统计信息"""
        stats = {
            'initialized': self.initialized,
            'data_sources': {},
            'request_stats': dict(self.stats),
            'health_metrics': dict(self._health_metrics)
        }
        
        for name, source in self.data_sources.items():
            stats['data_sources'][name] = {
                'type': source.type.value,
                'enabled': source.enabled,
                'priority': source.priority,
                'initialized': source.initialized,
                'success_count': source.success_count,
                'failure_count': source.failure_count,
                'circuit_open': self._is_circuit_open(source),
                'last_success': source.last_success,
                'last_failure': source.last_failure
            }
        
        return stats
    
    async def _health_monitor_loop(self):
        """健康监控循环"""
        logger.info("健康监控循环已启动")
        
        while self.initialized:
            try:
                # 使用可中断的短休眠，每秒检查一次初始化状态
                for _ in range(self._health_check_interval):
                    if not self.initialized:
                        break
                    await asyncio.sleep(1)
                
                # 对每个启用的数据源进行健康检查
                check_tasks = []
                for source in self.data_sources.values():
                    if source.enabled and source.initialized:
                        check_tasks.append(
                            asyncio.create_task(self._check_source_health(source))
                        )
                
                if check_tasks:
                    await asyncio.gather(*check_tasks, return_exceptions=True)
                
                # 记录健康状态摘要
                healthy_count = sum(
                    1 for m in self._health_metrics.values() 
                    if m.get('status') == 'healthy'
                )
                total_count = len([s for s in self.data_sources.values() if s.enabled])
                
                logger.debug(f"健康检查完成: {healthy_count}/{total_count} 数据源正常")
                
            except asyncio.CancelledError:
                logger.info("健康监控循环已停止")
                break
            except Exception as e:
                logger.error(f"健康监控异常: {e}")
    
    async def _check_source_health(self, source: DataSourceInfo):
        """
        检查单个数据源健康状态
        
        Args:
            source: 数据源信息
        """
        try:
            start_time = time.time()
            
            # 执行测试查询
            if source.instance:
                # 使用一个常用的股票代码进行测试
                test_symbol = "000001"
                
                try:
                    # 设置超时
                    result = await asyncio.wait_for(
                        source.instance.get_realtime_quote(test_symbol),
                        timeout=5.0
                    )
                    
                    if result and not result.get('error'):
                        # 健康检查成功
                        latency = time.time() - start_time
                        
                        if source.name not in self._health_metrics:
                            self._health_metrics[source.name] = {
                                'status': 'healthy',
                                'latency_history': [],
                                'last_check': None,
                                'consecutive_failures': 0
                            }
                        
                        metrics = self._health_metrics[source.name]
                        metrics['status'] = 'healthy'
                        metrics['last_check'] = time.time()
                        metrics['latency_history'].append(latency)
                        metrics['consecutive_failures'] = 0
                        
                        # 保持历史记录在合理范围
                        if len(metrics['latency_history']) > 100:
                            metrics['latency_history'] = metrics['latency_history'][-100:]
                        
                        # 计算平均延迟
                        metrics['avg_latency'] = sum(metrics['latency_history']) / len(metrics['latency_history'])
                        
                        logger.debug(f"✅ {source.name} 健康检查通过 (延迟: {latency:.2f}s)")
                    else:
                        raise Exception("返回数据无效")
                        
                except asyncio.TimeoutError:
                    self._mark_source_unhealthy(source, "超时")
                except Exception as e:
                    self._mark_source_unhealthy(source, str(e))
            else:
                self._mark_source_unhealthy(source, "实例未初始化")
                
        except Exception as e:
            logger.error(f"健康检查 {source.name} 异常: {e}")
            self._mark_source_unhealthy(source, str(e))
    
    def _mark_source_unhealthy(self, source: DataSourceInfo, reason: str):
        """
        标记数据源为不健康
        
        Args:
            source: 数据源信息
            reason: 不健康原因
        """
        if source.name not in self._health_metrics:
            self._health_metrics[source.name] = {
                'status': 'unhealthy',
                'latency_history': [],
                'last_check': None,
                'consecutive_failures': 0
            }
        
        metrics = self._health_metrics[source.name]
        metrics['status'] = 'unhealthy'
        metrics['last_check'] = time.time()
        metrics['consecutive_failures'] += 1
        metrics['last_error'] = reason
        
        # 如果连续失败过多，考虑禁用数据源
        if metrics['consecutive_failures'] >= 10:
            logger.warning(f"⚠️ {source.name} 连续失败 {metrics['consecutive_failures']} 次，考虑暂时禁用")
        
        logger.debug(f"❌ {source.name} 健康检查失败: {reason}")
    
    async def close(self):
        """关闭所有数据源"""
        logger.info("关闭数据源管理器...")
        
        # 停止健康监控
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        for source in self.data_sources.values():
            if source.instance and hasattr(source.instance, 'close'):
                try:
                    await source.instance.close()
                except Exception as e:
                    logger.error(f"关闭数据源 {source.name} 失败: {e}")
        
        self.initialized = False


# 全局实例
_data_source_manager: Optional[DataSourceManager] = None


async def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _data_source_manager
    
    if _data_source_manager is None:
        _data_source_manager = DataSourceManager()
        await _data_source_manager.initialize()
    
    return _data_source_manager


async def close_data_source_manager():
    """关闭全局数据源管理器"""
    global _data_source_manager
    
    if _data_source_manager:
        await _data_source_manager.close()
        _data_source_manager = None