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
# 日志配置数据类 (Logging configuration dataclass)
# ─────────────────────────────────────────────────────────────
@dataclass
class LogConfig:
    app_name: str = settings.app.name
    app_author: str = settings.app.author
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = settings.log.level
    active: bool = settings.log.active

    # 输出端 (Outputs)
    console: bool = True  # 启用控制台输出
    file_plain: bool = True  # 启用纯文本日志文件输出
    file_json: bool = settings.log.enable_json  # 启用JSON日志文件输出

    # 轮转与保留策略 (Rotation and retention policies)
    rotation_plain: str = settings.log.rotation  # 例如 "00:00" 表示在午夜进行每日轮转
    rotation_error: str = settings.log.rotation
    rotation_json: str = settings.log.rotation

    retention_plain: str = f"{settings.log.retention_days} days"
    retention_error: str = f"{settings.log.retention_days * 2} days"  # 错误日志保留时间是普通日志的两倍
    retention_json: str = f"{settings.log.retention_days} days"

    diagnose: bool | None = None  # 是否启用Loguru的诊断模式（None = 根据日志级别自动决定）
    compress: str = "zip"  # 轮转日志的压缩格式

    log_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        # 确定用户特定的日志目录并确保它存在
        self.log_dir = user_log_path(appname=self.app_name, appauthor=self.app_author)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 标准库日志转发到 loguru (Intercept standard logging into loguru)
# ─────────────────────────────────────────────────────────────
class _Intercept(logging.Handler):
    """
    一个从标准日志模块拦截日志并将其重定向到Loguru的logging.Handler，
    同时保留级别和异常信息。
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 获取对应的Loguru级别（如果存在），否则使用数字级别
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # 使用Loguru记录消息，包含捕获的异常信息和堆栈深度
        logger.opt(depth=6, record=True, exception=record.exc_info).log(level, record.getMessage())


def _patch_std(level: str | int) -> None:
    """
    用我们的拦截处理器替换标准日志处理器，
    将标准日志消息重定向到Loguru。
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(_Intercept())


# ─────────────────────────────────────────────────────────────
# Spring Boot 风格日志格式化器 (Spring Boot style log formatter)
# ─────────────────────────────────────────────────────────────
def _spring_formatter(color: bool = True) -> Callable[[dict], str]:
    """
    创建一个Spring Boot风格的日志格式化函数，用于Loguru的接收器。

    参数:
        color: 是否使用彩色输出（控制台为True，文件为False）。

    返回:
        一个可用于loguru接收器的格式化函数。
    """
    # 定义带颜色或不带颜色的格式化
    green = (lambda text: f"<green>{text}</green>") if color else (lambda text: f"{text}")
    level_fmt = (lambda text: f"<level>{text:<5}</level>") if color else (lambda text: f"{text:<5}")
    cyan = (lambda text: f"<cyan>{text}</cyan>") if color else (lambda text: f"{text}")
    yellow = (lambda text: f"<yellow>{text}</yellow>") if color else (lambda text: f"{text}")

    def _fmt(record: dict) -> str:
        # 格式化时间 (YYYY-MM-DD HH:MM:SS.sss)
        time_str = green(record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
        # 将级别名称格式化为固定宽度
        level_str = level_fmt(record["level"].name)
        # 进程ID和线程（PID右对齐到5位，线程名到10位）
        proc_thr = f'{record["process"]:>5} --- [{record["thread"].name:>10}]'
        # 源文件和行号
        location = f'{record["file"].name}:{record["line"]:<4}'
        # 服务名称（从额外上下文获取，如果没有则为'-'）
        service = record["extra"].get("service", "-")
        service_str = yellow(str(service))
        # 组合所有部分
        return (
            f"{time_str} | {level_str} | {proc_thr} | "
            f"{location:16} | {service_str:6} | {record['message']}\n"
        )
    return _fmt


# ─────────────────────────────────────────────────────────────
# 日志配置核心函数 (Core function to configure logging)
# ─────────────────────────────────────────────────────────────
_INITIAL_PID = os.getpid()
_CONFIGURED = False

def configure_logger(cfg: LogConfig | None = None) -> Path | None:
    """
    使用Loguru配置日志系统。

    参数:
        cfg: 自定义LogConfig设置（如果为None，则使用settings中的默认值）。

    返回:
        如果日志记录处于活动状态，则返回日志目录的路径，否则返回None。
    """
    global _CONFIGURED
    if _CONFIGURED:
        # 已经配置过：返回现有的日志目录
        return cfg.log_dir if cfg else settings.log_dir

    cfg = cfg or LogConfig()

    if not cfg.active:
        # 日志记录被配置禁用：移除所有处理器并且不做任何操作
        logger.remove()
        _CONFIGURED = True
        return None

    # 如果在派生的子进程中，移除继承的处理器以避免重复
    if os.getpid() != _INITIAL_PID:
        logger.remove()

    # 使用应用程序名称（小写）和日期（YYYYMMDD）准备日志文件名前缀
    date_str = datetime.now().strftime("%Y%m%d")
    prefix = f"{cfg.app_name.lower()}_{date_str}"
    sinks: list[dict[str, Any]] = []

    # 控制台输出（标准输出）
    if cfg.console:
        sinks.append({
            "sink": sys.stdout,
            "level": cfg.level,
            "format": _spring_formatter(color=True),
            "enqueue": True,
            "backtrace": True if cfg.level == "DEBUG" else False,
            "diagnose": cfg.diagnose if cfg.diagnose is not None else (True if cfg.level == "DEBUG" else False),
        })

    # 文件输出（纯文本日志）
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
        # 错误日志单独文件（ERROR及以上级别）
        sinks.append({
            "sink": cfg.log_dir / f"{prefix}_err.log",
            "level": 0,  # 捕获所有级别，过滤器会缩小范围
            "filter": lambda record: record["level"].no >= logger.level("ERROR").no,
            "format": _spring_formatter(color=False),
            "rotation": cfg.rotation_error,
            "retention": cfg.retention_error,
            "compression": cfg.compress,
            "enqueue": True,
        })

    # JSON文件输出（用于ELK等日志系统的结构化日志）
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

    # 将所有配置的接收器应用到loguru日志记录器
    logger.remove()
    for sink_cfg in sinks:
        logger.add(**sink_cfg)
    # Redirect standard logging to loguru
    _patch_std(cfg.level)

    _CONFIGURED = True
    logger.debug("Logger configured → {} (pid={})", cfg.log_dir, os.getpid())
    return cfg.log_dir


# ─────────────────────────────────────────────────────────────
# 日志获取工厂函数 (Factory to get a configured logger with extra context)
# ─────────────────────────────────────────────────────────────
def get_logger(**extra):
    """
    Get a loguru logger instance with bound extra context.

    If the logging system is not yet configured, it will configure with default settings.

    Args:
        **extra: Additional context (fields) to bind to the logger (e.g., service name).

    Returns:
        A loguru logger with the extra context bound.
    """
    if not _CONFIGURED:
        configure_logger()
    return logger.bind(**extra)
