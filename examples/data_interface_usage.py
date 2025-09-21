# encoding:utf-8
"""
数据接口层使用示例
演示如何使用统一的数据接口访问星耀数智数据
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
from loguru import logger

from deepsearch.interfaces.data import (
    AmazingDataConfig,
    AmazingDataProvider,
    DataCache,
    SecurityType,
    PeriodType,
    AdjustType,
    DataProviderError,
    AuthenticationError,
    RateLimitError
)


class DataInterfaceExample:
    """数据接口使用示例"""

    def __init__(self):
        self.provider = None
        self.cache = None

    async def setup(self):
        """初始化设置"""
        # 创建缓存
        self.cache = DataCache(
            ttl=300,
            memory_size=1000,
            redis_config=None  # 可选配置Redis
        )

        # 创建配置
        config = AmazingDataConfig(
            username="your_username",  # 替换为实际用户名
            password="your_password",  # 替换为实际密码
            host="120.86.124.106",
            port=8600,
            cache_enabled=True,
            cache_ttl=300,
            auto_reconnect=True
        )

        # 创建数据提供者
        self.provider = AmazingDataProvider(config)

        # 初始化
        try:
            await self.provider.initialize()
            logger.info("数据接口初始化成功")
        except AuthenticationError as e:
            logger.error(f"认证失败: {e.message}")
            raise
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        if self.provider:
            await self.provider.disconnect()
            logger.info("已断开数据源连接")

    async def example_basic_data(self):
        """基础数据示例"""
        logger.info("=" * 50)
        logger.info("基础数据示例")

        # 获取A股代码列表
        stock_list = await self.provider.get_code_list(SecurityType.STOCK_A)
        logger.info(f"A股总数: {len(stock_list)}")
        logger.info(f"前10个: {stock_list[:10]}")

        # 获取ETF列表
        etf_list = await self.provider.get_code_list(SecurityType.ETF)
        logger.info(f"ETF总数: {len(etf_list)}")

        # 获取交易日历
        today = datetime.now()
        start_date = (today - timedelta(days=30)).strftime('%Y%m%d')
        end_date = today.strftime('%Y%m%d')
        trading_days = await self.provider.get_trading_calendar(
            start_date, end_date
        )
        logger.info(f"最近30天交易日: {len(trading_days)}天")

    async def example_market_data(self):
        """市场数据示例"""
        logger.info("=" * 50)
        logger.info("市场数据示例")

        # 获取日K线
        kline_df = await self.provider.get_kline(
            symbol='000001',
            period=PeriodType.DAILY,
            start_date='20250101',
            end_date='20250115',
            adjust=AdjustType.FORWARD  # 前复权
        )
        if not kline_df.empty:
            logger.info(f"获取到{len(kline_df)}条K线数据")
            logger.info(f"最新收盘价: {kline_df['close'].iloc[-1]}")
            logger.info(f"平均成交量: {kline_df['volume'].mean():.0f}")

        # 获取分钟K线
        minute_df = await self.provider.get_kline(
            symbol='000001',
            period=PeriodType.MINUTE_5,
            count=100  # 最近100条
        )
        if not minute_df.empty:
            logger.info(f"获取到{len(minute_df)}条5分钟K线")

        # 获取实时快照
        symbols = ['000001', '000002', '600000']
        snapshot = await self.provider.get_snapshot(symbols)
        logger.info("实时行情:")
        for symbol, data in snapshot.items():
            logger.info(
                f"  {symbol} {data['name']}: "
                f"{data['last_price']} ({data['change_percent']:+.2f}%)"
            )

    async def example_financial_data(self):
        """财务数据示例"""
        logger.info("=" * 50)
        logger.info("财务数据示例")

        symbols = ['000001', '600000']

        # 获取主要财务指标
        indicators = await self.provider.get_key_indicators(
            symbols, '2024Q3'
        )
        if not indicators.empty:
            logger.info("主要财务指标:")
            for symbol in symbols:
                symbol_data = indicators[indicators['symbol'] == symbol]
                if not symbol_data.empty:
                    row = symbol_data.iloc[0]
                    logger.info(f"  {symbol}:")
                    logger.info(f"    ROE: {row.get('roe', 0):.2f}%")
                    logger.info(f"    EPS: {row.get('eps', 0):.2f}")
                    logger.info(f"    资产负债率: {row.get('debt_ratio', 0):.2f}%")

    async def example_special_data(self):
        """特色数据示例"""
        logger.info("=" * 50)
        logger.info("特色数据示例")

        # 获取龙虎榜
        dragon_tiger = await self.provider.get_dragon_tiger(
            start_date='20250101',
            end_date='20250115'
        )
        if not dragon_tiger.empty:
            logger.info(f"龙虎榜记录数: {len(dragon_tiger)}")
            latest = dragon_tiger.iloc[0]
            logger.info(
                f"最新: {latest['symbol']} {latest['name']} "
                f"净买入: {latest.get('net_amount', 0) / 10000:.2f}万"
            )

        # 获取北向资金
        north_flow = await self.provider.get_north_flow(
            start_date='20250101',
            end_date='20250115'
        )
        if not north_flow.empty:
            logger.info(f"北向资金记录数: {len(north_flow)}")
            total = north_flow['total_flow'].sum()
            logger.info(f"期间净流入: {total / 100000000:.2f}亿")

    async def example_subscription(self):
        """订阅数据示例"""
        logger.info("=" * 50)
        logger.info("订阅数据示例")

        # 定义回调函数
        def on_snapshot(data):
            logger.info(f"收到快照: {data}")

        # 订阅实时快照
        success = await self.provider.subscribe(
            symbols=['000001', '600000'],
            data_type=PeriodType.SNAPSHOT,
            callback=on_snapshot
        )

        if success:
            logger.info("订阅成功，等待推送...")
            # 等待一段时间接收数据
            await asyncio.sleep(10)

            # 取消订阅
            await self.provider.unsubscribe(['000001', '600000'])
            logger.info("已取消订阅")

    async def example_error_handling(self):
        """错误处理示例"""
        logger.info("=" * 50)
        logger.info("错误处理示例")

        async def safe_get_data(symbol: str) -> pd.DataFrame:
            """安全获取数据"""
            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                try:
                    # 尝试获取数据
                    df = await self.provider.get_kline(symbol)
                    return df

                except AuthenticationError as e:
                    logger.error(f"认证失败: {e.message}")
                    # 重新连接
                    await self.provider.connect()

                except RateLimitError as e:
                    logger.warning(f"触发限流: {e.message}")
                    # 等待后重试
                    wait_time = e.details.get('retry_after', retry_delay)
                    await asyncio.sleep(wait_time)

                except DataProviderError as e:
                    logger.error(f"数据错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        raise

            return pd.DataFrame()

        # 测试错误处理
        df = await safe_get_data('000001')
        if not df.empty:
            logger.info("成功获取数据")
        else:
            logger.warning("获取数据失败")

    async def example_performance(self):
        """性能优化示例"""
        logger.info("=" * 50)
        logger.info("性能优化示例")

        # 批量获取多个股票的K线
        symbols = ['000001', '000002', '600000', '600036']

        # 方法1：串行获取（慢）
        start_time = asyncio.get_event_loop().time()
        for symbol in symbols:
            await self.provider.get_kline(symbol, count=100)
        serial_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"串行获取耗时: {serial_time:.2f}秒")

        # 方法2：并发获取（快）
        start_time = asyncio.get_event_loop().time()
        tasks = [
            self.provider.get_kline(symbol, count=100)
            for symbol in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        parallel_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"并发获取耗时: {parallel_time:.2f}秒")
        logger.info(f"性能提升: {serial_time / parallel_time:.1f}倍")

        # 处理结果
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"{symbol}获取失败: {result}")
            else:
                logger.info(f"{symbol}获取成功: {len(result)}条")

    async def run_all_examples(self):
        """运行所有示例"""
        try:
            await self.setup()

            # 运行各个示例
            await self.example_basic_data()
            await self.example_market_data()
            await self.example_financial_data()
            await self.example_special_data()
            # await self.example_subscription()  # 需要实时数据权限
            await self.example_error_handling()
            await self.example_performance()

            # 显示统计信息
            stats = await self.provider.get_statistics()
            logger.info("=" * 50)
            logger.info("统计信息:")
            logger.info(f"  查询次数: {stats['statistics']['queries']}")
            logger.info(f"  错误次数: {stats['statistics']['query_errors']}")
            logger.info(f"  缓存命中: {stats['statistics']['cache_hits']}")
            logger.info(f"  缓存未命中: {stats['statistics']['cache_misses']}")

            if stats['statistics']['queries'] > 0:
                hit_rate = stats['statistics']['cache_hits'] / stats['statistics']['queries']
                logger.info(f"  缓存命中率: {hit_rate:.1%}")

        finally:
            await self.cleanup()


async def main():
    """主函数"""
    # 配置日志
    logger.add("data_interface_example.log", level="DEBUG")

    # 运行示例
    example = DataInterfaceExample()
    await example.run_all_examples()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())