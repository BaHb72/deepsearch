# encoding:utf-8
"""
MiniQMT Data Collector
适用于免费版QMT的MiniQMT数据采集器
Author: DeepSearch Team
Version: 1.0.0

运行要求：
1. MiniQMT已安装并运行
2. Python 3.6+ 环境
3. xtdata模块可用
"""

import threading
import time
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from deepsearch.observability import get_logger

# 配置日志
logger = get_logger(__name__)


class MiniQMTCollector:
    """
    MiniQMT数据采集器

    适配免费版QMT，通过xtdata与MiniQMT交互
    支持Level1数据的历史下载、实时订阅和主动获取
    """

    def __init__(self, mini_qmt_path: Optional[str] = None):
        """
        初始化MiniQMT采集器

        Args:
            mini_qmt_path: MiniQMT安装路径（可选）
        """
        self.xtdata: Any = None
        self.connected = False
        self.mini_qmt_path = mini_qmt_path

        # 订阅管理
        self.subscriptions: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.subscription_locks = threading.Lock()

        # 数据缓存
        self.data_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self.cache_ttl = 300  # 缓存有效期5分钟

        # 消息队列
        self.message_queue: Queue[Dict[str, Any]] = Queue()

        # 初始化连接
        self._init_connection()

    def _init_connection(self):
        """初始化MiniQMT连接"""
        from deepsearch.infrastructure.providers.implementations.qmt.connection_guard import (
            MiniQMTConnectionGuard,
        )

        # 检查是否应该尝试连接（可能在静默期间）
        if not MiniQMTConnectionGuard.should_attempt_connection():
            self.connected = False
            return

        try:
            import xtquant.xtdata as xtdata

            self.xtdata = xtdata

            # 对于MiniQMT，通常不需要显式连接
            # xtdata会自动处理与MiniQMT的通信

            self.connected = True
            MiniQMTConnectionGuard.mark_available()
            logger.info("MiniQMT连接成功")

        except ImportError as e:
            MiniQMTConnectionGuard.log_connection_error(f"无法导入xtdata模块: {e}")
            MiniQMTConnectionGuard.mark_unavailable()
            self.connected = False
        except Exception as e:
            MiniQMTConnectionGuard.log_connection_error(f"连接失败: {e}")
            MiniQMTConnectionGuard.mark_unavailable()
            self.connected = False

    # ==================== 1. 历史数据下载 ====================
    def download_history_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = 0,
        dividend_type: str = "none",
    ) -> Dict[str, Any]:
        """
        下载历史K线数据（Level1）

        Parameters:
        -----------
        stock_code: 股票代码 如'000001.SZ'
        period: 周期
            - '1m': 1分钟
            - '5m': 5分钟
            - '15m': 15分钟
            - '30m': 30分钟
            - '60m': 60分钟
            - '1d': 日线
            - '1w': 周线
            - '1mon': 月线
        start_time: 开始时间 'YYYYMMDD' 或 'YYYYMMDD HH:MM:SS'
        end_time: 结束时间
        count: 数据条数（与时间范围二选一）
        dividend_type: 复权类型 'none'不复权 'front'前复权 'back'后复权

        Returns:
        --------
        包含DataFrame数据的字典
        """
        if not self.connected:
            return {"success": False, "error": "MiniQMT未连接"}

        try:
            # 检查缓存
            cache_key = f"{stock_code}_{period}_{start_time}_{end_time}_{dividend_type}"
            cached_data = self._get_cached_data(cache_key)
            if cached_data:
                return cached_data

            # 调用MiniQMT下载接口
            # 注意：MiniQMT需要先确保有数据，如果不足需要先补充
            self.xtdata.download_history_data(
                stock_code=stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
            )

            # 等待数据下载完成
            time.sleep(0.5)

            # 获取下载的数据
            field_list = ["time", "open", "high", "low", "close", "volume", "amount"]

            data = self.xtdata.get_market_data_ex(
                field_list=field_list,
                stock_list=[stock_code],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
                dividend_type=dividend_type,
                fill_data=True,  # 填充停牌数据
            )

            if data and stock_code in data:
                df = data[stock_code]

                # 处理数据格式
                if not df.empty:
                    # 转换时间格式
                    if "time" in df.columns:
                        df["time"] = pd.to_datetime(df["time"], format="%Y%m%d%H%M%S")

                    result = {
                        "success": True,
                        "symbol": stock_code,
                        "period": period,
                        "dividend_type": dividend_type,
                        "count": len(df),
                        "data": df.to_dict("records"),
                    }

                    # 缓存数据
                    self._cache_data(cache_key, result)

                    logger.debug(f"下载成功: {len(df)} 条数据")
                    return result
                else:
                    return {"success": False, "error": "返回数据为空"}
            else:
                return {"success": False, "error": "未获取到数据"}

        except Exception as e:
            logger.error(f"❌ 下载历史数据失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 2. 实时数据订阅 ====================
    def subscribe_quote(
        self, stock_code: str, period: str = "tick", callback: Optional[Callable] = None
    ) -> bool:
        """
        订阅实时行情（Level1）

        Parameters:
        -----------
        stock_code: 股票代码
        period: 周期 'tick'分笔 '1m'一分钟 等
        callback: 数据回调函数

        Returns:
        --------
        是否订阅成功
        """
        if not self.connected:
            return False

        try:
            # 定义内部回调
            def on_data(data):
                # 处理接收到的数据
                processed = self._process_realtime_data(stock_code, period, data)

                # 触发用户回调
                if callback:
                    callback(processed)

                # 发送到消息队列
                self.message_queue.put(processed)

            self.xtdata.subscribe_quote(
                stock_code=stock_code,
                period=period,
                start_time="",
                end_time="",
                count=0,
                callback=on_data,
            )

            # 保存订阅信息
            with self.subscription_locks:
                self.subscriptions[f"{stock_code}_{period}"] = on_data

            return True

        except Exception as e:
            logger.error(f"❌ 订阅失败: {e}")
            return False

    def unsubscribe_quote(self, stock_code: str, period: str = "tick") -> bool:
        """
        取消订阅

        Parameters:
        -----------
        stock_code: 股票代码
        period: 周期

        Returns:
        --------
        是否取消成功
        """
        if not self.connected:
            return False

        try:

            self.xtdata.unsubscribe_quote(stock_code, period)

            # 移除订阅信息
            with self.subscription_locks:
                key = f"{stock_code}_{period}"
                if key in self.subscriptions:
                    del self.subscriptions[key]

            return True

        except Exception as e:
            logger.error(f"❌ 取消订阅失败: {e}")
            return False

    # ==================== 3. 主动获取数据 ====================
    def get_market_data(
        self,
        stock_list: List[str],
        field_list: Optional[List[str]] = None,
        period: str = "1d",
        count: int = 20,
    ) -> Dict[str, pd.DataFrame]:
        """
        主动获取市场数据（Level1）

        Parameters:
        -----------
        stock_list: 股票代码列表
        field_list: 字段列表 ['open', 'high', 'low', 'close', 'volume']
        period: 周期
        count: 获取最近N条数据

        Returns:
        --------
        {stock_code: DataFrame}
        """
        if not self.connected:
            return {}

        try:
            if field_list is None:
                field_list = ["time", "open", "high", "low", "close", "volume", "amount"]

            # 获取数据
            data = self.xtdata.get_market_data(
                field_list=field_list, stock_list=stock_list, period=period, count=count
            )

            result = {}
            for stock in stock_list:
                if stock in data:
                    # 转换为DataFrame
                    df = pd.DataFrame(data[stock])
                    if not df.empty:
                        df = df.T  # 转置
                        df.index.name = "time"
                        df.reset_index(inplace=True)
                        result[stock] = df

            return result

        except Exception as e:
            logger.error(f"❌ 获取市场数据失败: {e}")
            return {}

    def get_full_tick(self, stock_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        获取最新tick数据（含五档盘口）

        Parameters:
        -----------
        stock_codes: 股票代码列表

        Returns:
        --------
        {stock_code: tick_data}
        """
        if not self.connected:
            return {}

        try:

            # 获取tick数据
            tick_data = self.xtdata.get_full_tick(stock_codes)

            result = {}
            for code in stock_codes:
                if code in tick_data:
                    tick = tick_data[code]

                    # 格式化tick数据
                    result[code] = {
                        "symbol": code,
                        "time": tick.get("time", 0),
                        "last_price": tick.get("lastPrice", 0),
                        "open": tick.get("open", 0),
                        "high": tick.get("high", 0),
                        "low": tick.get("low", 0),
                        "volume": tick.get("volume", 0),
                        "amount": tick.get("amount", 0),
                        "pre_close": tick.get("lastClose", 0),
                        # 买卖盘
                        "bid_price": [tick.get(f"bidPrice{i}", 0) for i in range(1, 6)],
                        "ask_price": [tick.get(f"askPrice{i}", 0) for i in range(1, 6)],
                        "bid_volume": [tick.get(f"bidVol{i}", 0) for i in range(1, 6)],
                        "ask_volume": [tick.get(f"askVol{i}", 0) for i in range(1, 6)],
                    }

            return result

        except Exception as e:
            logger.error(f"❌ 获取Tick数据失败: {e}")
            return {}

    # ==================== 4. 财务数据 ====================
    def get_financial_data(
        self, stock_list: List[str], table_list: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        获取财务数据

        Parameters:
        -----------
        stock_list: 股票代码列表
        table_list: 财务表列表 ['Balance', 'Income', 'CashFlow']

        Returns:
        --------
        {stock_code: DataFrame}
        """
        if not self.connected:
            return {}

        try:
            if table_list is None:
                table_list = ["Balance", "Income", "CashFlow"]

            result = {}

            for stock in stock_list:
                stock_finance = {}

                for table in table_list:
                    # 获取财务数据
                    data = self.xtdata.get_financial_data(stock_code=stock, table_name=table)

                    if data:
                        stock_finance[table] = pd.DataFrame(data)

                if stock_finance:
                    result[stock] = stock_finance

            return result

        except Exception as e:
            logger.error(f"❌ 获取财务数据失败: {e}")
            return {}

    # ==================== 5. 合约基础信息 ====================
    def get_instrument_detail(self, stock_code: str) -> Dict[str, Any]:
        """
        获取合约详细信息

        Parameters:
        -----------
        stock_code: 股票代码

        Returns:
        --------
        合约信息字典
        """
        if not self.connected:
            return {}

        try:

            # 获取合约信息
            info = self.xtdata.get_instrument_detail(stock_code)

            if info:
                result = {
                    "symbol": stock_code,
                    "name": info.get("InstrumentName", ""),
                    "exchange": info.get("ExchangeID", ""),
                    "product_type": info.get("ProductType", ""),
                    "listed_date": info.get("OpenDate", ""),
                    "expired_date": info.get("ExpireDate", ""),
                    "price_tick": info.get("PriceTick", 0),
                    "volume_multiple": info.get("VolumeMultiple", 1),
                    "create_date": info.get("CreateDate", ""),
                }

                return result
            else:
                return {}

        except Exception as e:
            logger.error(f"❌ 获取合约信息失败: {e}")
            return {}

    # ==================== 6. 板块分类信息 ====================
    def get_stock_list_in_sector(self, sector_name: str) -> List[str]:
        """
        获取板块成分股

        Parameters:
        -----------
        sector_name: 板块名称

        Returns:
        --------
        股票代码列表
        """
        if not self.connected:
            return []

        try:

            # 获取板块成分股
            stock_list_raw = self.xtdata.get_stock_list_in_sector(sector_name)
            if isinstance(stock_list_raw, list):
                stock_list = [str(item) for item in stock_list_raw]
            else:
                stock_list = []

            return stock_list

        except Exception as e:
            logger.error(f"❌ 获取板块成分股失败: {e}")
            return []

    # ==================== 工具方法 ====================
    def _process_realtime_data(self, stock_code: str, period: str, data: Any) -> Dict:
        """处理实时数据"""
        return {
            "type": "realtime_quote",
            "symbol": stock_code,
            "period": period,
            "timestamp": time.time(),
            "data": data,
        }

    def _get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存数据"""
        if key in self.data_cache:
            cached_time, cached_data = self.data_cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data
            else:
                del self.data_cache[key]
        return None

    def _cache_data(self, key: str, data: Dict[str, Any]) -> None:
        """缓存数据"""
        self.data_cache[key] = (time.time(), data)

    def clear_cache(self):
        """清空缓存"""
        self.data_cache.clear()

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "connected": self.connected,
            "subscriptions": len(self.subscriptions),
            "cached_items": len(self.data_cache),
            "queue_size": self.message_queue.qsize(),
        }

    def close(self):
        """关闭连接"""
        try:
            # 取消所有订阅
            for key in list(self.subscriptions.keys()):
                stock_code, period = key.split("_", 1)
                self.unsubscribe_quote(stock_code, period)

            # 清空缓存
            self.clear_cache()

            self.connected = False
            logger.info("👋 MiniQMT连接已关闭")

        except Exception as e:
            logger.error(f"关闭连接失败: {e}")


# ==================== 使用示例 ====================
def example_usage():
    """使用示例"""

    # 创建采集器
    collector = MiniQMTCollector()

    # 1. 下载历史数据
    print("\n" + "=" * 50)
    print("1. 下载历史K线数据")
    print("=" * 50)

    history_data = collector.download_history_data(
        stock_code="000001.SZ",
        period="1d",
        start_time="20240101",
        end_time="20240131",
        dividend_type="front",
    )

    if history_data.get("success"):
        print(f"下载成功: {history_data['count']} 条数据")

    # 2. 获取实时Tick
    print("\n" + "=" * 50)
    print("2. 获取实时Tick数据")
    print("=" * 50)

    tick_data = collector.get_full_tick(["000001.SZ", "600000.SH"])
    for symbol, tick in tick_data.items():
        print(f"{symbol}: 最新价={tick['last_price']}, 成交量={tick['volume']}")

    # 3. 订阅实时行情
    print("\n" + "=" * 50)
    print("3. 订阅实时行情")
    print("=" * 50)

    def on_quote(data):
        print(f"收到行情: {data}")

    collector.subscribe_quote("000001.SZ", "tick", callback=on_quote)

    # 等待接收数据
    time.sleep(10)

    # 4. 获取财务数据
    print("\n" + "=" * 50)
    print("4. 获取财务数据")
    print("=" * 50)

    finance_data = collector.get_financial_data(["000001.SZ"])
    if finance_data:
        print(f"获取到财务数据: {list(finance_data.keys())}")

    # 5. 获取合约信息
    print("\n" + "=" * 50)
    print("5. 获取合约信息")
    print("=" * 50)

    instrument = collector.get_instrument_detail("000001.SZ")
    if instrument:
        print(f"股票名称: {instrument.get('name')}")
        print(f"交易所: {instrument.get('exchange')}")

    # 6. 查看连接状态
    print("\n" + "=" * 50)
    print("6. 连接状态")
    print("=" * 50)

    status = collector.get_connection_status()
    print(f"连接状态: {status}")

    # 关闭连接
    collector.close()


if __name__ == "__main__":
    example_usage()
