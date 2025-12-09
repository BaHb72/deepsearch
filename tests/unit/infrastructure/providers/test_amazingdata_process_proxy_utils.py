import os
import time

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    AmazingDataProcessProxy,
)


def test_summarize_worker_exit_with_signal():
    proxy = AmazingDataProcessProxy()

    class DummyProcess:
        pid = 321
        exitcode = -15

    proxy.worker_process = DummyProcess()
    summary = proxy._summarize_worker_exit()
    assert summary["pid"] == 321
    assert summary["exitcode"] == -15
    assert summary["signal"] == 15


def test_health_check_marks_logged_in_when_process_missing():
    proxy = AmazingDataProcessProxy()
    proxy.last_login_username = "tester"
    proxy.worker_process = None
    proxy.is_running = False

    payload = proxy.health_check()

    assert payload["status"] == "error"
    assert payload["loggedIn"] is True


def test_handle_worker_exit_code_zero_without_restart(monkeypatch):
    proxy = AmazingDataProcessProxy()
    proxy.restart_on_crash = True
    proxy.is_running = True

    class DummyProcess:
        pid = 456
        exitcode = 0

    proxy.worker_process = DummyProcess()
    proxy.request_queue = None
    proxy.response_queue = None

    start_calls = {"count": 0}

    def fake_start():
        start_calls["count"] += 1
        return True

    monkeypatch.setattr(proxy, "start", fake_start)

    response = proxy._handle_worker_crash("req-1")

    assert response.success is False
    assert response.error_type == "ProcessExit"
    assert proxy.is_running is False
    assert proxy.stats["process_restarts"] == 0
    assert proxy.stats["last_crash_reason"] == "process_exit_clean"
    assert start_calls["count"] == 0


def test_start_respects_restart_backoff(monkeypatch):
    proxy = AmazingDataProcessProxy()
    proxy.is_running = False
    proxy.worker_process = None
    proxy._next_restart_time = time.time() + 5
    proxy._pending_restart_reason = "backoff_test"

    call_count = {"count": 0}

    def fake_start_local(self):
        call_count["count"] += 1
        return True

    monkeypatch.setattr(AmazingDataProcessProxy, "_start_local_worker", fake_start_local)

    result = proxy.start()

    assert result is False
    assert proxy._last_start_failure_type == "RestartBackoff"
    assert "delayed" in (proxy._last_start_failure or "")
    assert proxy.stats["last_start_failure"]
    assert proxy._worker_lock_handle is None
    assert call_count["count"] == 0


def test_start_blocked_by_existing_lock(monkeypatch, tmp_path):
    os.environ["DEEPSEARCH_AMAZINGDATA_LOCK_DIR"] = str(tmp_path)
    proxy1 = AmazingDataProcessProxy()
    proxy2 = AmazingDataProcessProxy()

    def fake_start_local(self):
        self.worker_process = type("P", (), {"is_alive": lambda self: True})()
        self.is_running = True
        return True

    monkeypatch.setattr(AmazingDataProcessProxy, "_start_local_worker", fake_start_local)

    try:
        assert proxy1.start() is True
        assert proxy1._worker_lock_handle is not None

        result = proxy2.start()
        assert result is False
        assert proxy2._last_start_failure_type == "WorkerLockBusy"
        assert proxy2.stats["last_start_failure"] == "Worker lock busy"
    finally:
        proxy1.is_running = False
        proxy1._release_worker_lock()
        os.environ.pop("DEEPSEARCH_AMAZINGDATA_LOCK_DIR", None)
