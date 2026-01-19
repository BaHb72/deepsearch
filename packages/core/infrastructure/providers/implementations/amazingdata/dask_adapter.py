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
import json
import uuid
from typing import TYPE_CHECKING, Any

import pandas as pd
from core.infrastructure.providers.interfaces.base import DataProviderError
from loguru import logger

if TYPE_CHECKING:
    from distributed import Client, Future
    from redis.asyncio import Redis as AsyncRedis

# Redis key 前缀，用于存储 Dask 调用结果
_REDIS_RESULT_PREFIX = "dask_result:"


def _check_worker_has_actor(dask_worker: Any) -> bool:
    """检查 Worker 上是否有 amazingdata Actor（模块级函数，可被 pickle 序列化）"""
    actors = getattr(dask_worker, "actors", {})
    return "amazingdata" in actors


def _ping_amazingdata_actor() -> str:
    """在 Worker 上执行 ping 测试，检查 Actor 是否可用"""
    from distributed import get_worker

    worker = get_worker()
    actors = getattr(worker, "actors", {})
    if "amazingdata" in actors:
        return "pong"
    return "no_actor"


class AmazingDataDaskAdapter:
    """AmazingData Dask Client Adapter

    实现 DataProvider 接口，通过 Dask 分布式调用远程 Actor。

    使用 Redis 作为结果传递通道，彻底绕过 Dask Future 的返回机制，
    解决 Dask tornado IOLoop 与 FastAPI asyncio 的事件循环冲突问题。

    Attributes:
        name: 数据源名称
        _client: Dask distributed Client 实例
        _redis: Redis 异步客户端（用于获取调用结果）
        _timeout: 远程调用超时时间（秒）
        _retry_count: 失败重试次数
        _windows_worker: 缓存的 Windows Worker 地址
        _actor_available: Actor 是否可用
    """

    name = "amazingdata"

    def __init__(
        self,
        dask_client: "Client",
        redis_client: "AsyncRedis | None" = None,
        timeout: float = 45.0,
        first_call_timeout: float = 90.0,
        retry_count: int = 3,
    ):
        """初始化 Dask Adapter

        Args:
            dask_client: Dask distributed Client 实例
            redis_client: Redis 异步客户端（用于获取结果）
            timeout: 后续调用超时时间（秒），纯 SDK 执行
            first_call_timeout: 首次调用超时时间（秒），包含登录流程
            retry_count: 失败重试次数
        """
        self._client = dask_client
        self._redis = redis_client
        self._timeout = timeout
        self._first_call_timeout = first_call_timeout
        self._retry_count = retry_count

        # 缓存 Windows Worker 地址
        self._windows_worker: str | None = None
        self._actor_available = False
        self._initialized = False
        self._first_call_done = False  # 跟踪是否完成首次调用

        # Future 生命周期管理（防止内存泄漏）
        self._pending_futures: dict[str, "Future"] = {}

        logger.info(
            "[AmazingDataDaskAdapter] 初始化 | scheduler={} | redis={}",
            dask_client.scheduler.address if dask_client.scheduler else "unknown",
            "connected" if redis_client else "none",
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
                logger.error("[AmazingData/Dask] 未找到 Windows Worker (WIN:1)")
                return False

            # 验证 Actor 是否已注册
            self._actor_available = await self._check_actor_available()
            if not self._actor_available:
                logger.error(
                    "[AmazingData/Dask] Worker {} 上未找到 amazingdata Actor",
                    self._windows_worker,
                )
                return False

            self._initialized = True
            logger.info(
                "[AmazingData/Dask] 初始化成功 | worker={} | actor=available",
                self._windows_worker,
            )
            return True

        except Exception as e:
            logger.error("[AmazingData/Dask] 初始化失败: {}", e, exc_info=True)
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
                        "[AmazingData/Dask] 找到 Windows Worker | addr={} | resources={}",
                        worker_addr,
                        resources,
                    )
                    return worker_addr

            logger.warning("[AmazingData/Dask] 未找到 Windows Worker (WIN:1)")
            return None

        except Exception as e:
            logger.error("[AmazingData/Dask] 查找 Worker 失败: {}", e)
            return None

    async def _check_actor_available(self) -> bool:
        """检查 Windows Worker 是否可用

        只验证 Windows Worker 存在且有 WIN 资源，Actor 的可用性在实际调用时验证。
        这是因为 Actor 检查需要复杂的序列化，而 Dask 服务发现已经告诉我们 Worker 信息。

        Returns:
            Windows Worker 是否可用
        """
        # 已经在 _find_windows_worker 中验证了 Worker 存在
        # Actor 的注册日志显示已成功，直接信任
        if self._windows_worker:
            logger.info(
                "[AmazingData/Dask] Windows Worker 可用: {}，假定 Actor 已注册",
                self._windows_worker,
            )
            return True
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

        使用 Redis 作为结果传递通道，彻底绕过 Dask Future 的返回机制。

        实现原理：
        1. 生成唯一的 task_id
        2. 提交任务到 Worker（fire-and-forget，不等待 future.result()）
        3. 轮询 Redis 获取结果（Worker 在完成后将结果存入 Redis）

        为什么需要这样做：
        - Dask Client 内部使用 tornado IOLoop
        - FastAPI 使用 asyncio 事件循环
        - 两者在同一进程中运行时存在根本性冲突
        - future.result() 无法正常返回，即使 Worker 已成功完成任务
        - 尝试过线程隔离、进程隔离，都无法解决
        - Redis 是一个简单可靠的消息传递系统，可以绕过这个问题

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

        if not self._redis:
            raise DataProviderError("Redis 客户端未配置，无法获取调用结果")

        # 生成唯一任务ID（包含方法名和短UUID，用于 Redis 键和 Dask Dashboard）
        # 格式: {method}:{short_uuid}，例如 query_kline:a1b2c3d4
        task_id = f"{method}:{uuid.uuid4().hex[:8]}"

        # 根据是否首次调用选择超时时间
        current_timeout = self._first_call_timeout if not self._first_call_done else self._timeout

        try:
            worker_addr = self._windows_worker

            logger.info(
                "[AmazingData/Dask] 提交任务 | method={} | task_id={} | worker={} | timeout={}s{}",
                method,
                task_id,
                worker_addr,
                current_timeout,
                " (首次调用，含登录)" if not self._first_call_done else "",
            )

            # 定义远程调用函数（命名体现业务含义，便于在 Dask Dashboard 中识别）
            def _execute_amazingdata_method(
                task_id_inner: str, method_inner: str, kwargs_inner: dict
            ) -> None:
                """在 Worker 上执行 AmazingData SDK 方法

                注意：这里使用 fire-and-forget 模式，不返回结果。
                结果通过 Redis 传递，由 call_sync 内部处理。
                """
                from distributed import get_worker

                worker = get_worker()
                actor = getattr(worker, "actors", {}).get("amazingdata")
                if actor is None:
                    raise RuntimeError("amazingdata Actor 未注册")

                # 调用 Actor，传递 task_id 让它将结果存入 Redis
                actor.call_sync(method_inner, task_id=task_id_inner, **kwargs_inner)

            # 提交任务并追踪 Future（防止内存泄漏）
            # key 参数指定任务名称，便于在 Dask Dashboard 中识别
            # 格式: amazingdata:{method}:{short_id}
            # 例如: amazingdata:query_kline:a1b2c3d4
            future = self._client.submit(
                _execute_amazingdata_method,
                task_id,
                method,
                kwargs,
                key=f"amazingdata:{task_id}",
                workers=[worker_addr],
                resources={"WIN": 1},
                pure=False,
            )
            self._pending_futures[task_id] = future

            # 轮询 Redis 获取结果
            redis_key = f"{_REDIS_RESULT_PREFIX}{task_id}"
            poll_interval = 0.1  # 100ms 轮询间隔
            max_polls = int(current_timeout / poll_interval)

            try:
                for i in range(max_polls):
                    result_data = await self._redis.get(redis_key)
                    if result_data:
                        # 删除 Redis key
                        await self._redis.delete(redis_key)

                        # 解析结果
                        data = json.loads(result_data)
                        if data["status"] == "success":
                            # 首次调用成功，后续使用普通超时
                            if not self._first_call_done:
                                self._first_call_done = True
                                logger.info(
                                    "[AmazingData/Dask] 首次调用成功 | method={} | task_id={} | 后续超时={}s",
                                    method,
                                    task_id,
                                    self._timeout,
                                )
                            else:
                                logger.info(
                                    "[AmazingData/Dask] 调用成功 | method={} | task_id={}",
                                    method,
                                    task_id,
                                )
                            return data["result"]
                        else:
                            error_msg = data.get("error", "Unknown error")
                            logger.error(
                                "[AmazingData/Dask] Worker 返回错误 | method={} | error={}",
                                method,
                                error_msg,
                            )
                            raise DataProviderError(f"Actor 调用失败: {error_msg}")

                    await asyncio.sleep(poll_interval)

                    # 每 10 秒记录一次等待日志
                    if (i + 1) % 100 == 0:
                        elapsed = (i + 1) * poll_interval
                        logger.debug(
                            "[AmazingData/Dask] 等待结果 | method={} | elapsed={:.1f}s",
                            method,
                            elapsed,
                        )

                # 超时 - 删除 Redis key 防止泄漏
                logger.error(
                    "[AmazingData/Dask] 调用超时 | method={} | timeout={}s{}",
                    method,
                    current_timeout,
                    " (首次调用)" if not self._first_call_done else "",
                )

                # 超时时也要删除 Redis key（防止泄漏）
                try:
                    await self._redis.delete(redis_key)
                except Exception as e:
                    logger.warning(
                        "[AmazingData/Dask] 删除超时 Redis key 失败 | key={} | error={}",
                        redis_key,
                        e,
                    )

                if retry < self._retry_count:
                    logger.info("[AmazingData/Dask] 重试 {}/{}", retry + 1, self._retry_count)
                    return await self._call_actor(method, retry=retry + 1, **kwargs)

                raise DataProviderError(f"Actor 调用超时: {method}")

            finally:
                # 释放 Future 引用（防止内存泄漏）
                self._release_future(task_id)
                # 清理其他已完成的 Future（定期回收）
                self._cleanup_completed_futures()

        except DataProviderError:
            raise
        except Exception as e:
            logger.error(
                "[AmazingData/Dask] 调用失败 | method={} | error={}",
                method,
                str(e),
                exc_info=True,
            )
            if retry < self._retry_count:
                logger.info("[AmazingData/Dask] 重试 {}/{}", retry + 1, self._retry_count)
                await asyncio.sleep(1)  # 延迟重试
                return await self._call_actor(method, retry=retry + 1, **kwargs)
            raise DataProviderError(f"Actor 调用失败: {method} - {e}")

    def _release_future(self, task_id: str) -> None:
        """释放 Future 引用，防止内存泄漏

        Dask Future 对象持有对结果的引用，如果不释放会导致内存持续增长。
        此方法从追踪字典中移除 Future，并尝试调用 release() 方法。

        Args:
            task_id: 任务 ID
        """
        future = self._pending_futures.pop(task_id, None)
        if future is not None:
            try:
                # 尝试释放 Future（如果 Dask 支持）
                if hasattr(future, "release"):
                    future.release()
                elif hasattr(future, "cancel"):
                    # 如果任务还在运行，取消它
                    if not future.done():
                        future.cancel()
            except Exception as e:
                logger.debug(
                    "[AmazingData/Dask] 释放 Future 时发生异常 | task_id={} | error={}",
                    task_id,
                    e,
                )

    def _cleanup_completed_futures(self) -> int:
        """清理已完成的 Future 对象，防止内存泄漏

        遍历 _pending_futures 字典，找出所有已完成（done）的 Future 并释放。
        此方法应在每次 _call_actor 调用后执行，确保及时回收内存。

        Returns:
            清理的 Future 数量
        """
        if not self._pending_futures:
            return 0

        # 找出所有已完成的 Future
        completed_task_ids = [
            task_id for task_id, future in self._pending_futures.items() if future.done()
        ]

        # 释放已完成的 Future
        for task_id in completed_task_ids:
            self._release_future(task_id)

        if completed_task_ids:
            logger.debug(
                "[AmazingData/Dask] 已清理 {} 个已完成的 Future | 剩余={}",
                len(completed_task_ids),
                len(self._pending_futures),
            )

        return len(completed_task_ids)

    async def cleanup_pending_futures(self) -> int:
        """清理所有挂起的 Future

        用于关闭 Adapter 时清理资源。

        Returns:
            清理的 Future 数量
        """
        count = len(self._pending_futures)
        task_ids = list(self._pending_futures.keys())
        for task_id in task_ids:
            self._release_future(task_id)
        if count > 0:
            logger.info("[AmazingData/Dask] 已清理 {} 个挂起的 Future", count)
        return count

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

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取股票列表（领域层接口）

        实现 StockListCapable 协议，供 DataProxy 使用。
        将 market/board 参数转换为 security_type 后调用 SDK。

        Args:
            market: 市场过滤 ("SH", "SZ", "BJ")，None 表示全部
            board: 板块过滤 ("主板", "创业板", "科创板")，None 表示全部

        Returns:
            股票信息列表
        """
        # 默认获取沪深北A股
        security_type = "EXTRA_STOCK_A"

        # Actor 会将 get_stock_list 映射到 get_code_list
        result = await self._call_actor("get_code_list", security_type=security_type)

        if result is None:
            return []

        # 转换为领域层期望的格式 (list[dict])
        stocks = []
        for code in result:
            if not isinstance(code, str):
                continue

            # 按市场过滤
            if market:
                if market == "SH" and not code.endswith(".SH"):
                    continue
                if market == "SZ" and not code.endswith(".SZ"):
                    continue
                if market == "BJ" and not code.endswith(".BJ"):
                    continue

            stocks.append({"symbol": code, "name": ""})

        return stocks

    async def get_calendar_range(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[int] | None:
        """3.5.2.7 交易日历（SDK 原生 API）

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

    async def get_calendar(
        self,
        market: str = "SH",
        data_type: str = "int",
    ) -> list[int]:
        """获取交易日历（领域层接口）

        实现 CalendarCapable 协议，供 DataProxy 使用。

        Args:
            market: 市场代码 ("SH", "SZ", "BJ")，A股市场统一日历，此参数仅为接口兼容
            data_type: 返回数据类型 ("int" 或 "str")，兼容 factory 调用

        Returns:
            交易日列表 (格式: 20250102)
        """
        # SDK 的 get_calendar() 不接受 market 参数，A股市场统一使用同一日历
        # 这里不传递任何参数给 Actor，由 Actor 内部调用 SDK 的无参版本
        result = await self._call_actor("get_calendar")
        if result is None:
            return []
        return [int(d) for d in result]

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
        global _DASK_PROCESS_POOL

        self._actor_available = False
        self._initialized = False

        # 清理挂起的 Future（防止内存泄漏）
        await self.cleanup_pending_futures()

        # 关闭进程池
        if _DASK_PROCESS_POOL is not None:
            try:
                _DASK_PROCESS_POOL.shutdown(wait=False)
                _DASK_PROCESS_POOL = None
                logger.info("[AmazingData/Dask] 进程池已关闭")
            except Exception as e:
                logger.warning("[AmazingData/Dask] 关闭进程池时出错: {}", e)

        logger.info("[AmazingData/Dask] 已关闭")


__all__ = ["AmazingDataDaskAdapter"]
