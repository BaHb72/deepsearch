# encoding:utf-8
"""
Free QMT Adapter
免费版QMT适配器 - 功能限制版本
Author: DeepSearch Team
Version: 1.0.0

免费版限制：
1. 无Level2数据权限
2. 部分高级接口不可用
3. 数据延迟可能较大
"""

import time
from typing import Any, Callable, Dict, List

import pandas as pd

from deepsearch.observability import get_logger
from deepsearch.core.utils.status_display import get_status_display

logger = get_logger(__name__)


class FreeQMTAdapter:
    """
    免费版QMT适配器

    专门为免费版QMT用户设计，避开收费功能
    提供基础但实用的数据获取能力
    """

    # 免费版可用功能列表
    FREE_FEATURES = {
        "history_kline": True,  # 历史K线
        "realtime_quote": True,  # 实时行情（Level1）
        "basic_tick": True,  # 基础tick数据
        "financial_data": True,  # 财务数据
        "stock_list": True,  # 股票列表
        "sector_info": True,  # 板块信息
        # 免费版不可用
        "level2_tick": False,  # Level2逐笔
        "level2_order": False,  # Level2逐笔委托
        "longhubang": False,  # 龙虎榜（部分免费版无）
        "north_flow": False,  # 北向资金（部分免费版无）
        "option_data": False,  # 期权数据
        "futures_data": False,  # 期货数据
    }

    def __init__(self):
        """初始化适配器"""
        self.xtdata = None
        self._status = get_status_display()
        self._init_xtdata()

    def _init_xtdata(self):
        """初始化xtdata模块"""
        try:
            import xtquant.xtdata as xtdata

            self.xtdata = xtdata
            logger.info("✅ xtdata模块加载成功")
        except ImportError:
            logger.error("❌ 无法加载xtdata模块，请检查MiniQMT安装")
            raise

    def check_feature_availability(self, feature: str) -> bool:
        """
        检查功能是否可用

        Args:
            feature: 功能名称

        Returns:
            是否可用
        """
        return self.FREE_FEATURES.get(feature, False)

    # ==================== 基础功能实现 ====================

    def get_history_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str = "",
        end_date: str = "",
        count: int = 100,
        adjust: str = "none",
    ) -> pd.DataFrame:
        """
        获取历史K线数据（免费版可用）

        Parameters:
        -----------
        symbol: 股票代码
        period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1mon)
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        count: 数据条数
        adjust: 复权类型 (none, front, back)

        Returns:
        --------
        DataFrame with OHLCV data
        """
        if not self.check_feature_availability("history_kline"):
            raise ValueError("历史K线功能不可用")

        try:
            # 先下载数据到本地
            logger.info(f"下载 {symbol} 的历史数据...")
            self.xtdata.download_history_data(
                stock_code=symbol,
                period=period,
                start_time=start_date,
                end_time=end_date,
                count=count,
            )

            # 等待下载完成
            time.sleep(1)

            # 获取数据
            field_list = ["time", "open", "high", "low", "close", "volume", "amount"]

            # 对于免费版，使用基础的get_market_data
            data = self.xtdata.get_market_data(
                field_list=field_list, stock_list=[symbol], period=period, count=count
            )

            if data and symbol in data:
                # 转换为DataFrame
                df_dict = {}
                for field in field_list:
                    if field in data[symbol]:
                        df_dict[field] = data[symbol][field]

                df = pd.DataFrame(df_dict)

                # 处理时间格式
                if "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d%H%M%S")
                    df.set_index("time", inplace=True)

                # 简单复权处理（免费版可能不支持自动复权）
                if adjust == "front" and len(df) > 0:
                    # 前复权：使用最新价格为基准
                    factor = df["close"].iloc[-1] / df["close"]
                    for col in ["open", "high", "low", "close"]:
                        df[col] = df[col] * factor

                # 使用动态状态更新而不是日志
                self._status.update_source(
                    "MiniQMT", request=True, success=True
                )
                return df
            else:
                logger.warning("未获取到数据")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"获取历史K线失败: {e}")
            return pd.DataFrame()

    def get_realtime_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        获取实时行情（免费版Level1）

        Parameters:
        -----------
        symbols: 股票代码列表

        Returns:
        --------
        {symbol: quote_data}
        """
        if not self.check_feature_availability("realtime_quote"):
            raise ValueError("实时行情功能不可用")

        try:
            result = {}

            # 使用get_full_tick获取最新行情
            tick_data = self.xtdata.get_full_tick(symbols)

            for symbol in symbols:
                if symbol in tick_data:
                    tick = tick_data[symbol]

                    # 提取基础行情数据
                    result[symbol] = {
                        "symbol": symbol,
                        "last": tick.get("lastPrice", 0),
                        "open": tick.get("open", 0),
                        "high": tick.get("high", 0),
                        "low": tick.get("low", 0),
                        "volume": tick.get("volume", 0),
                        "amount": tick.get("amount", 0),
                        "pre_close": tick.get("lastClose", 0),
                        # 涨跌幅计算
                        "change": tick.get("lastPrice", 0) - tick.get("lastClose", 0),
                        "pct_change": (
                            (tick.get("lastPrice", 0) - tick.get("lastClose", 0))
                            / tick.get("lastClose", 1)
                            * 100
                            if tick.get("lastClose", 0) > 0
                            else 0
                        ),
                        # 基础五档（免费版通常有）
                        "bid1": tick.get("bidPrice1", 0),
                        "ask1": tick.get("askPrice1", 0),
                        "bid1_volume": tick.get("bidVol1", 0),
                        "ask1_volume": tick.get("askVol1", 0),
                    }

            # 使用动态状态更新
            self._status.update_source("MiniQMT", request=True, success=True)
            return result

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {}

    def subscribe_quotes(
        self, symbols: List[str], callback: Callable[..., None], period: str = "tick"
    ) -> bool:
        """
        订阅实时行情（免费版）

        Parameters:
        -----------
        symbols: 股票代码列表
        callback: 回调函数
        period: 周期

        Returns:
        --------
        是否订阅成功
        """
        if not self.check_feature_availability("realtime_quote"):
            raise ValueError("实时订阅功能不可用")

        try:
            success_count = 0

            for symbol in symbols:
                try:
                    # 订阅单个股票
                    self.xtdata.subscribe_quote(
                        stock_code=symbol,
                        period=period,
                        start_time="",
                        end_time="",
                        count=0,
                        callback=callback,
                    )
                    success_count += 1
                    # 动态状态更新
                    self._status.update_source("MiniQMT", request=True, success=True)
                except Exception as e:
                    logger.error(f"订阅 {symbol} 失败: {e}")

            return success_count > 0

        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False

    def get_financial_basic(self, symbol: str) -> Dict[str, Any]:
        """
        获取基础财务数据（免费版）

        Parameters:
        -----------
        symbol: 股票代码

        Returns:
        --------
        基础财务指标
        """
        if not self.check_feature_availability("financial_data"):
            raise ValueError("财务数据功能不可用")

        try:
            # 获取最新的财务数据
            result = {
                "symbol": symbol,
                "eps": 0,  # 每股收益
                "bvps": 0,  # 每股净资产
                "roe": 0,  # ROE
                "pe": 0,  # 市盈率
                "pb": 0,  # 市净率
            }

            # 尝试获取财务数据
            try:
                finance_data = self.xtdata.get_financial_data(
                    stock_code=symbol, table_name="Income"  # 利润表
                )

                if finance_data:
                    # 提取关键指标
                    # 注意：具体字段名需要根据实际返回调整
                    pass

            except Exception as e:
                logger.warning(f"获取财务数据失败: {e}")

            # 从实时行情中获取PE、PB等
            tick = self.xtdata.get_full_tick([symbol])
            if symbol in tick:
                # 某些版本的tick数据包含PE、PB
                result["pe"] = tick[symbol].get("pe", 0)
                result["pb"] = tick[symbol].get("pb", 0)

            return result

        except Exception as e:
            logger.error(f"获取财务数据失败: {e}")
            return {}

    def get_stock_list(self, market: str = "SH") -> List[str]:
        """
        获取股票列表（免费版）

        Parameters:
        -----------
        market: 市场 (SH, SZ)

        Returns:
        --------
        股票代码列表
        """
        if not self.check_feature_availability("stock_list"):
            raise ValueError("股票列表功能不可用")

        try:
            # 获取所有A股股票
            stock_list = []

            # 尝试通过板块获取
            if market == "SH":
                # 上海市场
                sectors = ["上证50", "沪深300"]
            else:
                # 深圳市场
                sectors = ["中证500", "创业板"]

            for sector in sectors:
                try:
                    stocks = self.xtdata.get_stock_list_in_sector(sector)
                    stock_list.extend(stocks)
                except Exception:
                    pass

            # 去重
            stock_list = list(set(stock_list))

            logger.debug(f"获取到 {len(stock_list)} 只股票")
            return stock_list

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    # ==================== 工具方法 ====================

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            # 尝试获取一个股票的数据
            test_symbol = "000001.SZ"
            tick = self.xtdata.get_full_tick([test_symbol])

            if tick and test_symbol in tick:
                logger.debug("连接测试成功")
                return True
            else:
                logger.warning("⚠️ 连接测试失败：无数据返回")
                return False

        except Exception as e:
            logger.error(f"❌ 连接测试失败: {e}")
            return False

    def get_available_features(self) -> Dict[str, bool]:
        """获取可用功能列表"""
        available = {}

        for feature, enabled in self.FREE_FEATURES.items():
            if enabled:
                # 实际测试功能是否可用
                try:
                    if feature == "history_kline":
                        # 测试历史K线
                        df = self.get_history_kline("000001.SZ", count=1)
                        available[feature] = not df.empty
                    elif feature == "realtime_quote":
                        # 测试实时行情
                        quotes = self.get_realtime_quotes(["000001.SZ"])
                        available[feature] = len(quotes) > 0
                    else:
                        available[feature] = enabled
                except Exception:
                    available[feature] = False
            else:
                available[feature] = False

        return available


# ==================== 使用示例 ====================
def example():
    """使用示例"""
    print("=" * 60)
    print("免费版QMT适配器测试")
    print("=" * 60)

    # 创建适配器
    adapter = FreeQMTAdapter()

    # 1. 测试连接
    print("\n1. 测试连接")
    if adapter.test_connection():
        print("连接正常")

    # 2. 获取可用功能
    print("\n2. 可用功能列表")
    features = adapter.get_available_features()
    for feature, available in features.items():
        status = "✅" if available else "❌"
        print(f"  {status} {feature}")

    # 3. 获取历史K线
    print("\n3. 获取历史K线")
    df = adapter.get_history_kline(symbol="000001.SZ", period="1d", count=10)
    if not df.empty:
        print(f"获取到 {len(df)} 条K线数据")
        print(df.tail(3))

    # 4. 获取实时行情
    print("\n4. 获取实时行情")
    quotes = adapter.get_realtime_quotes(["000001.SZ", "600000.SH"])
    for symbol, quote in quotes.items():
        print(f"{symbol}: 最新价={quote['last']:.2f}, 涨跌幅={quote['pct_change']:.2f}%")

    # 5. 订阅实时数据
    print("\n5. 订阅实时数据")

    def on_quote(data):
        print(f"收到行情推送: {data}")

    if adapter.subscribe_quotes(["000001.SZ"], callback=on_quote):
        print("订阅成功，等待数据推送...")
        time.sleep(5)

    print("\n测试完成")


if __name__ == "__main__":
    example()
