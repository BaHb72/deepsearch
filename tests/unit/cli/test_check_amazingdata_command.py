import asyncio
import json
import sys
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner
from core.config.models.amazingdata import AmazingDataConfig as SettingsAmazingDataConfig
from core.config.models.amazingdata import AmazingDataConnectionConfig
from core.config.models.data_sources import DataSourceProviderConfig, DataSourcesConfig

cli_main = import_module("core.cli.main")
cli = cli_main.cli


class _DummySocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_outputs_tgw_snippet(monkeypatch, tmp_path):
    log_file = tmp_path / "tgw.log"
    log_file.write_text("line1\nline2\n", encoding="utf-8")

    connection = AmazingDataConnectionConfig(
        username="real_user",
        password="real_pass",  # pragma: allowlist secret
        host="101.230.159.234",
        port=8600,
        tgw_log_path=str(log_file),
    )
    settings_config = SettingsAmazingDataConfig(enabled=True, connection=connection)

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(amazingdata=settings_config),
    )

    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    tgw_name = next(name for name in checks if "TGW" in name)
    assert checks[tgw_name]["status"] == "ok"
    assert "line2" in checks[tgw_name]["detail"]
    assert payload["status"] == "ok"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_reads_data_sources_provider_config(monkeypatch, tmp_path):
    log_file = tmp_path / "tgw-provider.log"
    log_file.write_text("provider-line1\nprovider-line2\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )

    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert "AmazingData 配置来源" in checks
    assert checks["AmazingData 配置来源"]["status"] == "ok"
    assert (
        checks["AmazingData 配置来源"]["detail"]
        == "检测到 settings.data_sources.providers.amazingdata"
    )
    assert payload["status"] == "ok"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_marks_overall_failed_when_tgw_path_missing(monkeypatch, tmp_path):
    missing_log_path = tmp_path / "missing-dir"

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(missing_log_path),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )

    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["TGW 日志配置"]["status"] == "failed"
    assert payload["status"] == "failed"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_fails_when_distributed_without_workers(monkeypatch, tmp_path):
    log_file = tmp_path / "distributed.log"
    log_file.write_text("distributed-line\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "distributed",
            "dask_scheduler_address": "tcp://localhost:8786",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )

    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _FakeDaskClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scheduler_info(self):
            return {"workers": {}}

    monkeypatch.setitem(sys.modules, "distributed", SimpleNamespace(Client=_FakeDaskClient))

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["Dask Worker 可用性"]["status"] == "failed"
    assert payload["status"] == "failed"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_fails_when_scheduler_cannot_reach_win_worker(monkeypatch, tmp_path):
    log_file = tmp_path / "distributed-backconnect-failed.log"
    log_file.write_text("distributed-backconnect-failed\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "distributed",
            "dask_scheduler_address": "tcp://localhost:8786",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    worker_addr = "tcp://172.18.32.1:53489"

    class _FakeDaskClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scheduler_info(self):
            return {
                "workers": {
                    worker_addr: {
                        "resources": {"WIN": 1.0},
                    }
                }
            }

        def run_on_scheduler(self, *_args, **_kwargs):
            return {
                worker_addr: {
                    "reachable": False,
                    "error": "OSError: No route to host",
                    "host": "172.18.32.1",
                    "port": 53489,
                }
            }

    monkeypatch.setitem(sys.modules, "distributed", SimpleNamespace(Client=_FakeDaskClient))

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["Dask Worker 可用性"]["status"] == "ok"
    assert checks["Scheduler 到 Worker 回连"]["status"] == "failed"
    assert payload["status"] == "failed"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_passes_when_scheduler_can_reach_win_worker(monkeypatch, tmp_path):
    log_file = tmp_path / "distributed-backconnect-ok.log"
    log_file.write_text("distributed-backconnect-ok\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "distributed",
            "dask_scheduler_address": "tcp://localhost:8786",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    worker_addr = "tcp://172.29.32.1:53072"

    class _FakeDaskClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scheduler_info(self):
            return {
                "workers": {
                    worker_addr: {
                        "resources": {"WIN": 1.0},
                    }
                }
            }

        def run_on_scheduler(self, *_args, **_kwargs):
            return {
                worker_addr: {
                    "reachable": True,
                    "error": "",
                    "host": "172.29.32.1",
                    "port": 53072,
                }
            }

    monkeypatch.setitem(sys.modules, "distributed", SimpleNamespace(Client=_FakeDaskClient))

    runner = CliRunner()
    result = runner.invoke(cli, ["check-amazingdata", "dev", "--timeout", "0.1"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["Dask Worker 可用性"]["status"] == "ok"
    assert checks["Scheduler 到 Worker 回连"]["status"] == "ok"
    assert payload["status"] == "ok"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_skipped_when_no_win_worker(monkeypatch, tmp_path):
    log_file = tmp_path / "distributed-no-win.log"
    log_file.write_text("distributed-no-win\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "distributed",
            "dask_scheduler_address": "tcp://localhost:8786",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _FakeDaskClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scheduler_info(self):
            return {
                "workers": {
                    "tcp://127.0.0.1:61000": {
                        "resources": {"CPU": 1.0},
                    }
                }
            }

    monkeypatch.setitem(sys.modules, "distributed", SimpleNamespace(Client=_FakeDaskClient))
    get_provider_mock = AsyncMock(return_value=object())
    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async", get_provider_mock
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["Dask Worker 可用性"]["status"] == "failed"
    assert checks["真实 API Smoke"]["status"] == "warning"
    assert "未执行 get_calendar 探测" in checks["真实 API Smoke"]["detail"]
    get_provider_mock.assert_not_awaited()


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_skipped_when_scheduler_unreachable(monkeypatch, tmp_path):
    log_file = tmp_path / "distributed-scheduler-unreachable.log"
    log_file.write_text("distributed-scheduler-unreachable\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "distributed",
            "dask_scheduler_address": "tcp://localhost:8786",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _BrokenDaskClient:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("scheduler unreachable")

    monkeypatch.setitem(sys.modules, "distributed", SimpleNamespace(Client=_BrokenDaskClient))
    get_provider_mock = AsyncMock(return_value=object())
    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async", get_provider_mock
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["Dask Worker 可用性"]["status"] == "failed"
    assert checks["真实 API Smoke"]["status"] == "warning"
    assert "未执行 get_calendar 探测" in checks["真实 API Smoke"]["detail"]
    get_provider_mock.assert_not_awaited()


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_calendar_success(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-success.log"
    log_file.write_text("probe-ok\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _FakeAmazingDataProvider:
        async def get_calendar(self, data_type="int", market="SH"):
            return [20260101, 20260102, 20260105]

    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(return_value=_FakeAmazingDataProvider()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "ok"
    assert "返回 3 条" in checks["真实 API Smoke"]["detail"]
    assert payload["status"] == "ok"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_calendar_failed_when_provider_unavailable(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-failed.log"
    log_file.write_text("probe-failed\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )
    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(return_value=None),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "failed"
    assert payload["status"] == "failed"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_actor_worker_unreachable_hint(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-worker-unreachable.log"
    log_file.write_text("probe-worker-unreachable\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )
    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(side_effect=RuntimeError("Unable to contact Actor's worker")),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "failed"
    assert "回连链路" in checks["真实 API Smoke"]["suggestion"]


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_ignores_dynamic_getattr_lifecycle(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-dynamic.log"
    log_file.write_text("probe-dynamic\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _ProxyStyleProvider:
        async def get_calendar(self, data_type="int", market="SH"):
            return [20260101]

        async def cleanup(self):
            return None

        def __getattr__(self, _name):
            async def _proxy(*_args, **_kwargs):
                raise AssertionError("不应调用动态代理生命周期方法")

            return _proxy

    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(return_value=_ProxyStyleProvider()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "ok"


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_prefers_actor_call_when_available(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-actor.log"
    log_file.write_text("probe-actor\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _Actor:
        async def call(self, method_name: str, **kwargs):
            assert method_name == "get_calendar"
            assert kwargs["market"] == "SH"
            return [20260106, 20260107]

    class _ProviderWithActor:
        def __init__(self) -> None:
            self._actor = _Actor()

        async def get_calendar(self, *_args, **_kwargs):
            raise AssertionError("存在 _actor.call 时不应走 provider.get_calendar")

        async def cleanup(self):
            return None

    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(return_value=_ProviderWithActor()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "ok"
    assert "返回 2 条" in checks["真实 API Smoke"]["detail"]


@pytest.mark.usefixtures("tmp_path")
def test_check_amazingdata_probe_timeout_is_warning(monkeypatch, tmp_path):
    log_file = tmp_path / "probe-timeout.log"
    log_file.write_text("probe-timeout\n", encoding="utf-8")

    provider = DataSourceProviderConfig(
        enabled=True,
        config={
            "mode": "local",
            "connection": {
                "username": "provider_user",
                "password": "provider_pass",  # pragma: allowlist secret
                "host": "101.230.159.234",
                "port": 8600,
                "tgw_log_path": str(log_file),
            },
        },
    )
    data_sources = DataSourcesConfig(providers={"amazingdata": provider})

    monkeypatch.setattr(
        "core.config.get_config",
        lambda: SimpleNamespace(data_sources=data_sources),
    )
    monkeypatch.setattr(
        cli_main.socket,
        "create_connection",
        lambda *args, **kwargs: _DummySocket(),
    )

    class _Actor:
        async def call(self, method_name: str, **kwargs):
            raise asyncio.TimeoutError()

    class _ProviderWithTimeoutActor:
        def __init__(self) -> None:
            self._actor = _Actor()

        async def get_calendar(self, *_args, **_kwargs):
            return [20260108]

        async def cleanup(self):
            return None

    monkeypatch.setattr(
        "apps.api.api.providers.DataProviderFactory.get_provider_async",
        AsyncMock(return_value=_ProviderWithTimeoutActor()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "check-amazingdata",
            "dev",
            "--timeout",
            "0.1",
            "--probe-calendar",
            "--probe-timeout",
            "1",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["真实 API Smoke"]["status"] == "warning"
    assert "调用超时" in checks["真实 API Smoke"]["detail"]
    assert payload["status"] == "warning"
