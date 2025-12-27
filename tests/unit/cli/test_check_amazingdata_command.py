import json
from importlib import import_module
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from deepsearch.config.models.amazingdata import AmazingDataConfig as SettingsAmazingDataConfig
from deepsearch.config.models.amazingdata import AmazingDataConnectionConfig

cli_main = import_module("deepsearch.cli.main")
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
        password="real_pass",
        host="101.230.159.234",
        port=8600,
        tgw_log_path=str(log_file),
    )
    settings_config = SettingsAmazingDataConfig(enabled=True, connection=connection)

    monkeypatch.setattr(
        "deepsearch.config.get_config",
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
