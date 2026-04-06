from __future__ import annotations

import sys

from core.core.runtime import async_runner


def test_run_async_engine_normal_exit_also_shutdowns_process_manager(monkeypatch):
    run_calls: list[str] = []
    shutdown_calls: list[tuple[float, bool]] = []

    def fake_asyncio_run(coro):
        coro.close()
        run_calls.append("called")

    def fake_shutdown(*, timeout: float, force: bool):
        shutdown_calls.append((timeout, force))

    monkeypatch.setattr(async_runner.asyncio, "run", fake_asyncio_run)
    monkeypatch.setattr(async_runner.process_manager, "shutdown", fake_shutdown)

    async_runner.run_async_engine(mode="engine", config={"no_frontend": True})

    assert run_calls == ["called"]
    assert shutdown_calls == [(10.0, sys.platform == "win32")]


def test_run_async_engine_keyboard_interrupt_still_shutdowns_process_manager(monkeypatch):
    shutdown_calls: list[tuple[float, bool]] = []

    def fake_asyncio_run(coro):
        coro.close()
        raise KeyboardInterrupt

    def fake_shutdown(*, timeout: float, force: bool):
        shutdown_calls.append((timeout, force))

    monkeypatch.setattr(async_runner.asyncio, "run", fake_asyncio_run)
    monkeypatch.setattr(async_runner.process_manager, "shutdown", fake_shutdown)

    async_runner.run_async_engine()

    assert shutdown_calls == [(10.0, sys.platform == "win32")]
