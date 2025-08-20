# encoding:utf-8
"""
AmazingData 数据提供者
提供 AmazingData SDK 的完整功能接入
Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

import pandas as pd
from loguru import logger

# AmazingData SDK
try:
    import AmazingData as ad

    HAS_AMAZINGDATA = True
except ImportError:
    HAS_AMAZINGDATA = False
    ad = None
    logger.error("AmazingData SDK 未安装，请先安装: pip install AmazingData")

from .base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataSourceType,
    DataProviderError
)


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
        super().__init__(
            name="amazingdata",
            source_type=DataSourceType.CUSTOM,
            **kwargs
        )
        self.username = username
        self.password = password
        self.host = host
        self.port = port

        # AmazingData 特有配置
        self.heartbeat_interval = kwargs.get('heartbeat_interval', 30)
        self.subscription_batch_size = kwargs.get('subscription_batch_size', 100)
        self.max_subscriptions = kwargs.get('max_subscriptions', 500)
        self.auto_reconnect = kwargs.get('auto_reconnect', True)
        self.reconnect_interval = kwargs.get('reconnect_interval', 5)


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

        # 订阅管理
        self._subscriptions = {}  # {symbol: {callbacks: [], subscription_id: str}}
        self._subscription_data = None  # SubscribeData 实例

        # 统计信息
        self._stats = {
            'queries': 0,
            'query_errors': 0,
            'subscriptions': 0,
            'messages_received': 0,
            'last_heartbeat': None
        }

        if not HAS_AMAZINGDATA:
            raise DataProviderError("AmazingData SDK 未安装")

    async def _initialize_source(self) -> None:
        """初始化数据源"""
        logger.info(f"初始化 AmazingData 数据源...")

        # 执行登录
        await self._login()

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

        # 登出
        await self._logout()

    async def _login(self) -> bool:
        """
        登录 AmazingData
        
        Returns:
            是否登录成功
        """
        try:
            logger.info(f"正在登录 AmazingData (host={self.config.host}:{self.config.port})...")

            # 在线程池中执行同步登录
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                ad.login,
                self.config.username,
                self.config.password,
                self.config.host,
                self.config.port
            )

            if result == 0:  # 登录成功返回 0
                self._connected = True
                self._login_time = datetime.now()
                logger.info("✅ AmazingData 登录成功")
                return True
            else:
                logger.error(f"❌ AmazingData 登录失败，错误码: {result}")
                return False

        except Exception as e:
            logger.error(f"❌ AmazingData 登录异常: {e}")
            return False

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
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                if self._connected:
                    # 发送心跳（通过查询一个简单数据来保持连接）
                    try:
                        loop = asyncio.get_event_loop()
                        # 查询交易日历作为心跳
                        await loop.run_in_executor(
                            None,
                            ad.BaseData.get_trading_calendar,
                            datetime.now().strftime('%Y%m%d'),
                            datetime.now().strftime('%Y%m%d')
                        )
                        self._stats['last_heartbeat'] = datetime.now()
                        logger.debug("💓 AmazingData 心跳成功")
                    except Exception as e:
                        logger.warning(f"心跳失败: {e}")
                        self._connected = False

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
                    logger.info("检测到连接断开，尝试重连...")
                    if await self._login():
                        logger.info("✅ 重连成功")
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
        logger.info("恢复订阅...")
        for symbol, info in self._subscriptions.items():
            # 重新订阅每个符号
            pass  # TODO: 实现订阅恢复

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
            if data:
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

            if data:
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
