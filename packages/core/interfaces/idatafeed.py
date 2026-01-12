"""
统一数据源接口定义

定义所有数据源必须实现的通用接口，实现跨供应商的数据获取抽象层。
灵感来自 vn.py DataFeed 设计模式。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IDataFeed(Protocol):
    """统一数据源接口 - 所有数据源必须实现

    此协议定义了跨供应商（AmazingData, MiniQMT, AkShare）的统一数据获取方法。
    所有实现都应遵循以下符号格式标准：

    标准格式（后缀）：
    - 上交所: 600000.SH
    - 深交所: 000001.SZ
    - 北交所: 430047.BJ
    - ETF: 510300.SH
    """

    # === 元信息 ===
    @property
    def name(self) -> str:
        """数据源名称"""
        ...

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        ...

    # === 符号转换 ===
    def normalize_symbol(self, symbol: str) -> str:
        """将任意格式转为 SDK 需要的格式

        输入: SH.600000 或 600000.SH 或 600000
        输出: SDK 期望的格式
        """
        ...

    def standardize_symbol(self, symbol: str) -> str:
        """将 SDK 返回的格式转为标准后缀格式

        输入: SDK 返回的任意格式
        输出: 600000.SH (标准格式)
        """
        ...

    # === 基础数据 ===
    async def get_calendar(
        self,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """获取交易日历

        Args:
            start: 开始日期 (YYYYMMDD)
            end: 结束日期 (YYYYMMDD)

        Returns:
            交易日列表
        """
        ...

    async def get_stock_info(self, symbols: list[str]) -> list[dict]:
        """获取股票基础信息

        Args:
            symbols: 股票代码列表

        Returns:
            包含名称、行业、状态等信息的字典列表
        """
        ...

    async def get_code_list(self, market: str = "ALL") -> list[str]:
        """获取代码列表

        Args:
            market: 市场代码 (SH / SZ / BJ / ALL)

        Returns:
            股票代码列表
        """
        ...

    # === K线数据 ===
    async def get_kline(
        self,
        symbols: list[str],
        start: int,
        end: int,
        period: str = "daily",
        adjust: str | None = None,
    ) -> dict[str, list]:
        """获取K线数据

        Args:
            symbols: 股票代码列表
            start: 开始日期 (YYYYMMDD)
            end: 结束日期 (YYYYMMDD)
            period: 周期 (1min / 5min / 15min / 30min / 60min / daily / weekly / monthly)
            adjust: 复权类型 (None / qfq / hfq)

        Returns:
            {symbol: [OHLCV记录列表]}
        """
        ...

    # === 实时行情 ===
    async def get_snapshot(self, symbols: list[str]) -> dict[str, dict]:
        """获取最新快照

        Args:
            symbols: 股票代码列表

        Returns:
            {symbol: 快照数据}
        """
        ...

    async def get_realtime_quote(self, symbols: list[str]) -> dict[str, dict]:
        """获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            {symbol: 行情数据}
        """
        ...

    # === 财务数据 ===
    async def get_balance_sheet(
        self,
        symbols: list[str],
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """获取资产负债表"""
        ...

    async def get_income(
        self,
        symbols: list[str],
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """获取利润表"""
        ...

    async def get_cash_flow(
        self,
        symbols: list[str],
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """获取现金流量表"""
        ...
