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

from config.setting import settings


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
# 日志核心配置函数
# ─────────────────────────────────────────────────────────────
_INITIAL_PID = os.getpid()
_CONFIGURED = False


def configure_logger(cfg: LoggerConfig | None = None) -> Path | None:
    global _CONFIGURED
    if _CONFIGURED:
        return cfg.log_dir if cfg else settings.log_dir

    cfg = cfg or LoggerConfig()

    if not cfg.active:
        logger.remove()
        _CONFIGURED = True
        return None

    if os.getpid() != _INITIAL_PID:
        logger.remove()

    date_str = datetime.now().strftime("%Y%m%d")
    prefix = f"{cfg.app_name.lower()}_{date_str}"
    sinks: list[dict[str, Any]] = []

    # console
    if cfg.console:
        sinks.append({
            "sink": sys.stdout,
            "level": cfg.level,
            "format": _spring_formatter(color=True),
            "enqueue": True,
            "backtrace": cfg.level == "DEBUG",
            "diagnose": cfg.diagnose if cfg.diagnose is not None else (cfg.level == "DEBUG"),
        })

    # text file
    if cfg.file_plain:
        sinks.append({
            "sink": cfg.log_dir / f"{prefix}.log",
            "level": cfg.level,
            "format": _spring_formatter(color=False),
            "rotation": cfg.rotation_plain,
            "retention": cfg.retention_plain,
            "compression": cfg.compress,
            "enqueue": True,
        })
        sinks.append({  # error file
            "sink": cfg.log_dir / f"{prefix}_err.log",
            "level": 0,
            "filter": lambda r: r["level"].no >= logger.level("ERROR").no,
            "format": _spring_formatter(color=False),
            "rotation": cfg.rotation_error,
            "retention": cfg.retention_error,
            "compression": cfg.compress,
            "enqueue": True,
        })

    # JSON file
    if cfg.file_json:
        sinks.append({
            "sink": cfg.log_dir / f"{prefix}.json",
            "level": cfg.level,
            "serialize": True,
            "rotation": cfg.rotation_json,
            "retention": cfg.retention_json,
            "compression": cfg.compress,
            "enqueue": True,
        })

    logger.remove()
    for s in sinks:
        logger.add(**s)

    _patch_std(cfg.level)
    _CONFIGURED = True
    logger.debug("Logger configured → {} (pid={})", cfg.log_dir, os.getpid())
    return cfg.log_dir


# ─────────────────────────────────────────────────────────────
# 快捷获取 logger
# ─────────────────────────────────────────────────────────────
def get_logger(**extra):
    if not _CONFIGURED:
        configure_logger()
    return logger.bind(**extra)
