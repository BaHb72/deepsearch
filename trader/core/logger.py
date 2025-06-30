import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

from loguru import logger
from platformdirs import user_log_path

from trader.core.setting import settings


# ─────────────────────────────────────────────────────────────
# 日志配置数据类
# ─────────────────────────────────────────────────────────────
@dataclass
class LogConfig:
    app_name: str = settings.app.name
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = settings.log.level
    active: bool = settings.log.active

    # 输出端
    console: bool = True
    file_plain: bool = True
    file_json: bool = settings.log.enable_json

    # 轮转与保留策略（全部取自 YAML）
    rotation_plain: str = settings.log.rotation  # 如 "00:00"
    rotation_error: str = settings.log.rotation
    rotation_json: str = settings.log.rotation

    retention_plain: str = f"{settings.log.retention_days} days"
    retention_error: str = f"{settings.log.retention_days * 2} days"
    retention_json: str = f"{settings.log.retention_days} days"

    diagnose: bool | None = None
    compress: str = "zip"

    log_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.log_dir = user_log_path(self.app_name)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 标准库日志转发到loguru
# ─────────────────────────────────────────────────────────────
class _Intercept(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, record=True, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _patch_std(level: str | int) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(_Intercept())


# ─────────────────────────────────────────────────────────────
# Spring Boot风格日志格式化器
# ─────────────────────────────────────────────────────────────
def _spring_formatter(color: bool = True) -> Callable[[dict], str]:
    """
    创建Spring Boot风格的日志格式化函数

    Args:
        color: 是否启用彩色输出，控制台输出时设为True，文件输出时设为False

    Returns:
        可被loguru sink使用的格式化函数
    """
    green = "<green>{}</green>".format if color else "{}".format
    level_fmt = "<level>{:<5}</level>".format if color else "{:<5}".format
    cyan = "<cyan>{}</cyan>".format if color else "{}".format
    yellow = "<yellow>{}</yellow>".format if color else "{}".format

    def _fmt(record: dict) -> str:
        time_str = green(record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        level_str = level_fmt(record["level"].name)
        proc_thr = f'{record["process"]:>5} --- [{record["thread"].name:>10}]'
        location = f'{record["file"].name}:{record["line"]:<4}'
        service = record["extra"].get("service", "-")
        service_str = yellow(f"{service}")
        return (
            f"{time_str} | {level_str} | {proc_thr} | "
            f"{location:16} | {service_str:6} | {record['message']}\n"
        )

    return _fmt


# ─────────────────────────────────────────────────────────────
# 日志配置核心函数
# ─────────────────────────────────────────────────────────────
_INITIAL_PID = os.getpid()
_CONFIGURED = False


def configure_logger(cfg: LogConfig | None = None) -> Path | None:
    """
    配置日志系统

    Args:
        cfg: 日志配置对象，如果为None则使用默认配置

    Returns:
        日志目录路径，如果日志未启用则返回None
    """
    global _CONFIGURED
    if _CONFIGURED:
        return cfg.log_dir if cfg else settings.log_dir

    cfg = cfg or LogConfig()

    if not cfg.active:
        logger.disable(cfg.app_name)
        _CONFIGURED = True
        return None

    # fork 子进程
    if os.getpid() != _INITIAL_PID:
        logger.remove()

    date = datetime.now().strftime("%Y%m%d")
    prefix = f"{cfg.app_name.lower()}_{date}"
    sinks: list[dict[str, Any]] = []

    # console
    if cfg.console:
        sinks.append(
            dict(
                sink=sys.stdout,
                level=cfg.level,
                format=_spring_formatter(color=True),
                enqueue=True,
                backtrace=cfg.level == "DEBUG",
                diagnose=cfg.diagnose if cfg.diagnose is not None else cfg.level == "DEBUG",
            )
        )

    # 文件
    if cfg.file_plain:
        sinks.append(
            dict(
                sink=cfg.log_dir / f"{prefix}.log",
                level=cfg.level,
                format=_spring_formatter(color=False),
                rotation=cfg.rotation_plain,
                retention=cfg.retention_plain,
                compression=cfg.compress,
                enqueue=True,
            )
        )
        sinks.append(
            dict(
                sink=cfg.log_dir / f"{prefix}_err.log",
                level=0,
                filter=lambda r: r["level"].no >= logger.level("ERROR").no,
                format=_spring_formatter(color=False),
                rotation=cfg.rotation_error,
                retention=cfg.retention_error,
                compression=cfg.compress,
                enqueue=True,
            )
        )

    # JSON
    if cfg.file_json:
        sinks.append(
            dict(
                sink=cfg.log_dir / f"{prefix}.json",
                level=cfg.level,
                serialize=True,
                rotation=cfg.rotation_json,
                retention=cfg.retention_json,
                compression=cfg.compress,
                enqueue=True,
            )
        )

    # 应用 sink
    logger.remove()
    for s in sinks:
        logger.add(**s)
    _patch_std(cfg.level)
    _CONFIGURED = True

    logger.debug("Logger configured → {} (pid={})", cfg.log_dir, os.getpid())
    return cfg.log_dir


# ─────────────────────────────────────────────────────────────
# 日志获取工厂函数
# ─────────────────────────────────────────────────────────────
def get_logger(**extra):
    """
    获取日志记录器实例

    首次调用时会自动配置日志系统

    Args:
        **extra: 要绑定到日志记录器的额外字段，如service名称等

    Returns:
        配置好的loguru日志记录器实例
    """
    if not _CONFIGURED:
        configure_logger(LogConfig())
    return logger.bind(**extra)
