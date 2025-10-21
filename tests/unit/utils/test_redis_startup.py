import pytest

from deepsearch.config.models.database import CacheDatabaseConfig, CacheDatabaseWSLConfig
from deepsearch.utils.system import redis_startup
from deepsearch.utils.system.redis_startup import RedisStartupError


def _noop_echo(_message: str) -> None:
    """测试中的占位 echo 函数。"""


def test_decode_subprocess_output_utf16():
    data = "172.29.32.133".encode("utf-16")
    decoded = redis_startup._decode_subprocess_output(data)
    assert decoded == "172.29.32.133"


def test_ensure_redis_running_skip_when_disabled(monkeypatch):
    config = CacheDatabaseConfig(enabled=False)

    def _fail_can_connect(_config):
        raise AssertionError("should not try to ping when cache disabled")

    monkeypatch.setattr(redis_startup, "_can_connect", _fail_can_connect)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)


def test_ensure_redis_running_start_service(monkeypatch):
    config = CacheDatabaseConfig()
    config.windows_service_names = ["Redis"]

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)
    monkeypatch.setattr(redis_startup, "_wait_for_redis", lambda _cfg, _hook=None: True)

    started = {"service": False}

    def _fake_start(names, echo):
        started["service"] = True
        return True

    monkeypatch.setattr(redis_startup, "_start_via_services", _fake_start)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert started["service"] is True


def test_ensure_redis_running_binary_fallback(monkeypatch):
    config = CacheDatabaseConfig()
    config.startup_binary_path = "C:/redis/redis-server.exe"

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)
    monkeypatch.setattr(redis_startup, "_wait_for_redis", lambda _cfg, _hook=None: True)
    monkeypatch.setattr(redis_startup, "_start_via_services", lambda _names, _echo: False)

    invoked = {"binary": False}

    def _fake_binary(path, args, echo):  # pragma: no cover - patched in tests
        invoked["binary"] = True
        return True

    monkeypatch.setattr(redis_startup, "_start_via_binary", _fake_binary)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert invoked["binary"] is True


def test_ensure_redis_running_auto_start_disabled(monkeypatch):
    config = CacheDatabaseConfig(auto_start_windows=False)

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)

    with pytest.raises(RedisStartupError):
        redis_startup.ensure_redis_running(config, echo=_noop_echo)


def test_ensure_redis_running_non_windows(monkeypatch):
    config = CacheDatabaseConfig()

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Linux")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)

    with pytest.raises(RedisStartupError):
        redis_startup.ensure_redis_running(config, echo=_noop_echo)


def test_ensure_redis_running_startup_command(monkeypatch):
    config = CacheDatabaseConfig()
    config.startup_command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "service",
        "redis-server",
        "start",
    ]

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)
    monkeypatch.setattr(redis_startup, "_wait_for_redis", lambda _cfg, _hook=None: True)
    monkeypatch.setattr(redis_startup, "_start_via_services", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(redis_startup, "_start_via_binary", lambda *_args, **_kwargs: False)

    called = {"command": False}

    def _fake_command(cmd, echo):
        called["command"] = True
        return True

    monkeypatch.setattr(redis_startup, "_start_via_command", _fake_command)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert called["command"] is True


def test_ensure_redis_running_wsl_default_command(monkeypatch):
    config = CacheDatabaseConfig()
    config.windows_service_names = []
    config.startup_binary_path = None
    config.startup_arguments = []
    config.startup_command = []
    config.wsl = CacheDatabaseWSLConfig(enabled=True, distro="Ubuntu")

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_can_connect", lambda _cfg: False)
    monkeypatch.setattr(redis_startup, "_wait_for_redis", lambda _cfg, _hook=None: True)
    monkeypatch.setattr(redis_startup, "_refresh_wsl_host", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(redis_startup, "_start_via_services", lambda *_args, **_kwargs: False)

    captured = {}

    def _fake_command(cmd, echo):
        captured["command"] = cmd
        return True

    monkeypatch.setattr(redis_startup, "_start_via_command", _fake_command)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert captured["command"] == [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "-u",
        "root",
        "service",
        "redis-server",
        "start",
    ]


def test_wsl_host_resolution(monkeypatch):
    config = CacheDatabaseConfig(
        host="localhost",
        wsl=CacheDatabaseWSLConfig(enabled=True, distro="Ubuntu"),
    )

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_resolve_wsl_ip", lambda _cfg: "172.29.32.133")
    redis_startup._WSL_NETWORK_MODE = None
    monkeypatch.setattr(redis_startup, "_detect_wsl_network_mode", lambda: "nat")

    captured_hosts = []

    def _fake_can_connect(cfg):
        captured_hosts.append(cfg.host)
        return True

    monkeypatch.setattr(redis_startup, "_can_connect", _fake_can_connect)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert captured_hosts == ["172.29.32.133"]
    assert config.host == "172.29.32.133"


def test_wsl_host_resolution_mirrored(monkeypatch):
    config = CacheDatabaseConfig(
        host="localhost",
        wsl=CacheDatabaseWSLConfig(enabled=True, distro="Ubuntu"),
    )

    monkeypatch.setattr(redis_startup.platform, "system", lambda: "Windows")
    monkeypatch.setattr(redis_startup, "_resolve_wsl_ip", lambda _cfg: "192.168.0.50")
    redis_startup._WSL_NETWORK_MODE = None
    monkeypatch.setattr(redis_startup, "_detect_wsl_network_mode", lambda: "mirrored")

    captured_hosts = []

    def _fake_can_connect(cfg):
        captured_hosts.append(cfg.host)
        return True

    monkeypatch.setattr(redis_startup, "_can_connect", _fake_can_connect)

    redis_startup.ensure_redis_running(config, echo=_noop_echo)

    assert captured_hosts == ["127.0.0.1"]
    assert config.host == "127.0.0.1"
