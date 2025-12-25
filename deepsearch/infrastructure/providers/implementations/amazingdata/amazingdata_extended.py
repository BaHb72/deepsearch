# encoding:utf-8
"""
AmazingData 扩展接口实现
实现35个API文档中的所有接口

Author: DeepSearch Team
Version: 2.0.0
Date: 2025-09-18
"""

import asyncio
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union, cast

import pandas as pd

from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError, TGWError
# AmazingData SDK
from .amazingdata import AmazingDataProvider
from .amazingdata_types import StockListItem
from .common import SubscriptionCallback
from .config import ProviderConfigLike
from .helpers import _normalize_date_to_int
from .logging_utils import ProcessLoggerAdapter
from .process import ProcessIsolatedAmazingDataProvider, SnapshotAlignPolicy

# 导入枚举类型供文档引用使用
# 用户可通过以下方式使用枚举:
#   from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
#       AmazingDataTradingPhase, AmazingDataDivProgress, AmazingDataProgress,
#       get_trading_phase_name, get_div_progress_name, get_progress_name
#   )

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

def _is_tgw_connection_error(error_msg: str) -> bool:
    """识别是否为TGW连接相关错误
    
    TGW错误模式包括:
    - 未登录/登录失败
    - 连接超时
    - 网络错误
    - 进程崩溃
    - SDK系统退出
    """
    tgw_patterns = [
        "not login", "login first", "未登录", "登录失败",
        "connection", "timeout", "超时", "连接失败",
        "tgw", "push_init_failed", "tgw_push",
        "systemexit", "process crash", "进程崩溃",
        "network", "socket", "网络错误",
        "sdk unavailable", "sdk not detected",
    ]
    error_lower = error_msg.lower()
    return any(pattern in error_lower for pattern in tgw_patterns)


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


def _get_default_date_range(
    begin_date: Optional[int] = None,
    end_date: Optional[int] = None,
    default_days: int = 30
) -> tuple[int, int]:
    """
    获取日期范围的默认值
    
    根据SDK文档要求，begin_date和end_date是必填参数。
    当参数为None时，提供合理的默认值：
    - end_date 默认为今天
    - begin_date 默认为end_date往前推default_days天
    
    Args:
        begin_date: 开始日期（YYYYMMDD格式整数），可选
        end_date: 结束日期（YYYYMMDD格式整数），可选
        default_days: 默认天数范围，默认30天
        
    Returns:
        tuple[int, int]: (begin_date, end_date)
    """
    today = datetime.now()
    
    if end_date is None:
        end_date = int(today.strftime("%Y%m%d"))
    
    if begin_date is None:
        # 从end_date往前推default_days天
        end_dt = datetime.strptime(str(end_date), "%Y%m%d")
        begin_dt = end_dt - timedelta(days=default_days)
        begin_date = int(begin_dt.strftime("%Y%m%d"))
    
    return begin_date, end_date

class AmazingDataExtended(AmazingDataProvider):
    """AmazingData 扩展实现，包含所有35个API接口"""

    def __init__(self, config: ProviderConfigLike):
        """初始化扩展接口"""
        super().__init__(config)
        self._base_data: Any = None
        self._info_data: Any = None
        self._market_data: Any = None
        self._initialized_objects = False
        
        # 进程隔离后端，防止SDK调用sys.exit()导致主进程崩溃
        self._process_backend: Optional["ProcessIsolatedAmazingDataProvider"] = None
        # 是否启用进程隔离模式（默认启用）
        self._use_process_isolation: bool = True

    async def initialize(self) -> bool:
        """
        初始化AmazingDataExtended，使用进程隔离后端
        
        重写父类方法，确保进程隔离后端在Provider创建后立即初始化，
        而不是等到API方法调用时。这样可以在get_amazingdata_provider
        检查_connected状态时返回正确的值。
        
        注意：始终使用进程隔离模式，跳过父类的initialize()调用，
        因为父类会尝试直接SDK登录导致阻塞或主进程崩溃。
        """
        # 进程隔离模式：只使用进程隔离后端登录，跳过父类的直接SDK登录
        # 父类initialize()会执行_initialize_source()和_start_source()，
        # 这些方法内部会调用_perform_login()进行直接SDK登录，
        # 在主进程中调用SDK可能导致阻塞或崩溃
        logger.info("[AmazingDataExtended] 使用进程隔离后端初始化")
        await self._ensure_process_isolated_objects()
        logger.info(
            f"[AmazingDataExtended] initialize完成: "
            f"_connected={self._connected}, _sdk_available={self._sdk_available}"
        )
        
        return True

    async def _ensure_data_objects(self):
        """确保数据对象已初始化"""
        # 如果启用进程隔离模式，使用代理对象
        if self._use_process_isolation:
            await self._ensure_process_isolated_objects()
            return
        
        # 以下是原有的直接SDK调用逻辑（作为fallback，不推荐使用）
        await self._ensure_data_objects_direct()
    
    async def _ensure_process_isolated_objects(self):
        """使用进程隔离代理初始化SDK对象（安全模式）"""
        if self._initialized_objects:
            return
        
        logger.debug("[ProcessIsolation] 开始初始化进程隔离SDK对象...")
        
        try:
            from .sdk_proxy import ProcessIsolatedSDKProxySync
            from .process import ProcessIsolatedAmazingDataProvider
            
            # 初始化进程隔离后端
            if self._process_backend is None:
                logger.debug("[ProcessIsolation] 创建ProcessIsolatedAmazingDataProvider...")
                self._process_backend = ProcessIsolatedAmazingDataProvider(self.config)
            
            # 调用_ensure_ready()等待登录完成（而不是只调用initialize）
            # _ensure_ready会启动worker进程并执行登录，登录成功后会设置_connected=True
            logger.debug("[ProcessIsolation] 等待TGW登录完成...")
            await self._process_backend._ensure_ready()
            logger.debug("[ProcessIsolation] TGW登录流程完成")
            
            # 同步连接状态
            self._connected = self._process_backend.is_connected()
            self._sdk_available = getattr(self._process_backend, '_sdk_available', True)
            
            logger.debug(f"[ProcessIsolation] 连接状态: _connected={self._connected}")
            
            if not self._connected:
                # 获取详细错误信息
                last_error = getattr(self._process_backend, '_last_error', None)
                error_msg = (
                    f"AmazingData 进程隔离后端登录失败。"
                    f"状态: _connected={self._connected}。"
                    f"详情: {last_error or '未知错误'}。"
                    "请检查: 1) TGW配置是否正确 2) 网络是否连通"
                )
                logger.error(f"[ProcessIsolation] {error_msg}")
                raise TGWError(error_msg, error_code="TGW_NOT_CONNECTED", is_recoverable=True)
            
            # 创建同步代理对象替代直接的SDK对象
            # 使用同步代理(ProcessIsolatedSDKProxySync)以兼容run_in_executor调用模式
            # 这些代理会将所有方法调用转发到子进程执行
            logger.debug("[ProcessIsolation] 创建SDK同步代理对象...")
            self._base_data = ProcessIsolatedSDKProxySync("BaseData", self._process_backend)
            self._info_data = ProcessIsolatedSDKProxySync("InfoData", self._process_backend)
            self._market_data = ProcessIsolatedSDKProxySync("MarketData", self._process_backend)
            
            self._initialized_objects = True
            logger.info("[ProcessIsolation] SDK同步代理初始化成功，所有SDK调用将在子进程中安全执行")
            
        except TGWError:
            raise
        except Exception as e:
            error_str = str(e)
            logger.error(f"[ProcessIsolation] 初始化失败: {e}")
            if _is_tgw_connection_error(error_str):
                raise TGWError(
                    f"TGW进程隔离初始化失败: {e}",
                    error_code="TGW_PROCESS_INIT_FAILED",
                    is_recoverable=True
                )
            raise DataProviderError(f"Failed to initialize process-isolated SDK objects: {e}")
    
    async def _ensure_data_objects_direct(self):
        """直接初始化SDK对象（不安全，可能导致主进程崩溃）"""
        # 添加详细调试日志
        logger.debug(
            f"[DEBUG] _ensure_data_objects_direct called: "
            f"_initialized_objects={self._initialized_objects}, "
            f"_connected={self._connected}, "
            f"_degraded_mode={self._degraded_mode}, "
            f"_sdk_available={self._sdk_available}"
        )
        
        # 关键修复：如果未连接，抛出TGWError明确错误而不是静默跳过
        if not self._connected:
            error_msg = (
                "AmazingData 未连接，无法获取数据。"
                f"状态: _connected={self._connected}, "
                f"_degraded_mode={self._degraded_mode}, "
                f"_sdk_available={self._sdk_available}。"
                "请检查: 1) SDK是否安装 2) 账号密码是否正确 3) 网络是否能连接TGW服务器(端口600)"
            )
            logger.error(f"[DEBUG] {error_msg}")
            raise TGWError(error_msg, error_code="TGW_NOT_CONNECTED", is_recoverable=True)
        
        if not self._initialized_objects:
            logger.debug("[DEBUG] 开始初始化数据对象...")
            try:
                sdk = self._require_sdk()
                loop = asyncio.get_event_loop()

                # 初始化基础数据对象
                logger.debug("[DEBUG] 初始化 BaseData...")
                self._base_data = await loop.run_in_executor(None, sdk.BaseData)
                logger.debug(f"[DEBUG] BaseData 初始化完成: {type(self._base_data)}")

                # 初始化信息数据对象
                logger.debug("[DEBUG] 初始化 InfoData...")
                self._info_data = await loop.run_in_executor(None, sdk.InfoData)
                logger.debug(f"[DEBUG] InfoData 初始化完成: {type(self._info_data)}")

                # 获取交易日历
                logger.debug("[DEBUG] 获取交易日历...")
                calendar = await self.get_calendar()
                if calendar:
                    # 初始化市场数据对象
                    logger.debug("[DEBUG] 初始化 MarketData...")
                    self._market_data = await loop.run_in_executor(None, sdk.MarketData, calendar)
                    logger.debug(f"[DEBUG] MarketData 初始化完成: {type(self._market_data)}")
                else:
                    logger.warning("[DEBUG] 未能获取交易日历，MarketData 未初始化")

                self._initialized_objects = True
                logger.debug("[DEBUG] AmazingData 数据对象初始化成功")
            except TGWError:
                raise  # TGWError直接向上传播
            except Exception as e:
                error_str = str(e)
                logger.error(f"[DEBUG] 初始化数据对象失败: {e}")
                # 识别TGW相关错误
                if _is_tgw_connection_error(error_str):
                    raise TGWError(
                        f"TGW数据对象初始化失败: {e}", 
                        error_code="TGW_INIT_FAILED",
                        is_recoverable=True
                    )
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

        except TGWError:
            raise  # TGW错误向上传播，让调用方处理
        except Exception as e:
            error_str = str(e)
            # 识别TGW相关错误
            if _is_tgw_connection_error(error_str):
                raise TGWError(f"获取证券信息时TGW连接失败: {e}", error_code="TGW_CONNECTION_FAILED")
            import traceback
            logger.error(f"获取证券信息失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取股票基础信息失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 使用lambda包装以支持关键字参数，避免与worker端enforced_kwargs冲突
            result = await loop.run_in_executor(
                None, 
                lambda: self._base_data.get_backward_factor(
                    code_list, local_path, is_local=is_local
                )
            )

            logger.info("成功获取后复权因子数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取后复权因子失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 使用lambda包装以支持关键字参数，避免与worker端enforced_kwargs冲突
            result = await loop.run_in_executor(
                None, 
                lambda: self._base_data.get_adj_factor(
                    code_list, local_path, is_local=is_local
                )
            )

            logger.info("成功获取单次复权因子数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取单次复权因子失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 使用lambda包装以支持关键字参数，避免与worker端enforced_kwargs冲突
            result = await loop.run_in_executor(
                None, 
                lambda: self._info_data.get_history_stock_status(
                    code_list, local_path, is_local=is_local
                )
            )

            logger.info("成功获取历史证券状态信息")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取历史证券状态失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取北交所代码映射失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.5.4 业绩快报
        获取指定股票的业绩快报数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 报告期开始日期筛选(格式: YYYYMMDD)，可选
            end_date: 报告期结束日期筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 业绩快报数据，包含字段:
                MARKET_CODE: 证券代码
                REPORTING_PERI: 报告期
                ANN_DATE: 公告日期
                TOTAL_ASSETS: 总资产(万元)
                NET_PRO_EXCL_MIN_INT_INC: 归母净利润(万元)
                TOT_OPERA_REV: 营业总收入(万元)
                TOTAL_PROFIT: 利润总额(万元)
                EPS_BASIC: 每股收益(元)
                等40+字段
        """
        await self._ensure_data_objects()

        try:
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=90)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_profit_express(code_list, **kwargs)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_profit_express(code_list, **kwargs)
                )

            logger.info("成功获取业绩快报数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取业绩快报失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_profit_notice(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.5.5 业绩预告
        获取指定股票的业绩预告数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 报告期开始日期筛选(格式: YYYYMMDD)，可选
            end_date: 报告期结束日期筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 业绩预告数据，包含字段:
                MARKET_CODE: 证券代码
                SECURITY_NAME: 证券简称
                P_TYPECODE: 业绩预告类型代码(1-11对应不同类型)
                REPORTING_PERIOD: 报告期
                ANN_DATE: 公告日期
                P_CHANGE_MAX: 预告净利润变动幅度上限(%)
                P_CHANGE_MIN: 预告净利润变动幅度下限(%)
                NET_PROFIT_MAX: 预告净利润最高值(万元)
                等字段
        """
        await self._ensure_data_objects()

        try:
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=90)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_profit_notice(code_list, **kwargs)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_profit_notice(code_list, **kwargs)
                )

            logger.info("成功获取业绩预告数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取业绩预告失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_balance_sheet(code_list, local_path=local_path, is_local=is_local)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: self._info_data.get_balance_sheet(code_list, local_path=local_path, is_local=is_local)
                )

            logger.info("成功获取资产负债表数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取资产负债表失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 不要掩盖错误，向上传播以便API返回 success: false

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
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_cash_flow(code_list, local_path=local_path, is_local=is_local)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: self._info_data.get_cash_flow(code_list, local_path=local_path, is_local=is_local)
                )

            logger.info("成功获取现金流量表数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取现金流量表失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_income(code_list, local_path=local_path, is_local=is_local)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: self._info_data.get_income(code_list, local_path=local_path, is_local=is_local)
                )

            logger.info("成功获取利润表数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取利润表失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    # ================== 股东股本数据接口 ==================

    async def get_share_holder(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.6.1 十大股东数据
        获取指定股票的十大股东数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 截止日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 截止日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 十大股东数据，包含字段:
                ANN_DATE: 公告日期
                MARKET_CODE: 证券代码
                HOLDER_ENDDATE: 截止日期  
                HOLDER_TYPE: 股东类型(10-十大股东, 20-流通股前十大股东)
                QTY_NUM: 持股数量
                HOLDER_NAME: 股东名称
                HOLDER_HOLDER_CATEGORY: 股东性质(1-个人, 2-公司)
                HOLDER_QUANTITY: 持股数(股)
                HOLDER_PCT: 持股占比(%)
                HOLDER_SHARECATEGORYNAME: 股东类型
                FLOAT_QTY: 流通股数量
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_share_holder(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_share_holder(code_list, **kwargs)

                )

            logger.info("成功获取十大股东数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取十大股东数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_holder_num(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.6.2 股东人数
        获取指定股票的股东人数数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 股东户数统计上报日开始筛选(格式: YYYYMMDD)，可选
            end_date: 股东户数统计上报日结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 股东人数数据，包含字段:
                MARKET_CODE: 证券代码
                ANN_DT: 公告日期
                HOLDER_ENDDATE: 股东户数统计上报日
                HOLDER_TOTAL_NUM: A股、B股、H股、优先股的总户数
                HOLDER_NUM: A级或B类户数
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_holder_num(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_holder_num(code_list, **kwargs)

                )

            logger.info("成功获取股东人数数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取股东人数失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_equity_structure(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.6.3 股本结构
        获取指定股票的股本结构数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 变动日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 变动日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 股本结构数据，包含字段:
                MARKET_CODE: 证券代码
                ANN_DATE: 公告日期
                CHANGE_DATE: 变动日期
                SHARE_CHANGE_REASON_STR: 股本变动原因说明
                EX_CHANGE_DATE: 除权日期
                CURRENT_SIGN: 是否有效(1-是, 0-否)
                IS_VALID: 是否有效
                TOT_SHARE: 总股本(万股)
                FLOAT_SHARE: 流通股(万股)
                FLOAT_A_SHARE: 流通A股(万股)
                FLOAT_B_SHARE: 流通B股(万股)
                FLOAT_HK_SHARE: 流通H股(万股)
                等30+字段
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_equity_structure(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_equity_structure(code_list, **kwargs)

                )

            logger.info("成功获取股本结构数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取股本结构失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_equity_pledge_freeze(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.6.4 股权质押/冻结
        获取指定股票的股权质押/冻结数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 公告日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 公告日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 股权质押/冻结数据，包含字段:
                MARKET_CODE: 证券代码
                ANN_DATE: 公告日期
                HOLDFR_NAME: 股东名称
                HOLDFR_TYPE_CODE: 股东类型代码(2-公司, 3-个人, 5-其他, 20-6-高管或创始人, 7-0-宏观政投, 7-8-非自然人股东, 9-保密, 1-未知)
                IS_EQUITY_PLEDGFR_REPO: 是否是股权质押(1-是, 0-否)
                IS_DISFROZEN: 是否是股权冻结(1-是, 0-否)
                FROZEN_INSTITLJTTON: 执行冻结机构
                DISFROZEN_TIME: 解冻时间
                SHR_CATEGORY_CODE: 股份性质类别代码(1-沪深主板; 2-个人或企业; 3-B股可交易; 4-已质押; 5-6-已质押或可质押; 9-保密; 远程- )
                FREEZE_TYPE: 冻结/质押类型(1-质押; 2-司法; 3-冻结; 6; 10)
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_equity_pledge_freeze(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_equity_pledge_freeze(code_list, **kwargs)

                )

            logger.info("成功获取股权质押/冻结数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取股权质押/冻结失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_equity_restricted(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.6.5 限售股解禁
        获取指定股票的限售股解禁数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 解禁日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 解禁日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 限售股解禁数据，包含字段:
                MARKET_CODE: 证券代码
                LIST_DATE: 解禁日期
                SHARE_RATIO: 解禁占总股本比(%)
                SHARE_LST_TYPE_NAME: 解禁分类型名称
                SHARE_LST: 解禁数(张)
                SHARE_LST_IS_ANN: 上市解禁是否公告在(0-否, 1-是, 为空时标示公告位置清晰)
                CLOSE_PRICE: 近日收盘价(元)
                SHARE_LST_MARKET_VALUE: 解禁市值(元)
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_equity_restricted(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_equity_restricted(code_list, **kwargs)

                )

            logger.info("成功获取限售股解禁数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取限售股解禁失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    # ================== 股东权益数据接口 ==================

    async def get_dividend(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.7.1 分红数据
        获取指定股票的分红数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 公告日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 公告日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 分红数据，包含字段:
                MARKET_CODE: 证券代码
                DIV_PROGRESS: 分红进度(需要从枚举值对应查询类型)
                DVD_PER_SHARE_S1K: 每股送转(股)
                DVD_PER_SHARE_PRE_T: 每股派息(税前)(元)
                DVD_PER_SHARE_AFTER_TAX_CASH: 每现派息(税后)(元)
                DATE_BOD_RECORD: 股权登记日
                DATE_EX: 除权除息日
                DATE_DVD_PAYOUT: 派息日
                LISTINGDATE_OF_DVD_SHR: 红股上市日
                DIV_PRELANDATE: 预案公告日
                DIV_SMTGDATE: 股东大会公告日
                DATE_DVD_ANN: 分红公告日
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_dividend(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_dividend(code_list, **kwargs)

                )

            logger.info("成功获取分红数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取分红数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_right_issue(
        self,
        code_list: List[str],
            local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.7.2 配股数据
        获取指定股票的配股数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 公告日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 公告日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 配股数据，包含字段:
                MARKET_CODE: 证券代码
                PROGRESS: 方案进度，参看股票配股进度代码表 (AmazingDataProgress枚举)
                使用 get_progress_name(value) 可获取进度说明
                PRICE: 配股价格(元)
                RATIO: 配股比例
                AMT_PLAN: 配股(计划)解禁(万股)
                AMT_REAL: 配股实际募集(万股)
                COLLECTION_FUND: 募集资金(元)
                PLAN_REG_DATE: 预计登记日
                EX_DIVIDEND_DATE: 除权日
                LISTED_DATE: 配股上市日
                PAY_START_DATE: 缴款起始日
                PAY_END_DATE: 缴款终止日
                PREPLAN_DATE: 预案公告日
                SMTG_ANN_DATE: 股东大会公告日
                PASS_DATE: 发审委通过公告日
                APPROVTD_DATE: 证监会核准公告日
                EXECUTE_DATE: 配股实施公告日
                RESULT_ANN_DATE: 配股结果公告日
                LIST_ANN_DATE: 上市公告日
                GUARANTOR: 担保方
                GUARTYPE: 担保类型(万股)
                RIGHTSISSUE_CODE: 配股代码
                ANN_DATE: 公告日期
                RIGHTSISSUE_YEAR: 配股年度
                RIGHTSISSUE_DESC: 配股说明
                RIGHTSISSUE_NAME: 配股简称
                RATIO_DENOMINATO_R: 配股比例分母
                RATIO_MOLECULAR: 配股比例分子
                SUBS_METHOD: 认购方式
                EXPECTED_FUND_RAISING: 预计募集资金(元)
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=365)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_right_issue(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_right_issue(code_list, **kwargs)

                )

            logger.info("成功获取配股数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取配股数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    # ================== 融资融券接口 ==================

    async def get_margin_summary(
        self,
        local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.8.1 融资融券交易汇总
        获取融资融券交易汇总数据

        Args:
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 交易日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 交易日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 融资融券汇总数据，包含字段:
                TRADE_DATE: 交易日期
                SUM_BORROW_MONEY_BALANCE: 融资余额(元)
                SUM_PURCH_WITH_BORROW_MONEY: 融资买入额(元)
                SUM_REPAYMENT_OF_BORROW_MONEY: 融资偿还额(元)
                SUM_SEC_LENDING_BALANCE: 融券余额(元)
                SUM_SALES_OF_BORROWED_SEC: 融券卖出量(股,份,手)
                SUM_MARGIN_TRADE_BALANCE: 融资融券余额(元)
        """
        await self._ensure_data_objects()

        try:
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_margin_summary(**kwargs)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_margin_summary(**kwargs)
                )

            logger.info("成功获取融资融券汇总数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取融资融券汇总失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_margin_detail(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.8.2 融资融券标的明细
        获取指定股票的融资融券明细数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 交易日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 交易日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 融资融券明细数据，包含字段:
                MARKET_CODE: 证券代码
                SECURITY_NAME: 证券简称
                TRADE_DATE: 交易日期
                BORROW_MONEY_BALANCE: 融资余额(元)
                PURCH_WITH_BORROW_MONEY: 融资买入额(元)
                REPAYMENT_OF_BORROW_MONEY: 融资偿还额(元)
                SEC_LENDING_BALANCE: 融券余额(元)
                SALES_OF_BORROWED_SEC: 融券卖出量(股,份,手)
                REPAYMENT_OF_BORROW_SEC: 融券偿还量(股,份,手)
                SEC_LENDING_BALANCE_VOL: 融券余量(股,份,手)
                MARGIN_TRADE_BALANCE: 融资融券余额(元)
        """
        await self._ensure_data_objects()

        try:
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_margin_detail(code_list, **kwargs)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_margin_detail(code_list, **kwargs)
                )

            logger.info("成功获取融资融券明细数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取融资融券明细失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    # ================== 市场异动数据接口 ==================

    async def get_long_hu_bang(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.9.1 龙虎榜
        获取指定股票的龙虎榜数据

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 交易日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 交易日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 龙虎榜数据，包含字段:
                MARKET_CODE: 证券代码
                TRADE_DATE: 交易日期
                SECURITY_NAME: 证券名称
                REASON_TYPE: 二级原因类别
                REASON_TYPE_NAME: 二级原因
                CHANGE_RANGE: 涨跌幅(%)
                TRADER_NAME: 营业部名称
                BUY_AMOUNT: 买入金额(万)
                SELL_AMOUNT: 卖出金额(万)
                FLOW_MARK: 资金标示(1表示买入,2表示卖出)
                TOTAL_AMOUNT: 交易总金额(万元)
                TOTAL_VOLUME: 交易总数量(万股)
        """
        await self._ensure_data_objects()

        try:
            # 处理local_path，确保传递必填参数
            local_path = self._prepare_local_path(local_path)
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                result = await self._info_data.get_long_hu_bang(code_list, **kwargs)
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_long_hu_bang(code_list, **kwargs)
                )

            logger.info("成功获取龙虎榜数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取龙虎榜数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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

        Args:
            code_list: 股票代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 交易日期开始筛选(格式: YYYYMMDD)，可选
            end_date: 交易日期结束筛选(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 大宗交易数据，包含字段:
                MARKET_CODE: 证券代码
                TRADE_DATE: 交易日期
                B_SHARE_PRICE: 成交价(元)
                B_SHARE_VOLUME: 成交量(万股)
                B_FREQUENCY: 年数
                BLOCK_AVG_VOLUME: 每笔成交数量(万股份)
                B_SHARE_AMOUNT: 成交金额(万元)
                B_BUYER_NAME: 买方席位部制
                B_SELLER_NAME: 卖方席位部制
        """
        await self._ensure_data_objects()

        try:
            local_path = self._prepare_local_path(local_path)
            logger.info(f"[get_block_trading] code_list={code_list}, local_path={local_path}")
            
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "local_path": local_path,
                "is_local": is_local,
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理
            if self._use_process_isolation and self._process_backend is not None:
                # 代理对象返回的是异步方法，直接await
                logger.info(f"[get_block_trading] Using process isolation, calling block_trading with kwargs={kwargs}")
                result = await self._info_data.get_block_trading(code_list, **kwargs)
                logger.info(f"[get_block_trading] Result type: {type(result).__name__}, is None: {result is None}")
            else:
                # 直接SDK对象是同步的，需要使用run_in_executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._info_data.get_block_trading(code_list, **kwargs)
                )

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
            import traceback
            logger.error(f"获取大宗交易数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误


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
        3.5.10.1 期权基本资料
        获取期权基本资料(沪深交易所的ETF期权)

        Args:
            code_list: 期权代码列表
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 期权基本资料，包含字段:
                CONTRACT_FULL_NAME: 合约全称
                CONTRACT_TYPE: 合约类型(C表示认购, P表示认沽)
                DELIVERY_MONTH: 交割月份
                EXPIRY_DATE: 到期日
                EXERCISE_PRICE: 行权价格
                EXERCISE_END_DATE: 权利行权日
                START_TRADE_DATE: 开始交易日
                LISTING_REF_PRICE: 挂牌参考价
                LAST_TRADE_DATE: 最后交易日
                EXCHANGE_CODE: 合约交易所代码
                DELIVERY_DATE: 标的交割日
                CONTRACT_UNIT: 合约单位
                IS_TRADE: 是否交易
                EXCHANGE_SHORT_NAME: 合约交易所简称
                CONTRACT_ADJUST_FLAG: 合约调整标识
                MARKET_CODE: 合约代码
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
            import traceback
            logger.error(f"获取期权基本资料失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_option_std_ctr_specs(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        3.5.10.2 期权标准合约属性
        获取沪深期权标准合约的结构属性(沪深交易所的ETF期权)

        Args:
            code_list: 期权代码列表(支持深沪ETF期权的代码列表，如159919.SZ、159915.SZ、159922.SZ等)
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 期权标准合约属性，包含字段:
                EXERCISE_DATE: 期权行权日
                CONTRACT_UNIT: 合约单位
                POSITION_DECLARE_MIN: 实行申报下限
                QUOTE_CURRENCY_UNIT: 报价货币单位
                LAST_TRADING_DATE: 最后交易日
                POSITION_LIMIT: 实行限制
                DELIST_DATE: 摘牌日期
                NOTIONAL_VALUE: 名义价值
                EXERCISE_METHOD: 行权方式
                DELIVERY_METHOD: 交割方式
                SETTLEMENT_MONTH: 合约结算月份
                TRADING_FEE: 交易费叙
                EXCHANGE_NAME: 交易所名称
                OPTION_EN_NAME: 期权英文名称
                CONTRACT_VALUE: 合约价值
                IS_SIMULATION: 是否仿真交易(0否1是)
                CONTRACT_UNIT_DIMENSI: 合约单位量纲
                OPTION_STRIKE_PRICE: 期权行权价
                IS_SIMULATION_TRADE: 是否仿真交易(0否1是)
                LISTED_DATE: 上市日期
                OPTION_NAME: 期权名称
                PREMIUM: 期权金
                OPTION_TYPE: 期权类型(ETF对标类型)
                TRADING_HOURS_DESC: 交易时间说明
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
            import traceback
            logger.error(f"获取期权合约属性失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_option_mon_ctr_spcon(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        3.5.10.3 期权月合约属性变动
        获取期权月度合约的规格变化数据

        Args:
            code_list: 支持沪深ETF期权合约代码列表，可见get_code_list
            local_path: 本地存储数据的路径，需指定路径，格式如: 'D://AmazingData_local_data//'
            is_local: 默认为True，是否从本地获取已下载数据

        Returns:
            DataFrame: 期权月合约属性变动column为block_trading约定等
            index为标的代码
            包含字段:
                CODE_OLD: 原交易代码
                CHANGE_DATE: 调整日期
                MARKET_CODE: 市场代码
                NAME_NEW: 新合约简称
                EXERCISE_PRICE_NEW: 新行权价格(元)
                NAME_OLD: 原合约简称
                CODE_NEW: 新交易代码
                EXERCISE_PRICE_OLD: 原行权价(元)
                UNIT_OLD: 原合约单位(份)
                UNIT_NEW: 新合约单位(份)
                CHANGE_REASON: 调整原因
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_option_mon_ctr_spcon, code_list
            )

            logger.info("成功获取期权月合约属性变动数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取期权月合约属性变动失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取ETF申赎清单失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取ETF份额数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取ETF IOPV失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取指数成分股失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取指数成分股权重失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_industry_daily(industry_code, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_industry_daily(industry_code, **kwargs)

                )

            logger.info("成功获取行业指数日行情数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取行业指数日行情数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取行业成分股失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_industry_base_info(
        self,
        local_path: Optional[str] = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """
        3.5.13.1 行业指数基本信息
        获取行业指数基本信息列表

        Args:
            local_path: 本地存储路径
            is_local: 是否使用本地存储

        Returns:
            DataFrame: 行业指数基本信息，包含字段:
                INDEX_CODE: 指数代码
                INDUSTRY_CODE: 行业代码
                LEVEL_TYPE: 指数类别
                    1: 一级行业
                    2: 二级行业
                    3: 三级行业
                LEVEL1_NAME: 一级行业
                LEVEL2_NAME: 二级行业
                LEVEL3_NAME: 三级行业
                IS_PUB: 是否发布
                    1: 已发布
                    2: 未发布
                CHANGE_REASON: 更改原因
        """
        await self._ensure_data_objects()

        try:
            _ = self._prepare_local_path(local_path)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._info_data.get_industry_base_info
            )

            logger.info("成功获取行业指数基本信息")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取行业指数基本信息失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

    async def get_industry_weight(
        self,
        code_list: List[str],
        local_path: Optional[str] = None,
        is_local: bool = True,
        begin_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        3.5.13.3 行业指数成分股日权重
        获取指定行业指数的成分股日权重数据

        Args:
            code_list: 行业指数代码列表(支持从get_industry_base_info获取的指数代码)
            local_path: 本地存储路径
            is_local: 是否使用本地存储
            begin_date: 开始日期(格式: YYYYMMDD)，可选
            end_date: 结束日期(格式: YYYYMMDD)，可选

        Returns:
            DataFrame: 行业指数成分股权重数据，包含字段:
                WEIGHT: 权重
                CON_CODE: 成份股代码
                TRADE_DATE: 交易日期
                INDEX_CODE: 指数代码
        """
        await self._ensure_data_objects()

        try:
            # 获取默认日期范围（SDK要求begin_date和end_date必填）
            begin_date, end_date = _get_default_date_range(begin_date, end_date, default_days=30)
            
            kwargs = {
                "begin_date": begin_date,
                "end_date": end_date,
            }

            # 检查是否使用进程隔离代理

            if self._use_process_isolation and self._process_backend is not None:

                # 代理对象返回的是异步方法，直接await

                result = await self._info_data.get_industry_weight(code_list, **kwargs)

            else:

                # 直接SDK对象是同步的，需要使用run_in_executor

                loop = asyncio.get_event_loop()

                result = await loop.run_in_executor(

                    None,

                    lambda: self._info_data.get_industry_weight(code_list, **kwargs)

                )

            logger.info("成功获取行业指数成分股权重数据")
            return _safe_dataframe(result)

        except Exception as e:
            import traceback
            logger.error(f"获取行业指数成分股权重数据失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
            import traceback
            logger.error(f"获取国债收益率失败: {e}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise  # 向上传播错误

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
# 注意: AmazingData 和 tgw 的 login 函数签名不同！优先使用 AmazingData
_SDK_CANDIDATES = ("AmazingData", "amazingdata", "tgw", "amazingdata_sdk")

__sdk_mod = None  # cache loaded SDK module


def _load_sdk():
    global __sdk_mod
    if __sdk_mod is not None:
        return __sdk_mod
    
    # 优先尝试直接导入 AmazingData（有正确的 login 签名）
    # 不优先使用 sys.modules 缓存，因为可能缓存了错误的 tgw 模块
    last_exc = None
    for name in _SDK_CANDIDATES:
        try:
            import importlib
            mod = importlib.import_module(name)
            # 验证模块有 login 函数
            if hasattr(mod, 'login') and callable(getattr(mod, 'login', None)):
                __sdk_mod = mod
                return __sdk_mod
        except Exception as e:  # pragma: no cover - import errors are environment-specific
            last_exc = e
            continue
    
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
