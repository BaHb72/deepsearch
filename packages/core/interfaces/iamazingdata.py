"""
AmazingData 扩展接口

定义 AmazingData 数据源特有的方法，继承自通用 IDataFeed 接口。
"""

from __future__ import annotations

from typing import Protocol

from .idatafeed import IDataFeed


class IAmazingDataFeed(IDataFeed, Protocol):
    """AmazingData 特有接口

    继承 IDataFeed 通用接口，并添加 AmazingData SDK 特有的方法。
    这些方法仅在 AmazingData 数据源上可用。
    """

    # === 融资融券 ===
    async def get_margin_summary(
        self,
        code_list: list[str] | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取融资融券汇总数据

        Args:
            code_list: 股票代码列表（可选）
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            融资融券汇总数据列表
        """
        ...

    async def get_margin_detail(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取融资融券明细数据"""
        ...

    # === 股东信息 ===
    async def get_share_holder(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取十大股东信息"""
        ...

    async def get_holder_num(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取股东人数"""
        ...

    # === ETF 数据 ===
    async def get_etf_pcf(self, code_list: list[str]) -> tuple:
        """获取 ETF 成分股 (PCF)

        Args:
            code_list: ETF 代码列表

        Returns:
            ETF 成分股数据
        """
        ...

    # === 市场异动 ===
    async def get_long_hu_bang(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取龙虎榜数据"""
        ...

    async def get_block_trading(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取大宗交易数据"""
        ...

    # === 行业数据 ===
    async def get_industry_daily(
        self,
        industry_code: str | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取行业日行情"""
        ...

    async def get_industry_weight(
        self,
        industry_code: str | None = None,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取行业成分权重"""
        ...

    # === 分红配股 ===
    async def get_dividend(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取分红送股数据"""
        ...

    async def get_right_issue(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """获取配股数据"""
        ...
