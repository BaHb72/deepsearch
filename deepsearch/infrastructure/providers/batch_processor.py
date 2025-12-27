"""
批量请求处理器

优化多个相同类型的请求，减少API调用次数
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, DefaultDict, Dict, List, Optional, Set, Tuple

from loguru import logger

from deepsearch.infrastructure.providers.api_config import APIConfigManager


@dataclass
class BatchRequest:
    """批量请求"""

    request_id: str
    api_name: str
    params: Dict[str, Any]
    timestamp: float
    future: asyncio.Future[Any]


class BatchProcessor:
    """
    批量请求处理器

    将多个单独的请求合并为批量请求，提高效率
    """

    def __init__(
        self,
        batch_timeout: float = 0.2,  # 批量超时（秒）
        max_batch_size: int = 20,  # 最大批量大小
        enabled: bool = True,  # 是否启用批量处理
    ):
        """
        初始化批量处理器

        Args:
            batch_timeout: 批量收集超时时间
            max_batch_size: 最大批量大小
            enabled: 是否启用批量处理
        """
        self.batch_timeout = batch_timeout
        self.max_batch_size = max_batch_size
        self.enabled = enabled

        # 待处理的批量请求 {api_name: [BatchRequest]}
        self.pending_batches: DefaultDict[str, List[BatchRequest]] = defaultdict(list)

        # 批量处理任务
        self.batch_tasks: Dict[str, asyncio.Task[Any]] = {}

        # 锁
        self.lock = asyncio.Lock()

        # 统计
        self.stats: Dict[str, Any] = {
            "total_requests": 0,
            "batched_requests": 0,
            "batch_executions": 0,
            "time_saved": 0.0,
        }

    async def add_request(self, api_name: str, params: Dict[str, Any], executor: Callable) -> Any:
        """
        添加请求到批量队列

        Args:
            api_name: API名称
            params: 请求参数
            executor: 执行函数

        Returns:
            请求结果
        """
        self.stats["total_requests"] += 1

        # 检查是否支持批量
        if not self.enabled or not APIConfigManager.supports_batch(api_name):
            # 不支持批量，直接执行
            return await executor(api_name, params)

        # 创建批量请求
        request_id = f"{api_name}_{time.time()}_{id(params)}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        batch_request = BatchRequest(
            request_id=request_id,
            api_name=api_name,
            params=params,
            timestamp=time.time(),
            future=future,
        )

        async with self.lock:
            # 添加到待处理队列
            self.pending_batches[api_name].append(batch_request)

            # 检查是否需要触发批量处理
            batch_size = APIConfigManager.get_batch_size(api_name) or self.max_batch_size

            if len(self.pending_batches[api_name]) >= batch_size:
                # 达到批量大小，立即处理
                await self._process_batch(api_name, executor)
            elif api_name not in self.batch_tasks:
                # 创建延迟处理任务
                task = asyncio.create_task(self._delayed_process(api_name, executor))
                self.batch_tasks[api_name] = task

        # 等待结果
        return await future

    async def _delayed_process(self, api_name: str, executor: Callable):
        """
        延迟批量处理

        Args:
            api_name: API名称
            executor: 执行函数
        """
        try:
            # 等待超时或更多请求
            await asyncio.sleep(self.batch_timeout)

            async with self.lock:
                await self._process_batch(api_name, executor)

                # 清理任务
                if api_name in self.batch_tasks:
                    del self.batch_tasks[api_name]

        except Exception as e:
            logger.error(f"批量处理失败: {e}")

    async def _process_batch(
        self,
        api_name: str,
        executor: Callable[[str, Dict[str, Any]], Awaitable[Any]],
    ) -> None:
        """
        处理批量请求

        Args:
            api_name: API名称
            executor: 执行函数
        """
        # 获取待处理的请求
        batch = self.pending_batches[api_name]
        if not batch:
            return

        # 清空待处理队列
        self.pending_batches[api_name] = []

        self.stats["batch_executions"] += 1
        self.stats["batched_requests"] += len(batch)

        logger.info(f"批量处理 {len(batch)} 个 {api_name} 请求")

        try:
            # 根据API类型决定批量策略
            if self._can_merge_to_single(api_name):
                # 可以合并为单个请求
                await self._process_merged_batch(api_name, batch, executor)
            else:
                # 并行执行多个请求
                await self._process_parallel_batch(api_name, batch, executor)

        except Exception as e:
            logger.error(f"批量处理失败: {e}")
            # 设置所有请求为失败
            for request in batch:
                if not request.future.done():
                    request.future.set_exception(e)

    def _can_merge_to_single(self, api_name: str) -> bool:
        """
        判断是否可以合并为单个请求

        某些API（如获取全市场数据）可以一次获取所有数据
        """
        mergeable_apis = {
            "stock_zh_a_spot_em",  # 全市场实时数据
            "stock_info_a_code_name",  # 股票列表
            "stock_zh_index_spot_em",  # 指数实时数据
        }

        return api_name in mergeable_apis

    async def _process_merged_batch(
        self, api_name: str, batch: List[BatchRequest], executor: Callable
    ):
        """
        合并处理批量请求

        Args:
            api_name: API名称
            batch: 批量请求列表
            executor: 执行函数
        """
        start_time = time.time()

        # 提取所有需要的股票代码
        all_symbols = set()
        for request in batch:
            if "symbol" in request.params:
                all_symbols.add(request.params["symbol"])
            elif "symbols" in request.params:
                all_symbols.update(request.params["symbols"])

        try:
            # 执行单个全量请求
            if api_name == "stock_zh_a_spot_em":
                # 获取全市场数据
                result = await executor(api_name, {})

                # 如果需要筛选特定股票
                if all_symbols:
                    # 筛选需要的股票
                    filtered_data = self._filter_market_data(result, all_symbols)

                    # 分发结果给各个请求
                    for request in batch:
                        symbol = request.params.get("symbol")
                        if symbol:
                            stock_data = filtered_data.get(symbol, {})
                            request.future.set_result(stock_data)
                        else:
                            request.future.set_result(result)
                else:
                    # 所有请求都获取全量数据
                    for request in batch:
                        request.future.set_result(result)
            else:
                # 其他可合并的API
                result = await executor(api_name, {})
                for request in batch:
                    request.future.set_result(result)

            # 统计时间节省
            time_saved = (len(batch) - 1) * (time.time() - start_time)
            self.stats["time_saved"] += time_saved

            logger.info(f"批量合并处理成功，节省时间: {time_saved:.2f}秒")

        except Exception as e:
            logger.error(f"批量合并处理失败: {e}")
            for request in batch:
                if not request.future.done():
                    request.future.set_exception(e)

    async def _process_parallel_batch(
        self,
        api_name: str,
        batch: List[BatchRequest],
        executor: Callable[[str, Dict[str, Any]], Awaitable[Any]],
    ) -> None:
        """
        并行处理批量请求

        Args:
            api_name: API名称
            batch: 批量请求列表
            executor: 执行函数
        """
        # 创建并行任务
        pending: List[Tuple[BatchRequest, Awaitable[Any]]] = []
        for request in batch:
            pending.append((request, executor(api_name, request.params)))

        # 并行执行
        results = await asyncio.gather(*(task for _, task in pending), return_exceptions=True)

        # 分发结果
        for (request, _), result in zip(pending, results):
            if isinstance(result, Exception):
                request.future.set_exception(result)
            else:
                request.future.set_result(result)

        logger.info(f"并行批量处理完成 {len(batch)} 个请求")

    def _filter_market_data(self, market_data: Dict[str, Any], symbols: Set[str]) -> Dict[str, Any]:
        """
        从全市场数据中筛选特定股票

        Args:
            market_data: 全市场数据
            symbols: 需要的股票代码集合

        Returns:
            筛选后的数据
        """
        filtered = {}

        if "data" in market_data and isinstance(market_data["data"], list):
            for item in market_data["data"]:
                code = item.get("代码") or item.get("symbol")
                if code and code in symbols:
                    filtered[code] = item

        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "batch_ratio": self.stats["batched_requests"] / max(self.stats["total_requests"], 1),
            "avg_batch_size": self.stats["batched_requests"]
            / max(self.stats["batch_executions"], 1),
            "pending_batches": sum(len(b) for b in self.pending_batches.values()),
        }

    async def flush(self, api_name: Optional[str] = None):
        """
        立即处理所有待处理的批量请求

        Args:
            api_name: 指定API，None表示处理所有
        """
        async with self.lock:
            if api_name:
                # 处理指定API的批量
                if api_name in self.batch_tasks:
                    self.batch_tasks[api_name].cancel()
                    del self.batch_tasks[api_name]

                # 这里需要executor，暂时跳过
                logger.warning(f"刷新批量请求需要executor: {api_name}")
            else:
                # 取消所有延迟任务
                for task in self.batch_tasks.values():
                    task.cancel()
                self.batch_tasks.clear()

                logger.info("已取消所有批量处理任务")
