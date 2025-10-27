# encoding:utf-8
"""
AmazingData SDK 进程代理

通过子进程隔离调用 AmazingData SDK，防止 SDK 意外影响主进程。
负责处理 SDK 的 SystemExit 和异常问题。
"""
from __future__ import annotations

import asyncio
import base64
import multiprocessing as mp
import os
import pickle
import queue
import socket
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from multiprocessing import connection
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, TypedDict, cast

from loguru import logger


class RequestType(Enum):
    """请求类型枚举"""

    LOGIN = "login"
    LOGOUT = "logout"
    GET_DATA = "get_data"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    HEALTH_CHECK = "health_check"
    SHUTDOWN = "shutdown"

class ProxyRequestPayload(TypedDict):
    """IPC 请求序列化结构"""

    request_id: str
    request_type: RequestType
    method: str
    args: tuple[Any, ...]
    kwargs: Dict[str, Any]
    timeout: float
    alt_methods: tuple[str, ...]
    alt_args: tuple[tuple[Any, ...], ...]
    kwargs_patches: tuple[Dict[str, Any], ...]

class ProxyResponsePayload(TypedDict):
    """IPC 响应序列化结构"""

    request_id: str
    success: bool
    result: Any
    error: Optional[str]
    error_type: Optional[str]
    timestamp: float

class WorkerQueue(Protocol):
    """统一进程间队列接口"""

    def get(self, timeout: Optional[float] = None) -> bytes: ...

    def put(self, data: bytes) -> None: ...

@dataclass
class ProxyRequest:
    """IPC 请求数据结构"""

    request_id: str
    request_type: RequestType
    method: str
    args: tuple[Any, ...]
    kwargs: Dict[str, Any]
    timeout: float = 30.0
    alt_methods: tuple[str, ...] = tuple()
    alt_args: tuple[tuple[Any, ...], ...] = tuple()
    kwargs_patches: tuple[Dict[str, Any], ...] = tuple()

    def to_payload(self) -> ProxyRequestPayload:
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "method": self.method,
            "args": self.args,
            "kwargs": dict(self.kwargs),
            "timeout": self.timeout,
            "alt_methods": self.alt_methods,
            "alt_args": self.alt_args,
            "kwargs_patches": tuple(dict(patch) for patch in self.kwargs_patches),
        }

    @classmethod
    def from_payload(cls, payload: ProxyRequestPayload) -> "ProxyRequest":
        return cls(
            request_id=payload["request_id"],
            request_type=payload["request_type"],
            method=payload["method"],
            args=tuple(payload["args"]),
            kwargs=dict(payload["kwargs"]),
            timeout=payload["timeout"],
            alt_methods=tuple(payload.get("alt_methods", ())),
            alt_args=tuple(tuple(args) for args in payload.get("alt_args", ())),
            kwargs_patches=tuple(dict(patch) for patch in payload.get("kwargs_patches", ())),
        )

    def to_payload(self) -> ProxyRequestPayload:
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "method": self.method,
            "args": self.args,
            "kwargs": dict(self.kwargs),
            "timeout": self.timeout,
        }

    @classmethod
    def from_payload(cls, payload: ProxyRequestPayload) -> "ProxyRequest":
        return cls(
            request_id=payload["request_id"],
            request_type=payload["request_type"],
            method=payload["method"],
            args=tuple(payload["args"]),
            kwargs=dict(payload["kwargs"]),
            timeout=payload["timeout"],
        )

@dataclass
class ProxyResponse:
    """代理响应数据结构"""

    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: float = 0.0

    def to_payload(self) -> ProxyResponsePayload:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "error_type": self.error_type,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_payload(cls, payload: ProxyResponsePayload) -> "ProxyResponse":
        return cls(
            request_id=payload["request_id"],
            success=payload["success"],
            result=payload["result"],
            error=payload["error"],
            error_type=payload["error_type"],
            timestamp=payload["timestamp"],
        )

class AmazingDataProcessProxy:
    """
    AmazingData SDK 进程代理

    支持两种运行模式：
    1. 使用当前解释器 + multiprocessing（默认）
    2. 指定外部 Python 解释器（用于 Python 3.9 Worker）
    """

    def __init__(
        self,
        max_workers: int = 1,
        restart_on_crash: bool = True,
        python_executable: Optional[str] = None,
        worker_env: Optional[Dict[str, str]] = None,
        startup_timeout: float = 10.0,
    ) -> None:
        """初始化进程代理"""

        self.max_workers = max_workers
        self.restart_on_crash = restart_on_crash
        self.python_executable = python_executable
        self.worker_env = dict(worker_env) if worker_env else {}
        self.startup_timeout = startup_timeout

        self.manager: Optional[SyncManager] = None
        self.request_queue: Optional[WorkerQueue] = None
        self.response_queue: Optional[WorkerQueue] = None
        self._queue_lock = threading.Lock()

        if self.python_executable is None:
            self._initialize_local_queues()

        self.worker_process: mp.Process | subprocess.Popen[bytes] | None = None
        self.is_running = False

        # 外部 worker 相关资源
        self.listener: Optional[connection.Listener] = None
        self.connection: Optional[connection.Connection] = None
        self._connection_lock = threading.Lock()
        self._pending_responses: Dict[str, ProxyResponse] = {}
        self._pending_lock = threading.Lock()

        # 统计信息
        self.stats: Dict[str, Any] = {
            "requests_sent": 0,
            "requests_completed": 0,
            "requests_failed": 0,
            "process_restarts": 0,
            "last_crash_time": None,
            "last_crash_reason": None,
            "last_health_status": None,
            "last_health_checked_at": None,
        }

        # 状态记录
        self.last_login_username: Optional[str] = None

    # ------------------------------------------------------------------
    # 初始化 / 启动
    # ------------------------------------------------------------------
    def _initialize_local_queues(self, *, force_reset: bool = False) -> None:
        with self._queue_lock:
            if force_reset:
                self._reset_local_queues_locked()
            if self.manager is None:
                manager = mp.Manager()
                self.manager = cast(SyncManager, manager)
                self.request_queue = cast(WorkerQueue, manager.Queue())
                self.response_queue = cast(WorkerQueue, manager.Queue())

    def _reset_local_queues_locked(self) -> None:
        if self.manager is not None:
            try:
                self.manager.shutdown()
            except Exception as exc:  # pragma: no cover - 调试信息
                logger.debug(f"Manager shutdown raised: {exc}")
            finally:
                self.manager = None
        self.request_queue = None
        self.response_queue = None

    def _reset_local_queues(self) -> None:
        with self._queue_lock:
            self._reset_local_queues_locked()

    def start(self) -> bool:
        """启动 Worker 进程"""

        if self.is_running and self._is_worker_alive():
            logger.info("AmazingData worker process already running")
            return True

        if self.python_executable:
            return self._start_external_worker()
        return self._start_local_worker()

    async def start_async(self) -> bool:
        """异步启动 Worker 进程，包装同步实现以兼容 asyncio。"""

        return await asyncio.to_thread(self.start)

    def _start_local_worker(self) -> bool:
        try:
            self._initialize_local_queues(force_reset=True)

            request_queue = self.request_queue
            response_queue = self.response_queue
            if request_queue is None or response_queue is None:
                logger.error("Worker queues not initialized")
                return False

            logger.info("Starting AmazingData worker process (local)...")
            process = mp.Process(
                target=self._worker_loop,
                args=(request_queue, response_queue),
                daemon=True,
            )
            process.start()
            time.sleep(0.5)

            if process.is_alive():
                self.worker_process = process
                self.is_running = True
                logger.info("AmazingData worker process started (local mode)")
                return True

            logger.error("Worker process failed to start (local mode)")
            return False
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error(f"Error starting local worker process: {exc}")
            return False

    def _start_external_worker(self) -> bool:
        if not self.python_executable:
            logger.error("Python executable not provided for external worker")
            return False

        interpreter_path = Path(self.python_executable)
        if not interpreter_path.exists():
            logger.error(f"Python executable not found: {interpreter_path}")
            return False

        if self.connection:
            try:
                self.connection.close()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
            self.connection = None
        if self.listener:
            try:
                self.listener.close()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
            self.listener = None

        authkey = os.urandom(32)
        try:
            self.listener = connection.Listener(("127.0.0.1", 0), authkey=authkey)
        except OSError as exc:
            logger.error(f"Failed to create listener for external worker: {exc}")
            return False
        listener_obj = self.listener
        if listener_obj is None:
            logger.error("Listener not initialized for external worker")
            return False
        address = listener_obj.address
        if not isinstance(address, tuple) or len(address) != 2:
            logger.error(f"Listener returned unexpected address: {address}")
            self._cleanup_external_channels()
            return False
        host, port = cast(tuple[str, int], address)
        encoded_key = base64.b64encode(authkey).decode("ascii")
        env = self._build_worker_env()
        cmd = [
            str(interpreter_path),
            "-m",
            "deepsearch.infrastructure.providers.implementations.amazingdata.py39_worker",
            "--host",
            str(host),
            "--port",
            str(port),
            "--authkey",
            encoded_key,
            "--log-level",
            "INFO",
        ]

        logger.info(
            "Starting AmazingData worker process (external interpreter %s)...",
            interpreter_path,
        )

        try:
            external_process = subprocess.Popen(cmd, env=env)
        except FileNotFoundError:
            logger.error(f"Python executable not found: {interpreter_path}")
            self._cleanup_external_channels()
            return False
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error(f"Failed to launch external worker: {exc}")
            self._cleanup_external_channels()
            return False

        try:
            self.connection = self._wait_for_connection(
                external_process, listener_obj, self.startup_timeout
            )
        except TimeoutError:
            logger.error("Worker failed to connect within %.1fs", self.startup_timeout)
            self._terminate_worker()
            self._cleanup_external_channels()
            return False
        except RuntimeError as exc:
            logger.error(str(exc))
            self._cleanup_external_channels()
            return False

        self.worker_process = external_process
        logger.info(
            "AmazingData worker process started (PID: %s, external mode)",
            external_process.pid,
        )
        self.is_running = True
        with self._pending_lock:
            self._pending_responses.clear()
        return True

    def _build_worker_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        project_root = Path(__file__).resolve().parents[5]
        python_path_entries = [str(project_root)]
        existing = env.get("PYTHONPATH")
        if existing:
            python_path_entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
        env.update(self.worker_env)
        return env

    def _wait_for_connection(
        self,
        process: subprocess.Popen[bytes],
        listener: connection.Listener,
        timeout: float,
    ) -> connection.Connection:
        deadline = time.time() + timeout
        raw_listener = getattr(listener, "_listener", None)
        sock: Optional[socket.socket]
        if raw_listener is not None:
            sock = cast(Optional[socket.socket], getattr(raw_listener, "_socket", None))
        else:
            sock = None
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError
            if sock is not None:
                sock.settimeout(min(1.0, remaining))
            try:
                conn = listener.accept()
                listener.close()
                self.listener = None
                return conn
            except socket.timeout:
                if process.poll() is not None:
                    raise RuntimeError("Worker exited before establishing connection")
                continue

    # ------------------------------------------------------------------
    # 停止与清理
    # ------------------------------------------------------------------
    def stop(self, timeout: float = 5.0, force: bool = False, with_logout: bool = True) -> bool:
        if not self.is_running:
            return True

        if self.python_executable:
            return self._stop_external_worker(timeout, force, with_logout)
        return self._stop_local_worker(timeout, force, with_logout)

    def _stop_local_worker(self, timeout: float, force: bool, with_logout: bool) -> bool:
        process_obj = self.worker_process
        if not isinstance(process_obj, mp.Process):
            self.is_running = False
            self._reset_local_queues()
            return True
        logger.info(
            "Stopping AmazingData worker process (local mode, with_logout=%s)...", with_logout
        )
        try:
            if with_logout and self.request_queue:
                logout_args: tuple[Any, ...] = ()
                if self.last_login_username:
                    logout_args = (self.last_login_username,)
                logout_request = ProxyRequest(
                    request_id="logout_before_stop",
                    request_type=RequestType.LOGOUT,
                    method="logout",
                    args=logout_args,
                    kwargs={},
                )
                self.request_queue.put(pickle.dumps(logout_request.to_payload()))
                process_obj.join(timeout=2.0)
                if not process_obj.is_alive():
                    self.is_running = False
                    return True

            shutdown_request = ProxyRequest(
                request_id="shutdown",
                request_type=RequestType.SHUTDOWN,
                method="shutdown",
                args=(),
                kwargs={},
            )
            if self.request_queue:
                self.request_queue.put(pickle.dumps(shutdown_request.to_payload()))

            remaining_timeout = max(1.0, timeout - (2.0 if with_logout else 0))
            process_obj.join(timeout=remaining_timeout)

            if process_obj.is_alive():
                logger.warning("Worker process not responding, terminating...")
                process_obj.terminate()
                process_obj.join(timeout=2.0)
                if process_obj.is_alive() and force:
                    logger.error("Force killing worker process")
                    process_obj.kill()

            self.is_running = False
            self.last_login_username = None
            self._reset_local_queues()
            return True
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error(f"Error stopping worker process: {exc}")
            return False

    def _stop_external_worker(self, timeout: float, force: bool, with_logout: bool) -> bool:
        logger.info(
            "Stopping AmazingData worker process (external mode, with_logout=%s)...", with_logout
        )

        if with_logout and self.last_login_username:
            try:
                logout_request = ProxyRequest(
                    request_id="logout_before_stop",
                    request_type=RequestType.LOGOUT,
                    method="logout",
                    args=(self.last_login_username,),
                    kwargs={},
                )
                self._send_bytes(pickle.dumps(logout_request.to_payload()))
                time.sleep(0.2)
            except Exception as exc:  # pragma: no cover - 防御性日志
                logger.warning(f"Failed to send logout request before shutdown: {exc}")

        shutdown_request = ProxyRequest(
            request_id="shutdown",
            request_type=RequestType.SHUTDOWN,
            method="shutdown",
            args=(),
            kwargs={},
        )
        try:
            self._send_bytes(pickle.dumps(shutdown_request.to_payload()))
        except Exception:
            pass

        success = self._join_worker(timeout)
        if not success and force:
            logger.warning("Force terminating external worker process")
            self._terminate_worker()
            success = self._join_worker(2.0)
            if not success:
                self._kill_worker()

        self._cleanup_external_channels()
        self.is_running = False
        self.last_login_username = None
        return success

    def _cleanup_external_channels(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
            self.connection = None
        if self.listener:
            try:
                self.listener.close()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
            self.listener = None

    # ------------------------------------------------------------------
    # 请求执行
    # ------------------------------------------------------------------
    def execute(
        self,
        method: str,
        *args,
        request_type: RequestType = RequestType.GET_DATA,
        timeout: float = 30.0,
            alt_methods: Sequence[str] | None = None,
            alt_args: Sequence[Sequence[Any]] | None = None,
            kwargs_patches: Sequence[Mapping[str, Any]] | None = None,
        **kwargs,
    ) -> ProxyResponse:
        if not self.is_running or not self._is_worker_alive():
            if self.restart_on_crash:
                logger.warning("Worker process not running, attempting restart...")
                if not self.start():
                    return ProxyResponse(
                        request_id="",
                        success=False,
                        error="Failed to start worker process",
                    )
                self.stats["process_restarts"] += 1
            else:
                return ProxyResponse(
                    request_id="",
                    success=False,
                    error="Worker process not running",
                )

        request_id = f"{method}_{time.time()}"
        request = ProxyRequest(
            request_id=request_id,
            request_type=request_type,
            method=method,
            args=tuple(args),
            kwargs=dict(kwargs),
            timeout=timeout,
            alt_methods=tuple(alt_methods or ()),
            alt_args=tuple(tuple(a) for a in (alt_args or ())),
            kwargs_patches=tuple(dict(patch) for patch in (kwargs_patches or ())),
        )

        self.stats["requests_sent"] += 1

        if self.python_executable:
            return self._execute_external(request, args, request_type, timeout)
        return self._execute_local(request, args, request_type, timeout)

    def _execute_local(
        self,
        request: ProxyRequest,
        args: tuple[Any, ...],
        request_type: RequestType,
        timeout: float,
    ) -> ProxyResponse:
        if not self.request_queue or not self.response_queue:
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error="Local queues not initialized",
            )

        try:
            self.request_queue.put(pickle.dumps(request.to_payload()))
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self._is_worker_alive():
                    return self._handle_worker_crash(request.request_id)
                try:
                    response_data = self.response_queue.get(timeout=0.1)
                    payload = cast(ProxyResponsePayload, pickle.loads(response_data))
                    response = ProxyResponse.from_payload(payload)
                    if response.request_id != request.request_id:
                        continue
                    self._post_process_response(response, request_type, args)
                    return response
                except queue.Empty:
                    continue
                except Exception as exc:  # pragma: no cover - 防御性日志
                    logger.error(f"Error getting response: {exc}")
                    continue

            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error=f"Request timeout after {timeout}s",
                error_type="Timeout",
            )
        except Exception as exc:
            logger.error(f"Error executing request: {exc}")
            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def _execute_external(
        self,
        request: ProxyRequest,
        args: tuple[Any, ...],
        request_type: RequestType,
        timeout: float,
    ) -> ProxyResponse:
        try:
            if not self._send_bytes(pickle.dumps(request.to_payload())):
                return ProxyResponse(
                    request_id=request.request_id,
                    success=False,
                    error="Failed to send request to worker",
                )

            with self._pending_lock:
                pending = self._pending_responses.pop(request.request_id, None)
            if pending:
                self._post_process_response(pending, request_type, args)
                return pending

            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self._is_worker_alive():
                    return self._handle_worker_crash(request.request_id)

                response_data = self._receive_bytes(timeout=0.2)
                if response_data is None:
                    continue

                try:
                    payload = cast(ProxyResponsePayload, pickle.loads(response_data))
                    response = ProxyResponse.from_payload(payload)
                except Exception as exc:  # pragma: no cover - 防御性日志
                    logger.error(f"Failed to decode response: {exc}")
                    continue

                if response.request_id == request.request_id:
                    self._post_process_response(response, request_type, args)
                    return response

                with self._pending_lock:
                    self._pending_responses[response.request_id] = response

            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error=f"Request timeout after {timeout}s",
                error_type="Timeout",
            )
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error(f"External request execution failed: {exc}")
            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    def _post_process_response(
        self,
        response: ProxyResponse,
        request_type: RequestType,
        args: tuple[Any, ...],
    ) -> None:
        if response.success:
            self.stats["requests_completed"] += 1
            if request_type == RequestType.LOGIN and args:
                self.last_login_username = args[0]
                logger.info(f"[Proxy] Saved login username: {self.last_login_username}")
        else:
            self.stats["requests_failed"] += 1

    def _handle_worker_crash(self, request_id: str) -> ProxyResponse:
        logger.error("Worker process crashed during request")
        self.stats["last_crash_time"] = time.time()
        self.stats["last_crash_reason"] = "Process died during request"
        if self.python_executable is None:
            self._reset_local_queues()
        if self.restart_on_crash:
            self.stats["process_restarts"] += 1
            self.start()
        return ProxyResponse(
            request_id=request_id,
            success=False,
            error="Worker process crashed",
            error_type="ProcessCrash",
        )

    # ------------------------------------------------------------------
    # 健康检查与统计
    # ------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        now = time.time()
        if not self.is_running or not self._is_worker_alive():
            payload = {
                "status": "error",
                "reason": "process_not_running",
                "timestamp": now,
            }
            self.stats["last_health_status"] = payload
            self.stats["last_health_checked_at"] = now
            return payload

        response = self.execute(
            "health_check",
            request_type=RequestType.HEALTH_CHECK,
            timeout=5.0,
        )

        if response.success and isinstance(response.result, Mapping):
            payload = dict(response.result)
        elif response.success:
            payload = {
                "status": "ok",
                "timestamp": response.timestamp or now,
                "resultSummary": self._summarize_probe_result(response.result),
            }
        else:
            payload = {
                "status": "error",
                "error": response.error,
                "errorType": response.error_type,
                "timestamp": response.timestamp or now,
            }

        if "timestamp" not in payload or not isinstance(payload["timestamp"], (int, float)):
            payload["timestamp"] = response.timestamp or now

        # 规范化 status 字段
        status = str(payload.get("status") or "unknown").lower()
        payload["status"] = status

        self.stats["last_health_status"] = payload
        self.stats["last_health_checked_at"] = payload["timestamp"]
        return payload

    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()

    # ------------------------------------------------------------------
    # 辅助工具
    # ------------------------------------------------------------------
    def _is_worker_alive(self) -> bool:
        process = self.worker_process
        if process is None:
            return False
        if self.python_executable:
            return cast(subprocess.Popen[bytes], process).poll() is None
        return cast(mp.Process, process).is_alive()

    def is_worker_alive(self) -> bool:
        """对外公开的 worker 存活检查"""
        return self._is_worker_alive()

    def _terminate_worker(self) -> None:
        if self.worker_process:
            try:
                self.worker_process.terminate()
            except Exception:  # pragma: no cover - 仅用于清理
                pass

    def _kill_worker(self) -> None:
        if self.worker_process:
            try:
                self.worker_process.kill()
            except Exception:  # pragma: no cover - 仅用于清理
                pass

    def _join_worker(self, timeout: float) -> bool:
        process = self.worker_process
        if not process:
            return True
        try:
            if self.python_executable:
                external_process = cast(subprocess.Popen[bytes], process)
                external_process.wait(timeout=timeout)
                return external_process.poll() is not None
            local_process = cast(mp.Process, process)
            local_process.join(timeout=timeout)
            return not local_process.is_alive()
        except subprocess.TimeoutExpired:
            return False

    def _send_bytes(self, data: bytes) -> bool:
        if self.python_executable:
            if not self.connection:
                return False
            try:
                with self._connection_lock:
                    self.connection.send_bytes(data)
                return True
            except (BrokenPipeError, EOFError, OSError) as exc:
                logger.error(f"Connection to worker failed: {exc}")
                return False
        if not self.request_queue:
            return False
        self.request_queue.put(data)
        return True

    def _receive_bytes(self, timeout: float) -> Optional[bytes]:
        if self.python_executable:
            if not self.connection:
                return None
            try:
                if self.connection.poll(timeout):
                    with self._connection_lock:
                        return self.connection.recv_bytes()
            except (EOFError, OSError) as exc:
                logger.error(f"Error receiving data from worker: {exc}")
                return None
            return None
        if not self.response_queue:
            return None
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Worker 主循环（共享给外部解释器）
    # ------------------------------------------------------------------
    @staticmethod
    def _worker_loop(request_queue: WorkerQueue, response_queue: WorkerQueue) -> None:
        sdk_imported = False
        ad: Any | None = None

        logger.info(f"Worker process started (PID: {mp.current_process().pid})")

        logged_in_username = None
        login_errors: list[str] = []

        while True:
            try:
                request_data = request_queue.get(timeout=1)
                payload = cast(ProxyRequestPayload, pickle.loads(request_data))
                request = ProxyRequest.from_payload(payload)

                if request.request_type == RequestType.SHUTDOWN:
                    logger.info("Worker received shutdown request")
                    break

                if not sdk_imported:
                    try:
                        import AmazingData as ad_module

                        ad = cast(Any, ad_module)
                        sdk_imported = True
                        logger.info("AmazingData SDK imported in worker process")
                    except Exception as exc:
                        logger.warning(f"AmazingData SDK 导入失败，进入降级模式: {exc}")
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=f"AmazingData SDK 导入失败: {exc}",
                            error_type=type(exc).__name__,
                        )
                        response.timestamp = time.time()
                        response_queue.put(pickle.dumps(response.to_payload()))
                        continue
                if ad is None:
                    response = ProxyResponse(
                        request_id=request.request_id,
                        success=False,
                        error="AmazingData SDK not available",
                        error_type="RuntimeError",
                    )
                    response.timestamp = time.time()
                    response_queue.put(pickle.dumps(response.to_payload()))
                    continue

                if request.request_type == RequestType.LOGIN:
                    try:
                        result = ad.login(*request.args, **request.kwargs)
                    except SystemExit as exc:  # pragma: no cover - SDK behaviour
                        exit_code = getattr(exc, "code", None)
                        logger.critical(f"SDK called SystemExit during login: {exit_code}")
                        code_value = "unknown" if exit_code is None else exit_code
                        login_errors = [
                            f"sdk_system_exit:{code_value}",
                            "tgw_push_init_failed",
                        ]
                        logged_in_username = None
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=f"SDK attempted to exit with code: {exit_code}",
                            error_type="SystemExit",
                            result={
                                "exit_code": exit_code,
                                "stage": "login",
                            },
                        )
                    else:
                        if result == 0 or result is True:
                            if request.args:
                                logged_in_username = request.args[0]
                                logger.info(f"Login successful, saved username: {logged_in_username}")
                            login_errors = []
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result=result,
                            )
                        else:
                            logged_in_username = None
                            login_errors = [f"login_failed:{result}"]
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=False,
                                error=f"Login failed with code: {result}",
                                result=result,
                            )
                elif request.request_type == RequestType.LOGOUT:
                    logger.info("Attempting safe logout...")
                    try:
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=True,
                            result="logout_initiated",
                        )
                        response.timestamp = time.time()
                        response_queue.put(pickle.dumps(response.to_payload()))

                        if hasattr(ad, "logout"):
                            username_to_logout = logged_in_username
                            if not username_to_logout and request.args:
                                username_to_logout = request.args[0]
                            if username_to_logout:
                                logger.info(f"Logging out user: {username_to_logout}")
                                ad.logout(username_to_logout)
                            else:
                                logger.warning("No username available for logout, skipping")

                        logger.info("Logout completed without crash")
                        logged_in_username = None
                        login_errors = []
                        break
                    except Exception as exc:
                        logger.warning(f"Logout failed: {exc}, terminating process")
                        break
                    continue
                elif request.request_type == RequestType.HEALTH_CHECK:
                    response = AmazingDataProcessProxy._handle_health_check(
                        request.request_id,
                        ad,
                        logged_in_username,
                        sdk_imported,
                        login_errors,
                    )
                else:
                    base_kwargs = dict(request.kwargs)
                    attempts = [(request.method, tuple(request.args), base_kwargs)]

                    for idx, alt_method in enumerate(request.alt_methods):
                        alt_args = tuple(request.args)
                        if idx < len(request.alt_args):
                            alt_args = tuple(request.alt_args[idx])
                        alt_kwargs = dict(base_kwargs)
                        if idx < len(request.kwargs_patches):
                            patch_source = dict(request.kwargs_patches[idx])
                            remove_keys = patch_source.pop("__remove__", ())
                            if isinstance(remove_keys, str):
                                remove_keys = (remove_keys,)
                            for key in remove_keys:
                                alt_kwargs.pop(str(key), None)
                            alt_kwargs.update(patch_source)
                        attempts.append((alt_method, alt_args, alt_kwargs))

                    response: ProxyResponse | None = None
                    last_error: Optional[str] = None
                    for method_path, call_args, call_kwargs in attempts:
                        target = AmazingDataProcessProxy._resolve_callable(ad, method_path)
                        if target is None:
                            last_error = f"Method {method_path} not found"
                            continue
                        try:
                            result = target(*tuple(call_args), **call_kwargs)
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result=result,
                            )
                            break
                        except (AttributeError, TypeError) as exc:  # pragma: no cover - 调整fallback日志
                            last_error = f"{method_path}: {exc}"
                            continue
                        except Exception as exc:  # pragma: no cover - 记录真实异常
                            response = ProxyResponse(
                                request_id=request.request_id,
                                success=False,
                                error=str(exc),
                                error_type=type(exc).__name__,
                            )
                            break

                    if response is None:
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=last_error or f"Method {request.method} not found",
                            error_type="AttributeError",
                        )

                response.timestamp = time.time()
                response_queue.put(pickle.dumps(response.to_payload()))

            except queue.Empty:
                continue
            except EOFError:
                logger.info("Request queue closed, terminating worker")
                break
            except SystemExit as exc:
                logger.critical(f"SDK called SystemExit: {exc}")
                response = ProxyResponse(
                    request_id=request.request_id,
                    success=False,
                    error=f"SDK attempted to exit with code: {exc.code}",
                    error_type="SystemExit",
                )
                response.timestamp = time.time()
                response_queue.put(pickle.dumps(response.to_payload()))
                break
            except Exception as exc:
                logger.error(f"Worker loop error: {exc}")
                logger.error(traceback.format_exc())
                response = ProxyResponse(
                    request_id=request.request_id,
                    success=False,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                response.timestamp = time.time()
                response_queue.put(pickle.dumps(response.to_payload()))

        logger.info("Worker process exiting")

    @staticmethod
    def _handle_health_check(
            request_id: str,
            ad: Any | None,
            logged_in_username: Optional[str],
            sdk_imported: bool,
            login_errors: Sequence[str] | None = None,
    ) -> ProxyResponse:
        """构建健康检查响应，避免泄露敏感信息。"""
        timestamp = time.time()
        payload: Dict[str, Any] = {
            "status": "unknown",
            "loggedIn": bool(logged_in_username),
            "usernameHint": AmazingDataProcessProxy._mask_username(logged_in_username),
            "pid": mp.current_process().pid,
            "timestamp": timestamp,
        }

        if not sdk_imported or ad is None:
            payload["status"] = "error"
            payload["errors"] = ["sdk_not_initialized"]
            return ProxyResponse(
                request_id=request_id,
                success=False,
                result=payload,
                error="AmazingData SDK not initialized",
                error_type="SDKUnavailable",
                timestamp=timestamp,
            )

        start = time.perf_counter()
        probe_success = False
        probe_result: Any = None
        probe_name: Optional[str] = None
        probe_errors: list[str] = []
        captured_errors: list[str] = list(login_errors or [])

        candidates = AmazingDataProcessProxy._health_probe_candidates(
            logged_in=bool(logged_in_username)
        )
        for path in candidates:
            probe_ok, result, error_message = AmazingDataProcessProxy._execute_health_probe(
                ad, path
            )
            if probe_ok:
                probe_success = True
                probe_result = result
                probe_name = path
                break
            if error_message:
                probe_errors.append(f"{path}: {error_message}")

        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        payload["latencyMs"] = latency_ms

        if probe_success and probe_name:
            payload["status"] = "ok"
            payload["probe"] = {
                "name": probe_name,
                "resultSummary": AmazingDataProcessProxy._summarize_probe_result(probe_result),
            }
        elif probe_errors:
            payload["status"] = "degraded"
            payload["errors"] = probe_errors[:2]
        elif captured_errors:
            payload["status"] = "degraded"
            payload["errors"] = captured_errors[:2]
        elif logged_in_username:
            logger.warning(
                "[Proxy] Logged in but no health probe succeeded; falling back to ok status"
            )
            payload["status"] = "ok"
            payload["probe"] = {
                "name": "fallback_logged_in",
                "resultSummary": "logged_in_without_probe",
            }
            payload["warnings"] = ["probe_not_available"]
        else:
            payload["status"] = "degraded"
            payload["errors"] = ["not_logged_in"]

        success = payload["status"] != "error"
        return ProxyResponse(
            request_id=request_id,
            success=success,
            result=payload,
            error=None if success else "Health probe reported error",
            error_type=None if success else "HealthCheckError",
            timestamp=timestamp,
        )

    @staticmethod
    def _health_probe_candidates(*, logged_in: bool) -> tuple[str, ...]:
        """返回健康探针的候选执行路径。登陆成功后额外尝试交易日历探针。"""
        base_candidates = (
            "health_check",
            "get_version",
        )
        if logged_in:
            return ("BaseData.get_calendar", "BaseData.get_code_list") + base_candidates
        return base_candidates

    @staticmethod
    def _execute_health_probe(ad: Any, path: str) -> tuple[bool, Any, Optional[str]]:
        """执行健康探针并返回结果、错误摘要。"""
        callable_obj = AmazingDataProcessProxy._resolve_callable(ad, path)
        if callable_obj is None:
            return False, None, None
        try:
            result = callable_obj()
            return True, result, None
        except Exception as exc:  # pragma: no cover - 防御性日志
            truncated = str(exc)
            if len(truncated) > 120:
                truncated = f"{truncated[:117]}..."
            return False, None, truncated

    @staticmethod
    def _summarize_probe_result(result: Any) -> str:
        """对探针结果做简要概述，避免输出敏感数据。"""
        if result is None:
            return "none"
        if isinstance(result, (bool, int, float)):
            return str(result)
        if isinstance(result, str):
            return result[:120]
        if isinstance(result, Mapping):
            keys = list(result.keys())[:5]
            return f"mapping(keys={keys})"
        if isinstance(result, Sequence) and not isinstance(result, (str, bytes, bytearray)):
            size = len(result)
            return f"sequence(len={size})"
        return type(result).__name__

    @staticmethod
    def _mask_username(username: Optional[str]) -> Optional[str]:
        """用户名脱敏，避免在日志中泄露。"""
        if not username:
            return None
        if len(username) <= 2:
            return "*" * len(username)
        if len(username) <= 6:
            return f"{username[0]}***{username[-1]}"
        return f"{username[:3]}***{username[-2:]}"

    @staticmethod
    def _resolve_callable(target: Any, method_path: str) -> Callable[..., Any] | None:
        """支持带点路径的属性访问，必要时自动实例化类。"""

        current = target
        for attr in method_path.split("."):
            if not attr:
                continue
            candidate = getattr(current, attr, None)
            if candidate is None:
                return None
            if isinstance(candidate, type):
                try:
                    current = candidate()
                    continue
                except Exception:  # pragma: no cover - 仅在实例化失败时触发
                    return None
            current = candidate

        return current if callable(current) else None
