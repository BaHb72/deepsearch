# encoding:utf-8
"""
AmazingData process pool manager.

Maintains dedicated worker processes per data source so adapters remain
isolated and faults do not cascade between strategies.

Author: DeepSearch Team
Version: 2.1.0
Date: 2025-10-11
"""

from __future__ import annotations

import multiprocessing as mp
import random
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple, TypedDict, cast

from loguru import logger
from typing_extensions import NotRequired

from .amazingdata_process_proxy import AmazingDataProcessProxy

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

WorkerProcess = mp.Process | subprocess.Popen[bytes] | None


class ProcessStatusEntry(TypedDict, total=False):
    """Snapshot of runtime state for a single worker process."""

    pid: int | None
    is_running: bool
    created_at: float
    last_used: float
    uptime_seconds: float
    restart_count: int
    requests_completed: int
    requests_failed: int
    auto_cleanup: bool
    reuse_count: NotRequired[int]
    is_test: NotRequired[bool]
    throttle: NotRequired[Dict[str, Any]]
    pending_login: NotRequired[bool]
    last_login_started_at: NotRequired[Optional[str]]
    last_login_completed_at: NotRequired[Optional[str]]
    last_login_success_at: NotRequired[Optional[str]]
    last_login_error_at: NotRequired[Optional[str]]
    last_login_error_reason: NotRequired[Optional[str]]
    last_health_status: NotRequired[Dict[str, Any]]
    last_health_check_at: NotRequired[Optional[str]]


class ProcessPoolStatus(TypedDict):
    """Aggregate metrics describing the entire process pool."""

    total_processes: int
    max_processes: int
    processes: Dict[str, ProcessStatusEntry]


class LoginThrottle:
    """Serialize login attempts with a simple backoff schedule."""

    _SCHEDULE = (5.0, 10.0, 20.0)

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._in_progress = False
        self._backoff_index = 0
        self._next_allowed = 0.0
        self._failure_streak = 0
        self._last_result_at = 0.0

    def wait_slot(self) -> None:
        """Block until the throttle allows another login attempt."""
        with self._condition:
            while self._in_progress:
                self._condition.wait()

            now = time.time()
            if now < self._next_allowed:
                self._condition.wait(timeout=self._next_allowed - now)

            self._in_progress = True

    def record_result(self, success: bool) -> None:
        """Update throttle state according to the login outcome."""
        with self._condition:
            now = time.time()
            if success:
                self._backoff_index = 0
                self._next_allowed = now
                self._failure_streak = 0
            else:
                index = min(self._backoff_index, len(self._SCHEDULE) - 1)
                base_delay = self._SCHEDULE[index]
                jitter = random.uniform(0.8, 1.2)
                self._next_allowed = now + base_delay * jitter
                if self._backoff_index < len(self._SCHEDULE) - 1:
                    self._backoff_index += 1
                self._failure_streak += 1
            self._last_result_at = now

            self._in_progress = False
            self._condition.notify_all()

    def get_state(self) -> Dict[str, Any]:
        """Expose current throttle metrics."""
        with self._condition:
            return {
                "in_progress": self._in_progress,
                "next_allowed": self._next_allowed,
                "backoff_index": self._backoff_index,
                "failure_streak": self._failure_streak,
                "last_result_at": self._last_result_at,
            }


@dataclass
class ProcessHandle:
    """Container that tracks a worker process and its metadata."""

    datasource_id: str
    proxy: AmazingDataProcessProxy
    created_at: float
    last_used: float
    auto_cleanup: bool = False
    cleanup_delay: float = 60.0
    config: dict[str, Any] = field(default_factory=dict)
    restart_count: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    reuse_count: int = 0
    reuse_window: float | None = None
    login_throttle: LoginThrottle = field(default_factory=LoginThrottle)
    last_login_started_at: float | None = None
    last_login_completed_at: float | None = None
    last_login_success_at: float | None = None
    last_login_error_at: float | None = None
    last_login_error_reason: str | None = None
    is_test: bool = False
    last_health_status: dict[str, Any] | None = None
    last_health_check_at: float | None = None
    health_failure_streak: int = 0

    def mark_used(self) -> None:
        """Refresh the last-used timestamp."""
        self.last_used = time.time()

    def should_reuse(self, now: float) -> bool:
        """Return True if the worker is still inside the reuse window."""
        if not self.is_test:
            return True
        if self.reuse_window is None:
            return True
        return now - self.created_at <= self.reuse_window

    def uptime(self, now: float) -> float:
        """Return the worker uptime in seconds."""
        return max(0.0, now - self.created_at)

    def clone_config(self) -> dict[str, Any]:
        """Return a shallow copy of the stored configuration."""
        return dict(self.config)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_worker_process(proxy: AmazingDataProcessProxy) -> WorkerProcess:
    return cast(WorkerProcess, proxy.worker_process)


def _get_worker_pid(proxy: AmazingDataProcessProxy) -> int | None:
    process = _get_worker_process(proxy)
    if process is None:
        return None
    pid = getattr(process, "pid", None)
    try:
        return int(pid) if pid is not None else None
    except (TypeError, ValueError):
        return None


def _is_worker_alive(process: WorkerProcess) -> bool:
    if process is None:
        return False
    if isinstance(process, mp.Process):
        return process.is_alive()
    if isinstance(process, subprocess.Popen):
        return process.poll() is None
    return False


def _terminate_worker(process: WorkerProcess, *, force: bool) -> None:
    if process is None:
        return
    try:
        if force and hasattr(process, "kill"):
            process.kill()  # type: ignore[attr-defined]
        else:
            process.terminate()  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug(f"[ProcessPool] Failed to terminate worker cleanly: {exc}")


def _safe_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_timestamp(value: Optional[float]) -> Optional[str]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _normalise_health_status(raw: Any) -> Dict[str, Any]:
    """Standardise the payload returned by proxy.health_check()."""
    timestamp = time.time()
    if isinstance(raw, Mapping):
        payload = dict(raw)
        payload["status"] = str(payload.get("status") or "unknown").lower()
        if "timestamp" not in payload or not isinstance(payload["timestamp"], (int, float)):
            payload["timestamp"] = timestamp
        return payload
    if isinstance(raw, bool):
        return {"status": "ok" if raw else "error", "timestamp": timestamp}
    return {"status": "unknown", "timestamp": timestamp}


def _log_health_transition(
        datasource_id: str,
        previous_status: Optional[str],
        health: Mapping[str, Any],
) -> None:
    """Emit concise log when health status changes."""
    status = str(health.get("status") or "unknown")
    prev = previous_status or "unknown"
    summary: Dict[str, Any] = {}
    for key in ("loggedIn", "usernameHint", "latencyMs"):
        if key in health:
            summary[key] = health[key]
    if "errors" in health:
        summary["errors"] = health["errors"]
    if "probe" in health:
        summary["probe"] = health["probe"]

    if status == "ok":
        logger.info(
            f"[ProcessPool] Health status for {datasource_id}: {prev} -> ok ({summary})"
        )
    elif status == "degraded":
        logger.warning(
            f"[ProcessPool] Health degraded for {datasource_id}: {prev} -> degraded ({summary})"
        )
    else:
        logger.error(
            f"[ProcessPool] Health error for {datasource_id}: {prev} -> {status} ({summary})"
        )


# ---------------------------------------------------------------------------
# Process pool implementation
# ---------------------------------------------------------------------------


class AmazingDataProcessPool:
    """Manage AmazingData worker processes: spawn, reuse, cleanup and monitor."""

    def __init__(self, max_processes: int = 10) -> None:
        """Initialise pool state and supporting structures."""
        self.max_processes = max_processes
        self._handles: Dict[str, ProcessHandle] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=3)
        self._datasource_locks: Dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._degraded_restart_threshold = 3
        self._start_health_monitor()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def _get_datasource_lock(self, datasource_id: str) -> threading.RLock:
        with self._locks_guard:
            lock = self._datasource_locks.get(datasource_id)
            if lock is None:
                lock = threading.RLock()
                self._datasource_locks[datasource_id] = lock
            return lock

    @contextmanager
    def _guard_datasource(self, datasource_id: str):
        lock = self._get_datasource_lock(datasource_id)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def get_test_process(
        self,
        datasource_type: str = "amazingdata",
        reuse_window: float = 30.0,
    ) -> Tuple[AmazingDataProcessProxy, str]:
        """Return or create a reusable process dedicated to integration tests."""
        current_time = time.time()
        test_process_id = f"{datasource_type}_test"

        with self.lock:
            handle = self._handles.get(test_process_id)
            if handle:
                proxy = handle.proxy
                handle.reuse_window = reuse_window
                age = current_time - handle.created_at

                if proxy.is_running and handle.should_reuse(current_time):
                    handle.reuse_count += 1
                    handle.mark_used()
                    pid = _get_worker_pid(proxy)
                    pid_info = pid if pid is not None else "unknown"
                    logger.info(
                        f"[ProcessPool] Reusing test process {test_process_id} "
                        f"(age: {age:.1f}s, reuse_count: {handle.reuse_count}, pid={pid_info})"
                    )
                    return proxy, test_process_id

                if age > reuse_window:
                    logger.info(
                        f"[ProcessPool] Test process expired "
                        f"(age {age:.1f}s > {reuse_window:.1f}s)"
                    )
                else:
                    logger.warning("[ProcessPool] Test process dead, creating a new one")

        # Reuse failed or process missing; tear down before creating a fresh one.
        self.stop(test_process_id, with_logout=True)

        logger.info(f"[ProcessPool] Creating new test process {test_process_id}")
        proxy = AmazingDataProcessProxy(restart_on_crash=False)
        if not proxy.start():
            raise RuntimeError("Failed to start test process")

        now = time.time()
        handle = ProcessHandle(
            datasource_id=test_process_id,
            proxy=proxy,
            created_at=now,
            last_used=now,
            auto_cleanup=False,
            cleanup_delay=0.0,
            config={},
            is_test=True,
            reuse_window=reuse_window,
        )

        with self.lock:
            self._handles[test_process_id] = handle

        pid = _get_worker_pid(proxy)
        pid_info = pid if pid is not None else "unknown"
        logger.info(f"[ProcessPool] Test process created (PID: {pid_info})")
        return proxy, test_process_id

    def get_or_create(
        self,
        datasource_id: str,
        auto_cleanup: bool = False,
        cleanup_delay: float = 60.0,
        config: Optional[Mapping[str, Any]] = None,
    ) -> AmazingDataProcessProxy:
        """
        Return an existing worker for the data source or start a new one.

        Raises:
            RuntimeError: if the process cannot be created.
        """
        with self._guard_datasource(datasource_id):
            self._cleanup_idle_processes()

            with self.lock:
                handle = self._handles.get(datasource_id)
                if handle:
                    proxy = handle.proxy
                    if proxy.is_running:
                        handle.mark_used()
                        logger.info(f"[ProcessPool] Reusing process for {datasource_id}")
                        return proxy
                    logger.warning(f"[ProcessPool] Dead process detected for {datasource_id}")
                if len(self._handles) >= self.max_processes:
                    logger.debug(
                        "[ProcessPool] Max processes reached, attempting idle cleanup"
                    )

            if handle:
                self.stop(datasource_id)

            config_dict = dict(config or {})

            with self.lock:
                if len(self._handles) >= self.max_processes:
                    raise RuntimeError(
                        f"Reached max process limit ({self.max_processes}), "
                        f"cannot create {datasource_id}"
                    )

                logger.info(f"[ProcessPool] Creating new process for {datasource_id}")
                proxy = self._create_proxy(config_dict, auto_cleanup)
                if not proxy.start():
                    raise RuntimeError(f"Failed to start process for {datasource_id}")

                now = time.time()
                handle = ProcessHandle(
                    datasource_id=datasource_id,
                    proxy=proxy,
                    created_at=now,
                    last_used=now,
                    auto_cleanup=auto_cleanup,
                    cleanup_delay=cleanup_delay,
                    config=dict(config_dict),
                )
                self._handles[datasource_id] = handle

            if auto_cleanup:
                self.executor.submit(self._schedule_cleanup, datasource_id, cleanup_delay)

            pid = _get_worker_pid(proxy)
            pid_info = pid if pid is not None else "unknown"
            logger.info(f"[ProcessPool] Process created for {datasource_id} (PID: {pid_info})")
            return proxy

    def stop(self, datasource_id: str, force: bool = False, with_logout: bool = True) -> bool:
        """Stop the worker process bound to the given datasource."""
        with self._guard_datasource(datasource_id):
            with self.lock:
                handle = self._handles.get(datasource_id)
                if not handle:
                    return True

            proxy = handle.proxy
            logger.info(
                f"[ProcessPool] Stopping process for {datasource_id} (with_logout={with_logout})"
            )

            success = bool(
                proxy.stop(
                    timeout=5.0 if not force else 1.0,
                    with_logout=with_logout,
                )
            )

            if not success and force:
                logger.warning(f"[ProcessPool] Force killing process for {datasource_id}")
                _terminate_worker(_get_worker_process(proxy), force=True)

            with self.lock:
                self._handles.pop(datasource_id, None)

            return success

    def stop_all(self, force: bool = False) -> None:
        """Stop every active worker process managed by the pool."""
        logger.info("[ProcessPool] Stopping all processes")
        for datasource_id in self._snapshot_ids():
            self.stop(datasource_id, force=force)

    def restart(self, datasource_id: str, *, with_logout: bool | None = None) -> bool:
        """Restart the worker process for the specified datasource."""
        logger.info(f"[ProcessPool] Restarting process for {datasource_id}")
        with self._guard_datasource(datasource_id):
            with self.lock:
                handle = self._handles.get(datasource_id)
                stored_config = handle.clone_config() if handle else {}
                auto_cleanup = handle.auto_cleanup if handle else False

            stop_with_logout = True if with_logout is None else with_logout
            self.stop(datasource_id, with_logout=stop_with_logout)

            try:
                proxy = self.get_or_create(
                    datasource_id,
                    auto_cleanup=auto_cleanup,
                    config=stored_config,
                )
                with self.lock:
                    new_handle = self._handles.get(datasource_id)
                    if new_handle:
                        new_handle.restart_count += 1
                return proxy is not None
            except Exception as exc:
                logger.error(f"[ProcessPool] Failed to restart process: {exc}")
                return False

    def wait_for_login_slot(self, datasource_id: str) -> None:
        """Acquire a throttle slot before performing a login operation."""
        lock = self._get_datasource_lock(datasource_id)
        with lock:
            with self.lock:
                handle = self._handles.get(datasource_id)
            if not handle:
                return
            handle.login_throttle.wait_slot()
            with self.lock:
                handle.last_login_started_at = time.time()
                handle.last_login_error_reason = None

    def record_login_result(
            self, datasource_id: str, success: bool, error: Optional[str] = None
    ) -> None:
        """Record the outcome of a login attempt for throttle bookkeeping."""
        lock = self._get_datasource_lock(datasource_id)
        with lock:
            with self.lock:
                handle = self._handles.get(datasource_id)
            if not handle:
                return
            handle.login_throttle.record_result(success)
            timestamp = time.time()
            with self.lock:
                handle.last_login_completed_at = timestamp
                if success:
                    handle.last_login_success_at = timestamp
                    handle.last_login_error_reason = None
                else:
                    handle.last_login_error_at = timestamp
                    handle.last_login_error_reason = str(error) if error else None

    def get_status(self) -> ProcessPoolStatus:
        """Return a snapshot describing the current process pool state."""
        with self.lock:
            handles_snapshot = list(self._handles.items())

        process_entries: Dict[str, ProcessStatusEntry] = {}
        now = time.time()

        for datasource_id, handle in handles_snapshot:
            proxy = handle.proxy
            stats = proxy.get_stats()
            pid = _get_worker_pid(proxy)

            entry: ProcessStatusEntry = {
                "pid": pid,
                "is_running": proxy.is_running and _is_worker_alive(_get_worker_process(proxy)),
                "created_at": handle.created_at,
                "last_used": handle.last_used,
                "uptime_seconds": handle.uptime(now),
                "restart_count": handle.restart_count,
                "requests_completed": _safe_int(stats, "requests_completed"),
                "requests_failed": _safe_int(stats, "requests_failed"),
                "auto_cleanup": handle.auto_cleanup,
            }
            throttle_state = handle.login_throttle.get_state()
            if throttle_state:
                next_allowed = float(throttle_state.get("next_allowed") or 0.0)
                wait_seconds = max(0.0, next_allowed - now) if next_allowed > 0 else 0.0
                entry["throttle"] = {
                    "inProgress": bool(throttle_state.get("in_progress")),
                    "nextAllowedAt": _format_timestamp(next_allowed),
                    "waitSeconds": wait_seconds,
                    "backoffLevel": int(throttle_state.get("backoff_index", 0)),
                    "failureStreak": int(throttle_state.get("failure_streak", 0)),
                }
                entry["pending_login"] = bool(throttle_state.get("in_progress"))
            entry["last_login_started_at"] = _format_timestamp(handle.last_login_started_at)
            entry["last_login_completed_at"] = _format_timestamp(handle.last_login_completed_at)
            entry["last_login_success_at"] = _format_timestamp(handle.last_login_success_at)
            entry["last_login_error_at"] = _format_timestamp(handle.last_login_error_at)
            entry["last_login_error_reason"] = handle.last_login_error_reason
            if handle.last_health_status:
                entry["last_health_status"] = dict(handle.last_health_status)
            entry["last_health_check_at"] = _format_timestamp(handle.last_health_check_at)

            if handle.is_test:
                entry["is_test"] = True
            if handle.reuse_count:
                entry["reuse_count"] = handle.reuse_count

            process_entries[datasource_id] = entry

        return {
            "total_processes": len(process_entries),
            "max_processes": self.max_processes,
            "processes": process_entries,
        }

    # ------------------------------------------------------------------ #
    # Internal utilities
    # ------------------------------------------------------------------ #

    def _snapshot_ids(self) -> list[str]:
        with self.lock:
            return list(self._handles.keys())

    def _cleanup_idle_processes(self) -> None:
        """Clean up worker processes that have been idle for too long."""
        idle_threshold = 300  # five minutes
        current_time = time.time()
        candidates: list[Tuple[str, float]] = []

        with self.lock:
            for datasource_id, handle in list(self._handles.items()):
                if handle.auto_cleanup:
                    continue
                elapsed = current_time - handle.last_used
                if elapsed > idle_threshold:
                    candidates.append((datasource_id, elapsed))

        for datasource_id, elapsed in candidates:
            logger.info(
                f"[ProcessPool] Cleaning idle process: {datasource_id} (idle {elapsed:.0f}s)"
            )
            self.stop(datasource_id)

    def _schedule_cleanup(self, datasource_id: str, delay: float) -> None:
        """Trigger deferred auto-cleanup for the given datasource."""
        time.sleep(delay)
        should_cleanup = False
        with self.lock:
            handle = self._handles.get(datasource_id)
            if handle and handle.auto_cleanup:
                should_cleanup = True

        if should_cleanup:
            logger.info(f"[ProcessPool] Auto-cleanup triggered for {datasource_id}")
            self.stop(datasource_id)

    def _create_proxy(
        self,
        config: Mapping[str, Any],
        auto_cleanup: bool,
    ) -> AmazingDataProcessProxy:
        """Build a process proxy instance according to configuration."""
        python_executable_raw = str(config.get("python_executable", "") or "").strip()
        python_executable = python_executable_raw or None

        raw_worker_env = config.get("worker_env")
        worker_env: dict[str, str] | None = None
        if isinstance(raw_worker_env, Mapping):
            worker_env = {str(key): str(value) for key, value in raw_worker_env.items()}
        elif isinstance(raw_worker_env, dict):
            worker_env = {str(key): str(value) for key, value in raw_worker_env.items()}

        max_workers_raw = config.get("max_workers")
        try:
            max_workers = int(max_workers_raw) if max_workers_raw is not None else 1
        except (TypeError, ValueError):
            max_workers = 1
        max_workers = max(1, max_workers)

        startup_timeout_raw = config.get("startup_timeout")
        try:
            startup_timeout = (
                float(startup_timeout_raw) if startup_timeout_raw is not None else 10.0
            )
        except (TypeError, ValueError):
            startup_timeout = 10.0

        return AmazingDataProcessProxy(
            max_workers=max_workers,
            restart_on_crash=not auto_cleanup,
            python_executable=python_executable,
            worker_env=worker_env,
            startup_timeout=startup_timeout,
        )

    def _start_health_monitor(self) -> None:
        """Start a daemon thread that checks worker health periodically."""

        def monitor() -> None:
            while True:
                time.sleep(30)
                self._check_process_health()

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _check_process_health(self) -> None:
        """Inspect worker processes and restart unhealthy ones."""
        restart_targets: list[tuple[str, bool, int]] = []
        with self.lock:
            handles_snapshot = list(self._handles.items())

        for datasource_id, handle in handles_snapshot:
            proxy = handle.proxy
            try:
                raw_health = proxy.health_check()
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(f"[ProcessPool] Health check raised for {datasource_id}: {exc}")
                raw_health = {"status": "error", "error": str(exc)}

            health = _normalise_health_status(raw_health)
            status_value = str(health.get("status") or "unknown").lower()
            previous_status = (
                str(handle.last_health_status.get("status")).lower()
                if handle.last_health_status and "status" in handle.last_health_status
                else None
            )

            record_time = health.get("timestamp")
            if not isinstance(record_time, (int, float)):
                record_time = time.time()

            logged_in = bool(health.get("loggedIn"))
            failure_streak = 0

            with self.lock:
                current_handle = self._handles.get(datasource_id)
                if current_handle:
                    current_handle.last_health_status = dict(health)
                    current_handle.last_health_check_at = record_time
                    if status_value == "ok":
                        current_handle.health_failure_streak = 0
                    elif status_value in {"degraded", "error"}:
                        current_handle.health_failure_streak += 1
                    else:
                        current_handle.health_failure_streak = min(
                            current_handle.health_failure_streak + 1, self._degraded_restart_threshold
                        )
                    failure_streak = current_handle.health_failure_streak

            if previous_status != status_value:
                _log_health_transition(datasource_id, previous_status, health)

            if status_value == "error":
                if failure_streak >= 1:
                    restart_targets.append((datasource_id, logged_in, failure_streak))
            elif status_value == "degraded":
                errors = health.get("errors") or []
                if errors and failure_streak >= self._degraded_restart_threshold:
                    restart_targets.append((datasource_id, logged_in, failure_streak))

        for datasource_id, logged_in, streak in restart_targets:
            reason_label = "logged-in failure" if logged_in else "pre-login failure"
            logger.warning(
                f"[ProcessPool] Restarting unhealthy process {datasource_id} after {reason_label} streak (count={streak})"
            )
            self.restart(datasource_id, with_logout=logged_in)


_global_pool: Optional[AmazingDataProcessPool] = None


def get_global_pool() -> AmazingDataProcessPool:
    """Return the singleton AmazingData process pool."""
    global _global_pool
    if _global_pool is None:
        _global_pool = AmazingDataProcessPool()
    return _global_pool


def shutdown_pool() -> None:
    """Shut down and clear the singleton AmazingData process pool."""
    global _global_pool
    if _global_pool:
        _global_pool.stop_all(force=True)
        _global_pool = None
