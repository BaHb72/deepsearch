# encoding:utf-8
"""
AmazingData 扩展接口实现
实现35个API文档中的所有接口

Author: DeepSearch Team
Version: 2.0.0
Date: 2025-09-18
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import pandas as pd
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import DataProviderError

# AmazingData SDK
from ._sdk_loader import ad
from .amazingdata import AmazingDataProvider, ProviderConfigLike


class AmazingDataExtended(AmazingDataProvider):
    """AmazingData 扩展实现，包含所有35个API接口"""

    def __init__(self, config: ProviderConfigLike):
        """初始化扩展接口"""
        super().__init__(config)
        self._base_data: Any = None
        self._info_data: Any = None
        self._market_data: Any = None
        self._initialized_objects = False

    async def _ensure_data_objects(self):
        """确保数据对象已初始化"""
        if not self._initialized_objects and self._connected:
            try:
                loop = asyncio.get_event_loop()

                # 初始化基础数据对象
                self._base_data = await loop.run_in_executor(None, ad.BaseData)

                # 初始化信息数据对象
                self._info_data = await loop.run_in_executor(None, ad.InfoData)

                # 获取交易日历
                calendar = await self.get_calendar()
                if calendar:
                    # 初始化市场数据对象
                    self._market_data = await loop.run_in_executor(None, ad.MarketData, calendar)

                self._initialized_objects = True
                logger.info("AmazingData 数据对象初始化成功")
            except Exception as e:
                logger.error(f"初始化数据对象失败: {e}")
                raise DataProviderError(f"Failed to initialize data objects: {e}")

    # ================== P0基础接口 ==================

    async def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> Optional[pd.DataFrame]:
        """
        3.5.2.1 每日最新证券信息
        获取每日最新证券信息，包括证券简称、昨收价、涨跌停价等

        Args:
            security_type: 代码类型，默认EXTRA_STOCK_A（沪深北A股）

        Returns:
            DataFrame: 证券信息，columns包含symbol、pre_close、high_limited、low_limited等
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._base_data.get_code_info, security_type)

            logger.info(f"成功获取{len(result) if result is not None else 0}条证券信息")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取证券信息失败: {e}")
            return None

    async def get_calendar(
        self, data_type: str = "str", market: str = "SH"
    ) -> Optional[List[Union[str, datetime]]]:
        """
        3.5.2.7 交易日历
        获取交易所的交易日历

        Args:
            data_type: 返回数据类型，'str'或'datetime'
            market: 市场，'SH'上海或'SZ'深圳

        Returns:
            交易日列表
        """
        if not self._base_data:
            await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_calendar, data_type, market
            )

            logger.info(f"成功获取交易日历，共{len(result) if result else 0}个交易日")
            return cast(Optional[List[Union[str, datetime]]], result)

        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return None

    async def get_stock_basic(self, code_list: List[str]) -> Optional[pd.DataFrame]:
        """
        3.5.2.8 证券基础信息
        获取指定股票的基础信息，包括公司名称、上市日期、退市日期等

        Args:
            code_list: 股票代码列表

        Returns:
            DataFrame: 股票基础信息
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_stock_basic, code_list)

            logger.info(f"成功获取{len(result) if result is not None else 0}条股票基础信息")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            return None

    async def get_backward_factor(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.2.4 复权因子（后复权因子）
        获取复权因子数据并本地存储

        Args:
            code_list: 代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: index为交易日期，columns为股票代码
        """
        await self._ensure_data_objects()

        try:
            # 确保本地路径存在
            Path(local_path).mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_backward_factor, code_list, local_path, is_local
            )

            logger.info("成功获取后复权因子数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取后复权因子失败: {e}")
            return None

    async def get_adj_factor(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.2.5 复权因子（单次复权因子）
        获取复权因子数据并本地存储

        Args:
            code_list: 代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: index为交易日期，columns为股票代码
        """
        await self._ensure_data_objects()

        try:
            # 确保本地路径存在
            Path(local_path).mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_adj_factor, code_list, local_path, is_local
            )

            logger.info("成功获取单次复权因子数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取单次复权因子失败: {e}")
            return None

    async def get_history_stock_status(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.2.9 历史证券信息
        获取历史证券状态，包括停牌、ST、除权除息等信息

        Args:
            code_list: 代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 历史证券状态信息
        """
        await self._ensure_data_objects()

        try:
            # 确保本地路径存在
            Path(local_path).mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_history_stock_status, code_list, local_path, is_local
            )

            logger.info("成功获取历史证券状态信息")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取历史证券状态失败: {e}")
            return None

    async def get_hist_code_list(
        self,
        security_type: str = "EXTRA_STOCK_A_SH_SZ",
        start_date: int = 20130101,
        end_date: int = 20250101,
        local_path: str = "D://AmazingData_local_data//",
    ) -> Optional[List[str]]:
        """
        3.5.2.6 历史代码列表
        获取历史代码列表，先检查本地数据，再从服务端补齐

        Args:
            security_type: 代码类型
            start_date: 开始日期
            end_date: 结束日期
            local_path: 本地存储路径

        Returns:
            代码列表
        """
        await self._ensure_data_objects()

        try:
            # 确保本地路径存在
            Path(local_path).mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._base_data.get_hist_code_list,
                security_type,
                start_date,
                end_date,
                local_path,
            )

            logger.info(f"成功获取历史代码列表，共{len(result) if result else 0}个代码")
            return cast(Optional[List[str]], result)

        except Exception as e:
            logger.error(f"获取历史代码列表失败: {e}")
            return None

    async def get_code_list(self, security_type: str = "EXTRA_STOCK_A") -> Optional[List[str]]:
        """
        3.5.2.2 每日最新代码列表
        获取最新的每日代码列表

        Args:
            security_type: 代码类型

        Returns:
            代码列表
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._base_data.get_code_list, security_type)

            logger.info(f"成功获取代码列表，共{len(result) if result else 0}个代码")
            return cast(Optional[List[str]], result)

        except Exception as e:
            logger.error(f"获取代码列表失败: {e}")
            return None

    async def get_future_code_list(
        self, security_type: str = "EXTRA__FUTURE"
    ) -> Optional[List[str]]:
        """
        3.5.2.3 每日最新代码（期货特殊接口）
        获取最新的期货代码列表

        Args:
            security_type: 代码类型，默认EXTRA__FUTURE

        Returns:
            期货代码列表
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_future_code_list, security_type
            )

            logger.info(f"成功获取期货代码列表，共{len(result) if result else 0}个代码")
            return cast(Optional[List[str]], result)

        except Exception as e:
            logger.error(f"获取期货代码列表失败: {e}")
            return None

    async def get_bj_code_mapping(
        self, local_path: str = "D://AmazingData_local_data//", is_local: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        3.5.2.10 北交所代码新旧代码映射表
        获取北交所代码的新旧代码映射关系

        Args:
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 北交所代码映射表
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_bj_code_mapping)

            logger.info("成功获取北交所代码映射表")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取北交所代码映射失败: {e}")
            return None

    # ================== 历史行情接口 ==================

    async def query_snapshot(
        self, code_list: List[str], begin_date: int, end_date: int
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        3.5.4.1 历史快照
        查询历史快照数据

        Args:
            code_list: 代码列表
            begin_date: 开始日期，如20240101
            end_date: 结束日期，如20240201

        Returns:
            字典，key为代码，value为DataFrame
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._market_data.query_snapshot, code_list, begin_date, end_date
            )

            logger.info("成功获取历史快照数据")
            return cast(Optional[Dict[str, pd.DataFrame]], result)

        except Exception as e:
            logger.error(f"查询历史快照失败: {e}")
            return None

    async def query_kline(
        self, code_list: List[str], begin_date: int, end_date: int, period: Optional[str] = None
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        3.5.4.2 历史K线
        查询历史K线数据

        Args:
            code_list: 代码列表
            begin_date: 开始日期
            end_date: 结束日期
            period: 周期，如ad.constant.Period.day.value

        Returns:
            字典，key为代码，value为DataFrame
        """
        await self._ensure_data_objects()

        try:
            if period is None:
                period = ad.constant.Period.day.value

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._market_data.query_kline, code_list, begin_date, end_date, period
            )

            logger.info("成功获取历史K线数据")
            return cast(Optional[Dict[str, pd.DataFrame]], result)

        except Exception as e:
            logger.error(f"查询历史K线失败: {e}")
            return None

    # ================== 财务数据接口（扩展） ==================

    async def get_profit_express(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.5.4 业绩快报
        获取指定股票的业绩快报数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 业绩快报数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_profit_express, code_list)

            logger.info("成功获取业绩快报数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取业绩快报失败: {e}")
            return None

    async def get_profit_notice(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.5.5 业绩预告
        获取指定股票的业绩预告数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 业绩预告数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_profit_notice, code_list)

            logger.info("成功获取业绩预告数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取业绩预告失败: {e}")
            return None

    async def get_balance_sheet(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.5.1 资产负债表
        获取指定股票的资产负债表数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 资产负债表数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_balance_sheet, code_list)

            logger.info("成功获取资产负债表数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取资产负债表失败: {e}")
            return None

    async def get_cash_flow(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.5.2 现金流量表
        获取指定股票的现金流量表数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 现金流量表数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_cash_flow, code_list)

            logger.info("成功获取现金流量表数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取现金流量表失败: {e}")
            return None

    async def get_income(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.5.3 利润表
        获取指定股票的利润表数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 利润表数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_income, code_list)

            logger.info("成功获取利润表数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取利润表失败: {e}")
            return None

    # ================== 股东股本数据接口 ==================

    async def get_share_holder(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.6.1 十大股东数据
        获取指定股票的十大股东数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 十大股东数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_share_holder, code_list)

            logger.info("成功获取十大股东数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取十大股东数据失败: {e}")
            return None

    async def get_holder_num(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.6.2 股东人数
        获取指定股票的股东人数数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 股东人数数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_holder_num, code_list)

            logger.info("成功获取股东人数数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取股东人数失败: {e}")
            return None

    async def get_equity_structure(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.6.3 股本结构
        获取指定股票的股本结构数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 股本结构数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_structure, code_list
            )

            logger.info("成功获取股本结构数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取股本结构失败: {e}")
            return None

    async def get_equity_pledge_freeze(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.6.4 股权质押/冻结
        获取指定股票的股权质押/冻结数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 股权质押/冻结数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_pledge_freeze, code_list
            )

            logger.info("成功获取股权质押/冻结数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取股权质押/冻结失败: {e}")
            return None

    async def get_equity_restricted(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.6.5 限售股解禁
        获取指定股票的限售股解禁数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 限售股解禁数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_restricted, code_list
            )

            logger.info("成功获取限售股解禁数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取限售股解禁失败: {e}")
            return None

    # ================== 股东权益数据接口 ==================

    async def get_dividend(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.7.1 分红数据
        获取指定股票的分红数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 分红数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_dividend, code_list)

            logger.info("成功获取分红数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取分红数据失败: {e}")
            return None

    async def get_right_issue(
        self,
        code_list: List[str],
        local_path: str = "D://AmazingData_local_data//",
        is_local: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        3.5.7.2 配股数据
        获取指定股票的配股数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 配股数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_right_issue, code_list)

            logger.info("成功获取配股数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取配股数据失败: {e}")
            return None

    # ================== 融资融券接口 ==================

    async def get_margin_summary(self) -> Optional[pd.DataFrame]:
        """
        3.5.8.1 融资融券交易汇总
        获取融资融券交易汇总数据

        Returns:
            DataFrame: 融资融券汇总数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_margin_summary)

            logger.info("成功获取融资融券汇总数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取融资融券汇总失败: {e}")
            return None

    async def get_margin_detail(self, code_list: List[str]) -> Optional[pd.DataFrame]:
        """
        3.5.8.2 融资融券标的明细
        获取指定股票的融资融券明细数据

        Args:
            code_list: 股票代码列表

        Returns:
            DataFrame: 融资融券明细数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_margin_detail, code_list)

            logger.info("成功获取融资融券明细数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取融资融券明细失败: {e}")
            return None

    # ================== 市场异动数据接口 ==================

    async def get_long_hu_bang(self, code_list: List[str]) -> Optional[pd.DataFrame]:
        """
        3.5.9.1 龙虎榜
        获取指定股票的龙虎榜数据

        Args:
            code_list: 股票代码列表

        Returns:
            DataFrame: 龙虎榜数据
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_long_hu_bang, code_list)

            logger.info("成功获取龙虎榜数据")
            return cast(Optional[pd.DataFrame], result)

        except Exception as e:
            logger.error(f"获取龙虎榜数据失败: {e}")
            return None

    # ================== 账户管理接口 ==================

    async def update_password(self, old_password: str, new_password: str) -> bool:
        """
        3.5.1.3 修改密码
        修改账户密码

        Args:
            old_password: 旧密码
            new_password: 新密码

        Returns:
            是否修改成功
        """
        if not self._connected:
            logger.error("未登录，无法修改密码")
            return False

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, ad.update_password, self.config.username, old_password, new_password
            )

            if result:
                # 更新配置中的密码
                self.config.password = new_password
                logger.info("密码修改成功")
                return True
            else:
                logger.error("密码修改失败")
                return False

        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return False
