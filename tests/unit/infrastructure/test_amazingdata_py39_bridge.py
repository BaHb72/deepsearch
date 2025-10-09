import asyncio
import os
from pathlib import Path

import pytest

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")


from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
    AmazingDataProcessProxy,
    RequestType,
)

if os.name == "nt":
    PY39_EXECUTABLE = Path("runtime/interpreters/py39/Scripts/python.exe")
    PY39_SITE_PACKAGES = PY39_EXECUTABLE.parent.parent / "Lib" / "site-packages"
else:
    PY39_EXECUTABLE = Path("runtime/interpreters/py39/bin/python")
    PY39_SITE_PACKAGES = PY39_EXECUTABLE.parent.parent / "lib" / "python3.9" / "site-packages"

_required_modules = ["pandas", "pydantic", "redis"]
_missing_deps: list[str] = []
if PY39_SITE_PACKAGES.exists():
    _missing_deps = [name for name in _required_modules if not (PY39_SITE_PACKAGES / name).exists()]
if not PY39_EXECUTABLE.exists():
    PY39_SKIP_REASON = "Python 3.9 interpreter not available"
elif _missing_deps:
    PY39_SKIP_REASON = "Python 3.9 runtime missing dependencies: {}".format(
        ", ".join(_missing_deps)
    )
else:
    PY39_SKIP_REASON = ""
PY39_SKIP_CONDITION = bool(PY39_SKIP_REASON)


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
    PY39_SKIP_CONDITION, reason=PY39_SKIP_REASON or "Python 3.9 runtime unavailable"
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
        python_executable=str(PY39_EXECUTABLE),
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

        data = proxy.execute(
            "fetch_basic_data",
            "daily",
            ["000001"],
            timeout=5.0,
        )
        assert data.success
        assert data.result["args"][0] == "daily"

    finally:
        proxy.stop(with_logout=True)
        assert not proxy.is_worker_alive()
