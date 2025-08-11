from __future__ import annotations

"""
日志系统配置与初始化 (Logging configuration and bootstrap)

该模块提供了完整的日志系统，包括：
1. 日志分类（系统日志、业务日志、监控日志）
2. 结构化日志支持
3. 上下文管理
4. 敏感信息脱敏
5. 多输出通道
6. 美化输出格式
"""
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional

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

# 日志级别样式（整合自 pretty_logger）
LEVEL_STYLES = {
    "TRACE": {"color": "<white>", "icon": "🔍"},
    "DEBUG": {"color": "<cyan>", "icon": "🐛"},
    "INFO": {"color": "<green>", "icon": "ℹ️"},
    "SUCCESS": {"color": "<bold green>", "icon": "✅"},
    "WARNING": {"color": "<yellow>", "icon": "⚠️"},
    "ERROR": {"color": "<red>", "icon": "❌"},
    "CRITICAL": {"color": "<bold red>", "icon": "🚨"}
}

# 模块名称映射（简化显示）
MODULE_NAMES = {
    "deepsearch.core.engine": "引擎",
    "deepsearch.event.engine": "事件",
    "deepsearch.monitoring": "监控",
    "deepsearch.webui": "界面",
    "deepsearch.gateway": "网关",
    "deepsearch.messaging": "消息",
    "deepsearch.core.component_manager": "组件",
    "deepsearch.observability.logger": "日志",
    "deepsearch.trading": "交易",
    "deepsearch.strategy": "策略",
    "deepsearch.indicators": "指标",
}


# ==============================================================================
# Log Classification
# ==============================================================================

class LogClassifier:
    """日志分类器，根据模块名和内容分类日志"""

    # 模块分类定义
    SYSTEM_MODULES = ["core", "event", "messaging", "gateway", "webui", "config", "observability"]
    BUSINESS_MODULES = ["trading", "strategy", "indicators", "data"]
    MONITOR_MODULES = ["monitoring", "health", "metrics"]

    @classmethod
    def classify(cls, record: dict) -> str:
        """根据记录分类日志类型"""
        module = record.get("name", "")

        # 检查是否是业务日志
        for mod in cls.BUSINESS_MODULES:
            if mod in module:
                return "business"

        # 检查是否是监控日志
        for mod in cls.MONITOR_MODULES:
            if mod in module:
                return "monitor"

        # 默认为系统日志
        return "system"


# ==============================================================================
# Sensitive Information Filter
# ==============================================================================

class SensitiveFilter:
    """敏感信息过滤器"""

    # 敏感信息模式
    PATTERNS = {
        "password": r"password['\"]?\s*[:=]\s*['\"]?([^'\"\}\s]+)",
        "token": r"token['\"]?\s*[:=]\s*['\"]?([^'\"\}\s]+)",
        "key": r"(?:api_key|secret_key|access_key)['\"]?\s*[:=]\s*['\"]?([^'\"\}\s]+)",
        "secret": r"secret['\"]?\s*[:=]\s*['\"]?([^'\"\}\s]+)",
    }

    @classmethod
    def filter(cls, message: str) -> str:
        """过滤消息中的敏感信息"""
        if not isinstance(message, str):
            return str(message)

        filtered = message
        for name, pattern in cls.PATTERNS.items():
            filtered = re.sub(pattern, f"{name}=******", filtered, flags=re.IGNORECASE)

        return filtered


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
    # 业务日志特殊配置
    retention_business: str = f"{settings.log.retention_days * 2} days"  # 业务日志保留更长时间
    diagnose: Optional[bool] = None
    compress: str = "zip"
    log_dir: Path = field(init=False)
    # 美化输出配置
    pretty_output: bool = True
    use_icons: bool = True

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
# Context Manager
# ==============================================================================

class LogContext:
    """日志上下文管理器"""

    def __init__(self):
        self._context: Dict[str, Any] = {}

    def bind(self, **kwargs) -> "logger":
        """绑定上下文信息"""
        self._context.update(kwargs)
        return logger.bind(**self._context)

    def unbind(self, *keys) -> None:
        """解绑上下文信息"""
        for key in keys:
            self._context.pop(key, None)

    def clear(self) -> None:
        """清除所有上下文"""
        self._context.clear()

    @property
    def context(self) -> Dict[str, Any]:
        """获取当前上下文"""
        return self._context.copy()


# ==============================================================================
# Formatters
# ==============================================================================

def _format_module_name(module: str) -> str:
    """格式化模块名称"""
    # 查找匹配的模块名映射
    for key, value in MODULE_NAMES.items():
        if module.startswith(key):
            return value

    # 默认返回简化的模块名
    parts = module.split(".")
    if "deepsearch" in parts:
        idx = parts.index("deepsearch")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    return parts[-1] if parts else module


def _spring_formatter(color: bool = True) -> Callable[[dict], str]:
    """Spring Boot 风格格式化器"""
    green = (lambda t: f"<green>{t}</green>") if color else (lambda t: t)
    level_fmt = (lambda t: f"<level>{t:<{LEVEL_WIDTH}}</level>") if color else (lambda t: f"{t:<{LEVEL_WIDTH}}")
    cyan = (lambda t: f"<cyan>{t}</cyan>") if color else (lambda t: t)
    yellow = (lambda t: f"<yellow>{t}</yellow>") if color else (lambda t: t)

    def _fmt(record: dict) -> str:
        # 应用敏感信息过滤
        message = SensitiveFilter.filter(record["message"])
        
        time_str = green(record["time"].strftime(TIME_FORMAT)[:-3])
        level_str = level_fmt(record["level"].name)
        proc_thr = f'{record["process"]:>{PROCESS_WIDTH}} --- [{record["thread"].name:>{THREAD_WIDTH}}]'
        location = f'{record["file"].name}:{record["line"]:<4}'
        service = record["extra"].get("service", "-")
        service_str = yellow(str(service))
        return f"{time_str} | {level_str} | {proc_thr} | {location:{LOCATION_WIDTH}} | {service_str:{SERVICE_WIDTH}} | {message}\n"

    return _fmt


def _pretty_formatter(config: LoggerConfig) -> Callable[[dict], str]:
    """美化格式化器（整合自 pretty_logger）"""

    def _fmt(record: dict) -> str:
        level = record["level"].name
        style = LEVEL_STYLES.get(level, {"color": "<white>", "icon": "•"})

        # 应用敏感信息过滤
        message = SensitiveFilter.filter(record["message"])

        # 时间格式
        time_str = record["time"].strftime("%H:%M:%S")

        # 模块名
        module_str = _format_module_name(record["name"])

        # 根据级别使用不同的格式
        if config.use_icons:
            icon = style["icon"]
        else:
            icon = ""

        if level == "DEBUG":
            # DEBUG 信息使用灰色，不显眼
            return f"<dim>{icon} [{time_str}] [{module_str}] {message}</dim>"
        elif level in ["INFO", "SUCCESS"]:
            # INFO 和 SUCCESS 使用简洁格式
            return f"{style['color']}{icon} [{time_str}] {message}</>"
        elif level == "WARNING":
            # WARNING 突出显示
            return f"{style['color']}{icon} [{time_str}] [{module_str}] {message}</>"
        elif level in ["ERROR", "CRITICAL"]:
            # ERROR 和 CRITICAL 使用醒目格式
            return f"{style['color']}<bold>{icon} [{time_str}] [{module_str}] {message}</bold></>"
        else:
            return f"{icon} [{time_str}] [{module_str}] {message}"

    return _fmt


def _structured_formatter(record: dict) -> str:
    """结构化JSON格式化器"""
    # 基础字段
    structured = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": SensitiveFilter.filter(record["message"]),
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }

    # 添加额外字段
    if record.get("extra"):
        # 分类日志类型
        log_category = LogClassifier.classify(record)
        structured["category"] = log_category

        # 添加所有额外字段
        for key, value in record["extra"].items():
            if key not in structured:
                structured[key] = value

    # 异常信息
    if record.get("exception"):
        structured["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback
        }

    return json.dumps(structured, ensure_ascii=False) + "\n"


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
        # Windows 系统需要特殊处理编码
        if sys.platform == "win32":
            # 尝试设置控制台为 UTF-8 编码
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)  # UTF-8
            except Exception as e:
                # Windows console encoding setup failed, not critical
                pass
        
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

        # 静默第三方库的日志
        self._silence_third_party_loggers()
        
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

    def _silence_third_party_loggers(self) -> None:
        """静默第三方库的日志"""
        third_party_loggers = [
            "urllib3",
            "asyncio",
            "websockets",
            "watchfiles",
            "httpx",
            "httpcore",
            "uvicorn",
            "fastapi",
        ]

        for logger_name in third_party_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)


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
            logger.info("Logger system already started")
            return

        try:
            self._log_path = self._configurator.configure(config)
            self._configured = True
            logger.info("Logger system started successfully")
            if self._log_path:
                logger.info(f"Log directory: {self._log_path}")
        except Exception as e:
            # 日志系统启动失败不应该阻止程序运行，使用标准输出
            print(f"[ERROR] Failed to start logger system: {e}", file=sys.stderr)
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
            print("[INFO] Logger system stopped")
        except Exception as e:
            print(f"[ERROR] Failed to stop logger system: {e}", file=sys.stderr)

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
log_context = LogContext()  # 全局日志上下文


def configure_logger(cfg: Optional[LoggerConfig] = None) -> Optional[Path]:
    """配置日志系统的便捷函数"""
    return _logger_configurator.configure(cfg)


def get_logger(**extra) -> logger:
    """快捷获取 logger"""
    if not _logger_configurator._configured:
        configure_logger()
    return logger.bind(**extra)


def get_business_logger(**extra) -> logger:
    """获取业务日志记录器"""
    if not _logger_configurator._configured:
        configure_logger()
    return logger.bind(category="business", **extra)


def get_monitor_logger(**extra) -> logger:
    """获取监控日志记录器"""
    if not _logger_configurator._configured:
        configure_logger()
    return logger.bind(category="monitor", **extra)


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
