# encoding:utf-8
"""
Custom Data Feed for Backtrader
自定义Backtrader数据源 - 支持实时数据推送
Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
import os
import threading
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

bt: Any

try:
    import backtrader as _backtrader

    HAS_BACKTRADER = True
    bt = _backtrader
except ImportError:
    HAS_BACKTRADER = False
    bt = None

if TYPE_CHECKING:
    from backtrader import DataBase as BacktraderDataBase
    from backtrader.feeds import GenericCSVData as BacktraderGenericCSVData
else:
    BacktraderDataBase = Any
    BacktraderGenericCSVData = Any


def _allow_mock_data() -> bool:
    """Return True only during automated tests to allow mock streaming."""
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


class DeepSearchLiveData(bt.DataBase):
    """
    DeepSearch实时数据源

    继承Backtrader的DataBase，支持实时数据推送
    """

    params = (
        ("symbol", None),  # 股票代码
        ("source", "auto"),  # 数据源
        ("timeframe", "1m"),  # 时间周期
        ("historical", True),  # 是否加载历史数据
        ("backfill_days", 30),  # 历史数据回填天数
    )

    def __init__(self):
        """初始化数据源"""
        super().__init__()

        self.adapter = None
        self.live_data_queue = []
        self.current_index = 0
        self.historical_data = None
        self.is_live = False
        self._stop_event = threading.Event()
        self._data_thread = None

    def start(self):
        """启动数据源"""
        # 异步初始化适配器
        from deepsearch.backtest.adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter

        self.adapter = UnifiedBacktraderAdapter(source=self.p.source)
        self.adapter.initialize_sync()

        # 加载历史数据
        if self.p.historical:
            self._load_historical_data()

        # 启动实时数据线程
        if self.p.timeframe in ["1m", "5m"]:
            self._start_live_feed()

    def _load_historical_data(self):
        """加载历史数据"""
        if not self.p.symbol:
            logger.error("未指定股票代码")
            return

        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.p.backfill_days)

        logger.info(f"加载历史数据: {self.p.symbol} [{start_date} - {end_date}]")

        # 同步获取历史数据
        self.historical_data = self.adapter.get_data_sync(
            symbol=self.p.symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=self.p.timeframe,
            adjust="qfq",
        )

        if not self.historical_data.empty:
            logger.info(f"✅ 加载了 {len(self.historical_data)} 条历史数据")
        else:
            logger.warning("⚠️ 未获取到历史数据")

    def _start_live_feed(self):
        """启动实时数据推送"""
        logger.info(f"启动实时数据推送: {self.p.symbol}")

        self._stop_event.clear()
        self._data_thread = threading.Thread(target=self._live_data_worker)
        self._data_thread.daemon = True
        self._data_thread.start()

        self.is_live = True

    def _live_data_worker(self):
        """实时数据工作线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def subscribe_data():
            """Subscribe real-time data stream."""
            if not _allow_mock_data():
                logger.warning("mock live data generation is disabled outside tests")
                return
            # TODO: connect to actual live data source
            while not self._stop_event.is_set():
                await asyncio.sleep(60)  # refresh every minute
                new_data = self._generate_mock_tick()
                if new_data:
                    self.live_data_queue.append(new_data)

        try:
            loop.run_until_complete(subscribe_data())
        except Exception as e:
            logger.error(f"实时数据线程错误: {e}")
        finally:
            loop.close()

    def _generate_mock_tick(self) -> Optional[Dict]:
        """Generate mock tick data for tests only."""
        if not _allow_mock_data():
            return None
        import random

        if self.historical_data is not None and not self.historical_data.empty:
            last_close = self.historical_data["close"].iloc[-1]

            # 生成随机波动
            change = random.uniform(-0.02, 0.02)  # 2%波动
            new_price = last_close * (1 + change)

            return {
                "datetime": datetime.now(),
                "open": new_price,
                "high": new_price * 1.001,
                "low": new_price * 0.999,
                "close": new_price,
                "volume": random.randint(10000, 100000),
            }

        return None

    def _load(self):
        """加载下一条数据"""
        if bt is None:
            raise RuntimeError("Backtrader 未安装，无法加载数据")
        if self.historical_data is not None and self.current_index < len(self.historical_data):
            # 加载历史数据
            row = self.historical_data.iloc[self.current_index]

            self.lines.datetime[0] = bt.date2num(row.name)
            self.lines.open[0] = row.get("open", 0)
            self.lines.high[0] = row.get("high", 0)
            self.lines.low[0] = row.get("low", 0)
            self.lines.close[0] = row.get("close", 0)
            self.lines.volume[0] = row.get("volume", 0)

            self.current_index += 1
            return False  # 还有数据

        elif self.is_live and self.live_data_queue:
            # 加载实时数据
            tick = self.live_data_queue.pop(0)

            self.lines.datetime[0] = bt.date2num(tick["datetime"])
            self.lines.open[0] = tick["open"]
            self.lines.high[0] = tick["high"]
            self.lines.low[0] = tick["low"]
            self.lines.close[0] = tick["close"]
            self.lines.volume[0] = tick["volume"]

            return False  # 还有数据

        return True  # 没有更多数据

    def stop(self):
        """停止数据源"""
        logger.info("停止数据源")

        self._stop_event.set()

        if self._data_thread:
            self._data_thread.join(timeout=5)

        self.is_live = False


class DeepSearchCSVData(bt.feeds.GenericCSVData):
    """
    DeepSearch CSV数据源

    支持从CSV文件加载数据，自动识别字段格式
    """

    params = (
        ("nullvalue", float("NaN")),
        ("dtformat", "%Y-%m-%d"),
        ("tmformat", "%H:%M:%S"),
        ("datetime", 0),  # 日期列索引
        ("time", -1),  # 时间列索引
        ("open", 1),
        ("high", 2),
        ("low", 3),
        ("close", 4),
        ("volume", 5),
        ("openinterest", -1),
        ("reverse", False),
        ("header", 0),
        ("separator", ","),
        # 自动检测列名
        ("autodetect", True),
    )

    def __init__(self):
        """初始化CSV数据源"""
        super().__init__()

        if self.p.autodetect:
            self._autodetect_columns()

    def _autodetect_columns(self):
        """自动检测CSV列格式"""
        import pandas as pd

        try:
            # 读取前几行进行检测
            df = pd.read_csv(self.p.dataname, nrows=5, sep=self.p.separator, header=self.p.header)

            # 列名映射
            column_map = {
                "日期": "datetime",
                "date": "datetime",
                "Date": "datetime",
                "开盘": "open",
                "open": "open",
                "Open": "open",
                "最高": "high",
                "high": "high",
                "High": "high",
                "最低": "low",
                "low": "low",
                "Low": "low",
                "收盘": "close",
                "close": "close",
                "Close": "close",
                "成交量": "volume",
                "volume": "volume",
                "Volume": "volume",
            }

            # 设置列索引
            for i, col in enumerate(df.columns):
                if col in column_map:
                    param_name = column_map[col]
                    if param_name == "datetime":
                        self.p.datetime = i
                    elif param_name == "open":
                        self.p.open = i
                    elif param_name == "high":
                        self.p.high = i
                    elif param_name == "low":
                        self.p.low = i
                    elif param_name == "close":
                        self.p.close = i
                    elif param_name == "volume":
                        self.p.volume = i

            logger.info(
                f"自动检测CSV格式: datetime={self.p.datetime}, "
                f"open={self.p.open}, high={self.p.high}, "
                f"low={self.p.low}, close={self.p.close}, "
                f"volume={self.p.volume}"
            )

        except Exception as e:
            logger.error(f"自动检测CSV格式失败: {e}")


class MultiSourceData:
    """
    多数据源管理器

    同时管理多个数据源，支持数据源切换和对比
    """

    def __init__(self):
        """初始化多数据源管理器"""
        self.sources = {}
        self.active_source = None

    def add_source(self, name: str, data_feed: "BacktraderDataBase"):
        """
        添加数据源

        Args:
            name: 数据源名称
            data_feed: Backtrader数据源对象
        """
        self.sources[name] = data_feed

        if self.active_source is None:
            self.active_source = name

        logger.info(f"添加数据源: {name}")

    def switch_source(self, name: str):
        """
        切换活动数据源

        Args:
            name: 数据源名称
        """
        if name in self.sources:
            self.active_source = name
            logger.info(f"切换到数据源: {name}")
        else:
            logger.error(f"数据源不存在: {name}")

    def get_active_source(self) -> Optional["BacktraderDataBase"]:
        """获取当前活动数据源"""
        if self.active_source:
            return self.sources.get(self.active_source)
        return None

    def get_source(self, name: str) -> Optional["BacktraderDataBase"]:
        """获取指定数据源"""
        return self.sources.get(name)

    def compare_sources(self, source_names: list) -> Dict[str, Any]:
        """
        对比多个数据源

        Args:
            source_names: 数据源名称列表

        Returns:
            对比结果
        """
        sources_info: Dict[str, Dict[str, Any]] = {}
        differences: List[Dict[str, Any]] = []
        comparison: Dict[str, Any] = {"sources": sources_info, "differences": differences}

        for name in source_names:
            if name in self.sources:
                source = self.sources[name]
                # 获取数据源信息
                sources_info[name] = {
                    "type": type(source).__name__,
                    "params": source.params._getkwargs(),
                }

        # 实现更详细的数据对比
        if len(source_names) >= 2:
            # 获取第一个数据源作为基准
            base_name = source_names[0]
            base_source = self.sources.get(base_name)

            if base_source and hasattr(base_source, "data"):
                base_data = base_source.data

                # 对比每个数据源与基准数据源
                for name in source_names[1:]:
                    if name in self.sources:
                        compare_source = self.sources[name]

                        if hasattr(compare_source, "data"):
                            compare_data = compare_source.data

                            # 对比数据差异
                            diff = self._calculate_data_differences(
                                base_name, base_data, name, compare_data
                            )

                            if diff:
                                differences.append(diff)

            # 添加统计信息
            comparison["statistics"] = self._calculate_comparison_stats(source_names)

        return comparison

    def _calculate_data_differences(
        self, base_name: str, base_data, compare_name: str, compare_data
    ) -> Dict[str, Any]:
        """
        计算两个数据源之间的差异

        Args:
            base_name: 基准数据源名称
            base_data: 基准数据
            compare_name: 对比数据源名称
            compare_data: 对比数据

        Returns:
            差异信息
        """
        differences: List[Dict[str, Any]] = []
        diff_info: Dict[str, Any] = {
            "base_source": base_name,
            "compare_source": compare_name,
            "differences": differences,
        }

        try:
            # 对比数据长度
            base_len = len(base_data) if hasattr(base_data, "__len__") else 0
            compare_len = len(compare_data) if hasattr(compare_data, "__len__") else 0

            if base_len != compare_len:
                differences.append(
                    {
                        "type": "length",
                        "base_length": base_len,
                        "compare_length": compare_len,
                        "diff": compare_len - base_len,
                    }
                )

            # 如果都有数据，对比具体值
            if base_len > 0 and compare_len > 0:
                # 对比前几条数据
                sample_size = min(5, base_len, compare_len)

                for i in range(sample_size):
                    base_item = base_data[i]
                    compare_item = compare_data[i] if i < compare_len else None

                    if (
                        compare_item
                        and hasattr(base_item, "close")
                        and hasattr(compare_item, "close")
                    ):
                        # 对比收盘价
                        if abs(base_item.close[0] - compare_item.close[0]) > 0.01:
                            differences.append(
                                {
                                    "type": "value",
                                    "index": i,
                                    "field": "close",
                                    "base_value": float(base_item.close[0]),
                                    "compare_value": float(compare_item.close[0]),
                                    "diff": float(compare_item.close[0] - base_item.close[0]),
                                }
                            )

                    if (
                        compare_item
                        and hasattr(base_item, "datetime")
                        and hasattr(compare_item, "datetime")
                    ):
                        # 对比时间戳
                        base_dt = base_item.datetime.datetime(0)
                        compare_dt = compare_item.datetime.datetime(0)

                        if base_dt != compare_dt:
                            differences.append(
                                {
                                    "type": "timestamp",
                                    "index": i,
                                    "base_time": base_dt.isoformat(),
                                    "compare_time": compare_dt.isoformat(),
                                }
                            )

            # 统计差异数量
            diff_info["diff_count"] = len(diff_info["differences"])
            diff_info["has_differences"] = diff_info["diff_count"] > 0

        except Exception as e:
            logger.error(f"计算数据差异失败: {e}")
            diff_info["error"] = str(e)

        return diff_info

    def _calculate_comparison_stats(self, source_names: list) -> Dict[str, Any]:
        """
        计算对比统计信息

        Args:
            source_names: 数据源名称列表

        Returns:
            统计信息
        """
        stats: Dict[str, Any] = {
            "total_sources": len(source_names),
            "available_sources": 0,
            "data_ranges": {},
        }

        for name in source_names:
            if name in self.sources:
                source = self.sources[name]
                stats["available_sources"] += 1

                # 获取数据范围
                if hasattr(source, "data") and len(source.data) > 0:
                    try:
                        first_data = source.data[0]
                        last_data = source.data[-1]

                        if hasattr(first_data, "datetime") and hasattr(last_data, "datetime"):
                            stats["data_ranges"][name] = {
                                "start": first_data.datetime.datetime(0).isoformat(),
                                "end": last_data.datetime.datetime(0).isoformat(),
                                "count": len(source.data),
                            }
                    except Exception as e:
                        logger.debug(f"获取数据范围失败: {e}")

        return stats
