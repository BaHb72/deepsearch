"""AmazingData Dask Client Adapter

通过 Dask Client 远程调用 Windows Worker 上的 AmazingDataActor。
用于分布式部署场景，实现 DataProvider 接口。

Architecture:
    Client (FastAPI)                    Worker (Windows)
           │                                   │
           │  ─── client.submit() ──────────▶  │
           │                                   │
           │                      worker.actors["amazingdata"]
           │                              │
           │                      actor.call_sync(method, **kwargs)
           │                              │
           │  ◀─────── result ───────────  │

Features:
    - 自动选择 Windows Worker (WIN:1 资源标签)
    - 连接池管理和复用
    - 错误处理和自动重试
    - 超时保护

Usage:
    >>> from distributed import Client
    >>> dask_client = Client("tcp://localhost:8786")
    >>> adapter = AmazingDataDaskAdapter(dask_client)
    >>> await adapter.initialize()
    >>> result = await adapter.query_kline(code_list=["000001.SZ"], ...)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pandas as pd
from core.infrastructure.providers.interfaces.base import DataProviderError
from loguru import logger

if TYPE_CHECKING:
    from distributed import Client, Future


class AmazingDataDaskAdapter:
    """AmazingData Dask Client Adapter

    实现 DataProvider 接口，通过 Dask 分布式调用远程 Actor。

    Attributes:
        name: 数据源名称
        _client: Dask distributed Client 实例
        _timeout: 远程调用超时时间（秒）
        _retry_count: 失败重试次数
        _windows_worker: 缓存的 Windows Worker 地址
        _actor_available: Actor 是否可用
    """

    name = "amazingdata"

    def __init__(
        self,
        dask_client: "Client",
        timeout: float = 30.0,
        retry_count: int = 3,
    ):
        """初始化 Dask Adapter

        Args:
            dask_client: Dask distributed Client 实例
            timeout: 远程调用超时时间（秒）
            retry_count: 失败重试次数
        """
        self._client = dask_client
        self._timeout = timeout
        self._retry_count = retry_count

        # 缓存 Windows Worker 地址
        self._windows_worker: str | None = None
        self._actor_available = False
        self._initialized = False

        logger.info(
            "[AmazingDataDaskAdapter] 初始化 | scheduler={}",
            dask_client.scheduler.address if dask_client.scheduler else "unknown",
        )

    # ==================== 连接管理 ====================

    async def initialize(self) -> bool:
        """初始化 Adapter，查找可用的 Windows Worker

        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True

        try:
            # 查找有 WIN:1 资源的 Worker
            self._windows_worker = await self._find_windows_worker()
            if not self._windows_worker:
                logger.error("[DaskAdapter] 未找到 Windows Worker (WIN:1)")
                return False

            # 验证 Actor 是否已注册
            self._actor_available = await self._check_actor_available()
            if not self._actor_available:
                logger.error(
                    "[DaskAdapter] Worker {} 上未找到 amazingdata Actor",
                    self._windows_worker,
                )
                return False

            self._initialized = True
            logger.info(
                "[DaskAdapter] 初始化成功 | worker={} | actor=available",
                self._windows_worker,
            )
            return True

        except Exception as e:
            logger.error("[DaskAdapter] 初始化失败: {}", e, exc_info=True)
            return False

    async def _find_windows_worker(self) -> str | None:
        """查找有 WIN:1 资源的 Worker

        Returns:
            Worker 地址，未找到返回 None
        """
        try:
            # 获取所有 Worker 信息
            scheduler_info = self._client.scheduler_info()
            workers = scheduler_info.get("workers", {})

            for worker_addr, worker_info in workers.items():
                # 检查资源标签
                resources = worker_info.get("resources", {})
                if resources.get("WIN", 0) >= 1:
                    logger.debug(
                        "[DaskAdapter] 找到 Windows Worker | addr={} | resources={}",
                        worker_addr,
                        resources,
                    )
                    return worker_addr

            logger.warning("[DaskAdapter] 未找到 Windows Worker (WIN:1)")
            return None

        except Exception as e:
            logger.error("[DaskAdapter] 查找 Worker 失败: {}", e)
            return None

    async def _check_actor_available(self) -> bool:
        """检查 Actor 是否在 Worker 上可用

        Returns:
            Actor 是否可用
        """
        try:

            def _check(dask_worker: Any) -> bool:
                """检查 Worker 上是否有 amazingdata Actor"""
                actors = getattr(dask_worker, "actors", {})
                return "amazingdata" in actors

            future: "Future[bool]" = self._client.submit(
                _check,
                workers=[self._windows_worker],
                pure=False,
            )
            result = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=10.0,
            )
            return bool(result)

        except asyncio.TimeoutError:
            logger.warning("[DaskAdapter] 检查 Actor 超时")
            return False
        except Exception as e:
            logger.warning("[DaskAdapter] 检查 Actor 失败: {}", e)
            return False

    def is_connected(self) -> bool:
        """检查是否已连接

        Returns:
            是否已连接并可用
        """
        return self._initialized and self._actor_available

    # ==================== 核心远程调用 ====================

    async def _call_actor(
        self,
        method: str,
        retry: int = 0,
        **kwargs: Any,
    ) -> Any:
        """通用远程调用方法

        Args:
            method: Actor 方法名 (如 "query_kline")
            retry: 当前重试次数
            **kwargs: 方法参数

        Returns:
            Actor 方法返回值

        Raises:
            DataProviderError: 调用失败或超时
        """
        if not self._actor_available:
            raise DataProviderError("Actor 不可用，请先调用 initialize()")

        try:

            def _remote_call(dask_worker: Any) -> Any:
                """在 Worker 上执行的函数"""
                actor = getattr(dask_worker, "actors", {}).get("amazingdata")
                if actor is None:
                    raise RuntimeError("amazingdata Actor 未注册")

                # 调用 Actor 的同步方法
                return actor.call_sync(method, **kwargs)

            # 提交任务到 Windows Worker
            future: "Future[Any]" = self._client.submit(
                _remote_call,
                workers=[self._windows_worker],
                resources={"WIN": 1},
                pure=False,
            )

            # 等待结果（带超时）
            result = await asyncio.wait_for(
                asyncio.wrap_future(future),
                timeout=self._timeout,
            )

            logger.debug(
                "[DaskAdapter] 调用成功 | method={} | worker={}",
                method,
                self._windows_worker,
            )
            return result

        except asyncio.TimeoutError:
            logger.error(
                "[DaskAdapter] 调用超时 | method={} | timeout={}s",
                method,
                self._timeout,
            )
            if retry < self._retry_count:
                logger.info("[DaskAdapter] 重试 {}/{}", retry + 1, self._retry_count)
                return await self._call_actor(method, retry=retry + 1, **kwargs)
            raise DataProviderError(f"Actor 调用超时: {method}")

        except Exception as e:
            logger.error(
                "[DaskAdapter] 调用失败 | method={} | error={}",
                method,
                str(e),
                exc_info=True,
            )
            if retry < self._retry_count:
                logger.info("[DaskAdapter] 重试 {}/{}", retry + 1, self._retry_count)
                await asyncio.sleep(1)  # 延迟重试
                return await self._call_actor(method, retry=retry + 1, **kwargs)
            raise DataProviderError(f"Actor 调用失败: {method} - {e}")

    # ==================== 基础数据接口 (BaseData) ====================

    async def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
        """3.5.2.1 每日最新证券信息

        Args:
            security_type: 代码类型，默认EXTRA_STOCK_A（沪深北A股）

        Returns:
            DataFrame: 证券信息
        """
        result = await self._call_actor("get_code_info", security_type=security_type)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_code_list(self, security_type: str = "EXTRA_STOCK_A") -> list[str] | None:
        """3.5.2.2 每日最新代码列表

        Args:
            security_type: 代码类型

        Returns:
            代码列表
        """
        result = await self._call_actor("get_code_list", security_type=security_type)
        return result

    async def get_calendar(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[int] | None:
        """3.5.2.7 交易日历

        Args:
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            交易日列表
        """
        kwargs: dict[str, Any] = {}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_calendar", **kwargs)
        return result

    async def get_stock_basic(self, code_list: list[str]) -> pd.DataFrame:
        """3.5.2.8 证券基础信息

        Args:
            code_list: 股票代码列表

        Returns:
            DataFrame: 证券基础信息
        """
        result = await self._call_actor("get_stock_basic", code_list=code_list)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_backward_factor(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.2.4 复权因子（后复权）

        Args:
            code_list: 代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 复权因子
        """
        result = await self._call_actor(
            "get_backward_factor",
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_adj_factor(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.2.5 复权因子（单次）

        Args:
            code_list: 代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 复权因子
        """
        result = await self._call_actor(
            "get_adj_factor",
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_hist_code_list(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
        security_type: str = "EXTRA_STOCK_A",
    ) -> pd.DataFrame:
        """3.5.2.6 历史代码列表

        Args:
            begin_date: 开始日期
            end_date: 结束日期
            security_type: 证券类型

        Returns:
            DataFrame: 历史代码列表
        """
        result = await self._call_actor(
            "get_hist_code_list",
            begin_date=begin_date,
            end_date=end_date,
            security_type=security_type,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_history_stock_status(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.2.9 历史证券信息

        Args:
            code_list: 代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 历史证券状态
        """
        result = await self._call_actor(
            "get_history_stock_status",
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_bj_code_mapping(self) -> pd.DataFrame:
        """3.5.2.10 北交所代码映射

        Returns:
            DataFrame: 北交所代码映射
        """
        result = await self._call_actor("get_bj_code_mapping")
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_future_code_list(
        self,
        exchange: str | None = None,
    ) -> list[str] | None:
        """3.5.2.3 每日最新代码（期货）

        Args:
            exchange: 交易所

        Returns:
            期货代码列表
        """
        kwargs: dict[str, Any] = {}
        if exchange is not None:
            kwargs["exchange"] = exchange

        result = await self._call_actor("get_future_code_list", **kwargs)
        return result

    # ==================== 历史行情接口 (MarketData) ====================

    async def query_snapshot(
        self,
        code_list: list[str],
        date: int,
        time_point: int | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """3.5.4.1 历史快照

        Args:
            code_list: 代码列表
            date: 日期 (YYYYMMDD)
            time_point: 时间点 (HHMMSS)

        Returns:
            字典，key为代码，value为DataFrame
        """
        kwargs: dict[str, Any] = {
            "code_list": code_list,
            "date": date,
        }
        if time_point is not None:
            kwargs["time_point"] = time_point

        result = await self._call_actor("query_snapshot", **kwargs)
        if result is None:
            return None

        # 转换结果
        return {k: pd.DataFrame(v) for k, v in result.items()}

    async def query_kline(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        period: str | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """3.5.4.2 历史K线

        Args:
            code_list: 代码列表
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            period: 周期，默认日线 ("day")

        Returns:
            字典，key为代码，value为DataFrame
        """
        kwargs: dict[str, Any] = {
            "code_list": code_list,
            "begin_date": begin_date,
            "end_date": end_date,
        }
        if period is not None:
            kwargs["period"] = period

        result = await self._call_actor("query_kline", **kwargs)
        if result is None:
            return None

        # 转换结果
        return {k: pd.DataFrame(v) for k, v in result.items()}

    # ==================== 财务数据接口 (InfoData) ====================

    async def get_balance_sheet(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        """3.5.5.1 资产负债表

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报表类型

        Returns:
            DataFrame: 资产负债表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date
        if report_type is not None:
            kwargs["report_type"] = report_type

        result = await self._call_actor("get_balance_sheet", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_cash_flow(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        """3.5.5.2 现金流量表

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报表类型

        Returns:
            DataFrame: 现金流量表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date
        if report_type is not None:
            kwargs["report_type"] = report_type

        result = await self._call_actor("get_cash_flow", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_income(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        """3.5.5.3 利润表

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期
            report_type: 报表类型

        Returns:
            DataFrame: 利润表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date
        if report_type is not None:
            kwargs["report_type"] = report_type

        result = await self._call_actor("get_income", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_profit_express(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.5.4 业绩快报

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期

        Returns:
            DataFrame: 业绩快报数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_profit_express", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_profit_notice(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.5.5 业绩预告

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期

        Returns:
            DataFrame: 业绩预告数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_profit_notice", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 股东数据接口 ====================

    async def get_share_holder(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.6.1 十大股东

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期

        Returns:
            DataFrame: 十大股东数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_share_holder", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_holder_num(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """股东人数

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期

        Returns:
            DataFrame: 股东人数数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_holder_num", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_structure(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """股本结构

        Args:
            code_list: 股票代码列表
            begin_date: 报告期开始日期
            end_date: 报告期结束日期

        Returns:
            DataFrame: 股本结构数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_equity_structure", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_pledge_freeze(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """股权质押冻结

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 股权质押冻结数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_equity_pledge_freeze", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_restricted(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """限售股解禁

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 限售股解禁数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_equity_restricted", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 资讯数据接口 ====================

    async def get_dividend(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.7.5 分红配送

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 分红配送数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_dividend", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_right_issue(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """配股

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 配股数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_right_issue", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_margin_summary(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.7.2 融资融券汇总

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 融资融券汇总数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_margin_summary", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_margin_detail(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """融资融券明细

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 融资融券明细数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_margin_detail", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.7.4 龙虎榜

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 龙虎榜数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_long_hu_bang", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_block_trading(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.7.1 大宗交易

        Args:
            code_list: 股票代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 大宗交易数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_block_trading", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 行业数据接口 ====================

    async def get_industry_daily(
        self,
        industry_code: str,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """行业日线

        Args:
            industry_code: 行业代码
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 行业日线数据
        """
        kwargs: dict[str, Any] = {"industry_code": industry_code}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_industry_daily", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_industry_weight(
        self,
        industry_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """行业权重

        Args:
            industry_code: 行业代码
            date: 日期

        Returns:
            DataFrame: 行业权重数据
        """
        kwargs: dict[str, Any] = {"industry_code": industry_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_industry_weight", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_industry_constituent(
        self,
        industry_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """行业成分股

        Args:
            industry_code: 行业代码
            date: 日期

        Returns:
            DataFrame: 行业成分股数据
        """
        kwargs: dict[str, Any] = {"industry_code": industry_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_industry_constituent", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_industry_base_info(
        self,
        industry_type: str | None = None,
    ) -> pd.DataFrame:
        """行业基础信息

        Args:
            industry_type: 行业分类类型

        Returns:
            DataFrame: 行业基础信息
        """
        kwargs: dict[str, Any] = {}
        if industry_type is not None:
            kwargs["industry_type"] = industry_type

        result = await self._call_actor("get_industry_base_info", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 特色数据接口 ====================

    async def get_option_code_list(
        self,
        underlying_code: str | None = None,
    ) -> list[str] | None:
        """期权代码列表

        Args:
            underlying_code: 标的代码

        Returns:
            期权代码列表
        """
        kwargs: dict[str, Any] = {}
        if underlying_code is not None:
            kwargs["underlying_code"] = underlying_code

        result = await self._call_actor("get_option_code_list", **kwargs)
        return result

    async def get_option_basic_info(
        self,
        code_list: list[str],
    ) -> pd.DataFrame:
        """期权基础信息

        Args:
            code_list: 期权代码列表

        Returns:
            DataFrame: 期权基础信息
        """
        result = await self._call_actor("get_option_basic_info", code_list=code_list)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_option_std_ctr_specs(
        self,
        underlying_code: str | None = None,
    ) -> pd.DataFrame:
        """期权标准合约规格

        Args:
            underlying_code: 标的代码

        Returns:
            DataFrame: 期权标准合约规格
        """
        kwargs: dict[str, Any] = {}
        if underlying_code is not None:
            kwargs["underlying_code"] = underlying_code

        result = await self._call_actor("get_option_std_ctr_specs", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_option_mon_ctr_spcon(
        self,
        underlying_code: str | None = None,
        month: str | None = None,
    ) -> pd.DataFrame:
        """期权月度合约

        Args:
            underlying_code: 标的代码
            month: 月份

        Returns:
            DataFrame: 期权月度合约
        """
        kwargs: dict[str, Any] = {}
        if underlying_code is not None:
            kwargs["underlying_code"] = underlying_code
        if month is not None:
            kwargs["month"] = month

        result = await self._call_actor("get_option_mon_ctr_spcon", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_etf_pcf(
        self,
        code_list: list[str],
        date: int | None = None,
    ) -> pd.DataFrame:
        """ETF PCF 申赎清单

        Args:
            code_list: ETF 代码列表
            date: 日期

        Returns:
            DataFrame: ETF PCF 数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_etf_pcf", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_fund_share(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """基金份额

        Args:
            code_list: 基金代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 基金份额数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_fund_share", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_fund_iopv(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """基金 IOPV

        Args:
            code_list: 基金代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 基金 IOPV 数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_fund_iopv", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_index_constituent(
        self,
        index_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """指数成分股

        Args:
            index_code: 指数代码
            date: 日期

        Returns:
            DataFrame: 指数成分股数据
        """
        kwargs: dict[str, Any] = {"index_code": index_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_index_constituent", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_index_weight(
        self,
        index_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """指数权重

        Args:
            index_code: 指数代码
            date: 日期

        Returns:
            DataFrame: 指数权重数据
        """
        kwargs: dict[str, Any] = {"index_code": index_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_index_weight", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_treasury_yield(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """国债收益率

        Args:
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 国债收益率数据
        """
        kwargs: dict[str, Any] = {}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_treasury_yield", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 生命周期管理 ====================

    async def shutdown(self) -> None:
        """关闭 Adapter"""
        self._actor_available = False
        self._initialized = False
        logger.info("[DaskAdapter] 已关闭")


__all__ = ["AmazingDataDaskAdapter"]
