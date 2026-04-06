from pathlib import Path

from core.config.models.log import LogConfig
from core.config.settings import Settings
from core.constants import LOG_DIR


def test_log_dir_uses_configured_directory_relative_to_project_root():
    settings = Settings.model_construct(log=LogConfig(directory="./data/logs"))

    expected = (Path(__file__).resolve().parents[3] / "data" / "logs").resolve()
    assert settings.log_dir == expected


def test_log_dir_falls_back_to_system_log_dir_when_directory_not_configured():
    settings = Settings.model_construct(log=LogConfig())

    assert settings.log_dir == LOG_DIR
