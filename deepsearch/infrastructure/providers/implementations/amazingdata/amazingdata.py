# encoding:utf-8
"""
AmazingData 数据提供者
提供 AmazingData SDK 的完整功能接入

重要说明：
- 本项目只使用 AmazingData (银河证券星耀数智) API接口
- 不使用 TGW 接口，请勿混淆两者
- AmazingData 是项目的主要数据源
- TGW 库仅作为备用保留，未集成到系统中

Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
import random
import time
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Any, Callable

import pandas as pd
from loguru import logger

from deepsearch.utils.network.connection_pool import ConnectionPool, PoolConfig

from deepsearch.observability.monitoring.data_source_monitor import DataAccessType
from deepsearch.observability.decorators.decorators import monitor_data_source

# AmazingData SDK
try:
    import AmazingData as ad

    HAS_AMAZINGDATA = True
except ImportError:
    HAS_AMAZINGDATA = False
    ad = None
    logger.error("AmazingData SDK 未安装，请先安装: pip install AmazingData")

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataSourceType,
    DataProviderError
)


def async_retry(max_attempts=3, backoff_base=2, max_delay=60, jitter=True):
    """
    异步重试装饰器，支持指数退避和抖动
    
    Args:
        max_attempts: 最大重试次数
        backoff_base: 退避基数
        max_delay: 最大延迟时间（秒）
        jitter: 是否添加随机抖动
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        raise
                    
                    delay = min(backoff_base ** attempt, max_delay)
                    if jitter:
                        delay += random.uniform(0, 1)
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}, retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class AmazingDataConfig(DataProviderConfig):
    """AmazingData 配置"""

    def __init__(
            self,
            username: str,
            password: str,
            host: str,
            port: int,
            **kwargs
    ):
        # 提取AmazingData特有的参数
        heartbeat_interval = kwargs.pop('heartbeat_interval', 60)  # 增加到60秒，减少心跳频率
        subscription_batch_size = kwargs.pop('subscription_batch_size', 100)
        max_subscriptions = kwargs.pop('max_subscriptions', 500)
        auto_reconnect = kwargs.pop('auto_reconnect', True)
        reconnect_interval = kwargs.pop('reconnect_interval', 10)  # 增加重连间隔到10秒
        subscription_enabled = kwargs.pop('subscription_enabled', True)

        # 调用父类初始化（只传递父类接受的参数）
        # 注意：DataProviderConfig 是 dataclass，不接受 source_type
        super().__init__(
            name="amazingdata",
            **kwargs
        )
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.source_type = DataSourceType.AMAZINGDATA  # 手动设置数据源类型

        # AmazingData 特有配置
        self.heartbeat_interval = heartbeat_interval
        self.subscription_batch_size = subscription_batch_size
        self.max_subscriptions = max_subscriptions
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.subscription_enabled = subscription_enabled


class AmazingDataProvider(DataProvider):
    """
    AmazingData 数据提供者
    
    提供完整的 AmazingData SDK 功能接入，包括：
    - 基础数据查询 (BaseData)
    - 市场数据查询 (MarketData)
    - 资讯数据查询 (InfoData)
    - 实时数据订阅 (SubscribeData)
    """

    def __init__(self, config: AmazingDataConfig):
        """
        初始化 AmazingData 提供者
        
        Args:
            config: AmazingData 配置
        """
        super().__init__(config)

        self.config: AmazingDataConfig = config
        self._connected = False
        self._login_time = None
        self._reconnect_task = None

        # 连接池配置
        self._connection_pool = None
        self._pool_config = PoolConfig(
            min_size=2,
            max_size=10,
            idle_timeout=300,
            validation_interval=60,
            acquire_timeout=5.0
        )

        # 订阅管理
        self._subscriptions = {}  # {symbol: {callbacks: [], subscription_id: str}}
        self._subscription_data = None  # SubscribeData 实例

        # 统计信息
        self._stats = {
            'queries': 0,
            'query_errors': 0,
            'subscriptions': 0,
            'messages_received': 0,
            'last_heartbeat': None,
            'pool_stats': {}
        }

        if not HAS_AMAZINGDATA:
            raise DataProviderError("AmazingData SDK 未安装")

    async def _initialize_source(self) -> None:
        """初始化数据源"""
        logger.info(f"初始化 AmazingData 数据源...")

        # 初始化连接池
        self._connection_pool = ConnectionPool(
            factory=self._create_connection,
            config=self._pool_config,
            validator=self._validate_connection,
            closer=self._close_connection
        )
        await self._connection_pool.initialize()

        # 执行登录（带重试）
        await self._login_with_retry()

        # 启动心跳任务
        if self.config.heartbeat_interval > 0:
            asyncio.create_task(self._heartbeat_loop())

        # 启动自动重连任务
        if self.config.auto_reconnect:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

        logger.info("✅ AmazingData 初始化成功")

    async def _start_source(self) -> None:
        """启动数据源"""
        logger.info("启动 AmazingData 数据源...")

        # 初始化订阅管理器
        if self.config.subscription_enabled:
            await self._init_subscription_manager()

    async def _stop_source(self) -> None:
        """停止数据源"""
        logger.info("停止 AmazingData 数据源...")

        # 停止订阅
        if self._subscription_data:
            try:
                # 停止订阅线程
                if hasattr(self._subscription_data, 'stop'):
                    self._subscription_data.stop()
            except Exception as e:
                logger.error(f"停止订阅失败: {e}")

        # 停止重连任务
        if self._reconnect_task:
            self._reconnect_task.cancel()

        # 关闭连接池
        if self._connection_pool:
            await self._connection_pool.close()

        # 登出
        await self._logout()
    
    async def _create_connection(self):
        """创建新的数据连接"""
        # AmazingData 使用单例模式，这里返回一个连接标识
        return {
            'id': id(self),
            'created_at': time.time(),
            'active': True
        }
    
    async def _validate_connection(self, conn) -> bool:
        """验证连接是否有效"""
        # 检查连接是否还活跃
        if not conn.get('active'):
            return False
        
        # 检查是否登录状态
        if not self._connected:
            return False
        
        # 可以添加一个简单的测试查询
        return True
    
    async def _close_connection(self, conn):
        """关闭连接"""
        if conn:
            conn['active'] = False

    @async_retry(max_attempts=3, backoff_base=2)
    async def _login_with_retry(self) -> bool:
        """带重试机制的登录"""
        return await self._login()
    
    async def _login(self) -> bool:
        """
        安全的登录方法，隔离SDK的SystemExit

        Returns:
            是否登录成功

        Raises:
            DataProviderError: 包含详细错误信息
        """
        def safe_login():
            """
            包装的登录函数，捕获所有异常包括SystemExit
            使用线程执行，避免signal在非主线程中的限制

            错误码定义：
            -999: SDK调用了exit()
            -998: 其他未知异常
            -997: 网络连接失败
            """
            import threading
            import traceback

            # 用于存储登录结果
            result_holder = {'result': None, 'exception': None}

            def login_in_thread():
                """在独立线程中执行登录"""
                try:
                    result = ad.login(
                        self.config.username,
                        self.config.password,
                        self.config.host,
                        self.config.port
                    )
                    result_holder['result'] = result

                except SystemExit as e:
                    # SDK尝试退出程序
                    logger.critical(f"CRITICAL: AmazingData SDK attempted system exit with code: {e.code}")
                    logger.critical(f"Stack trace: {traceback.format_exc()}")
                    result_holder['result'] = -999
                    result_holder['exception'] = e

                except ConnectionError as e:
                    logger.error(f"Network connection failed: {e}")
                    result_holder['result'] = -997
                    result_holder['exception'] = e

                except Exception as e:
                    logger.error(f"Unexpected error in SDK login: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    result_holder['result'] = -998
                    result_holder['exception'] = e

            # 创建并启动线程
            thread = threading.Thread(target=login_in_thread, daemon=True)
            thread.start()

            # 等待线程完成，最多等待30秒
            thread.join(timeout=30)

            # 检查线程是否仍在运行（超时情况）
            if thread.is_alive():
                logger.error("Login thread timeout after 30 seconds")
                # 注意：线程可能仍在后台运行
                return -998  # 返回未知错误码

            # 返回结果
            if result_holder['result'] is None:
                logger.error("Login thread did not produce a result")
                return -998

            return result_holder['result']

        try:
            logger.info(f"Attempting safe login to AmazingData (host={self.config.host}:{self.config.port})")

            loop = asyncio.get_event_loop()

            # 在线程池中执行包装的登录函数
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, safe_login),
                    timeout=self.config.timeout or 5.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Login timeout after {self.config.timeout or 5}s")
                raise DataProviderError(
                    "AmazingData登录超时，可能的原因：\n"
                    "1. 网络连接问题\n"
                    "2. 服务器地址错误\n"
                    "3. 防火墙阻止连接"
                )

            # 处理返回结果
            if result == -999:
                # SDK强制退出 - 严重错误
                error_msg = (
                    "AmazingData SDK尝试强制退出程序（SystemExit）。\n"
                    "这通常由以下原因导致：\n"
                    "1. TGW初始化失败：检查网络模式配置\n"
                    "2. 推送服务器连接失败：检查8600端口是否可访问\n"
                    "3. 认证Token无效：检查用户名密码\n"
                    "建议：系统将自动降级到备用数据源"
                )
                logger.critical(error_msg)

                # 触发监控告警
                await self._trigger_alert("SDK_EXIT", error_msg)

                raise DataProviderError(error_msg)

            elif result == -997:
                raise DataProviderError("网络连接失败，请检查网络设置")

            elif result == -998:
                raise DataProviderError("SDK内部错误，请查看日志")

            elif result == 0 or result is True:
                # 登录成功
                self._connected = True
                self._login_time = datetime.now()
                logger.info("AmazingData login successful")
                return True

            else:
                # 其他错误码
                error_msg = f"AmazingData登录失败，错误码: {result}"
                logger.error(error_msg)
                raise DataProviderError(error_msg)

        except DataProviderError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during login process: {e}")
            raise DataProviderError(f"登录过程异常: {e}")

    async def _logout(self) -> None:
        """登出 AmazingData"""
        try:
            if self._connected:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, ad.logout)
                self._connected = False
                logger.info("AmazingData 已登出")
        except Exception as e:
            logger.error(f"登出失败: {e}")

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        consecutive_failures = 0  # 连续失败计数
        max_consecutive_failures = 3  # 最大连续失败次数
        
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                if self._connected:
                    # 发送心跳（通过查询一个简单数据来保持连接）
                    try:
                        loop = asyncio.get_event_loop()
                        # 查询交易日历作为心跳，设置超时
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                ad.BaseData.get_trading_calendar,
                                datetime.now().strftime('%Y%m%d'),
                                datetime.now().strftime('%Y%m%d')
                            ),
                            timeout=10.0  # 10秒超时
                        )
                        self._stats['last_heartbeat'] = datetime.now()
                        consecutive_failures = 0  # 重置失败计数
                        
                        # 减少心跳日志噪音，每10分钟记录一次
                        if self._stats.get('heartbeat_count', 0) % 10 == 0:  # 60秒一次，10次=10分钟
                            logger.info("✅ AmazingData heartbeat OK | count={}".format(
                                self._stats.get('heartbeat_count', 0)
                            ))
                        self._stats['heartbeat_count'] = self._stats.get('heartbeat_count', 0) + 1
                        
                    except asyncio.TimeoutError:
                        consecutive_failures += 1
                        logger.warning(f"AmazingData heartbeat timeout ({consecutive_failures}/{max_consecutive_failures})")
                        
                        # 连续失败超过阈值才断开连接
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(f"AmazingData heartbeat failed {consecutive_failures} times, disconnecting")
                            self._connected = False
                            consecutive_failures = 0
                            
                    except Exception as e:
                        consecutive_failures += 1
                        # 只在连续失败多次后才记录错误
                        if consecutive_failures >= max_consecutive_failures:
                            from deepsearch.observability.log_standard import LogStandard
                            logger.error(
                                f"AmazingData heartbeat failed {consecutive_failures} times",
                                extra=LogStandard.format_error(e, include_traceback=False)
                            )
                            self._connected = False
                            consecutive_failures = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳循环异常: {e}")

    async def _reconnect_loop(self) -> None:
        """自动重连循环"""
        while True:
            try:
                await asyncio.sleep(self.config.reconnect_interval)

                if not self._connected:
                    logger.info("AmazingData reconnecting | attempts={}".format(
                        self._stats.get('reconnect_attempts', 0)
                    ))
                    self._stats['reconnect_attempts'] = self._stats.get('reconnect_attempts', 0) + 1
                    if await self._login():
                        logger.info("AmazingData reconnected | attempts={}".format(
                            self._stats.get('reconnect_attempts', 0)
                        ))
                        self._stats['reconnect_attempts'] = 0
                        # 恢复订阅
                        if self._subscriptions:
                            await self._restore_subscriptions()
                    else:
                        logger.warning("重连失败，稍后重试...")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"重连循环异常: {e}")

    async def _restore_subscriptions(self) -> None:
        """恢复订阅"""
        logger.debug("Restoring subscriptions | count={}".format(len(self._subscriptions)))
        for symbol, info in self._subscriptions.items():
            # 重新订阅每个符号
            pass  # TODO: 实现订阅恢复

    async def _trigger_alert(self, alert_type: str, message: str) -> None:
        """
        触发监控告警

        Args:
            alert_type: 告警类型（如 SDK_EXIT, CONNECTION_LOST等）
            message: 告警消息
        """
        try:
            # 记录到日志
            logger.critical(f"[ALERT][{alert_type}] {message}")

            # 更新统计信息
            if alert_type not in self._stats:
                self._stats[alert_type] = []

            self._stats[alert_type].append({
                'timestamp': datetime.now().isoformat(),
                'message': message
            })

            # 保留最近的10条告警记录
            if len(self._stats[alert_type]) > 10:
                self._stats[alert_type] = self._stats[alert_type][-10:]

            # TODO: 未来可以集成外部告警系统（邮件、微信、钉钉等）

        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")

    # ==================== 数据查询接口 ====================

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的统一接口
        
        Args:
            request: 数据请求
            
        Returns:
            数据 DataFrame
        """
        if not self._connected:
            raise DataProviderError("AmazingData 未连接")

        # 根据请求类型调用不同的接口
        if 'data_type' in request.extra_params:
            data_type = request.extra_params['data_type']

            if data_type == 'kline':
                return await self.get_kline(
                    symbol=request.symbol,
                    period=request.period,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    adjust=request.adjust
                )
            elif data_type == 'realtime':
                quotes = await self.get_realtime_quote(request.symbols or [request.symbol])
                return pd.DataFrame(quotes).T
            elif data_type == 'financial':
                return await self.get_financial_data(
                    symbol=request.symbol,
                    report_type=request.extra_params.get('report_type', 'balance_sheet')
                )
            else:
                raise DataProviderError(f"不支持的数据类型: {data_type}")
        else:
            # 默认返回K线数据
            return await self.get_kline(
                symbol=request.symbol,
                period=request.period,
                start_date=request.start_date,
                end_date=request.end_date,
                adjust=request.adjust
            )

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.HISTORICAL_KLINE,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get('symbol')
    )
    async def get_kline(
            self,
            symbol: str,
            period: str = '1d',
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            count: int = 0,
            adjust: str = 'none'
    ) -> pd.DataFrame:
        """
        获取K线数据
        
        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数
            adjust: 复权类型 (none, qfq, hfq)
            
        Returns:
            K线数据 DataFrame
        """
        try:
            self._stats['queries'] += 1

            # 转换周期格式
            period_map = {
                '1m': ad.constant.Period.m1.value,
                '5m': ad.constant.Period.m5.value,
                '15m': ad.constant.Period.m15.value,
                '30m': ad.constant.Period.m30.value,
                '60m': ad.constant.Period.m60.value,
                '1d': ad.constant.Period.day.value,
                '1w': ad.constant.Period.week.value,
                '1M': ad.constant.Period.month.value
            }
            ad_period = period_map.get(period, ad.constant.Period.day.value)

            # 转换复权类型
            adjust_map = {
                'none': ad.constant.Adjust.none.value,
                'qfq': ad.constant.Adjust.forward.value,
                'hfq': ad.constant.Adjust.backward.value
            }
            ad_adjust = adjust_map.get(adjust, ad.constant.Adjust.none.value)

            # 调用 SDK 获取数据
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.MarketData.get_kline_data,
                [symbol],  # 股票列表
                ad_period,  # 周期
                start_date or '',  # 开始时间
                end_date or '',  # 结束时间
                count,  # 条数
                ad_adjust,  # 复权类型
                True  # 是否填充停牌数据
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
                df.rename(columns={
                    'time': 'datetime',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume',
                    'amount': 'amount'
                }, inplace=True)

                # 设置时间索引
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df.set_index('datetime', inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取K线数据失败: {e}")
            raise DataProviderError(f"获取K线数据失败: {e}")

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.REALTIME_QUOTE,
        extract_symbol=lambda *args, **kwargs: ','.join(args[1]) if len(args) > 1 and isinstance(args[1], list) else ','.join(kwargs.get('symbols', []))
    )
    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            {symbol: quote_data}
        """
        try:
            self._stats['queries'] += 1

            # 调用 SDK 获取快照数据
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.MarketData.get_snapshot,
                symbols
            )

            result = {}
            if data is not None and (isinstance(data, dict) and data or isinstance(data, pd.DataFrame) and not data.empty):
                for symbol in symbols:
                    if symbol in data:
                        snapshot = data[symbol]
                        result[symbol] = {
                            'symbol': symbol,
                            'name': snapshot.get('name', ''),
                            'last': snapshot.get('last_price', 0),
                            'open': snapshot.get('open', 0),
                            'high': snapshot.get('high', 0),
                            'low': snapshot.get('low', 0),
                            'close': snapshot.get('prev_close', 0),
                            'volume': snapshot.get('volume', 0),
                            'amount': snapshot.get('amount', 0),
                            'bid1': snapshot.get('bid1', 0),
                            'ask1': snapshot.get('ask1', 0),
                            'bid1_volume': snapshot.get('bid1_volume', 0),
                            'ask1_volume': snapshot.get('ask1_volume', 0),
                            'change': snapshot.get('change', 0),
                            'change_percent': snapshot.get('change_percent', 0),
                            'time': snapshot.get('time', ''),
                            'status': snapshot.get('status', '')
                        }

            return result

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取实时行情失败: {e}")
            return {}

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.FINANCIAL_DATA,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get('symbol')
    )
    async def get_financial_data(
            self,
            symbol: str,
            report_type: str = 'balance_sheet',
            report_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取财务数据
        
        Args:
            symbol: 股票代码
            report_type: 报表类型 (balance_sheet, income_statement, cash_flow)
            report_date: 报告期
            
        Returns:
            财务数据 DataFrame
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()

            # 根据报表类型调用不同的接口
            if report_type == 'balance_sheet':
                data = await loop.run_in_executor(
                    None,
                    ad.InfoData.get_balance_sheet,
                    [symbol],
                    report_date or ''
                )
            elif report_type == 'income_statement':
                data = await loop.run_in_executor(
                    None,
                    ad.InfoData.get_income_statement,
                    [symbol],
                    report_date or ''
                )
            elif report_type == 'cash_flow':
                data = await loop.run_in_executor(
                    None,
                    ad.InfoData.get_cash_flow,
                    [symbol],
                    report_date or ''
                )
            else:
                raise DataProviderError(f"不支持的报表类型: {report_type}")

            if data and symbol in data:
                return pd.DataFrame(data[symbol])
            else:
                return pd.DataFrame()

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取财务数据失败: {e}")
            raise DataProviderError(f"获取财务数据失败: {e}")

    async def get_key_indicators(
            self,
            symbol: str,
            report_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取主要财务指标
        
        Args:
            symbol: 股票代码
            report_date: 报告期
            
        Returns:
            主要指标 DataFrame
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.InfoData.get_key_indicators,
                [symbol],
                report_date or ''
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
                df.rename(columns={
                    'roa': 'roa',  # 总资产收益率
                    'roe': 'roe',  # 净资产收益率
                    'eps': 'eps',  # 每股收益
                    'bps': 'bvps',  # 每股净资产
                    'gross_margin': 'gross_profit_margin',  # 毛利率
                    'net_margin': 'net_profit_margin',  # 净利率
                    'debt_ratio': 'asset_liability_ratio',  # 资产负债率
                    'current_ratio': 'current_ratio',  # 流动比率
                    'quick_ratio': 'quick_ratio',  # 速动比率
                }, inplace=True)
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取主要指标失败: {e}")
            raise DataProviderError(f"获取主要指标失败: {e}")

    async def get_shareholder_info(
            self,
            symbol: str,
            report_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取股东信息
        
        Args:
            symbol: 股票代码
            report_date: 报告期
            
        Returns:
            股东信息字典
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()

            # 获取十大股东
            top10_holders = await loop.run_in_executor(
                None,
                ad.InfoData.get_top10_holders,
                [symbol],
                report_date or ''
            )

            # 获取十大流通股东
            top10_tradable = await loop.run_in_executor(
                None,
                ad.InfoData.get_top10_tradable_holders,
                [symbol],
                report_date or ''
            )

            # 获取股东户数
            holder_num = await loop.run_in_executor(
                None,
                ad.InfoData.get_holder_num,
                [symbol],
                report_date or ''
            )

            result = {
                'symbol': symbol,
                'report_date': report_date,
                'top10_holders': [],
                'top10_tradable': [],
                'holder_num': None,
                'avg_holding': None
            }

            # 处理十大股东数据
            if top10_holders and symbol in top10_holders:
                for holder in top10_holders[symbol]:
                    result['top10_holders'].append({
                        'name': holder.get('holder_name', ''),
                        'holding': holder.get('hold_num', 0),
                        'ratio': holder.get('hold_ratio', 0)
                    })

            # 处理十大流通股东数据
            if top10_tradable and symbol in top10_tradable:
                for holder in top10_tradable[symbol]:
                    result['top10_tradable'].append({
                        'name': holder.get('holder_name', ''),
                        'holding': holder.get('hold_num', 0),
                        'ratio': holder.get('hold_ratio', 0)
                    })

            # 处理股东户数
            if holder_num and symbol in holder_num:
                result['holder_num'] = holder_num[symbol].get('holder_num', 0)
                result['avg_holding'] = holder_num[symbol].get('avg_hold', 0)

            return result

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取股东信息失败: {e}")
            return {}

    async def get_dragon_tiger(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取龙虎榜数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            龙虎榜数据列表
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.InfoData.get_dragon_tiger,
                [symbol],
                start_date or '',
                end_date or ''
            )

            result = []
            if data and symbol in data:
                for item in data[symbol]:
                    record = {
                        'symbol': symbol,
                        'trade_date': item.get('trade_date', ''),
                        'reason': item.get('reason', ''),
                        'buy_amount': item.get('buy_amount', 0),
                        'sell_amount': item.get('sell_amount', 0),
                        'net_amount': item.get('net_amount', 0),
                        'turnover_rate': item.get('turnover_rate', 0),
                        'buy_list': [],
                        'sell_list': []
                    }

                    # 买入席位
                    if 'buy_list' in item:
                        for seat in item['buy_list']:
                            record['buy_list'].append({
                                'name': seat.get('seat_name', ''),
                                'amount': seat.get('buy_amount', 0)
                            })

                    # 卖出席位
                    if 'sell_list' in item:
                        for seat in item['sell_list']:
                            record['sell_list'].append({
                                'name': seat.get('seat_name', ''),
                                'amount': seat.get('sell_amount', 0)
                            })

                    result.append(record)

            return result

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取龙虎榜数据失败: {e}")
            return []

    async def get_margin_trading(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取融资融券数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            融资融券数据 DataFrame
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.InfoData.get_margin_trading,
                [symbol],
                start_date or '',
                end_date or ''
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
                df.rename(columns={
                    'fin_balance': 'margin_balance',  # 融资余额
                    'fin_buy': 'margin_buy',  # 融资买入
                    'fin_repay': 'margin_repay',  # 融资偿还
                    'sec_balance': 'short_balance',  # 融券余额
                    'sec_sell': 'short_sell',  # 融券卖出
                    'sec_repay': 'short_repay',  # 融券偿还
                    'fin_sec_ratio': 'margin_ratio'  # 融资融券比率
                }, inplace=True)

                # 时间处理
                if 'trade_date' in df.columns:
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
                    df.set_index('trade_date', inplace=True)
                    df.sort_index(inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取融资融券数据失败: {e}")
            raise DataProviderError(f"获取融资融券数据失败: {e}")

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.NORTH_FLOW,
        extract_symbol=lambda *args, **kwargs: "NORTH_FLOW"
    )
    async def get_north_flow(
            self,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取北向资金流向数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            北向资金数据 DataFrame
        """
        try:
            self._stats['queries'] += 1

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                ad.InfoData.get_north_flow,
                start_date or '',
                end_date or ''
            )

            if data is not None and (not hasattr(data, 'empty') or (hasattr(data, '__len__') and len(data) > 0)):
                df = pd.DataFrame(data)
                # 标准化列名
                df.rename(columns={
                    'trade_date': 'date',
                    'sh_flow': 'shanghai_flow',  # 沪股通流入
                    'sz_flow': 'shenzhen_flow',  # 深股通流入
                    'total_flow': 'total_flow',  # 总流入
                    'sh_balance': 'shanghai_balance',  # 沪股通余额
                    'sz_balance': 'shenzhen_balance',  # 深股通余额
                }, inplace=True)

                # 时间处理
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    df.sort_index(inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._stats['query_errors'] += 1
            logger.error(f"获取北向资金数据失败: {e}")
            raise DataProviderError(f"获取北向资金数据失败: {e}")

    # ==================== 订阅接口 ====================

    async def _init_subscription_manager(self) -> None:
        """初始化订阅管理器"""
        try:
            self._subscription_data = ad.SubscribeData()
            logger.info("订阅管理器初始化成功")
        except Exception as e:
            logger.error(f"订阅管理器初始化失败: {e}")

    async def subscribe_quote(
            self,
            symbols: List[str],
            callback: Callable,
            data_type: str = 'snapshot'
    ) -> bool:
        """
        订阅实时行情
        
        Args:
            symbols: 股票代码列表
            callback: 回调函数
            data_type: 数据类型 (snapshot, kline, tick)
            
        Returns:
            是否订阅成功
        """
        if not self._subscription_data:
            logger.error("订阅管理器未初始化")
            return False

        try:
            # 注册订阅
            if data_type == 'snapshot':
                period = ad.constant.Period.snapshot.value
            elif data_type == 'kline':
                period = ad.constant.Period.m1.value
            elif data_type == 'tick':
                period = ad.constant.Period.tick.value
            else:
                logger.error(f"不支持的订阅类型: {data_type}")
                return False

            # 定义回调包装函数
            @self._subscription_data.register(code_list=symbols, period=period)
            def on_data(data, period):
                self._stats['messages_received'] += 1
                # 转换数据格式并调用用户回调
                asyncio.create_task(self._handle_subscription_data(data, period, callback))

            # 记录订阅信息
            for symbol in symbols:
                if symbol not in self._subscriptions:
                    self._subscriptions[symbol] = {
                        'callbacks': [],
                        'data_type': data_type
                    }
                self._subscriptions[symbol]['callbacks'].append(callback)

            self._stats['subscriptions'] = len(self._subscriptions)

            # 启动订阅线程
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self._subscription_data.run)

            logger.info(f"成功订阅 {len(symbols)} 个股票的 {data_type} 数据")
            return True

        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False

    async def _handle_subscription_data(
            self,
            data: Any,
            period: int,
            callback: Callable
    ) -> None:
        """处理订阅推送的数据"""
        try:
            # 转换数据格式
            converted_data = self._convert_subscription_data(data, period)
            # 调用用户回调
            if asyncio.iscoroutinefunction(callback):
                await callback(converted_data)
            else:
                callback(converted_data)
        except Exception as e:
            logger.error(f"处理订阅数据失败: {e}")

    def _convert_subscription_data(self, data: Any, period: int) -> Dict:
        """转换订阅数据格式"""
        # TODO: 根据数据类型进行格式转换
        return {
            'data': data,
            'period': period,
            'timestamp': datetime.now()
        }

    async def unsubscribe_quote(self, symbols: List[str]) -> bool:
        """
        取消订阅
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            是否取消成功
        """
        try:
            for symbol in symbols:
                if symbol in self._subscriptions:
                    del self._subscriptions[symbol]

            self._stats['subscriptions'] = len(self._subscriptions)
            logger.info(f"取消订阅 {len(symbols)} 个股票")
            return True

        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False

    # ==================== 统计与监控 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = super().get_statistics()
        stats.update({
            'connected': self._connected,
            'login_time': self._login_time.isoformat() if self._login_time else None,
            'amazingdata_stats': self._stats
        })
        return stats

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    # ==================== 实现抽象方法 ====================

    async def initialize(self) -> bool:
        """初始化数据源（实现抽象方法）"""
        try:
            await self._initialize_source()
            await self._start_source()
            return True
        except Exception as e:
            logger.error(f"初始化AmazingData失败: {e}")
            return False

    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表（实现抽象方法）"""
        try:
            # 使用AmazingData SDK获取股票列表
            if not HAS_AMAZINGDATA or not ad:
                logger.warning("AmazingData SDK未安装")
                return []

            loop = asyncio.get_event_loop()
            stock_list = await loop.run_in_executor(
                None,
                ad.BaseData.get_stock_list
            )

            if stock_list is not None and isinstance(stock_list, pd.DataFrame):
                result = stock_list.to_dict('records')
                if limit:
                    result = result[:limit]
                return result
            return []
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """获取K线数据（实现抽象方法）"""
        try:
            # 调用现有的 get_kline 方法
            df = await self.get_kline(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=limit,
                adjust=kwargs.get('adjust', 'none')
            )

            if not df.empty:
                # 重置索引以包含时间列
                df.reset_index(inplace=True)
                return df.to_dict('records')
            return []
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None


# ==================== 工具函数 ====================

def create_amazingdata_provider(config: Dict[str, Any]) -> AmazingDataProvider:
    """
    创建 AmazingData 提供者实例
    
    Args:
        config: 配置字典
        
    Returns:
        AmazingDataProvider 实例
    """
    ad_config = AmazingDataConfig(
        username=config.get('username'),
        password=config.get('password'),
        host=config.get('host', 'localhost'),
        port=config.get('port', 8888),
        enabled=config.get('enabled', True),
        cache_enabled=config.get('cache_enabled', True),
        cache_ttl=config.get('cache_ttl', 300),
        heartbeat_interval=config.get('heartbeat_interval', 30),
        auto_reconnect=config.get('auto_reconnect', True)
    )

    return AmazingDataProvider(ad_config)
