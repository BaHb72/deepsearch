import importlib.util
import os
import time
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "deepsearch"
    / "webui"
    / "api"
    / "endpoints"
    / "system"
    / "logs.py"
)
spec = importlib.util.spec_from_file_location("system_logs_module", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("无法加载 system.logs 模块")
system_logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(system_logs)


def _make_temp_log(directory: Path, name: str, content: str, mtime: float) -> Path:
    file_path = directory / name
    file_path.write_text(content, encoding="utf-8")
    os.utime(file_path, (mtime, mtime))
    return file_path


def test_get_latest_log_file_prefers_non_empty_directory(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_logs"
    empty_dir.mkdir()

    active_dir = tmp_path / "active_logs"
    active_dir.mkdir()

    ts = time.time()
    expected_file = _make_temp_log(active_dir, "deepsearch_2025-10-02.log", "test", ts)

    monkeypatch.setattr(system_logs, "_existing_log_directories", lambda: [empty_dir, active_dir])

    latest_log = system_logs.get_latest_log_file()

    assert latest_log == expected_file


@pytest.mark.asyncio
async def test_list_log_files_aggregates_all_directories(tmp_path, monkeypatch):
    first_dir = tmp_path / "first_logs"
    second_dir = tmp_path / "second_logs"
    first_dir.mkdir()
    second_dir.mkdir()

    now = time.time()
    older_log = _make_temp_log(first_dir, "older.log", "old", now - 120)
    newer_log = _make_temp_log(second_dir, "newer.log", "new", now)

    monkeypatch.setattr(system_logs, "_existing_log_directories", lambda: [first_dir, second_dir])

    result = await system_logs.list_log_files()

    assert result["status"] == "success"
    assert result["log_dir"] == str(first_dir)
    names = [item["name"] for item in result["files"]]
    assert names == ["newer.log", "older.log"]
    paths = {item["path"] for item in result["files"]}
    assert str(older_log) in paths and str(newer_log) in paths
