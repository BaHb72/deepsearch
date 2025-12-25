# encoding:utf-8
"""
AmazingData SDK 进程代理

通过子进程隔离调用 AmazingData SDK，防止 SDK 意外影响主进程。
负责处理 SDK 的 SystemExit 和异常问题。
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import inspect
import multiprocessing as mp
import os
import pickle
import queue
import random
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from multiprocessing import connection
from multiprocessing.context import BaseContext
from pathlib import Path
from typing import IO, Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Sized, TypedDict, cast


class _MsvcrtModule(Protocol):
    LK_LOCK: int
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, handle: int, mode: int, nbytes: int) -> None: ...


class _FcntlModule(Protocol):
    LOCK_EX: int
    LOCK_NB: int
    LOCK_UN: int

    def flock(self, fileno: int, operation: int) -> None: ...


if os.name == "nt":  # pragma: no cover - 平台相关
    import msvcrt as _msvcrt

    msvcrt: _MsvcrtModule = cast(_MsvcrtModule, _msvcrt)
else:  # pragma: no cover - 平台相关
    import fcntl as _fcntl

    fcntl: _FcntlModule = cast(_FcntlModule, _fcntl)



from .param_guards import CachePolicy
from loguru import logger

_WORKER_FILE_SINK_ATTACHED = False


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


def _summarize_payload_shape(payload: Any) -> str:
    """返回请求结构概况，便于日志定位"""
    if payload is None:
        return "None"
    type_name: str = payload.__class__.__name__
    if isinstance(payload, Sized):
        try:
            length = len(payload)
        except Exception:
            length = None
        if length is not None:
            return f"{type_name}(len={length})"
    return type_name


def _attach_worker_file_sink(level: str) -> None:
    global _WORKER_FILE_SINK_ATTACHED
    if _WORKER_FILE_SINK_ATTACHED:
        return
    log_dir = Path(os.environ.get("DEEPSEARCH_WORKER_LOG_DIR") or (Path("data") / "logs" / "datasource"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"amazingdata_worker_{datetime.now():%Y%m%d}.log"
        logger.add(
            log_file,
            level=level,
            format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
            encoding="utf-8",
            rotation="00:00",
            retention="7 days",
        )
        _WORKER_FILE_SINK_ATTACHED = True
    except Exception as exc:  # pragma: no cover - 日志目录异常仅提示
        logger.warning("Unable to attach worker file logger: {}", exc)


class _InterProcessFileLock:
    """跨进程文件锁，确保 AmazingData worker 只被单实例占用。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: IO[str] | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self, *, blocking: bool = False) -> bool:
        if self._handle is not None:
            return True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:  # pragma: no cover - 目录创建失败不致命
            pass
        try:
            handle = self._path.open("a+", encoding="utf-8")
        except OSError as exc:  # pragma: no cover - 文件不可写
            logger.warning("Failed to open worker lock file {}: {}", self._path, exc)
            return False

        try:
            fileno = handle.fileno()
            handle.seek(0)
            if os.name == "nt":  # pragma: no cover - Windows 分支
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(fileno, mode, 1)
            else:  # pragma: no cover - POSIX 分支
                flags = fcntl.LOCK_EX
                if not blocking:
                    flags |= fcntl.LOCK_NB
                fcntl.flock(fileno, flags)
        except (OSError, BlockingIOError):
            handle.close()
            return False

        try:
            handle.seek(0)
            handle.truncate(0)
            handle.write(f"{os.getpid()}\n")
            handle.flush()
        except Exception:  # pragma: no cover - 注释失败不影响锁本身
            logger.debug("Unable to annotate worker lock file {}", self._path)
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            fileno = handle.fileno()
            if os.name == "nt":  # pragma: no cover - Windows 分支
                with contextlib.suppress(OSError):
                    handle.seek(0)
                    msvcrt.locking(fileno, msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - POSIX 分支
                fcntl.flock(fileno, fcntl.LOCK_UN)
        except Exception:  # pragma: no cover - 容错
            logger.debug("Failed to release worker lock {}", self._path)
        finally:
            handle.close()
            self._handle = None


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
    2. 指定外部 Python 解释器（用于隔离运行的 Worker）
    """

    _CLASS_INSTANCE_CACHE: dict[type, Any] = {}
    _IS_LOCAL_COMPAT_CACHE: dict[str, bool] = {}
    _MARKET_CALENDAR_CACHE: Sequence[int] | None = None

    @classmethod
    def _reset_class_caches(cls) -> None:
        cls._CLASS_INSTANCE_CACHE.clear()
        cls._IS_LOCAL_COMPAT_CACHE.clear()
        cls._MARKET_CALENDAR_CACHE = None

    def __init__(
        self,
        max_workers: int = 1,
        restart_on_crash: bool = True,
        python_executable: Optional[str] = None,
        worker_env: Optional[Dict[str, str]] = None,
        startup_timeout: float = 10.0,
    ) -> None:
        """初始化进程代理"""

        self._reset_class_caches()
        self.max_workers = max_workers
        self.restart_on_crash = restart_on_crash
        self.python_executable = python_executable
        self.worker_env = dict(worker_env) if worker_env else {}
        self.startup_timeout = startup_timeout

        self._mp_context: BaseContext = mp.get_context("spawn")
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
        self._worker_lock_handle: _InterProcessFileLock | None = None
        self._last_start_failure: str | None = None
        self._last_start_failure_type: str | None = None
        self._restart_attempts: int = 0
        self._next_restart_time: float = 0.0
        self._pending_restart_reason: str | None = None
        self._pending_restart_wait: float = 0.0

    @staticmethod
    def _ensure_worker_file_logger(level: str = "INFO") -> None:
        _attach_worker_file_sink(level)


    # ------------------------------------------------------------------
    # 初始化 / 启动
    # ------------------------------------------------------------------
    def _initialize_local_queues(self, *, force_reset: bool = False) -> None:
        with self._queue_lock:
            if force_reset:
                self._reset_local_queues_locked()
            if self.request_queue is None or self.response_queue is None:
                ctx = self._mp_context
                self.request_queue = cast(WorkerQueue, ctx.Queue())
                self.response_queue = cast(WorkerQueue, ctx.Queue())

    def _reset_local_queues_locked(self) -> None:
        for queue_obj in (self.request_queue, self.response_queue):
            if queue_obj is None:
                continue
            close_method = getattr(queue_obj, "close", None)
            if callable(close_method):
                close_callable = cast(Callable[[], None], close_method)
                try:
                    close_callable()
                except Exception as exc:  # pragma: no cover - 临时容错
                    logger.debug(f"Queue close raised: {exc}")
            join_method = getattr(queue_obj, "join_thread", None)
            if callable(join_method):
                join_callable = cast(Callable[[], None], join_method)
                try:
                    join_callable()
                except Exception as exc:  # pragma: no cover - 临时容错
                    logger.debug(f"Queue join_thread raised: {exc}")
        self.request_queue = None
        self.response_queue = None

    def _reset_local_queues(self) -> None:
        with self._queue_lock:
            self._reset_local_queues_locked()

    def _resolve_worker_lock_path(self) -> Path:
        lock_dir_env = os.environ.get("DEEPSEARCH_AMAZINGDATA_LOCK_DIR")
        base_dir = Path(lock_dir_env) if lock_dir_env else Path(tempfile.gettempdir())
        components: list[str] = []
        if self.worker_env:
            components.extend(f"{key}={self.worker_env[key]}" for key in sorted(self.worker_env))
        if self.python_executable:
            components.append(f"py={self.python_executable}")
        token_source = "|".join(components) or "default"
        digest = hashlib.sha256(token_source.encode("utf-8")).hexdigest()[:12]
        return base_dir / f"amazingdata_worker_{digest}.lock"

    def _acquire_worker_lock(self) -> bool:
        if self._worker_lock_handle is not None:
            return True
        lock = _InterProcessFileLock(self._resolve_worker_lock_path())
        if not lock.acquire():
            logger.warning("Worker lock busy; skip starting worker (path={})", lock.path)
            self._last_start_failure = "Worker lock busy"
            self._last_start_failure_type = "WorkerLockBusy"
            return False
        self._worker_lock_handle = lock
        logger.debug("Worker lock acquired path={}", lock.path)
        return True

    def _release_worker_lock(self) -> None:
        if self._worker_lock_handle is None:
            return
        logger.debug("Releasing worker lock path={}", self._worker_lock_handle.path)
        self._worker_lock_handle.release()
        self._worker_lock_handle = None

    def _reset_restart_backoff(self) -> None:
        self._restart_attempts = 0
        self._next_restart_time = 0.0
        self._pending_restart_reason = None
        self._pending_restart_wait = 0.0
        self.stats.pop("next_restart_seconds", None)

    def _schedule_restart_backoff(self, reason: str) -> None:
        self._restart_attempts = min(self._restart_attempts + 1, 10)
        base_delay = min(60.0, 2 ** (self._restart_attempts - 1))
        extra_delay = min(5.0, 1.0 * self._restart_attempts)
        jitter = 0.0
        if base_delay > 1.0:
            jitter = random.uniform(0.0, min(3.0, base_delay * 0.1))
        delay = base_delay + extra_delay + jitter
        self._next_restart_time = time.time() + delay
        self._pending_restart_reason = reason
        self._pending_restart_wait = delay
        self.stats["next_restart_seconds"] = delay
        self._last_start_failure = f"Worker restart delayed for {delay:.1f}s (reason={reason})"
        self._last_start_failure_type = "RestartBackoff"
        logger.warning(
            "Worker restart deferred for {:.1f}s (attempt={} reason={})",
            delay,
            self._restart_attempts,
            reason,
        )

    def _should_delay_restart(self) -> tuple[bool, float]:
        if self._next_restart_time <= 0:
            return False, 0.0
        remaining = self._next_restart_time - time.time()
        if remaining > 0:
            self._last_start_failure = (
                    self._last_start_failure
                    or f"Worker restart delayed for {remaining:.1f}s (reason={self._pending_restart_reason or 'backoff'})"
            )
            self._last_start_failure_type = self._last_start_failure_type or "RestartBackoff"
            self.stats["next_restart_seconds"] = remaining
            return True, remaining
        self._reset_restart_backoff()
        return False, 0.0
    def start(self) -> bool:
        """启动 Worker 进程"""

        if self.is_running and self._is_worker_alive():
            logger.info("AmazingData worker process already running")
            return True

        delayed, remaining = self._should_delay_restart()
        if delayed:
            reason = self._pending_restart_reason or "backoff"
            logger.warning("Worker restart delayed for {:.1f}s (reason={})", remaining, reason)
            self.stats["last_start_failure"] = self._last_start_failure
            return False

        if not self._acquire_worker_lock():
            self.stats["last_start_failure"] = self._last_start_failure
            return False

        success = False
        try:
            if self.python_executable:
                success = self._start_external_worker()
            else:
                success = self._start_local_worker()
        except Exception:
            self._release_worker_lock()
            raise

        if success:
            self._reset_restart_backoff()
            self._last_start_failure = None
            self._last_start_failure_type = None
            self.stats.pop("last_start_failure", None)
            return True

        self._release_worker_lock()
        self._last_start_failure = self._last_start_failure or "Failed to start worker process"
        self._last_start_failure_type = self._last_start_failure_type or "StartFailure"
        self._schedule_restart_backoff("start_failure")
        self.stats["last_start_failure"] = self._last_start_failure
        return False

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
            process_factory = cast(Callable[..., mp.Process], getattr(self._mp_context, "Process"))
            process = process_factory(
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
        except Exception as exc:  # pragma: no cover - ��������־
            logger.opt(exception=exc).error("Error starting local worker process")
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
            logger.opt(exception=exc).error("Failed to create listener for external worker")
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
            "deepsearch.infrastructure.providers.implementations.amazingdata.external_worker",
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
            "Starting AmazingData worker process (external interpreter {})...",
            interpreter_path,
        )

        try:
            external_process = subprocess.Popen(cmd, env=env)
        except FileNotFoundError:
            logger.error(f"Python executable not found: {interpreter_path}")
            self._cleanup_external_channels()
            return False
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.opt(exception=exc).error("Failed to launch external worker")
            self._cleanup_external_channels()
            return False

        try:
            self.connection = self._wait_for_connection(
                external_process, listener_obj, self.startup_timeout
            )
        except TimeoutError:
            logger.error("Worker failed to connect within {:.1f}s", self.startup_timeout)
            self._terminate_worker()
            self._cleanup_external_channels()
            return False
        except RuntimeError as exc:
            logger.error(str(exc))
            self._cleanup_external_channels()
            return False

        self.worker_process = external_process
        logger.info(
            "AmazingData worker process started (PID: {}, external mode)",
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
        if process_obj is None or not hasattr(process_obj, 'is_alive'):
            self.is_running = False
            self._reset_local_queues()
            self._release_worker_lock()
            self._reset_restart_backoff()
            return True
        local_process = cast(mp.Process, process_obj)
        logger.info(
            "Stopping AmazingData worker process (local mode, with_logout={})...", with_logout
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
                local_process.join(timeout=2.0)
                if not local_process.is_alive():
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
            local_process.join(timeout=remaining_timeout)

            if local_process.is_alive():
                logger.warning("Worker process not responding, terminating...")
                local_process.terminate()
                local_process.join(timeout=2.0)
                if local_process.is_alive() and force:
                    logger.error("Force killing worker process")
                    local_process.kill()

            self.is_running = False
            self.last_login_username = None
            self._reset_local_queues()
            return True
        except Exception as exc:  # pragma: no cover - ��������־
            logger.opt(exception=exc).error("Error stopping worker process")
            return False
        finally:
            self._release_worker_lock()
            self._reset_restart_backoff()

    def _stop_external_worker(self, timeout: float, force: bool, with_logout: bool) -> bool:
        logger.info(
            "Stopping AmazingData worker process (external mode, with_logout={})...", with_logout
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
        self._release_worker_lock()
        self._reset_restart_backoff()
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
                        error=self._last_start_failure or "Failed to start worker process",
                        error_type=self._last_start_failure_type or "StartFailure",
                    )
                self.stats["process_restarts"] += 1
            else:
                return ProxyResponse(
                    request_id="",
                    success=False,
                    error="Worker process not running",
                    error_type="ProcessNotRunning",
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
                    return self._handle_worker_crash(request.request_id, request)
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
                    logger.opt(exception=exc).error("Error getting response from worker")
                    continue

            self.stats["requests_failed"] += 1
            return ProxyResponse(
                request_id=request.request_id,
                success=False,
                error=f"Request timeout after {timeout}s",
                error_type="Timeout",
            )
        except Exception as exc:
            logger.opt(exception=exc).error("Error executing request")
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
                    return self._handle_worker_crash(request.request_id, request)

                response_data = self._receive_bytes(timeout=0.2)
                if response_data is None:
                    continue

                try:
                    payload = cast(ProxyResponsePayload, pickle.loads(response_data))
                    response = ProxyResponse.from_payload(payload)
                except Exception as exc:  # pragma: no cover - 防御性日志
                    logger.opt(exception=exc).error("Failed to decode worker response")
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
            logger.opt(exception=exc).error("External request execution failed")
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

    def _summarize_worker_exit(self) -> Dict[str, Any]:
        """收集 worker 进程的退出信息。"""
        summary: Dict[str, Any] = {}
        process = self.worker_process
        if process is None:
            summary["state"] = "not_started"
            return summary

        pid = getattr(process, "pid", None)
        if pid is not None:
            summary["pid"] = pid

        exit_code: Optional[int] = None
        if self.python_executable:
            exit_code = cast(subprocess.Popen[bytes], process).poll()
        elif hasattr(process, "exitcode"):
            exit_code = getattr(process, "exitcode", None)

        if exit_code is not None:
            summary["exitcode"] = exit_code
            if exit_code < 0:
                summary["signal"] = -exit_code
        return {key: value for key, value in summary.items() if value is not None}

    def _handle_worker_crash(self, request_id: str, request: Optional["ProxyRequest"] = None) -> ProxyResponse:
        crash_details = self._summarize_worker_exit()
        request_label = (
            f"{request.request_type.name}:{request.method}"
            if request and request.method
            else request.request_type.name
            if request
            else "unknown"
        )
        exit_code = crash_details.get("exitcode") if crash_details else None
        restart_required = self.restart_on_crash

        if crash_details:
            if exit_code == 0:
                restart_required = False
                logger.info(
                    "Worker process exited cleanly during request {} (details={})",
                    request_label,
                    crash_details,
                )
            elif exit_code == 1:
                logger.error(
                    "Worker process exited with code 1 during request {} (details={})",
                    request_label,
                    crash_details,
                )
            else:
                logger.error(
                    "Worker process crashed during request {} (details={})",
                    request_label,
                    crash_details,
                )
        else:
            logger.error("Worker process crashed during request {}", request_label)

        reason_label = "process_exit_clean" if exit_code == 0 else "process_exit_error"
        self.stats["last_crash_time"] = time.time()
        self.stats["last_crash_reason"] = reason_label
        if crash_details:
            self.stats["last_crash_details"] = crash_details

        self.is_running = False
        if self.python_executable is None:
            self._reset_local_queues()
        self._release_worker_lock()

        if restart_required:
            self.stats["process_restarts"] += 1
            self._schedule_restart_backoff(reason_label)
        else:
            self._reset_restart_backoff()
        error_message = "Worker process exited" if exit_code == 0 else "Worker process crashed"
        error_type = "ProcessExit" if exit_code == 0 else "ProcessCrash"
        return ProxyResponse(
            request_id=request_id,
            success=False,
            error=error_message,
            error_type=error_type,
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
                "loggedIn": bool(self.last_login_username),
            }
            exit_summary = self._summarize_worker_exit()
            if exit_summary.get("exitcode") is not None:
                payload["exitcode"] = exit_summary["exitcode"]
            if exit_summary.get("signal") is not None:
                payload["signal"] = exit_summary["signal"]
            if exit_summary.get("pid") is not None:
                payload["pid"] = exit_summary["pid"]
            if self._next_restart_time > now:
                remaining = self._next_restart_time - now
                if remaining > 0:
                    payload["nextRestartIn"] = remaining
                    if self._pending_restart_reason:
                        payload["restartBackoffReason"] = self._pending_restart_reason
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

        if not self._is_worker_alive():
            exit_summary = self._summarize_worker_exit()
            if exit_summary.get("exitcode") is not None:
                payload.setdefault("exitcode", exit_summary["exitcode"])
            if exit_summary.get("signal") is not None:
                payload.setdefault("signal", exit_summary["signal"])
            if exit_summary.get("pid") is not None:
                payload.setdefault("pid", exit_summary["pid"])
        payload.setdefault("loggedIn", bool(self.last_login_username))
        if self._next_restart_time > now:
            remaining = self._next_restart_time - now
            if remaining > 0:
                payload.setdefault("nextRestartIn", remaining)
                if self._pending_restart_reason:
                    payload.setdefault("restartBackoffReason", self._pending_restart_reason)

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
        if hasattr(process, 'is_alive'):
            return cast(mp.Process, process).is_alive()
        return False

    def is_worker_alive(self) -> bool:
        """���⹫���� worker �����"""
        return self._is_worker_alive()

    def _terminate_worker(self) -> None:
        if self.worker_process:
            try:
                self.worker_process.terminate()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
        self._release_worker_lock()
        self._reset_restart_backoff()

    def _kill_worker(self) -> None:
        if self.worker_process:
            try:
                self.worker_process.kill()
            except Exception:  # pragma: no cover - 仅用于清理
                pass
        self._release_worker_lock()
        self._reset_restart_backoff()

    def _join_worker(self, timeout: float) -> bool:
        process = self.worker_process
        if not process:
            return True
        try:
            if self.python_executable:
                external_process = cast(subprocess.Popen[bytes], process)
                external_process.wait(timeout=timeout)
                return external_process.poll() is not None
            if hasattr(process, 'join'):
                local_process = cast(mp.Process, process)
                local_process.join(timeout=timeout)
                return not local_process.is_alive()
            return True
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
                logger.opt(exception=exc).error("Connection to worker failed")
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
                logger.opt(exception=exc).error("Error receiving data from worker")
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
        AmazingDataProcessProxy._ensure_worker_file_logger(logger.level("INFO").name)

        logged_in_username = None
        login_errors: list[str] = []
        login_method_name: Optional[str] = None  # 记录检测到的login方法名 (login或Login)

        while True:
            request: ProxyRequest | None = None
            payload_request_id: Optional[str] = None
            try:
                request_data = request_queue.get(timeout=1)
                if request_data is None:
                    logger.debug("Received empty request payload")
                    continue
                payload = cast(ProxyRequestPayload, pickle.loads(request_data))
                payload_request_id = payload.get("request_id")
                request = ProxyRequest.from_payload(payload)

                if request.request_type == RequestType.SHUTDOWN:
                    logger.info("Worker received shutdown request")
                    break

                if not sdk_imported:
                    # 尝试多个可能的SDK包名
                    # 注意: AmazingData 和 tgw 的 login 函数签名不同！优先使用 AmazingData
                    # 注意: tgw 模块使用 Login (大写L)，而 AmazingData 使用 login (小写l)
                    sdk_candidates = ("AmazingData", "amazingdata", "tgw", "amazingdata_sdk")
                    for sdk_name in sdk_candidates:
                        try:
                            ad_module = __import__(sdk_name)
                            # 验证模块有正确的 login 函数 (检查两种大小写)
                            if hasattr(ad_module, 'login') and callable(getattr(ad_module, 'login', None)):
                                ad = cast(Any, ad_module)
                                sdk_imported = True
                                login_method_name = 'login'
                                logger.info(f"AmazingData SDK imported in worker process (package: {sdk_name}, login_method: login)")
                                break
                            elif hasattr(ad_module, 'Login') and callable(getattr(ad_module, 'Login', None)):
                                ad = cast(Any, ad_module)
                                sdk_imported = True
                                login_method_name = 'Login'
                                logger.info(f"AmazingData SDK imported in worker process (package: {sdk_name}, login_method: Login)")
                                break
                        except ImportError:
                            continue
                    
                    if not sdk_imported:
                        logger.warning(f"AmazingData SDK 导入失败，尝试了: {sdk_candidates}")
                        response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=f"AmazingData SDK 导入失败，尝试了: {sdk_candidates}",
                            error_type="ImportError",
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
                        # 使用检测到的login方法名 (login或Login)
                        login_func = getattr(ad, login_method_name or 'login', None) or getattr(ad, 'Login', None)
                        if login_func is None:
                            raise AttributeError(f"SDK module has no login/Login method (method_name={login_method_name})")
                        result = login_func(*request.args, **request.kwargs)
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

                    call_response: ProxyResponse | None = None
                    last_error: Optional[str] = None
                    for method_path, call_args, call_kwargs in attempts:
                        target = AmazingDataProcessProxy._resolve_callable(ad, method_path)
                        if target is None:
                            last_error = f"Method {method_path} not found"
                            continue
                        enforced_kwargs = dict(call_kwargs)
                        if request.request_type in {RequestType.GET_DATA, RequestType.SUBSCRIBE,
                                                    RequestType.UNSUBSCRIBE}:
                            if AmazingDataProcessProxy._method_supports_is_local(method_path, target):
                                enforced_kwargs.setdefault('is_local', False)
                        cache_policy = CachePolicy.from_kwargs(
                            context=method_path,
                            kwargs=enforced_kwargs,
                        )
                        enforced_kwargs = cache_policy.apply(enforced_kwargs)
                        call_started = time.perf_counter()
                        method_category = method_path.split(".", 1)[0] if method_path else "unknown"
                        should_log_category = method_category in {"InfoData", "MarketData"}
                        if should_log_category:
                            logger.debug(
                                "{} call invoking method={} args={} kwargs_keys={}",
                                method_category,
                                method_path,
                                AmazingDataProcessProxy._summarize_call_details(call_args),
                                sorted(enforced_kwargs.keys()),
                            )
                        try:
                            result = target(*tuple(call_args), **enforced_kwargs)
                            if inspect.iscoroutine(result):
                                # SDK方法返回了协程，需要执行它
                                # 由于worker loop看起来是同步的，我们需要创建一个临时的事件循环来运行它
                                # 或者简单的使用 asyncio.run (created new loop)
                                try:
                                    result = asyncio.run(result)
                                except RuntimeError:
                                    # 如果已经有运行中的loop (不太可能，因为这是在multiprocessing target中)，尝试其他方法
                                    loop = asyncio.new_event_loop()
                                    try:
                                        asyncio.set_event_loop(loop)
                                        result = loop.run_until_complete(result)
                                    finally:
                                        loop.close()

                            duration = time.perf_counter() - call_started
                            if should_log_category:
                                logger.info(
                                    "{} call success method={} duration={:.3f}s result={}",
                                    method_category,
                                    method_path,
                                    duration,
                                    _summarize_payload_shape(result),
                                )
                            call_response = ProxyResponse(
                                request_id=request.request_id,
                                success=True,
                                result=result,
                            )
                            break
                        except (AttributeError, TypeError) as exc:  # pragma: no cover - fallback
                            duration = time.perf_counter() - call_started
                            if should_log_category:
                                logger.warning(
                                    "{} call fallback method={} duration={:.3f}s args={} kwargs_keys={} error={}",
                                    method_category,
                                    method_path,
                                    duration,
                                    AmazingDataProcessProxy._summarize_call_details(call_args),
                                    sorted(enforced_kwargs.keys()),
                                    exc,
                                )
                            message = str(exc)
                            message_lower = message.lower()
                            if 'is_local' in enforced_kwargs and 'is_local' in message_lower and 'unexpected' in message_lower:
                                fallback_kwargs = dict(enforced_kwargs)
                                fallback_kwargs.pop('is_local', None)
                                try:
                                    fallback_result = target(*tuple(call_args), **fallback_kwargs)
                                    duration = time.perf_counter() - call_started
                                    if should_log_category:
                                        logger.info(
                                            "{} call success method={} duration={:.3f}s result={} (fallback)",
                                            method_category,
                                            method_path,
                                            duration,
                                            _summarize_payload_shape(fallback_result),
                                        )
                                    call_response = ProxyResponse(
                                        request_id=request.request_id,
                                        success=True,
                                        result=fallback_result,
                                    )
                                    break
                                except Exception as inner_exc:  # pragma: no cover - fallback
                                    last_error = f"{method_path}: {inner_exc}"
                                    continue
                            last_error = f"{method_path}: {exc}"
                            continue
                        except Exception as exc:  # pragma: no cover - final failure
                            duration = time.perf_counter() - call_started
                            if should_log_category:
                                logger.error(
                                    "{} call failed method={} duration={:.3f}s error={}",
                                    method_category,
                                    method_path,
                                    duration,
                                    exc,
                                )
                            call_response = ProxyResponse(
                                request_id=request.request_id,
                                success=False,
                                error=str(exc),
                                error_type=type(exc).__name__,
                            )
                            break

                    if call_response is None:
                        call_response = ProxyResponse(
                            request_id=request.request_id,
                            success=False,
                            error=last_error or f"Method {request.method} not found",
                            error_type="AttributeError",
                        )

                    response = call_response
                response.timestamp = time.time()
                response_queue.put(pickle.dumps(response.to_payload()))

            except queue.Empty:
                continue
            except (FileNotFoundError, EOFError, OSError) as exc:
                logger.info("Request queue closed, terminating worker: {}", exc)
                break
            except SystemExit as exc:
                logger.critical(f"SDK called SystemExit: {exc}")
                request_id = request.request_id if request else payload_request_id
                if request_id:
                    response = ProxyResponse(
                        request_id=request_id,
                        success=False,
                        error=f"SDK attempted to exit with code: {exc.code}",
                        error_type="SystemExit",
                    )
                    response.timestamp = time.time()
                    response_queue.put(pickle.dumps(response.to_payload()))
                break
            except Exception as exc:
                request_label = (
                    f"{request.request_type.name}:{request.method}"
                    if request and request.method
                    else request.request_type.name
                    if request
                    else "unknown"
                )
                request_identifier = request.request_id if request else payload_request_id
                logger.opt(exception=exc).error(
                    "Worker loop error while processing {} (request_id={})",
                    request_label,
                    request_identifier,
                )
                request_id = request_identifier
                if request_id:
                    response = ProxyResponse(
                        request_id=request_id,
                        success=False,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    response.timestamp = time.time()
                    response_queue.put(pickle.dumps(response.to_payload()))
                else:
                    logger.error("Unable to emit response because request_id is missing")

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
    def _summarize_call_details(args: Sequence[Any]) -> str:
        """对调用参数进行摘要，避免日志输出过长。"""

        if not args:
            return "[]"
        summaries: list[str] = []
        for index, arg in enumerate(args):
            if index >= 3:
                summaries.append(f"...(+{len(args) - index})")
                break
            summaries.append(_summarize_payload_shape(arg))
        return "[" + ", ".join(summaries) + "]"

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

    @classmethod
    def _method_supports_is_local(
            cls,
            method_key: str,
            callable_obj: Callable[..., Any],
    ) -> bool:
        cached = cls._IS_LOCAL_COMPAT_CACHE.get(method_key)
        if cached is not None:
            return cached

        supports = False
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            supports = False
        else:
            for parameter in signature.parameters.values():
                if parameter.kind in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                ) and parameter.name == "is_local":
                    supports = True
                    break
                if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                    supports = True
                    break

        cls._IS_LOCAL_COMPAT_CACHE[method_key] = supports
        return supports

    @classmethod
    def _ensure_market_calendar(cls, sdk: Any) -> Sequence[int] | None:
        if cls._MARKET_CALENDAR_CACHE is not None:
            return cls._MARKET_CALENDAR_CACHE

        base_cls = getattr(sdk, "BaseData", None)
        if not callable(base_cls):
            return None

        try:
            base_instance = base_cls()
        except Exception:  # pragma: no cover - base class instantiation depends on SDK
            return None

        try:
            raw_calendar = base_instance.get_calendar()
        except Exception:  # pragma: no cover - external SDK behaviour
            return None

        if not isinstance(raw_calendar, Sequence) or isinstance(raw_calendar, (str, bytes, bytearray)):
            return None

        try:
            normalized_calendar = tuple(int(item) for item in raw_calendar)
        except (TypeError, ValueError):
            return None

        cls._MARKET_CALENDAR_CACHE = normalized_calendar
        return normalized_calendar

    @classmethod
    def _instantiate_class(cls, sdk: Any, class_obj: type, class_name: str) -> Any | None:
        cached = cls._CLASS_INSTANCE_CACHE.get(class_obj)
        if cached is not None:
            return cached

        instance: Any | None = None
        try:
            instance = class_obj()
        except TypeError:
            instance = None
        except Exception:  # pragma: no cover - SDK constructor failures
            instance = None

        if instance is None and class_name == "MarketData":
            calendar = cls._ensure_market_calendar(sdk)
            if calendar is not None:
                try:
                    instance = class_obj(calendar)
                except TypeError:
                    try:
                        instance = class_obj(calendar=calendar)
                    except Exception:  # pragma: no cover - depends on SDK
                        instance = None
                except Exception:  # pragma: no cover - depends on SDK
                    instance = None
            if instance is None:
                try:
                    instance = class_obj(None)
                except Exception:  # pragma: no cover - depends on SDK
                    instance = None

        if instance is None:
            return None

        cls._CLASS_INSTANCE_CACHE[class_obj] = instance
        return instance

    @classmethod
    def _resolve_callable(cls, target: Any, method_path: str) -> Callable[..., Any] | None:
        """支持带点路径的属性访问，必要时自动实例化类。"""

        current = target
        for attr in method_path.split("."):
            if not attr:
                continue
            candidate = getattr(current, attr, None)
            if candidate is None:
                return None
            if isinstance(candidate, type):
                instance = cls._instantiate_class(target, candidate, attr)
                if instance is None:
                    return None
                current = instance
                continue
            current = candidate

        return current if callable(current) else None
