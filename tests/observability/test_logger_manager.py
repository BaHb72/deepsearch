import logging
import os
import zipfile
from datetime import datetime, timedelta

from deepsearch.observability.logger import LoggerManager


def test_retention_handler_archives_expired_logs(tmp_path):
    manager = LoggerManager()
    manager._archive_enabled = True
    manager._archive_format = "zip"
    manager._archive_after_days = 1
    manager._archive_purge_days = None

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    log_file = tmp_path / "test.log"
    log_file.write_text("hello log", encoding="utf-8")
    old_ts = (datetime.now() - timedelta(days=2)).timestamp()
    os.utime(log_file, (old_ts, old_ts))

    retention = manager._build_retention_handler(archive_base=archive_dir, retention_days=1)
    retention([str(log_file)])

    archives = list(archive_dir.glob("*.zip"))
    assert archives, "压缩包未生成"
    assert not log_file.exists(), "原始日志未清理"

    with zipfile.ZipFile(archives[0], "r") as zf:
        assert "test.log" in zf.namelist()

    manager._archive_purge_days = 1
    old_archive = archive_dir / "old.zip"
    with zipfile.ZipFile(old_archive, "w") as zf:
        zf.writestr("dummy.txt", "payload")
    very_old_ts = (datetime.now() - timedelta(days=3)).timestamp()
    os.utime(old_archive, (very_old_ts, very_old_ts))

    retention([])

    assert not old_archive.exists(), "过期压缩包未清理"


def test_module_sink_writes_logs(tmp_path):
    manager = LoggerManager()
    manager._load_log_configuration = lambda: None  # 跳过配置加载依赖
    manager.log_path = tmp_path
    manager.log_level = "INFO"
    manager._module_logging_enabled = True
    manager._archive_enabled = False

    try:
        manager.start()
        logging.getLogger("deepsearch.core.runtime.engine").info("module log ping")
    finally:
        manager.stop()

    base_dir = tmp_path / manager._module_directory_name
    assert base_dir.exists(), "模块日志目录未创建"
    files = list(base_dir.rglob("*.log"))
    assert files, "模块日志文件未生成"
    assert any("module log ping" in path.read_text(encoding="utf-8") for path in files)
