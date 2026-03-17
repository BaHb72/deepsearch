"""Dask Worker Plugin for AmazingData Actor management.

This plugin initializes and manages AmazingDataActor lifecycle on Dask Workers.
使用 Dask 原生 setup/teardown 作为唯一的生命周期管理入口。

架构设计:
- Plugin.setup(): 创建并初始化 Actor，注册到 worker.actors，启动 Redis 任务监听器
- Plugin.teardown(): 停止监听器，清理 Actor 资源
- Actor 保持 SDK 登录状态
- Redis 任务队列替代 Dask Client 提交，解决 Tornado/asyncio 事件循环冲突

Task Queue 协议:
    API 进程 RPUSH 任务到 Redis List "amazingdata:task_queue"
    Worker 进程 BLPOP 取出任务并执行，结果写入 Redis "dask_result:{task_id}"

Usage:
    from distributed import Client
    from core.infrastructure.providers.implementations.amazingdata.dask_plugin import (
        AmazingDataWorkerPlugin,
    )
    from core.compute.plugins.config import AmazingDataPluginConfig

    client = Client("tcp://scheduler:8786")
    config = AmazingDataPluginConfig(redis_url="redis://localhost:6379")
    plugin = AmazingDataWorkerPlugin(config)
    client.register_plugin(plugin)
"""

from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING, Any

from core.compute.plugins.base_plugin import BaseWorkerPlugin
from core.compute.plugins.config import AmazingDataPluginConfig
from loguru import logger

if TYPE_CHECKING:
    from distributed import Worker

# Redis 任务队列 key
TASK_QUEUE_KEY = "amazingdata:task_queue"
# Redis 结果 key 前缀（与 dask_adapter.py 中 _REDIS_RESULT_PREFIX 一致）
RESULT_PREFIX = "dask_result:"


class RedisTaskListener:
    """Redis 任务队列监听器

    在 Worker 进程中运行一个后台线程，通过 BLPOP 监听 Redis 任务队列。
    收到任务后调用 Worker 上注册的 Actor 执行方法，结果写入 Redis。

    这样 API 进程无需创建 Dask Client，完全通过 Redis 通信，
    彻底消除 Tornado/asyncio 事件循环冲突。
    """

    def __init__(self, worker: Worker, redis_url: str) -> None:
        self._worker = worker
        self._redis_url = redis_url
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._runtime_marker_value = f"ready:{worker.address}"
        self._last_marker_refresh = 0.0
        self._marker_refresh_interval = 3.0
        self._marker_ttl_seconds = 12
        self._heartbeat_error_count = 0
        self._last_heartbeat_error: str | None = None

    def start(self) -> None:
        """启动监听线程"""
        self._thread = threading.Thread(
            target=self._listen_loop,
            name="amazingdata-redis-listener",
            daemon=True,
        )
        self._thread.start()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="amazingdata-marker-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.info("[RedisTaskListener] 监听线程已启动 | queue={}", TASK_QUEUE_KEY)

    def stop(self) -> None:
        """停止监听线程"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=3.0)
        logger.info("[RedisTaskListener] 监听线程已停止")

    def _listen_loop(self) -> None:
        """主监听循环，使用 BLPOP 阻塞等待任务"""
        import redis

        r = redis.from_url(self._redis_url)  # type: ignore[attr-defined]

        while not self._stop_event.is_set():
            try:
                # BLPOP 阻塞 1 秒，超时后检查 stop_event
                result = r.blpop(TASK_QUEUE_KEY, timeout=1)
                if result is None:
                    continue

                _, task_json = result
                if isinstance(task_json, bytes):
                    task_json = task_json.decode("utf-8")

                task = json.loads(task_json)
                task_id = task["task_id"]
                method = task["method"]
                kwargs = task.get("kwargs", {})

                self._execute_task(r, task_id, method, kwargs)

            except Exception as e:
                if self._stop_event.is_set():
                    break
                logger.error("[RedisTaskListener] 监听循环异常 | error={}", e, exc_info=True)
                # 短暂等待后重试，避免密集错误循环
                self._stop_event.wait(1.0)

        try:
            self._clear_runtime_markers(r)
            r.close()
        except Exception:
            pass

    def _heartbeat_loop(self) -> None:
        """独立心跳线程，周期性刷新运行时标记。"""
        import redis

        redis_client: Any | None = None
        while not self._stop_event.is_set():
            try:
                if redis_client is None:
                    redis_client = redis.from_url(self._redis_url)  # type: ignore[attr-defined]

                self._refresh_runtime_markers(redis_client, force=True)
                self._heartbeat_error_count = 0
                self._last_heartbeat_error = None

                if self._stop_event.wait(self._marker_refresh_interval):
                    break
            except Exception as e:
                self._heartbeat_error_count += 1
                self._last_heartbeat_error = str(e)
                logger.warning(
                    "[RedisTaskListener] 心跳标记刷新失败 | count={} | error={}",
                    self._heartbeat_error_count,
                    e,
                )

                if redis_client is not None:
                    try:
                        redis_client.close()
                    except Exception:
                        pass
                    redis_client = None

                if self._stop_event.wait(1.0):
                    break

        if redis_client is not None:
            try:
                self._clear_runtime_markers(redis_client)
                redis_client.close()
            except Exception:
                pass

    def _refresh_runtime_markers(self, redis_client: Any, force: bool = False) -> None:
        """刷新 Actor 运行时标记（ready + heartbeat）。

        目的：当 Worker 因 SDK hard-exit 崩溃后，标记会在短 TTL 后自然消失，
        API 侧可快速感知并进入降级状态。
        """
        now = time.monotonic()
        if not force and (now - self._last_marker_refresh) < self._marker_refresh_interval:
            return

        redis_client.setex(
            "dask_actor_ready:amazingdata",
            self._marker_ttl_seconds,
            self._runtime_marker_value,
        )
        redis_client.setex(
            "dask_actor_heartbeat:amazingdata",
            self._marker_ttl_seconds,
            self._runtime_marker_value,
        )
        self._last_marker_refresh = now

    def _clear_runtime_markers(self, redis_client: Any) -> None:
        """清理本 Worker 对应的运行时标记（避免误删其他 Worker 的新标记）。"""
        for key in ("dask_actor_ready:amazingdata", "dask_actor_heartbeat:amazingdata"):
            try:
                current = redis_client.get(key)
                if isinstance(current, bytes):
                    current = current.decode("utf-8", errors="ignore")
                if current == self._runtime_marker_value:
                    redis_client.delete(key)
            except Exception:
                logger.debug("[RedisTaskListener] 清理运行时标记失败 | key={}", key, exc_info=True)

    def _execute_task(
        self,
        r: Any,
        task_id: str,
        method: str,
        kwargs: dict,
    ) -> None:
        """在 Worker 上执行一个任务

        从 worker.actors 获取 Actor 并调用方法，结果通过 Redis 传回。
        """
        actors = getattr(self._worker, "actors", {})

        logger.info(
            "[RedisTaskListener] 执行任务 | task_id={} | method={} | actors={}",
            task_id,
            method,
            list(actors.keys()),
        )

        actor = actors.get("amazingdata")

        # 特殊方法：健康检查（只检查 Actor 是否存在，不触发登录）
        if method == "_health_check":
            result_data = json.dumps(
                {
                    "status": "success",
                    "result": actor is not None,
                }
            )
            redis_key = f"{RESULT_PREFIX}{task_id}"
            r.setex(redis_key, 60, result_data)
            return

        if actor is None:
            error_msg = f"amazingdata Actor 未注册 (已注册: {list(actors.keys())})"
            logger.error("[RedisTaskListener] {}", error_msg)
            self._store_error(r, task_id, error_msg)
            return

        try:
            # 调用 Actor 方法，传递 task_id 让它将结果存入 Redis
            actor.call_sync(method, task_id=task_id, **kwargs)
        except Exception as e:
            error_msg = f"Actor 调用失败: {type(e).__name__}: {e}"
            logger.error(
                "[RedisTaskListener] {} | task_id={} | method={}",
                error_msg,
                task_id,
                method,
            )
            self._store_error(r, task_id, error_msg)

    def _store_error(self, r: Any, task_id: str, error_msg: str) -> None:
        """将错误写入 Redis"""
        try:
            redis_key = f"{RESULT_PREFIX}{task_id}"
            error_data = json.dumps(
                {
                    "status": "error",
                    "error": error_msg,
                    "result": None,
                }
            )
            r.setex(redis_key, 300, error_data)
        except Exception as e:
            logger.error(
                "[RedisTaskListener] Redis 写入错误失败 | task_id={} | error={}",
                task_id,
                e,
            )


class AmazingDataWorkerPlugin(BaseWorkerPlugin):
    """Dask Worker Plugin for AmazingData Actor.

    继承 BaseWorkerPlugin，只需实现三个钩子方法:
    - _load_dependencies: 加载依赖（AmazingData 无需加载 SDK）
    - _create_actor: 创建 AmazingDataActor 实例
    - _get_actor_name: 返回 Actor 注册名称

    额外功能:
    - setup 完成后启动 RedisTaskListener，监听 Redis 任务队列
    - teardown 时停止监听器

    Attributes:
        name: Plugin 名称
        config: AmazingDataPluginConfig 配置对象
    """

    name = "amazingdata-actor"

    def __init__(self, config: AmazingDataPluginConfig) -> None:
        super().__init__(config)
        self._task_listener: RedisTaskListener | None = None

    async def setup(self, worker: Worker) -> None:
        """Plugin 启动流程

        先执行父类标准 setup（创建 Actor、注册到 Worker），
        然后启动 Redis 任务监听器。
        """
        await super().setup(worker)

        # 只在 Actor 初始化成功后启动监听器
        if self._initialized and self._actor is not None:
            redis_url = getattr(self.config, "redis_url", "redis://localhost:6379")
            self._task_listener = RedisTaskListener(worker, redis_url)
            self._task_listener.start()

    async def teardown(self, worker: Worker) -> None:
        """Plugin 清理流程

        先停止监听器，再执行父类清理。
        """
        if self._task_listener is not None:
            self._task_listener.stop()
            self._task_listener = None

        await super().teardown(worker)

    async def _load_dependencies(self) -> None:
        """加载依赖

        AmazingData 使用 HTTP API，无需加载 SDK。
        """
        pass

    async def _create_actor(self) -> Any:
        """创建 AmazingDataActor 实例

        关键修复: 只提取 connection 内层字段，避免外层占位符污染。

        Returns:
            AmazingDataActor 实例，失败时返回 None
        """
        from core.compute.actors.amazingdata_actor import AmazingDataActor
        from core.config import get_config

        app_config = get_config()
        data_sources = getattr(app_config, "data_sources", None)

        # 构建 Actor 配置
        actor_config: dict[str, Any] = {
            "redis_url": self.config.redis_url,
            "distributed_session_enabled": True,
        }

        # 提取 AmazingData 配置
        if data_sources:
            providers = getattr(data_sources, "providers", {})
            if hasattr(providers, "model_dump"):
                providers = providers.model_dump()

            amazingdata_config = providers.get("amazingdata", {})
            if hasattr(amazingdata_config, "model_dump"):
                amazingdata_config = amazingdata_config.model_dump()

            config_data = amazingdata_config.get("config", {})

            # 关键修复: 只取 connection 内层，不取外层占位符
            if "connection" in config_data:
                connection = config_data["connection"]
                for key in ("host", "port", "username", "password", "timeout"):
                    if key in connection:
                        actor_config[key] = connection[key]

                # 其他 connection 配置
                for key in (
                    "auto_reconnect",
                    "heartbeat_interval",
                    "max_retries",
                    "reconnect_interval",
                ):
                    if key in connection:
                        actor_config[key] = connection[key]

            # 其他非敏感配置可以直接合并
            for key in ("cache", "subscription", "implementation_mode", "prewarm"):
                if key in config_data:
                    actor_config[key] = config_data[key]

        # 脱敏日志
        safe_config = {k: v for k, v in actor_config.items() if k != "password"}
        logger.info(f"[AmazingData] Actor 配置: {safe_config}")

        return AmazingDataActor(actor_config)

    def _get_actor_name(self) -> str:
        """获取 Actor 名称

        Returns:
            Actor 在 worker.actors 中的注册名称
        """
        return "amazingdata"


def register_amazingdata_plugin(
    client: Any,
    redis_url: str = "redis://localhost:6379",
    only_on_windows: bool = True,
) -> AmazingDataWorkerPlugin:
    """便捷函数：注册 AmazingData Plugin

    Args:
        client: Dask distributed Client
        redis_url: Redis URL for session coordination
        only_on_windows: Only activate on Windows workers

    Returns:
        已注册的 Plugin 实例
    """
    config = AmazingDataPluginConfig(
        redis_url=redis_url,
        only_on_windows=only_on_windows,
    )
    plugin = AmazingDataWorkerPlugin(config)
    client.register_plugin(plugin)
    logger.info(f"AmazingData worker plugin registered | redis_url={redis_url}")
    return plugin
