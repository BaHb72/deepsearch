from __future__ import annotations

"""
日志系统配置与初始化 (Logging configuration and bootstrap)
"""
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from loguru import logger
from platformdirs import user_log_path

from deepsearch.config import settings

# ==============================================================================
# Constants
# ==============================================================================

# Log level mapping
DEFAULT_LOG_LEVEL = "INFO"
ERROR_LEVEL_NO = 40  # logging.ERROR

# Time format
TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
DATE_FORMAT = "%Y%m%d"

# Field widths for formatting
LEVEL_WIDTH = 5
PROCESS_WIDTH = 5
THREAD_WIDTH = 10
LOCATION_WIDTH = 16
SERVICE_WIDTH = 6

# Default retention multiplier for error logs
ERROR_RETENTION_MULTIPLIER = 2

# Log depth for interceptor
INTERCEPTOR_DEPTH = 6


# ==============================================================================
# Logger Configuration Data Class
# ==============================================================================

@dataclass
class LoggerConfig:
    """日志配置数据类"""
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
    retention_error: str = f"{settings.log.retention_days * ERROR_RETENTION_MULTIPLIER} days"
    retention_json: str = f"{settings.log.retention_days} days"
    diagnose: Optional[bool] = None
    compress: str = "zip"
    log_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.log_dir = user_log_path(appname=self.app_name, appauthor=self.app_author)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Standard Library Log Interceptor
# ==============================================================================

class _Intercept(logging.Handler):
    """将标准库日志转发到 Loguru"""
    
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
        logger.opt(depth=INTERCEPTOR_DEPTH, record=True, exception=record.exc_info).log(level, record.getMessage())


def _patch_std(level: str | int) -> None:
    """配置标准库日志转发到 Loguru"""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(_Intercept())


# ==============================================================================
# Spring Boot Style Formatter
# ==============================================================================

def _spring_formatter(color: bool = True) -> Callable[[dict], str]:
    """Spring Boot 风格格式化器"""
    green = (lambda t: f"<green>{t}</green>") if color else (lambda t: t)
    level_fmt = (lambda t: f"<level>{t:<{LEVEL_WIDTH}}</level>") if color else (lambda t: f"{t:<{LEVEL_WIDTH}}")
    cyan = (lambda t: f"<cyan>{t}</cyan>") if color else (lambda t: t)
    yellow = (lambda t: f"<yellow>{t}</yellow>") if color else (lambda t: t)

    def _fmt(record: dict) -> str:
        time_str = green(record["time"].strftime(TIME_FORMAT)[:-3])
        level_str = level_fmt(record["level"].name)
        proc_thr = f'{record["process"]:>{PROCESS_WIDTH}} --- [{record["thread"].name:>{THREAD_WIDTH}}]'
        location = f'{record["file"].name}:{record["line"]:<4}'
        service = record["extra"].get("service", "-")
        service_str = yellow(str(service))
        return f"{time_str} | {level_str} | {proc_thr} | {location:{LOCATION_WIDTH}} | {service_str:{SERVICE_WIDTH}} | {record['message']}\n"

    return _fmt


# ==============================================================================
# Sink Factory
# ==============================================================================

class SinkFactory:
    """负责创建各种类型的日志输出目标"""

    def __init__(self, config: LoggerConfig, log_file_prefix: str):
        self.config = config
        self.log_file_prefix = log_file_prefix

    def create_console_sink(self) -> dict[str, Any]:
        """创建控制台输出配置"""
        return {
            "sink": sys.stdout,
            "level": "DEBUG",  # 控制台始终显示 DEBUG 级别
            "format": self._console_formatter_with_colors(),
            "enqueue": True,
            "backtrace": self.config.level == "DEBUG",
            "diagnose": self.config.diagnose if self.config.diagnose is not None else (self.config.level == "DEBUG"),
        }

    def _console_formatter_with_colors(self) -> Callable[[dict], str]:
        """控制台格式化器，根据日志级别使用不同颜色"""

        def _fmt(record: dict) -> str:
            time_str = f"<green>{record['time'].strftime(TIME_FORMAT)[:-3]}</green>"

            # 根据级别设置不同颜色
            level_name = record["level"].name
            if level_name == "DEBUG":
                level_str = f"<dim>{level_name:<{LEVEL_WIDTH}}</dim>"  # 灰色
            elif level_name == "INFO":
                level_str = f"<level>{level_name:<{LEVEL_WIDTH}}</level>"  # 默认颜色
            elif level_name == "WARNING":
                level_str = f"<yellow>{level_name:<{LEVEL_WIDTH}}</yellow>"  # 黄色
            elif level_name == "ERROR":
                level_str = f"<red>{level_name:<{LEVEL_WIDTH}}</red>"  # 红色
            elif level_name == "CRITICAL":
                level_str = f"<red><bold>{level_name:<{LEVEL_WIDTH}}</bold></red>"  # 红色加粗
            else:
                level_str = f"<level>{level_name:<{LEVEL_WIDTH}}</level>"

            proc_thr = f'{record["process"]:>{PROCESS_WIDTH}} --- [{record["thread"].name:>{THREAD_WIDTH}}]'
            location = f'{record["file"].name}:{record["line"]:<4}'
            service = record["extra"].get("service", "-")
            service_str = f"<yellow>{str(service)}</yellow>"

            # 消息内容也根据级别调整颜色
            if level_name == "DEBUG":
                message = f"<dim>{record['message']}</dim>"
            elif level_name == "ERROR" or level_name == "CRITICAL":
                message = f"<red>{record['message']}</red>"
            else:
                message = record['message']

            return f"{time_str} | {level_str} | {proc_thr} | {location:{LOCATION_WIDTH}} | {service_str:{SERVICE_WIDTH}} | {message}\n"

        return _fmt

    def create_plain_file_sink(self) -> dict[str, Any]:
        """创建普通文本文件输出配置"""
        return {
            "sink": self.config.log_dir / f"{self.log_file_prefix}.log",
            "level": "DEBUG",  # 文件日志也记录 DEBUG 级别
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
            "filter": lambda r: r["level"].no >= ERROR_LEVEL_NO,
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
            "level": "DEBUG",  # JSON 日志也记录 DEBUG 级别
            "serialize": True,
            "rotation": self.config.rotation_json,
            "retention": self.config.retention_json,
            "compression": self.config.compress,
            "enqueue": True,
        }


# ==============================================================================
# Logger Configurator
# ==============================================================================

class LoggerConfigurator:
    """负责日志系统的配置和初始化"""

    def __init__(self):
        self._initial_pid = os.getpid()
        self._configured = False

    def configure(self, config: Optional[LoggerConfig] = None) -> Optional[Path]:
        """配置日志系统"""
        if self._configured:
            return config.log_dir if config else settings.log_dir

        config = config or LoggerConfig()

        if not config.active:
            logger.remove()
            self._configured = True
            return None

        # Handle forked processes
        if os.getpid() != self._initial_pid:
            logger.remove()
            self._initial_pid = os.getpid()

        self._setup_logger(config)
        _patch_std(config.level)

        self._configured = True
        logger.debug("Logger configured → {} (pid={})", config.log_dir, os.getpid())
        return config.log_dir

    def _setup_logger(self, config: LoggerConfig) -> None:
        """设置日志记录器"""
        date_str = datetime.now().strftime(DATE_FORMAT)
        log_file_prefix = f"{config.app_name.lower()}_{date_str}"

        sink_factory = SinkFactory(config, log_file_prefix)
        sinks = self._create_sinks(config, sink_factory)

        logger.remove()
        for sink in sinks:
            try:
                logger.add(**sink)
            except Exception as e:
                print(f"[Warning] Failed to add log sink: {e}", file=sys.stderr)

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


# ==============================================================================
# Logger Manager
# ==============================================================================

class LoggerManager:
    """
    日志管理器，提供统一的日志系统生命周期管理接口
    
    该类封装了LoggerConfigurator，提供更简洁的start/stop接口，
    便于在MainEngine中进行统一管理。
    """

    def __init__(self):
        """初始化日志管理器"""
        self._configurator = LoggerConfigurator()
        self._configured = False
        self._log_path: Optional[Path] = None

    def start(self, config: Optional[LoggerConfig] = None) -> None:
        """
        启动日志系统
        
        :param config: 可选的日志配置，如果不提供则使用默认配置
        """
        if self._configured:
            logger.info("日志系统已经启动")
            return

        try:
            self._log_path = self._configurator.configure(config)
            self._configured = True
            logger.info("日志系统启动成功")
            if self._log_path:
                logger.info(f"日志目录: {self._log_path}")
        except Exception as e:
            # 日志系统启动失败不应该阻止程序运行，使用标准输出
            print(f"[错误] 启动日志系统失败: {e}", file=sys.stderr)
            self._configured = False

    def stop(self) -> None:
        """
        停止日志系统
        
        清理日志处理器并确保所有日志都已写入
        """
        if not self._configured:
            return

        try:
            # 移除所有处理器
            logger.remove()
            self._configured = False
            # 使用print因为logger已经被移除
            print("[信息] 日志系统已停止")
        except Exception as e:
            print(f"[错误] 停止日志系统失败: {e}", file=sys.stderr)

    @property
    def is_running(self) -> bool:
        """检查日志系统是否正在运行"""
        return self._configured

    @property
    def log_path(self) -> Optional[Path]:
        """获取日志目录路径"""
        return self._log_path

    def set_level(self, level: str) -> None:
        """
        动态设置日志级别
        
        :param level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        try:
            # 如果日志系统未启动，先启动
            if not self._configured:
                config = LoggerConfig(level=level)
                self.start(config)
                return

            # 动态更新日志级别
            logger.remove()
            config = LoggerConfig(level=level)
            self._configurator._setup_logger(config)
            _patch_std(level)
            logger.info(f"Log level changed to: {level}")
        except Exception as e:
            print(f"[ERROR] Failed to set log level: {e}", file=sys.stderr)


# ==============================================================================
# Global Instances and Public API
# ==============================================================================

_logger_configurator = LoggerConfigurator()
logger_manager = LoggerManager()


def configure_logger(cfg: Optional[LoggerConfig] = None) -> Optional[Path]:
    """配置日志系统的便捷函数"""
    return _logger_configurator.configure(cfg)


def get_logger(**extra) -> logger:
    """快捷获取 logger"""
    if not _logger_configurator._configured:
        configure_logger()
    return logger.bind(**extra)


# ==============================================================================
# Module Summary
# ==============================================================================
"""
This module provides a comprehensive logging system based on Loguru.

Key Components:
1. LoggerConfig: Configuration dataclass for logger settings
2. _Intercept: Handler to redirect standard library logs to Loguru
3. SinkFactory: Factory for creating different log output targets
4. LoggerConfigurator: Main configurator for the logging system

Key Features:
- Spring Boot style formatting
- Multiple output targets (console, plain file, error file, JSON)
- Automatic log rotation and retention
- Standard library log interception
- Process-aware configuration
- Type-safe configuration with dataclasses

Improvements in this refactored version:
- Added constants to replace magic numbers
- Enhanced error handling for sink creation
- Improved type hints throughout
- Better process fork handling
- Clear section organization
- Comprehensive module documentation
"""
