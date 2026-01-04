import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")

from core.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    RequestType,
)

EXTERNAL_EXECUTABLE = Path(os.environ.get("DEEPSEARCH_AMAZINGDATA_EXTERNAL_PYTHON", sys.executable))

_required_modules = ["pandas", "pydantic", "redis"]
_missing_deps: list[str] = []
if EXTERNAL_EXECUTABLE.exists():
    for name in _required_modules:
        result = subprocess.run(
            [str(EXTERNAL_EXECUTABLE), "-c", f"import {name}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _missing_deps.append(name)

if not EXTERNAL_EXECUTABLE.exists():
    EXTERNAL_SKIP_REASON = (
        "AmazingData 外部解释器未找到，请设置 DEEPSEARCH_AMAZINGDATA_EXTERNAL_PYTHON"
    )
elif _missing_deps:
    modules = ", ".join(_missing_deps)
    EXTERNAL_SKIP_REASON = f"AmazingData 外部解释器缺少依赖: {modules}"
else:
    EXTERNAL_SKIP_REASON = ""

EXTERNAL_SKIP_CONDITION = bool(EXTERNAL_SKIP_REASON)


@pytest.mark.asyncio
async def test_process_proxy_start_async_uses_to_thread(monkeypatch):
    proxy = AmazingDataProcessProxy(python_executable="dummy")
    proxy.is_running = False
    monkeypatch.setattr(proxy, "_is_worker_alive", lambda: False)

    start_called = False

    def fake_start() -> bool:
        nonlocal start_called
        start_called = True
        return True

    to_thread_called = False

    async def fake_to_thread(func, *args, **kwargs):
        nonlocal to_thread_called
        to_thread_called = True
        return func(*args, **kwargs)

    monkeypatch.setattr(proxy, "start", fake_start)
    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    result = await proxy.start_async()

    assert result is True
    assert start_called is True
    assert to_thread_called is True


@pytest.mark.skipif(
    EXTERNAL_SKIP_CONDITION, reason=EXTERNAL_SKIP_REASON or "AmazingData 外部解释器不可用"
)
def test_amazingdata_proxy_external_worker(tmp_path):
    pandas_stub = tmp_path / "pandas"
    pandas_stub.mkdir()
    (pandas_stub / "__init__.py").write_text(
        """# Minimal pandas stub for AmazingData worker tests
class DataFrame(dict):
    def to_dict(self, *_, **__):
        return dict(self)

class Series(list):
    pass

class Index(list):
    pass

class Timestamp(str):
    pass

NaT = None

def concat(objs, *_, **__):
    return DataFrame()

def to_datetime(value, *_, **__):
    return value

__all__ = ["DataFrame", "Series", "Index", "Timestamp", "NaT", "concat", "to_datetime"]
""",
        encoding="utf-8",
    )
    redis_stub = tmp_path / "redis"
    redis_stub.mkdir()
    redis_stub_init = redis_stub / "__init__.py"
    redis_stub_content = "\n".join(
        [
            "class Redis:",
            "    def __init__(self, *_, **__):",
            "        pass",
            "",
            "    def ping(self):",
            "        return True",
            "",
            "    def close(self):",
            "        pass",
            "",
            "class RedisError(Exception):",
            "    pass",
            "",
            "import sys",
            "from types import SimpleNamespace",
            "",
            "exceptions = SimpleNamespace(RedisError=RedisError)",
            'sys.modules[__name__ + ".exceptions"] = exceptions',
            "",
            '__all__ = ["Redis", "RedisError", "exceptions"]',
        ]
    )
    redis_stub_init.write_text(redis_stub_content, encoding="utf-8")
    extra_path = str(tmp_path)
    existing_path = os.environ.get("PYTHONPATH", "")
    combined_path = os.pathsep.join(filter(None, [extra_path, existing_path]))

    proxy = AmazingDataProcessProxy(
        python_executable=str(EXTERNAL_EXECUTABLE),
        worker_env={
            "DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub",
            "PYTHONPATH": combined_path,
        },
        startup_timeout=15.0,
    )

    try:
        assert proxy.start(), "external worker should start successfully"
        assert proxy.worker_process is not None
        assert proxy.is_worker_alive()

        response = proxy.execute(
            "login",
            "test_user",
            "password",
            "127.0.0.1",
            8600,
            request_type=RequestType.LOGIN,
            timeout=5.0,
        )
        assert response.success, response.error

        health = proxy.execute(
            "health_check",
            request_type=RequestType.HEALTH_CHECK,
            timeout=5.0,
        )
        assert health.success
        assert isinstance(health.result, dict)
        assert health.result.get("status") == "ok"

        version = proxy.execute(
            "get_version",
            timeout=5.0,
        )
        assert version.success
        assert version.result == "amazingdata-stub-3.0"

    finally:
        proxy.stop(with_logout=True)
        assert not proxy.is_worker_alive()
