"""
请求去重中间件

自动合并相同的并发请求，减少重复处理
"""

import asyncio
import json
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Set, Union, cast

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

try:
    import xxhash

    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False
    logger.warning("xxhash not available, falling back to MD5")


class RequestDeduplicator:
    """
    请求去重器

    功能：
    - 检测相同的并发请求
    - 让后续请求等待第一个请求的结果
    - 减少数据库查询和 API 调用
    - 自动清理过期的请求记录
    """

    def __init__(self, ttl_seconds: int = 5):
        """
        初始化去重器

        Args:
            ttl_seconds: 请求结果缓存时间（秒）
        """
        self.pending_requests: Dict[str, asyncio.Future[Any]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.request_count = 0
        self.dedup_count = 0
        self._lock = asyncio.Lock()

    def _make_hashable(self, value: Any) -> Any:
        """将请求参数递归转换为可哈希结构"""

        if isinstance(value, dict):
            # 对字典按键排序，确保顺序稳定
            return tuple(
                (str(key), self._make_hashable(val))
                for key, val in sorted(value.items(), key=lambda item: str(item[0]))
            )

        if isinstance(value, (list, tuple)):
            return tuple(self._make_hashable(item) for item in value)

        if isinstance(value, (set, frozenset)):
            normalized_items = tuple(self._make_hashable(item) for item in value)
            return tuple(sorted(normalized_items, key=lambda item: repr(item)))

        # 其他类型保持原样，由调用方负责保证其可哈希
        return value

    def get_request_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        生成请求的唯一标识 - 优化版本使用 xxhash

        Args:
            endpoint: API 端点
            params: 请求参数

        Returns:
            请求的哈希键
        """
        # 使用 frozenset 避免排序开销 - O(1) 平均情况
        normalized_params = self._make_hashable(params)

        key_data = (endpoint, normalized_params)

        # 使用 xxhash 进行快速哈希（比 MD5 快 10x）
        if XXHASH_AVAILABLE:
            return cast(str, xxhash.xxh64_hexdigest(str(key_data)))
        else:
            # 降级到 MD5
            import hashlib

            return hashlib.md5(str(key_data).encode(), usedforsecurity=False).hexdigest()  # nosec B324 - 仅用于请求去重

    async def deduplicate(
        self,
        key: str,
        coroutine: Union[Callable[[], Awaitable[Any]], Awaitable[Any]],
    ) -> Any:
        """
        执行去重逻辑

        Args:
            key: 请求键
            coroutine: 要执行的协程

        Returns:
            请求结果（可能来自缓存）
        """
        existing_future: Optional[asyncio.Future[Any]] = None

        async with self._lock:
            self.request_count += 1

            # 检查是否有相同的请求正在处理
            if key in self.pending_requests:
                self.dedup_count += 1
                existing_future = self.pending_requests[key]
                logger.debug(f"请求去重命中: {key[:8]}... (总去重: {self.dedup_count})")

        # 等待已存在的请求完成（在锁外等待，避免死锁）
        if existing_future is not None:
            try:
                return await existing_future
            except Exception as e:
                logger.error(f"等待去重请求失败: {e}")
                raise

        # 创建新的请求
        loop = asyncio.get_event_loop()
        new_future: asyncio.Future[Any] = loop.create_future()

        async with self._lock:
            # 再次检查（可能在等待锁期间有其他请求创建了）
            if key in self.pending_requests:
                return await self.pending_requests[key]

            self.pending_requests[key] = new_future
            logger.debug(f"创建新请求: {key[:8]}...")

        try:
            # 执行实际的请求 - 如果是函数则调用，否则直接await
            if callable(coroutine):
                result = await coroutine()
            else:
                result = await coroutine
            new_future.set_result(result)
            return result
        except Exception as e:
            new_future.set_exception(e)
            raise
        finally:
            # 异步清理（不阻塞返回）
            asyncio.create_task(self._cleanup_key(key))

    async def _cleanup_key(self, key: str):
        """
        延迟清理请求记录

        Args:
            key: 要清理的请求键
        """
        await asyncio.sleep(self.ttl.total_seconds())
        async with self._lock:
            self.pending_requests.pop(key, None)
            logger.debug(f"清理请求缓存: {key[:8]}...")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取去重统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_requests": self.request_count,
            "deduplicated_requests": self.dedup_count,
            "dedup_rate": f"{(self.dedup_count / max(self.request_count, 1)) * 100:.1f}%",
            "pending_requests": len(self.pending_requests),
            "ttl_seconds": self.ttl.total_seconds(),
        }

    def clear(self):
        """清空所有待处理的请求"""
        self.pending_requests.clear()
        logger.info("已清空所有待处理请求")


# 全局去重器实例（按数据类型分类）
_deduplicators = {
    "stock_data": RequestDeduplicator(ttl_seconds=5),  # 股票数据：5秒
    "market_overview": RequestDeduplicator(ttl_seconds=10),  # 市场概览：10秒
    "indicators": RequestDeduplicator(ttl_seconds=30),  # 技术指标：30秒
    "realtime": RequestDeduplicator(ttl_seconds=2),  # 实时数据：2秒
}


def get_deduplicator(data_type: str = "default") -> RequestDeduplicator:
    """
    获取指定类型的去重器

    Args:
        data_type: 数据类型

    Returns:
        对应的去重器实例
    """
    if data_type not in _deduplicators:
        _deduplicators[data_type] = RequestDeduplicator(ttl_seconds=5)
    return _deduplicators[data_type]


def get_all_stats() -> Dict[str, Any]:
    """
    获取所有去重器的统计信息

    Returns:
        汇总统计信息
    """
    total_requests = 0
    total_deduped = 0
    stats_by_type = {}

    for data_type, dedup in _deduplicators.items():
        stats = dedup.get_stats()
        stats_by_type[data_type] = stats
        total_requests += stats["total_requests"]
        total_deduped += stats["deduplicated_requests"]

    return {
        "total_requests": total_requests,
        "total_deduplicated": total_deduped,
        "overall_dedup_rate": f"{(total_deduped / max(total_requests, 1)) * 100:.1f}%",
        "by_type": stats_by_type,
    }


class DeduplicationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI请求去重中间件
    """

    def __init__(self, app: ASGIApp, ttl: int = 5, include_paths: Optional[Set[str]] = None):
        # FastAPI 应用满足 ASGI 协议，此处忽略 mypy 的类型误报
        super().__init__(app)
        self.deduplicator = RequestDeduplicator(ttl)
        self.include_paths = include_paths or {
            "/api/qmt/orderbook",
            "/api/chart/series",
            "/api/data/realtime",
        }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 只对特定路径进行去重
        path = request.url.path
        should_dedupe = any(path.startswith(p) for p in self.include_paths)

        if not should_dedupe:
            passthrough_response: Response = await call_next(request)
            return passthrough_response

        # 提取请求参数
        params = dict(request.query_params)
        if request.method == "POST":
            try:
                # 读取body时需要保存，因为body只能读取一次
                body = await request.body()
                if body:
                    params.update(json.loads(body))
                # 重新创建request以便后续使用
                # 创建新的request对象，包含原始body
                async def receive() -> dict[str, object]:
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }

                send_callable_raw = getattr(request, "_send", None)
                if send_callable_raw is None:
                    request = Request(scope=request.scope, receive=receive)
                else:
                    send_callable = cast(
                        Callable[[Mapping[str, object]], Awaitable[None]],
                        send_callable_raw,
                    )
                    request = Request(scope=request.scope, receive=receive, send=send_callable)
            except Exception as e:
                logger.debug(f"解析POST参数失败: {e}")

        # 去重处理
        try:
            # 创建处理函数
            async def handler() -> Response:
                response = cast(Response, await call_next(request))
                # 对于流式响应，需要特殊处理
                if hasattr(response, "body_iterator"):
                    # 收集所有响应体
                    body_parts = []
                    async for chunk in response.body_iterator:
                        body_parts.append(chunk)

                    # 重建响应
                    full_body = b"".join(body_parts)
                    return Response(
                        content=full_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                return response

            # 生成请求键
            key = self.deduplicator.get_request_key(path, params)

            # 执行去重 - 传递函数而非协程对象，避免 RuntimeWarning
            response = cast(Response, await self.deduplicator.deduplicate(key, handler))
            return response

        except Exception as e:
            logger.error(f"请求去重处理失败: {e}")
            # 出错时直接执行原始请求
            fallback_response: Response = await call_next(request)
            return fallback_response


# FastAPI 依赖注入辅助函数
async def deduplicate_request(
    endpoint: str, params: Dict[str, Any], coroutine, data_type: str = "default"
):
    """
    FastAPI 路由中使用的去重装饰器

    使用示例：
    ```python
    @router.get("/stock/{symbol}")
    async def get_stock_data(symbol: str):
        return await deduplicate_request(
            endpoint="/stock",
            params={"symbol": symbol},
            coroutine=fetch_stock_data(symbol),
            data_type="stock_data"
        )
    ```
    """
    dedup = get_deduplicator(data_type)
    key = dedup.get_request_key(endpoint, params)
    return await dedup.deduplicate(key, coroutine)
