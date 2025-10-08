"""
请求优化器
实现请求批处理、并发控制和智能调度
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger


class RequestPriority(Enum):
    """请求优先级"""

    URGENT = 0  # 紧急请求（实时数据）
    HIGH = 1  # 高优先级（用户交互）
    NORMAL = 2  # 正常优先级
    LOW = 3  # 低优先级（后台任务）
    BATCH = 4  # 批量请求（可延迟）


@dataclass
class RequestTask:
    """请求任务"""

    api_name: str
    params: Dict[str, Any]
    priority: RequestPriority = RequestPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    future: asyncio.Future = field(default_factory=asyncio.Future)
    retry_count: int = 0
    request_id: str = field(default="")

    def __post_init__(self):
        if not self.request_id:
            # 生成唯一请求ID
            content = f"{self.api_name}:{json.dumps(self.params, sort_keys=True)}"
            self.request_id = hashlib.md5(content.encode()).hexdigest()[:8]

    def __lt__(self, other):
        """比较优先级（用于优先队列）"""
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.timestamp < other.timestamp


class RequestOptimizer:
    """
    请求优化器
    - 请求批处理：将多个相似请求合并
    - 并发控制：限制同时执行的请求数
    - 智能调度：基于优先级和时间窗口
    - 去重缓存：避免重复请求
    """

    def __init__(self, max_concurrent: int = 10, batch_window: float = 0.1):
        """
        初始化请求优化器

        Args:
            max_concurrent: 最大并发请求数
            batch_window: 批处理时间窗口（秒）
        """
        self.max_concurrent = max_concurrent
        self.batch_window = batch_window

        # 请求队列（按优先级）
        self.request_queue: List[RequestTask] = []
        self.queue_lock = asyncio.Lock()

        # 执行中的请求
        self.executing: Dict[str, RequestTask] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # 批处理缓冲区
        self.batch_buffer: Dict[str, List[RequestTask]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}

        # 请求去重缓存（request_id -> result）
        self.dedup_cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = 60  # 缓存TTL（秒）

        # 统计信息
        self.stats: Dict[str, float | int] = {
            "total_requests": 0,
            "batched_requests": 0,
            "cache_hits": 0,
            "concurrent_peak": 0,
            "failed_requests": 0,
            "avg_wait_time": 0.0,
            "avg_exec_time": 0.0,
        }

        # 请求执行器（由外部设置）
        self.executor: Optional[Callable] = None

        # 后台清理任务
        self.cleanup_task = None
        self.running = False

    async def start(self):
        """启动优化器"""
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_cache())
        logger.info(
            f"请求优化器已启动: 最大并发={self.max_concurrent}, 批处理窗口={self.batch_window}秒"
        )

    async def stop(self):
        """停止优化器"""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # 取消所有批处理定时器
        for timer in self.batch_timers.values():
            timer.cancel()

        logger.info(f"请求优化器已停止. 统计: {self.stats}")

    async def submit(
        self,
        api_name: str,
        params: Dict[str, Any],
        priority: RequestPriority = RequestPriority.NORMAL,
        use_cache: bool = True,
    ) -> Any:
        """
        提交请求

        Args:
            api_name: API名称
            params: 请求参数
            priority: 优先级
            use_cache: 是否使用去重缓存

        Returns:
            API响应结果
        """
        self.stats["total_requests"] += 1

        # 创建请求任务
        task = RequestTask(api_name=api_name, params=params, priority=priority)

        # 检查去重缓存
        if use_cache and task.request_id in self.dedup_cache:
            result, cache_time = self.dedup_cache[task.request_id]
            if time.time() - cache_time < self.cache_ttl:
                self.stats["cache_hits"] += 1
                logger.debug(f"请求命中缓存: {api_name} [{task.request_id}]")
                return result
            else:
                # 缓存过期，删除
                del self.dedup_cache[task.request_id]

        # 根据优先级决定处理策略
        if priority == RequestPriority.URGENT:
            # 紧急请求直接执行
            return await self._execute_immediate(task)
        elif priority == RequestPriority.BATCH:
            # 批量请求进入批处理
            return await self._add_to_batch(task)
        else:
            # 普通请求进入队列
            return await self._add_to_queue(task)

    async def _execute_immediate(self, task: RequestTask) -> Any:
        """立即执行请求（用于紧急请求）"""
        async with self.semaphore:
            return await self._execute_task(task)

    async def _add_to_queue(self, task: RequestTask) -> Any:
        """添加到优先级队列"""
        async with self.queue_lock:
            # 插入到合适位置（保持优先级顺序）
            inserted = False
            for i, existing in enumerate(self.request_queue):
                if task < existing:
                    self.request_queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self.request_queue.append(task)

        # 触发处理
        asyncio.create_task(self._process_queue())

        # 等待结果
        return await task.future

    async def _add_to_batch(self, task: RequestTask) -> Any:
        """添加到批处理缓冲区"""
        api_name = task.api_name

        # 添加到缓冲区
        self.batch_buffer[api_name].append(task)
        self.stats["batched_requests"] += 1

        # 如果没有定时器，创建一个
        if api_name not in self.batch_timers:
            self.batch_timers[api_name] = asyncio.create_task(self._batch_timer(api_name))

        # 等待结果
        return await task.future

    async def _batch_timer(self, api_name: str):
        """批处理定时器"""
        await asyncio.sleep(self.batch_window)

        # 时间到，执行批处理
        if api_name in self.batch_buffer:
            tasks = self.batch_buffer.pop(api_name)
            del self.batch_timers[api_name]

            if tasks:
                await self._execute_batch(api_name, tasks)

    async def _execute_batch(self, api_name: str, tasks: List[RequestTask]):
        """执行批处理请求"""
        if not tasks:
            return

        logger.debug(f"执行批处理: {api_name}, {len(tasks)}个请求")

        # 合并参数（这里需要根据具体API定制）
        merged_params = self._merge_params(api_name, [t.params for t in tasks])

        try:
            # 执行合并后的请求
            async with self.semaphore:
                if self.executor:
                    result = await self.executor(api_name, merged_params)
                else:
                    raise RuntimeError("未设置请求执行器")

            # 分发结果
            self._distribute_batch_results(tasks, result)

        except Exception as e:
            # 批处理失败，回退到单独执行
            logger.warning(f"批处理失败，回退到单独执行: {e}")
            for task in tasks:
                asyncio.create_task(self._execute_immediate(task))

    async def _process_queue(self):
        """处理请求队列"""
        while self.request_queue:
            # 检查并发限制
            if len(self.executing) >= self.max_concurrent:
                await asyncio.sleep(0.01)
                continue

            async with self.queue_lock:
                if not self.request_queue:
                    break
                task = self.request_queue.pop(0)

            # 异步执行
            asyncio.create_task(self._execute_with_semaphore(task))

        # 更新峰值并发数
        current_concurrent = len(self.executing)
        if current_concurrent > self.stats["concurrent_peak"]:
            self.stats["concurrent_peak"] = current_concurrent

    async def _execute_with_semaphore(self, task: RequestTask):
        """使用信号量控制的执行"""
        async with self.semaphore:
            await self._execute_task(task)

    async def _execute_task(self, task: RequestTask):
        """执行单个任务"""
        start_time = time.time()
        self.executing[task.request_id] = task

        try:
            if self.executor:
                result = await self.executor(task.api_name, task.params)

                # 更新缓存
                self.dedup_cache[task.request_id] = (result, time.time())

                # 设置结果
                if not task.future.done():
                    task.future.set_result(result)

                # 更新统计
                exec_time = time.time() - start_time
                self.stats["avg_exec_time"] = self.stats["avg_exec_time"] * 0.9 + exec_time * 0.1

            else:
                raise RuntimeError("未设置请求执行器")

        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"执行请求失败 {task.api_name}: {e}")
            if not task.future.done():
                task.future.set_exception(e)

        finally:
            if task.request_id in self.executing:
                del self.executing[task.request_id]

    def _merge_params(self, api_name: str, params_list: List[Dict]) -> Dict:
        """
        合并请求参数
        根据不同API的特点实现智能参数合并
        """
        if not params_list:
            return {}

        # 获取第一个参数作为基础
        base_params = params_list[0].copy()

        # 1. 股票代码列表合并
        if any(key in api_name.lower() for key in ["stock", "realtime", "quote", "kline"]):
            # 处理代码参数（codes, symbol, code等）
            code_keys = ["codes", "code", "symbol", "stock_code", "ts_code"]
            for key in code_keys:
                if key in base_params:
                    merged_codes = set()
                    for params in params_list:
                        if key in params:
                            codes = params[key]
                            if isinstance(codes, list):
                                merged_codes.update(codes)
                            elif isinstance(codes, str):
                                # 处理逗号分隔的字符串
                                if "," in codes:
                                    merged_codes.update(codes.split(","))
                                else:
                                    merged_codes.add(codes)

                    # 转换回适当的格式
                    if isinstance(params_list[0][key], list):
                        base_params[key] = list(merged_codes)
                    else:
                        base_params[key] = ",".join(sorted(merged_codes))
                    break

        # 2. 日期范围合并（取最大范围）
        date_keys = {
            "start": ["start_date", "start_time", "begin_date", "from_date"],
            "end": ["end_date", "end_time", "finish_date", "to_date"],
        }

        for date_type, keys in date_keys.items():
            for key in keys:
                if key in base_params:
                    date_values = [params.get(key) for params in params_list]
                    dates: List[str] = [str(value) for value in date_values if value]
                    if dates:
                        if date_type == "start":
                            # 取最早的开始日期
                            base_params[key] = min(dates)
                        else:
                            # 取最晚的结束日期
                            base_params[key] = max(dates)

        # 3. 指标列表合并
        if "indicator" in api_name.lower() or "factor" in api_name.lower():
            indicator_keys = ["indicators", "fields", "metrics", "factors"]
            for key in indicator_keys:
                if key in base_params:
                    merged_indicators = set()
                    for params in params_list:
                        if key in params:
                            indicators = params[key]
                            if isinstance(indicators, list):
                                merged_indicators.update(indicators)
                            elif isinstance(indicators, str):
                                if "," in indicators:
                                    merged_indicators.update(indicators.split(","))
                                else:
                                    merged_indicators.add(indicators)

                    if isinstance(params_list[0][key], list):
                        base_params[key] = list(merged_indicators)
                    else:
                        base_params[key] = ",".join(sorted(merged_indicators))

        # 4. 分页参数处理（合并为批量请求）
        if "limit" in base_params or "page_size" in base_params:
            # 汇总所有请求的数量需求
            total_limit = 0
            limit_keys = ["limit", "page_size", "count", "num"]
            for key in limit_keys:
                if key in base_params:
                    total_limit = sum(p.get(key, 0) for p in params_list)
                    if total_limit > 0:
                        base_params[key] = min(total_limit, 5000)  # 设置上限
                    break

        # 5. 市场参数合并
        if "market" in base_params:
            markets = set()
            for params in params_list:
                if "market" in params:
                    market = params["market"]
                    if isinstance(market, list):
                        markets.update(market)
                    else:
                        markets.add(market)

            if len(markets) > 1:
                # 多个市场，可能需要分别请求
                base_params["market"] = list(markets)
            elif markets:
                base_params["market"] = markets.pop()

        # 6. 周期参数统一
        period_keys = ["period", "freq", "kline_type", "interval"]
        for key in period_keys:
            if key in base_params:
                # 取最小的周期（获取更详细的数据）
                periods = [p.get(key) for p in params_list if p.get(key)]
                if periods:
                    # 周期优先级：1min < 5min < 15min < 30min < 60min < daily < weekly < monthly
                    period_priority = {
                        "1": 1,
                        "1min": 1,
                        "1分钟": 1,
                        "5": 2,
                        "5min": 2,
                        "5分钟": 2,
                        "15": 3,
                        "15min": 3,
                        "15分钟": 3,
                        "30": 4,
                        "30min": 4,
                        "30分钟": 4,
                        "60": 5,
                        "60min": 5,
                        "60分钟": 5,
                        "daily": 6,
                        "day": 6,
                        "日线": 6,
                        "weekly": 7,
                        "week": 7,
                        "周线": 7,
                        "monthly": 8,
                        "month": 8,
                        "月线": 8,
                    }

                    sorted_periods = sorted(
                        periods, key=lambda x: period_priority.get(str(x).lower(), 99)
                    )
                    base_params[key] = sorted_periods[0]

        return base_params

    def _distribute_batch_results(self, tasks: List[RequestTask], result: Any):
        """
        分发批处理结果
        根据不同的数据结构和请求参数智能分发结果
        """
        if not tasks:
            return

        # 如果结果为空或错误，所有任务都获得相同结果
        if result is None or isinstance(result, Exception):
            for task in tasks:
                if not task.future.done():
                    if isinstance(result, Exception):
                        task.future.set_exception(result)
                    else:
                        task.future.set_result(result)
            return

        # 根据结果类型进行智能分发
        try:
            # 1. DataFrame类型结果
            if hasattr(result, "shape") and hasattr(result, "loc"):  # pandas DataFrame
                self._distribute_dataframe_results(tasks, result)

            # 2. 字典类型结果
            elif isinstance(result, dict):
                self._distribute_dict_results(tasks, result)

            # 3. 列表类型结果
            elif isinstance(result, list):
                self._distribute_list_results(tasks, result)

            # 4. 其他类型，简单分发
            else:
                for task in tasks:
                    if not task.future.done():
                        task.future.set_result(result)

        except Exception as e:
            logger.error(f"分发批处理结果失败: {e}")
            # 分发失败时，所有任务获得原始结果
            for task in tasks:
                if not task.future.done():
                    task.future.set_result(result)

    def _distribute_dataframe_results(self, tasks: List[RequestTask], df):
        """分发DataFrame类型的结果"""
        # 检查是否有代码列
        code_columns = ["code", "symbol", "stock_code", "ts_code", "代码", "股票代码"]
        code_col = None
        for col in code_columns:
            if col in df.columns:
                code_col = col
                break

        if code_col:
            # 按股票代码分发
            for task in tasks:
                # 获取任务请求的代码
                requested_codes = self._extract_codes_from_params(task.params)

                if requested_codes:
                    # 筛选出对应的数据
                    if isinstance(requested_codes, list):
                        task_result = df[df[code_col].isin(requested_codes)]
                    else:
                        task_result = df[df[code_col] == requested_codes]

                    if not task.future.done():
                        # 如果筛选后为空，返回空DataFrame而不是None
                        if task_result.empty:
                            task.future.set_result(df.iloc[0:0])  # 返回同结构的空DataFrame
                        else:
                            task.future.set_result(task_result.copy())
                else:
                    # 没有指定代码，返回全部数据
                    if not task.future.done():
                        task.future.set_result(df.copy())
        else:
            # 没有代码列，检查是否可以按其他维度分发
            # 比如日期范围
            date_columns = ["date", "trade_date", "datetime", "日期", "交易日期"]
            date_col = None
            for col in date_columns:
                if col in df.columns:
                    date_col = col
                    break

            if date_col:
                for task in tasks:
                    # 按日期范围筛选
                    start_date = task.params.get("start_date") or task.params.get("start_time")
                    end_date = task.params.get("end_date") or task.params.get("end_time")

                    if start_date or end_date:
                        task_result = df.copy()
                        if start_date:
                            task_result = task_result[task_result[date_col] >= start_date]
                        if end_date:
                            task_result = task_result[task_result[date_col] <= end_date]

                        if not task.future.done():
                            task.future.set_result(task_result)
                    else:
                        if not task.future.done():
                            task.future.set_result(df.copy())
            else:
                # 无法智能分发，所有任务获得完整数据副本
                for task in tasks:
                    if not task.future.done():
                        task.future.set_result(df.copy())

    def _distribute_dict_results(self, tasks: List[RequestTask], result_dict: dict):
        """分发字典类型的结果"""
        # 检查是否是按代码组织的字典
        if result_dict:
            first_key = next(iter(result_dict))
            # 判断是否是股票代码作为key
            if isinstance(first_key, str) and (
                len(first_key) == 6  # 纯代码
                or "." in first_key  # 带市场后缀
                or first_key.startswith(("SH", "SZ", "sh", "sz"))  # 带市场前缀
            ):
                # 按代码分发
                for task in tasks:
                    requested_codes = self._extract_codes_from_params(task.params)
                    if requested_codes:
                        task_result = {}
                        if isinstance(requested_codes, list):
                            for code in requested_codes:
                                if code in result_dict:
                                    task_result[code] = result_dict[code]
                        else:
                            if requested_codes in result_dict:
                                task_result = {requested_codes: result_dict[requested_codes]}

                        if not task.future.done():
                            task.future.set_result(task_result)
                    else:
                        if not task.future.done():
                            task.future.set_result(result_dict.copy())
            else:
                # 不是按代码组织，所有任务获得完整副本
                for task in tasks:
                    if not task.future.done():
                        task.future.set_result(result_dict.copy())
        else:
            # 空字典
            for task in tasks:
                if not task.future.done():
                    task.future.set_result({})

    def _distribute_list_results(self, tasks: List[RequestTask], result_list: list):
        """分发列表类型的结果"""
        if not result_list:
            # 空列表
            for task in tasks:
                if not task.future.done():
                    task.future.set_result([])
            return

        # 检查列表元素类型
        first_item = result_list[0]

        if isinstance(first_item, dict):
            # 列表中是字典，可能是股票数据
            code_keys = ["code", "symbol", "stock_code", "ts_code"]
            code_key = None
            for key in code_keys:
                if key in first_item:
                    code_key = key
                    break

            if code_key:
                # 按代码筛选
                for task in tasks:
                    requested_codes = self._extract_codes_from_params(task.params)
                    if requested_codes:
                        if isinstance(requested_codes, list):
                            task_result = [
                                item
                                for item in result_list
                                if item.get(code_key) in requested_codes
                            ]
                        else:
                            task_result = [
                                item
                                for item in result_list
                                if item.get(code_key) == requested_codes
                            ]

                        if not task.future.done():
                            task.future.set_result(task_result)
                    else:
                        if not task.future.done():
                            task.future.set_result(result_list.copy())
            else:
                # 无法按代码筛选，返回完整列表
                for task in tasks:
                    if not task.future.done():
                        task.future.set_result(result_list.copy())
        else:
            # 简单列表，所有任务获得副本
            for task in tasks:
                if not task.future.done():
                    task.future.set_result(result_list.copy())

    def _extract_codes_from_params(self, params: dict):
        """从参数中提取股票代码"""
        code_keys = ["codes", "code", "symbol", "stock_code", "ts_code"]
        for key in code_keys:
            if key in params:
                codes = params[key]
                if isinstance(codes, str) and "," in codes:
                    return codes.split(",")
                return codes
        return None

    async def _cleanup_cache(self):
        """定期清理过期缓存"""
        while self.running:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次

                now = time.time()
                expired = []

                for request_id, (_, cache_time) in self.dedup_cache.items():
                    if now - cache_time > self.cache_ttl:
                        expired.append(request_id)

                for request_id in expired:
                    del self.dedup_cache[request_id]

                if expired:
                    logger.debug(f"清理了 {len(expired)} 个过期缓存")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理缓存时出错: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_length": len(self.request_queue),
            "executing": len(self.executing),
            "cache_size": len(self.dedup_cache),
            "batch_buffer_size": sum(len(tasks) for tasks in self.batch_buffer.values()),
        }
