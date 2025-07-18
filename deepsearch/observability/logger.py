# trader/core/logger.py
"""
日志系统配置与初始化 (Logging configuration and bootstrap)
"""
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from loguru import logger
from platformdirs import user_log_path

from deepsearch.config.setting import settings


# ─────────────────────────────────────────────────────────────
# 日志配置数据类
# ─────────────────────────────────────────────────────────────
@dataclass
class LoggerConfig:
    app_name: str = settings.app.name
    app_author: str = settings.app.author
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = settings.log.level
    active: bool = settings.log.active
    # 输出端
    console: bool = True
    file_plain: bool = True
    file_json: bool = settings.log.enable_json
    # 轮转与保留策略
    rotation_plain: str = settings.log.rotation
    rotation_error: str = settings.log.rotation
    rotation_json: str = settings.log.rotation
    # 始终使用经过 Pydantic 校验后的正整数
    retention_plain: str = f"{settings.log.retention_days} days"
    retention_error: str = f"{settings.log.retention_days * 2} days"
    retention_json: str = f"{settings.log.retention_days} days"
    diagnose: bool | None = None
    compress: str = "zip"
    log_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.log_dir = user_log_path(appname=self.app_name, appauthor=self.app_author)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 将标准库日志转发到 Loguru
# ─────────────────────────────────────────────────────────────
class _Intercept(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        """
        将记录发送到指定的日志记录目标。
        该方法从给定的日志记录中提取日志级别，并根据记录的内容将日志详细信息发送到
        设置的日志记录系统。如果级别无效，则回退到默认的日志等级数值，并包括深度和
        异常信息。
        :param record: 一个 ``logging.LogRecord`` 对象，其包含日志的相关信息。
        :type record: logging.LogRecord
        :return: 无返回值。
        :rtype: None
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, record=True, exception=record.exc_info).log(level, record.getMessage())


def _patch_std(level: str | int) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(_Intercept())


# ─────────────────────────────────────────────────────────────
# Spring Boot 风格格式化器
# ─────────────────────────────────────────────────────────────
def _spring_formatter(color: bool = True) -> Callable[[dict], str]:
    green = (lambda t: f"<green>{t}</green>") if color else (lambda t: t)
    level_fmt = (lambda t: f"<level>{t:<5}</level>") if color else (lambda t: f"{t:<5}")
    cyan = (lambda t: f"<cyan>{t}</cyan>") if color else (lambda t: t)
    yellow = (lambda t: f"<yellow>{t}</yellow>") if color else (lambda t: t)

    def _fmt(record: dict) -> str:
        time_str = green(record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        level_str = level_fmt(record["level"].name)
        proc_thr = f'{record["process"]:>5} --- [{record["thread"].name:>10}]'
        location = f'{record["file"].name}:{record["line"]:<4}'
        service = record["extra"].get("service", "-")
        service_str = yellow(str(service))
        return f"{time_str} | {level_str} | {proc_thr} | {location:16} | {service_str:6} | {record['message']}\n"

    return _fmt


# ─────────────────────────────────────────────────────────────
# Sink 工厂类
# ─────────────────────────────────────────────────────────────
class SinkFactory:
    """负责创建各种类型的日志输出目标"""

    def __init__(self, config: LoggerConfig, log_file_prefix: str):
        self.config = config
        self.log_file_prefix = log_file_prefix

    def create_console_sink(self) -> dict[str, Any]:
        """创建控制台输出配置"""
        return {
            "sink": sys.stdout,
            "level": self.config.level,
            "format": _spring_formatter(color=True),
            "enqueue": True,
            "backtrace": self.config.level == "DEBUG",
            "diagnose": self.config.diagnose if self.config.diagnose is not None else (self.config.level == "DEBUG"),
        }

    def create_plain_file_sink(self) -> dict[str, Any]:
        """创建普通文本文件输出配置"""
        return {
            "sink": self.config.log_dir / f"{self.log_file_prefix}.log",
            "level": self.config.level,
            "format": _spring_formatter(color=False),
            "rotation": self.config.rotation_plain,
            "retention": self.config.retention_plain,
            "compression": self.config.compress,
            "enqueue": True,
        }

    def create_error_file_sink(self) -> dict[str, Any]:
        """创建错误文件输出配置"""
        return {
            "sink": self.config.log_dir / f"{self.log_file_prefix}_err.log",
            "level": 0,
            "filter": lambda r: r["level"].no >= logger.level("ERROR").no,
            "format": _spring_formatter(color=False),
            "rotation": self.config.rotation_error,
            "retention": self.config.retention_error,
            "compression": self.config.compress,
            "enqueue": True,
        }

    def create_json_file_sink(self) -> dict[str, Any]:
        """创建JSON文件输出配置"""
        return {
            "sink": self.config.log_dir / f"{self.log_file_prefix}.json",
            "level": self.config.level,
            "serialize": True,
            "rotation": self.config.rotation_json,
            "retention": self.config.retention_json,
            "compression": self.config.compress,
            "enqueue": True,
        }


# ─────────────────────────────────────────────────────────────
# 日志配置器类
# ─────────────────────────────────────────────────────────────
class LoggerConfigurator:
    """负责日志系统的配置和初始化"""

    def __init__(self):
        self._initial_pid = os.getpid()
        self._configured = False

    def configure(self, config: LoggerConfig | None = None) -> Path | None:
        """配置日志系统"""
        if self._configured:
            return config.log_dir if config else settings.log_dir

        config = config or LoggerConfig()

        if not config.active:
            logger.remove()
            self._configured = True
            return None

        if os.getpid() != self._initial_pid:
            logger.remove()

        self._setup_logger(config)
        _patch_std(config.level)

        self._configured = True
        logger.debug("Logger configured → {} (pid={})", config.log_dir, os.getpid())
        return config.log_dir

    def _setup_logger(self, config: LoggerConfig) -> None:
        """设置日志记录器"""
        date_str = datetime.now().strftime("%Y%m%d")
        log_file_prefix = f"{config.app_name.lower()}_{date_str}"

        sink_factory = SinkFactory(config, log_file_prefix)
        sinks = self._create_sinks(config, sink_factory)

        logger.remove()
        for sink in sinks:
            logger.add(**sink)

    def _create_sinks(self, config: LoggerConfig, sink_factory: SinkFactory) -> list[dict[str, Any]]:
        """创建所有需要的日志输出目标"""
        sinks = []

        if config.console:
            sinks.append(sink_factory.create_console_sink())

        if config.file_plain:
            sinks.append(sink_factory.create_plain_file_sink())
            sinks.append(sink_factory.create_error_file_sink())

        if config.file_json:
            sinks.append(sink_factory.create_json_file_sink())

        return sinks


# ─────────────────────────────────────────────────────────────
# 全局配置器实例
# ─────────────────────────────────────────────────────────────
_logger_configurator = LoggerConfigurator()


def configure_logger(cfg: LoggerConfig | None = None) -> Path | None:
    """配置日志系统的便捷函数"""
    return _logger_configurator.configure(cfg)


# ─────────────────────────────────────────────────────────────
# 快捷获取 logger
# ─────────────────────────────────────────────────────────────
def get_logger(**extra):
    if not _logger_configurator._configured:
        configure_logger()
    return logger.bind(**extra)
