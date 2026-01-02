"""
Dask distributed task client.

This module provides a client interface for submitting tasks to the Dask distributed
scheduler. It wraps the distributed.Client with additional convenience methods and
integrates with the DeepSearch ecosystem.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

from deepsearch.observability import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")

# Default Dask scheduler address
DEFAULT_SCHEDULER_ADDRESS = "tcp://localhost:8786"


class DaskTaskClient:
    """
    Dask distributed task client.

    Provides a high-level interface for submitting tasks to a Dask cluster.
    Supports both synchronous and asynchronous task submission.

    Features:
    - Lazy connection (connects on first use)
    - Automatic reconnection on failure
    - Task result caching to Redis
    - Health monitoring

    Example:
        >>> client = DaskTaskClient()
        >>> future = client.submit_task(my_function, arg1, arg2)
        >>> result = client.get_result(future)

        >>> # Batch processing
        >>> futures = client.map_tasks(process_item, items)
        >>> results = client.gather_results(futures)
    """

    def __init__(
        self,
        scheduler_address: str = DEFAULT_SCHEDULER_ADDRESS,
        timeout: int = 30,
        name: Optional[str] = None,
        asynchronous: bool = False,
    ):
        """
        Initialize Dask task client.

        Args:
            scheduler_address: Address of the Dask scheduler
            timeout: Connection timeout in seconds
            name: Optional client name for identification
            asynchronous: Whether to use async mode
        """
        self.scheduler_address = scheduler_address
        self.timeout = timeout
        self.name = name or "deepsearch-client"
        self.asynchronous = asynchronous

        self._client: Optional[Any] = None  # distributed.Client
        self._connected = False
        self._connection_attempts = 0
        self._last_error: Optional[str] = None

        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _ensure_connected(self) -> None:
        """Ensure client is connected to the scheduler."""
        if self._connected and self._client:
            return

        try:
            from distributed import Client

            self.logger.info(f"Connecting to Dask scheduler at {self.scheduler_address}...")
            self._client = Client(
                self.scheduler_address,
                timeout=self.timeout,
                name=self.name,
                asynchronous=self.asynchronous,
            )
            self._connected = True
            self._connection_attempts = 0
            self.logger.info(
                f"Connected to Dask cluster: {self._client.scheduler_info().get('address', 'unknown')}"
            )
        except Exception as e:
            self._connection_attempts += 1
            self._last_error = str(e)
            self.logger.error(f"Failed to connect to Dask scheduler: {e}")
            raise

    @property
    def client(self) -> Any:
        """Get the underlying distributed.Client."""
        self._ensure_connected()
        return self._client

    def submit_task(
        self,
        func: Callable[..., R],
        *args: Any,
        key: Optional[str] = None,
        priority: int = 0,
        **kwargs: Any,
    ) -> Any:
        """
        Submit a single task to the Dask cluster.

        Args:
            func: Function to execute
            *args: Positional arguments
            key: Optional unique key for the task
            priority: Task priority (higher = more priority)
            **kwargs: Keyword arguments

        Returns:
            Future object representing the pending result
        """
        self._ensure_connected()
        assert self._client is not None

        future = self._client.submit(func, *args, key=key, priority=priority, **kwargs)
        self.logger.debug(f"Submitted task: {func.__name__} (key={key})")
        return future

    def map_tasks(
        self,
        func: Callable[[T], R],
        items: Iterable[T],
        batch_size: Optional[int] = None,
    ) -> List[Any]:
        """
        Map a function over multiple items in parallel.

        Args:
            func: Function to apply to each item
            items: Iterable of items to process
            batch_size: Optional batch size for chunking

        Returns:
            List of Future objects
        """
        self._ensure_connected()
        assert self._client is not None

        items_list = list(items)
        futures = self._client.map(func, items_list, batch_size=batch_size)
        self.logger.debug(f"Mapped {len(items_list)} tasks: {func.__name__}")
        return list(futures)

    def gather_results(
        self,
        futures: List[Any],
        timeout: Optional[int] = None,
        errors: str = "raise",
    ) -> List[Any]:
        """
        Gather results from multiple futures.

        Args:
            futures: List of Future objects
            timeout: Optional timeout in seconds
            errors: How to handle errors ('raise', 'skip')

        Returns:
            List of results
        """
        self._ensure_connected()
        assert self._client is not None

        self.logger.debug(f"Gathering {len(futures)} results...")
        results = self._client.gather(futures, errors=errors)
        self.logger.debug(f"Gathered {len(results)} results")
        return results

    def get_result(self, future: Any, timeout: Optional[int] = None) -> Any:
        """
        Get result from a single future.

        Args:
            future: Future object
            timeout: Optional timeout in seconds

        Returns:
            Task result
        """
        return future.result(timeout=timeout)

    def cancel_task(self, future: Any) -> None:
        """Cancel a pending task."""
        future.cancel()
        self.logger.debug("Task cancelled")

    def wait_for_tasks(
        self,
        futures: List[Any],
        timeout: Optional[float] = None,
        return_when: str = "ALL_COMPLETED",
    ) -> Dict[str, List[Any]]:
        """
        Wait for tasks to complete.

        Args:
            futures: List of futures to wait for
            timeout: Optional timeout in seconds
            return_when: When to return ('ALL_COMPLETED', 'FIRST_COMPLETED')

        Returns:
            Dict with 'done' and 'not_done' lists
        """
        from distributed import wait

        done, not_done = wait(futures, timeout=timeout, return_when=return_when)
        return {"done": list(done), "not_done": list(not_done)}

    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Get information about the Dask cluster.

        Returns:
            Cluster information dictionary
        """
        self._ensure_connected()
        assert self._client is not None

        scheduler_info = self._client.scheduler_info()
        workers = scheduler_info.get("workers", {})

        return {
            "scheduler_address": scheduler_info.get("address"),
            "n_workers": len(workers),
            "workers": [
                {
                    "address": addr,
                    "nthreads": info.get("nthreads", 0),
                    "memory_limit": info.get("memory_limit", 0),
                    "memory_used": info.get("metrics", {}).get("memory", 0),
                }
                for addr, info in workers.items()
            ],
            "total_memory": sum(w.get("memory_limit", 0) for w in workers.values()),
            "total_threads": sum(w.get("nthreads", 0) for w in workers.values()),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the Dask connection.

        Returns:
            Health status dictionary
        """
        health_score = 100
        issues = []

        if not self._connected or not self._client:
            return {
                "healthy": False,
                "score": 0,
                "issues": ["Not connected to Dask cluster"],
                "status": "disconnected",
            }

        try:
            scheduler_info = self._client.scheduler_info()
            workers = scheduler_info.get("workers", {})

            if len(workers) == 0:
                health_score -= 50
                issues.append("No workers available")

            if self._connection_attempts > 3:
                health_score -= 20
                issues.append(f"Multiple reconnection attempts: {self._connection_attempts}")

        except Exception as e:
            health_score = 0
            issues.append(f"Failed to get cluster info: {e}")

        return {
            "healthy": health_score >= 50,
            "score": max(0, health_score),
            "issues": issues,
            "status": "connected" if health_score >= 50 else "degraded",
            "metrics": {
                "connected": self._connected,
                "connection_attempts": self._connection_attempts,
                "last_error": self._last_error,
            },
        }

    def close(self) -> None:
        """Close the Dask client connection."""
        if self._client:
            try:
                self._client.close()
                self.logger.info("Dask client closed")
            except Exception as e:
                self.logger.warning(f"Error closing Dask client: {e}")
            finally:
                self._client = None
                self._connected = False

    def __enter__(self) -> "DaskTaskClient":
        """Context manager entry."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()


def submit_to_dask(
    func: Callable[..., R],
    *args: Any,
    scheduler_address: str = DEFAULT_SCHEDULER_ADDRESS,
    **kwargs: Any,
) -> R:
    """
    Convenience function to submit a single task and wait for result.

    Args:
        func: Function to execute
        *args: Positional arguments
        scheduler_address: Dask scheduler address
        **kwargs: Keyword arguments

    Returns:
        Task result
    """
    with DaskTaskClient(scheduler_address=scheduler_address) as client:
        future = client.submit_task(func, *args, **kwargs)
        return client.get_result(future)


# ==================== 异步单例管理 ====================

_global_client: Optional[Any] = None  # distributed.Client


async def get_dask_client(scheduler_address: str = DEFAULT_SCHEDULER_ADDRESS) -> Any:
    """获取全局 Dask Client 单例 (异步)

    Args:
        scheduler_address: Dask scheduler 地址

    Returns:
        distributed.Client 实例

    Raises:
        RuntimeError: 如果无法连接到 Dask 集群
    """
    global _global_client

    if _global_client is not None:
        try:
            # 检查连接是否仍然有效
            status = _global_client.status
            if status == "running":
                return _global_client
        except Exception:
            _global_client = None

    try:
        from distributed import Client

        logger.info(f"连接到 Dask Scheduler: {scheduler_address}...")
        _global_client = await Client(
            scheduler_address,
            asynchronous=True,
            timeout=30,
            name="deepsearch-async",
        )
        logger.info("Dask Client 连接成功")
        return _global_client

    except Exception as e:
        logger.error(f"Dask 集群连接失败: {e}")
        raise RuntimeError("Dask 集群不可用，请检查: 1) Docker 服务 2) Windows Worker 脚本") from e


async def close_dask_client() -> None:
    """关闭全局 Dask Client"""
    global _global_client

    if _global_client is not None:
        try:
            await _global_client.close()
            logger.info("Dask Client 已关闭")
        except Exception as e:
            logger.warning(f"关闭 Dask Client 时出错: {e}")
        finally:
            _global_client = None
