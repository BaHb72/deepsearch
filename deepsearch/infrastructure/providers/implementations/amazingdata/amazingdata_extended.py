# encoding:utf-8
"""
AmazingData 扩展接口实现
实现35个API文档中的所有接口

Author: DeepSearch Team
Version: 2.0.0
Date: 2025-09-18
"""

import asyncio
import sys
from datetime import datetime
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union, cast

import pandas as pd

from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError
# AmazingData SDK
from .amazingdata import AmazingDataProvider
from .amazingdata_types import StockListItem
from .common import SubscriptionCallback
from .config import ProviderConfigLike
from .helpers import _normalize_date_to_int
from .logging_utils import ProcessLoggerAdapter
from .process import ProcessIsolatedAmazingDataProvider, SnapshotAlignPolicy

logger = ProcessLoggerAdapter(action="extended")


def _record_to_stock_item(record: StockListRecord) -> StockListItem:
    item: StockListItem = {
        "symbol": record.symbol,
        "name": record.name,
    }
    if record.exchange:
        item["exchange"] = record.exchange
    if record.list_date:
        item["list_date"] = record.list_date
    if record.delist_date:
        item["delist_date"] = record.delist_date
    if record.boards:
        item["board"] = record.boards[0]
    if record.market:
        item["market"] = record.market
    if record.security_type:
        item["security_type"] = record.security_type
    if record.status:
        item["status"] = record.status
    if record.is_listed is not None:
        item["is_listed"] = record.is_listed
    if record.company_id:
        item["company_id"] = record.company_id
    if record.pinyin:
        item["pinyin"] = record.pinyin
    if record.english_name:
        item["english_name"] = record.english_name
    if record.short_name:
        item["short_name"] = record.short_name
    return item

def _safe_dataframe(payload: Any) -> pd.DataFrame:
    """Normalize SDK responses into a DataFrame."""
    if isinstance(payload, pd.DataFrame):
        return payload.copy()
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, Mapping):
        try:
            return pd.DataFrame(payload)
        except Exception:
            return pd.DataFrame([payload])
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return pd.DataFrame(payload)
    return pd.DataFrame([payload])

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
                sdk = self._require_sdk()
                loop = asyncio.get_event_loop()

                # 初始化基础数据对象
                self._base_data = await loop.run_in_executor(None, sdk.BaseData)

                # 初始化信息数据对象
                self._info_data = await loop.run_in_executor(None, sdk.InfoData)

                # 获取交易日历
                calendar = await self.get_calendar()
                if calendar:
                    # 初始化市场数据对象
                    self._market_data = await loop.run_in_executor(None, sdk.MarketData, calendar)

                self._initialized_objects = True
                logger.info("AmazingData 数据对象初始化成功")
            except Exception as e:
                logger.error(f"初始化数据对象失败: {e}")
                raise DataProviderError(f"Failed to initialize data objects: {e}")

    # ================== P0基础接口 ==================

    async def get_stock_list_records(
            self,
            limit: Optional[int] = None,
            **kwargs: Any,
    ) -> List[StockListRecord]:
        """返回经规范化的 StockListRecord 列表，供领域层复用。"""

        payload = await super().get_stock_list(limit=limit, **kwargs)
        if not payload:
            return []

        records: list[StockListRecord] = []
        for entry in payload:
            if isinstance(entry, StockListRecord):
                record = entry
            elif isinstance(entry, Mapping):
                record = StockListRecord.from_payload(entry)
            else:
                continue
            if record.symbol:
                records.append(record)
        return records

    async def get_stock_list(
            self,
            limit: Optional[int] = None,
            **kwargs: Any,
    ) -> Optional[list[StockListItem]]:
        payload = await super().get_stock_list(limit=limit, **kwargs)
        if payload is None:
            return None
        if not payload:
            return []
        normalized: list[StockListItem] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            record = StockListRecord.from_payload(entry)
            if record.symbol:
                normalized.append(_record_to_stock_item(record))
        return normalized

    async def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取证券信息失败: {e}")
            return pd.DataFrame()

    async def get_calendar(
        self, data_type: str = "str", market: str = "SH"
    ) -> Optional[List[Union[int, datetime]]]:
        """
        3.5.2.7 交易日历
        获取交易所的交易日历

        Args:
            data_type: 返回数据类型，'str'或'datetime'
            market: 市场，'SH'上海或'SZ'深圳

        Returns:
            交易日列表，默认返回 int 格式的交易日（YYYYMMDD）
        """
        if not self._base_data:
            await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_calendar, data_type, market
            )

            if not result:
                logger.info("未获取到交易日历数据")
                return None

            if data_type and data_type.lower() == "datetime":
                normalized_datetime: list[int | datetime] = []
                for item in result:
                    if isinstance(item, datetime):
                        normalized_datetime.append(item)
                    elif isinstance(item, str):
                        try:
                            normalized_datetime.append(
                                datetime.strptime(item.replace("-", ""), "%Y%m%d")
                            )
                        except ValueError:
                            logger.warning(f"交易日转换失败（str->datetime）: {item}")
                    elif isinstance(item, (int, float)):
                        try:
                            normalized_datetime.append(
                                datetime.strptime(str(int(item)), "%Y%m%d")
                            )
                        except ValueError:
                            logger.warning(f"交易日转换失败（int->datetime）: {item}")
                logger.info("成功获取交易日历 %d 个交易日 (datetime 模式)" % len(normalized_datetime))
                return normalized_datetime if normalized_datetime else None

            normalized: list[int | datetime] = []
            for item in result:
                if isinstance(item, int):
                    normalized.append(item)
                elif isinstance(item, float):
                    normalized.append(int(item))
                elif isinstance(item, datetime):
                    normalized.append(int(item.strftime("%Y%m%d")))
                elif isinstance(item, str):
                    digits = "".join(ch for ch in item if ch.isdigit())
                    if len(digits) == 8:
                        normalized.append(int(digits))
                    else:
                        logger.warning(f"未知的交易日字符串格式: {item}")
                else:
                    logger.warning(f"忽略未知类型的交易日数据: {item}")

            logger.info("成功获取交易日历 %d 个交易日 (int 模式)" % len(normalized))
            return normalized if normalized else None

        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return None

    async def get_stock_basic(self, code_list: List[str]) -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取股票基础信息失败: {e}")
            return pd.DataFrame()

    async def get_backward_factor(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            local_path = self._prepare_local_path(local_path)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_backward_factor, code_list, local_path, is_local
            )

            logger.info("成功获取后复权因子数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取后复权因子失败: {e}")
            return pd.DataFrame()

    async def get_adj_factor(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            local_path = self._prepare_local_path(local_path)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_adj_factor, code_list, local_path, is_local
            )

            logger.info("成功获取单次复权因子数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取单次复权因子失败: {e}")
            return pd.DataFrame()

    async def get_history_stock_status(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            local_path = self._prepare_local_path(local_path)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_history_stock_status, code_list, local_path, is_local
            )

            logger.info("成功获取历史证券状态信息")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取历史证券状态失败: {e}")
            return pd.DataFrame()

    async def get_hist_code_list(
        self,
        security_type: str = "EXTRA_STOCK_A_SH_SZ",
        start_date: int = 20130101,
        end_date: int = 20250101,
            local_path: Optional[str] = None,
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
            local_path = self._prepare_local_path(local_path)

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
            self, local_path: Optional[str] = None, is_local: bool = True
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_bj_code_mapping)

            logger.info("成功获取北交所代码映射表")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取北交所代码映射失败: {e}")
            return pd.DataFrame()

    # ================== 历史行情接口 ==================

    async def query_snapshot(
            self,
            code_list: List[str],
            begin_date: int,
            end_date: int,
            *,
            market: str | None = None,
            align_policy: SnapshotAlignPolicy | str | None = SnapshotAlignPolicy.NEAREST_PREV,
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        3.5.4.1 历史快照
        查询历史快照数据

        Args:
            code_list: 股票列表
            begin_date: 开始日期，如 20240101
            end_date: 结束日期，如 20240201
            market: 指定市场代码（SH/SZ/BJ），为空时根据代码推断
            align_policy: 日期对齐策略

        Returns:
            字典，key 为代码，value 为 DataFrame
        """
        await self._ensure_data_objects()

        policy = SnapshotAlignPolicy.from_value(align_policy)
        requested_begin = begin_date
        requested_end = end_date

        def _detect_markets() -> set[str]:
            resolved: set[str] = set()
            if market:
                resolved.add(str(market).upper())
            for code in code_list:
                if not code:
                    continue
                upper = str(code).upper()
                if "." in upper:
                    suffix = upper.split(".")[-1]
                    if suffix in {"SH", "SZ", "BJ"}:
                        resolved.add(suffix)
            if not resolved:
                resolved.add("SH")
            return resolved

        trading_days: set[int] = set()
        for market_code in _detect_markets():
            try:
                calendar = await self.get_calendar(data_type="int", market=market_code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AmazingDataExtended 获取交易日失败 market={} error={}", market_code, exc)
                continue
            if not calendar:
                continue
            for item in calendar:
                normalized = _normalize_date_to_int(item)
                if normalized:
                    trading_days.add(normalized)

        if not trading_days:
            if policy is SnapshotAlignPolicy.STRICT:
                logger.info(
                    "AmazingDataExtended 历史快照严格策略缺少交易日 datasource={} begin={} end={}",
                    self.config.username,
                    requested_begin,
                    requested_end,
                )
                return {}
            policy = SnapshotAlignPolicy.PASSTHROUGH

        adjusted_begin = begin_date
        adjusted_end = end_date
        manual_adjusted = False

        if policy is SnapshotAlignPolicy.NEAREST_PREV and trading_days:
            sorted_days = sorted(trading_days)
            today_int = int(datetime.now(ProcessIsolatedAmazingDataProvider._LOCAL_TZ).strftime("%Y%m%d"))
            if adjusted_begin == adjusted_end:
                target_day = adjusted_begin
                needs_previous = False
                if target_day == today_int:
                    if target_day not in trading_days or not ProcessIsolatedAmazingDataProvider._is_within_trading_window(
                            datetime.now(ProcessIsolatedAmazingDataProvider._LOCAL_TZ)):
                        needs_previous = True
                elif target_day not in trading_days:
                    needs_previous = True
                if needs_previous:
                    previous = ProcessIsolatedAmazingDataProvider._resolve_previous_trading_day(trading_days,
                                                                                                target_day)
                    if previous is None:
                        logger.info(
                            "AmazingDataExtended 历史快照未找到前一交易日 begin={} end={} policy={}",
                            requested_begin,
                            requested_end,
                            policy.value,
                        )
                        return {}
                    adjusted_begin = previous
                    adjusted_end = previous
                    manual_adjusted = True
            adjusted_begin_candidate: Optional[int] = None
            for day in sorted_days:
                if day >= adjusted_begin:
                    adjusted_begin_candidate = day
                    break
            if adjusted_begin_candidate is None:
                adjusted_begin_candidate = sorted_days[-1]
            adjusted_end_candidate: Optional[int] = None
            for day in reversed(sorted_days):
                if day <= adjusted_end:
                    adjusted_end_candidate = day
                    break
            if adjusted_end_candidate is None:
                adjusted_end_candidate = sorted_days[0]
            if adjusted_begin_candidate > adjusted_end_candidate:
                logger.info(
                    "AmazingDataExtended 历史快照区间无效 begin={} end={} policy={}",
                    requested_begin,
                    requested_end,
                    policy.value,
                )
                return {}
            adjusted_begin = adjusted_begin_candidate
            adjusted_end = adjusted_end_candidate
        elif policy is SnapshotAlignPolicy.STRICT and trading_days:
            if adjusted_begin not in trading_days or adjusted_end not in trading_days:
                logger.info(
                    "AmazingDataExtended 历史快照严格策略拒绝非交易日 begin={} end={} policy={}",
                    requested_begin,
                    requested_end,
                    policy.value,
                )
                return {}

        if adjusted_begin > adjusted_end:
            logger.info(
                "AmazingDataExtended 历史快照调整后区间无效 begin={} end={} policy={}",
                adjusted_begin,
                adjusted_end,
                policy.value,
            )
            return {}

        if manual_adjusted or adjusted_begin != requested_begin or adjusted_end != requested_end:
            logger.info(
                "AmazingDataExtended 历史快照调整区间 begin={} end={} adjusted_begin={} adjusted_end={} policy={}",
                requested_begin,
                requested_end,
                adjusted_begin,
                adjusted_end,
                policy.value,
            )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._market_data.query_snapshot,
                code_list,
                adjusted_begin,
                adjusted_end,
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
            period: 周期，默认退回日线 ("day")

        Returns:
            字典，key为代码，value为DataFrame
        """
        await self._ensure_data_objects()

        try:
            effective_period = period
            if effective_period is None:
                try:
                    sdk = self._require_sdk()
                except DataProviderError:
                    sdk = None

                if sdk is not None:
                    constant = getattr(sdk, "constant", None)
                    if constant is not None:
                        try:
                            effective_period = constant.Period.day.value
                        except AttributeError:
                            logger.warning("AmazingData SDK 未提供周期常量，退回默认日线")

                if effective_period is None:
                    effective_period = "day"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._market_data.query_kline, code_list, begin_date, end_date, effective_period
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
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_profit_express, code_list)

            logger.info("成功获取业绩快报数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取业绩快报失败: {e}")
            return pd.DataFrame()

    async def get_profit_notice(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_profit_notice, code_list)

            logger.info("成功获取业绩预告数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取业绩预告失败: {e}")
            return pd.DataFrame()

    async def get_balance_sheet(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_balance_sheet, code_list)

            logger.info("成功获取资产负债表数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取资产负债表失败: {e}")
            return pd.DataFrame()

    async def get_cash_flow(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_cash_flow, code_list)

            logger.info("成功获取现金流量表数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取现金流量表失败: {e}")
            return pd.DataFrame()

    async def get_income(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取利润表失败: {e}")
            return pd.DataFrame()

    # ================== 股东股本数据接口 ==================

    async def get_share_holder(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_share_holder, code_list)

            logger.info("成功获取十大股东数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取十大股东数据失败: {e}")
            return pd.DataFrame()

    async def get_holder_num(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_holder_num, code_list)

            logger.info("成功获取股东人数数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取股东人数失败: {e}")
            return pd.DataFrame()

    async def get_equity_structure(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_structure, code_list
            )

            logger.info("成功获取股本结构数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取股本结构失败: {e}")
            return pd.DataFrame()

    async def get_equity_pledge_freeze(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_pledge_freeze, code_list
            )

            logger.info("成功获取股权质押/冻结数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取股权质押/冻结失败: {e}")
            return pd.DataFrame()

    async def get_equity_restricted(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_equity_restricted, code_list
            )

            logger.info("成功获取限售股解禁数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取限售股解禁失败: {e}")
            return pd.DataFrame()

    # ================== 股东权益数据接口 ==================

    async def get_dividend(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_dividend, code_list)

            logger.info("成功获取分红数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取分红数据失败: {e}")
            return pd.DataFrame()

    async def get_right_issue(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
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
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._info_data.get_right_issue, code_list)

            logger.info("成功获取配股数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取配股数据失败: {e}")
            return pd.DataFrame()

    # ================== 融资融券接口 ==================

    async def get_margin_summary(self) -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取融资融券汇总失败: {e}")
            return pd.DataFrame()

    async def get_margin_detail(self, code_list: List[str]) -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取融资融券明细失败: {e}")
            return pd.DataFrame()

    # ================== 市场异动数据接口 ==================

    async def get_long_hu_bang(self, code_list: List[str]) -> pd.DataFrame:
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
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取龙虎榜数据失败: {e}")
            return pd.DataFrame()

    async def get_block_trading(
            self,
            code_list: List[str],
            local_path: Optional[str] = None,
            is_local: bool = True,
            begin_date: Optional[int] = None,
            end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.9.2 大宗交易
        获取指定股票列表的大宗交易数据
        """
        await self._ensure_data_objects()

        try:
            local_path = self._prepare_local_path(local_path)

            block_method = getattr(self._info_data, "block_trading", None)
            if block_method is None:
                logger.error("AmazingData SDK 未提供 block_trading 接口")
                return pd.DataFrame()

            loop = asyncio.get_event_loop()

            def _invoke():
                try:
                    return block_method(
                        code_list,
                        local_path=local_path,
                        is_local=is_local,
                        begin_date=begin_date,
                        end_date=end_date,
                    )
                except TypeError:
                    args: list[object] = [code_list]
                    if local_path is not None:
                        args.append(local_path)
                        args.append(is_local)
                        if begin_date is not None:
                            args.append(begin_date)
                            if end_date is not None:
                                args.append(end_date)
                    return block_method(*args)

            result = await loop.run_in_executor(None, _invoke)
            if result is None:
                logger.info("未获取到大宗交易数据")
                return pd.DataFrame()

            if isinstance(result, pd.DataFrame):
                df = result.copy()
            elif isinstance(result, Mapping):
                frames: list[pd.DataFrame] = []
                for symbol, payload in result.items():
                    if isinstance(payload, pd.DataFrame):
                        item_df = payload.copy()
                    else:
                        item_df = pd.DataFrame(payload)
                    if not item_df.empty and "symbol" not in item_df.columns:
                        item_df["symbol"] = symbol
                    frames.append(item_df)
                df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            elif isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
                df = pd.DataFrame(result)
            else:
                df = pd.DataFrame(result)

            if df.empty:
                logger.info("大宗交易数据为空")
                return df

            column_map = {
                "MARKET_CODE": "symbol",
                "TRADE_DATE": "trade_date",
                "B_SHARE_PRICE": "price",
                "B_SHARE_VOLUME": "volume",
                "B_FREQUENCY": "frequency",
                "BLOCK_AVG_VOLUME": "avg_volume",
                "B_SHARE_AMOUNT": "amount",
                "B_BUYER_NAME": "buyer",
                "B_SELLER_NAME": "seller",
            }
            df.rename(columns=column_map, inplace=True)

            numeric_columns = ["price", "volume", "frequency", "avg_volume", "amount"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
                df.sort_values("trade_date", inplace=True)

            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.strip()

            logger.info("成功获取大宗交易数据")
            return df

        except Exception as e:
            logger.error(f"获取大宗交易数据失败: {e}")
            return None


    # ================== 期权相关接口 ==================

    async def get_option_code_list(self, security_type: str = "EXTRA_ETF_OP") -> Optional[List[str]]:
        """
        获取期权代码列表

        Args:
            security_type: 代码类型，默认EXTRA_ETF_OP（ETF期权）

        Returns:
            期权代码列表
        """
        await self._ensure_data_objects()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._base_data.get_option_code_list, security_type
            )

            logger.info(f"成功获取期权代码列表，共{len(result) if result else 0}个代码")
            return cast(Optional[List[str]], result)

        except Exception as e:
            logger.error(f"获取期权代码列表失败: {e}")
            return None

    async def get_option_basic_info(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取期权基本资料

        Args:
            code_list: 期权代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 期权基本资料，包含行权价、到期日、认购/认沽类型等
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_option_basic_info, code_list
            )

            logger.info("成功获取期权基本资料")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取期权基本资料失败: {e}")
            return pd.DataFrame()

    async def get_option_std_ctr_specs(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取期权合约属性

        Args:
            code_list: 期权代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 期权合约属性，包含合约单位、涨跌幅限制等
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_option_std_ctr_specs, code_list
            )

            logger.info("成功获取期权合约属性")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取期权合约属性失败: {e}")
            return pd.DataFrame()

    # ================== ETF 相关接口 ==================

    async def get_etf_pcf(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取ETF申赎清单 (PCF)

        Args:
            code_list: ETF代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: ETF申赎清单，包含现金替代标志、预估现金差额等
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_etf_pcf, code_list
            )

            logger.info("成功获取ETF申赎清单")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取ETF申赎清单失败: {e}")
            return pd.DataFrame()

    async def get_fund_share(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取ETF份额数据

        Args:
            code_list: ETF代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: ETF份额数据
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_fund_share, code_list
            )

            logger.info("成功获取ETF份额数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取ETF份额数据失败: {e}")
            return pd.DataFrame()

    async def get_fund_iopv(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取ETF IOPV (基金份额参考净值)

        Args:
            code_list: ETF代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: IOPV数据
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_fund_iopv, code_list
            )

            logger.info("成功获取ETF IOPV数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取ETF IOPV失败: {e}")
            return pd.DataFrame()

    # ================== 指数相关接口 ==================

    async def get_index_constituent(
        self,
        index_code: str,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取指数成分股

        Args:
            index_code: 指数代码
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 指数成分股，包含纳入/剔除日期
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_index_constituent, index_code
            )

            logger.info(f"成功获取指数 {index_code} 成分股")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取指数成分股失败: {e}")
            return pd.DataFrame()

    async def get_index_weight(
        self,
        index_code: str,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取指数成分股权重

        Args:
            index_code: 指数代码（支持上证50, 沪深300, 中证500/800/1000）
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 成分股权重数据
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_index_weight, index_code
            )

            logger.info(f"成功获取指数 {index_code} 成分股权重")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取指数成分股权重失败: {e}")
            return pd.DataFrame()

    async def get_industry_daily(
        self,
        industry_code: Optional[str] = None,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取行业指数日线数据

        Args:
            industry_code: 行业代码，为空则获取所有行业
            begin_date: 开始日期
            end_date: 结束日期
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 行业指数OHLC数据
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_industry_daily, industry_code, begin_date, end_date
            )

            logger.info("成功获取行业指数日线数据")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取行业指数日线数据失败: {e}")
            return pd.DataFrame()

    async def get_industry_constituent(
        self,
        industry_code: str,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取行业成分股

        Args:
            industry_code: 行业代码
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 行业成分股列表
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_industry_constituent, industry_code
            )

            logger.info(f"成功获取行业 {industry_code} 成分股")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取行业成分股失败: {e}")
            return pd.DataFrame()

    # ================== 其他接口 ==================

    async def get_treasury_yield(
        self,
        term: str = "y10",
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        获取国债收益率

        Args:
            term: 期限，如 'm3' (3个月), 'y1' (1年), 'y10' (10年)
            begin_date: 开始日期
            end_date: 结束日期
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 国债收益率数据
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_treasury_yield, term, begin_date, end_date
            )

            logger.info(f"成功获取国债收益率 (期限: {term})")
            return _safe_dataframe(result)

        except Exception as e:
            logger.error(f"获取国债收益率失败: {e}")
            return pd.DataFrame()

    # ================== 实时订阅接口 ==================

    async def subscribe_index_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅指数快照，复用通用订阅能力。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_stock_snapshot(
            self, code_list: Sequence[str], callback: SubscriptionCallback, data_type: str = "snapshot"
    ) -> bool:
        """订阅股票快照。"""
        return await self.subscribe_quote(list(code_list), callback, data_type=data_type)
        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_future_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅期货快照。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_etf_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅 ETF 快照。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_kzz_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅可转债快照。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_hkt_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅港股通快照。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_option_snapshot(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅期权快照。"""

        return await self.subscribe_quote(code_list, callback, data_type="snapshot")

    async def subscribe_kline(
        self, code_list: list[str], callback: SubscriptionCallback
    ) -> bool:
        """订阅 K 线推送。"""

        return await self.subscribe_quote(code_list, callback, data_type="kline")

    async def unsubscribe_all(self) -> bool:
        """取消所有订阅，兼容 WebAPI 的统一退出逻辑。"""

        if not self._subscriptions:
            return True
        return await self.unsubscribe_quote(list(self._subscriptions.keys()))

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
            sdk = self._require_sdk()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                sdk.update_password,
                self.config.username,
                old_password,
                new_password,
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


# --- Dynamic SDK forwarding and test patchable symbols ---
# Expose ad and HAS_AMAZINGDATA so tests can monkeypatch them on this module
try:  # pragma: no cover - optional dependency wiring
    from ._sdk_loader import ad as _loader_ad, HAS_AMAZINGDATA
except Exception:  # Safe fallbacks for test environments without SDK
    _loader_ad = None
    HAS_AMAZINGDATA = False

ad: Optional[ModuleType] = _loader_ad

# Candidate real SDK module names to import lazily
_SDK_CANDIDATES = ("AmazingData", "amazingdata", "tgw", "amazingdata_sdk")

__sdk_mod = None  # cache loaded SDK module


def _load_sdk():
    global __sdk_mod
    if __sdk_mod is not None:
        return __sdk_mod
    if "AmazingData" in sys.modules:
        __sdk_mod = sys.modules["AmazingData"]
        return __sdk_mod
    last_exc = None
    for name in _SDK_CANDIDATES:
        try:
            import importlib

            __sdk_mod = importlib.import_module(name)
            return __sdk_mod
        except Exception as e:  # pragma: no cover - import errors are environment-specific
            last_exc = e
    raise RuntimeError(
        f"Cannot import AmazingData SDK; tried {_SDK_CANDIDATES}. Last error: {last_exc!r}"
    )


# Alias map to tolerate different naming styles across SDKs
_ALIAS = {
    "onSnapshotindex": "on_snapshot_index",
    "onSnapshotfuture": "on_snapshot_future",
    "onSnapshotetf": "on_snapshot_etf",
    "onSnapshotkzz": "on_snapshot_kzz",
    "onSnapshothkt": "on_snapshot_hkt",
    "OnKLine": "on_kline",
}


def __getattr__(name: str) -> Any:
    """
    Delegate unknown attributes to the real SDK module.
    This allows tests or legacy code to resolve symbols on this shim module.
    """
    sdk = _load_sdk()
    if hasattr(sdk, name):
        return getattr(sdk, name)
    alt = _ALIAS.get(name)
    if alt and hasattr(sdk, alt):
        return getattr(sdk, alt)
    raise AttributeError(f"SDK has no attribute: {name}")
