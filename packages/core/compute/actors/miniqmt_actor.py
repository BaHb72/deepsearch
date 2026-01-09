"""
MiniQMT Dask Actor

基于 xtdata SDK 的 Dask Actor 实现，提供分布式数据访问能力。
"""

import time

from loguru import logger

# xtdata SDK 导入
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    xtdata = None  # type: ignore
    XTDATA_AVAILABLE = False


class MiniQMTActor:
    """
    MiniQMT Dask Actor

    功能：
    - 通过 xtdata SDK 获取行情数据
    - 支持交易日历、K线、实时行情、板块成分股等
    - 在 Dask Worker 中运行，提供 RPC 接口
    """

    def __init__(self, config: dict | None = None) -> None:
        """初始化 MiniQMT Actor"""
        self._config = config or {}
        self._initialized = False
        self._connected = False
        self._last_activity = time.time()
        self._error_count = 0

        logger.info("[MiniQMTActor] 实例已创建")

    # ==================== IDataFeed 兼容接口 ====================

    @property
    def name(self) -> str:
        """数据源名称"""
        return "MiniQMT"

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected and XTDATA_AVAILABLE

    @property
    def _sdk_available(self) -> bool:
        """SDK 是否可用（API 层检查用）"""
        return XTDATA_AVAILABLE

    # ==================== 初始化 ====================

    async def initialize(self) -> bool:
        """初始化 MiniQMT Actor"""
        if self._initialized:
            logger.debug("[MiniQMTActor] 已初始化，跳过")
            return True

        if not XTDATA_AVAILABLE:
            logger.error("[MiniQMTActor] xtquant SDK 不可用")
            return False

        try:
            logger.info("[MiniQMTActor] 开始初始化 xtdata...")

            # xtdata 会自动连接本地 QMT 终端
            # 测试获取交易日历来验证连接
            calendar = xtdata.get_trading_calendar("SH", "20250101", "20250110")  # type: ignore[attr-defined]
            if calendar:
                logger.info(f"[MiniQMTActor] xtdata 连接成功，测试日历: {len(calendar)} 天")
                self._connected = True
            else:
                logger.warning("[MiniQMTActor] xtdata 连接但日历为空")
                self._connected = True  # SDK 可用但可能没数据

            self._initialized = True
            self._last_activity = time.time()
            return True

        except Exception as e:
            logger.error(f"[MiniQMTActor] 初始化失败: {e}")
            self._error_count += 1
            return False

    # ==================== 交易日历 ====================

    async def get_calendar(
        self,
        market: str = "SH",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        """
        获取交易日历

        Args:
            market: 市场代码 (SH/SZ)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            交易日列表
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            # 默认日期范围
            if not start_date:
                start_date = "20200101"
            if not end_date:
                end_date = "20991231"

            result = xtdata.get_trading_calendar(market, start_date, end_date)  # type: ignore[attr-defined]
            logger.info(f"[MiniQMTActor.get_calendar] market={market}, 返回 {len(result)} 天")
            return list(result) if result else []

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_calendar] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 股票列表 ====================

    async def get_stock_list(
        self,
        sector: str = "沪深A股",
    ) -> list[str]:
        """
        获取板块成分股列表

        Args:
            sector: 板块名称（默认沪深A股）

        Returns:
            股票代码列表
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()
            result = xtdata.get_stock_list_in_sector(sector)
            logger.info(f"[MiniQMTActor.get_stock_list] sector={sector}, 返回 {len(result)} 支")
            return list(result) if result else []

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_stock_list] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== K线数据 ====================

    async def get_kline(
        self,
        symbols: list[str],
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "none",
    ) -> dict[str, list[dict]]:
        """
        获取 K 线数据

        Args:
            symbols: 股票代码列表
            period: 周期 (1m/5m/15m/30m/60m/1d/1w/1M)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 复权类型 (none/qfq/hfq)

        Returns:
            {代码: K线记录列表}
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            # 日期默认值
            if not start_date:
                start_date = "20200101"
            if not end_date:
                end_date = ""  # 空字符串表示最新

            # 获取数据
            result = xtdata.get_market_data_ex(  # type: ignore[call-arg]
                stock_list=symbols,
                period=period,
                start_time=start_date,
                end_time=end_date,
                count=-1,
                dividend_type=adjust,
            )

            # 转换为标准格式
            output: dict[str, list[dict]] = {}
            if result:
                for code, df in result.items():
                    if df is not None and len(df) > 0:
                        records = df.reset_index().to_dict("records")
                        output[code] = records

            logger.info(f"[MiniQMTActor.get_kline] symbols={len(symbols)}, 返回 {len(output)} 个")
            return output

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_kline] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 实时行情 ====================

    async def get_realtime_quote(
        self,
        symbols: list[str],
    ) -> dict[str, dict]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            {代码: 行情数据}
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            result = xtdata.get_full_tick(symbols)

            output: dict[str, dict] = {}
            if result:
                for code, data in result.items():
                    if data:
                        output[code] = dict(data) if hasattr(data, "items") else data

            logger.info(
                f"[MiniQMTActor.get_realtime_quote] symbols={len(symbols)}, 返回 {len(output)} 个"
            )
            return output

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_realtime_quote] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 合约详情 ====================

    async def get_stock_info(
        self,
        symbol: str,
    ) -> dict:
        """
        获取股票/合约详情

        Args:
            symbol: 股票代码

        Returns:
            合约信息字典
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            result = xtdata.get_instrument_detail(symbol)
            logger.info(f"[MiniQMTActor.get_stock_info] symbol={symbol}, 返回 {bool(result)}")
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_stock_info] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 板块列表 ====================

    async def get_sector_list(self) -> list[str]:
        """
        获取所有板块列表

        Returns:
            板块名称列表
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            result = xtdata.get_sector_list()
            logger.info(f"[MiniQMTActor.get_sector_list] 返回 {len(result)} 个板块")
            return list(result) if result else []

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_sector_list] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 指数权重 ====================

    async def get_index_weight(
        self,
        index_code: str,
    ) -> dict[str, float]:
        """
        获取指数成分股权重

        Args:
            index_code: 指数代码（如 000300.SH）

        Returns:
            {成分股代码: 权重}
        """
        if not XTDATA_AVAILABLE:
            raise RuntimeError("xtquant SDK 不可用")

        try:
            self._last_activity = time.time()

            result = xtdata.get_index_weight(index_code)
            logger.info(
                f"[MiniQMTActor.get_index_weight] index={index_code}, 返回 {len(result) if result else 0} 个成分"
            )
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f"[MiniQMTActor.get_index_weight] 失败: {e}")
            self._error_count += 1
            raise

    # ==================== 状态查询 ====================

    async def get_status(self) -> dict:
        """
        获取 Actor 状态

        Returns:
            状态信息字典
        """
        return {
            "name": self.name,
            "initialized": self._initialized,
            "connected": self._connected,
            "sdk_available": XTDATA_AVAILABLE,
            "error_count": self._error_count,
            "last_activity": self._last_activity,
        }
