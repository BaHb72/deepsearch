"""
Logger Manager for DeepSearch

Provides centralized logging management using loguru.
"""

import logging
import re
import sys
from collections.abc import Mapping as MappingABC
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Callable, Dict, MutableMapping, Optional, Sequence, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import FormatFunction, Record as LogRecordDict
else:
    FormatFunction = Callable[[MutableMapping[str, object]], str]
    LogRecordDict = MutableMapping[str, object]

MODULE_SPLIT_PATTERN = re.compile(r"[._]+")


class InterceptHandler(logging.Handler):
    """Redirect stdlib logging records into loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level_name = logger.level(record.levelname).name
        except ValueError:
            level_name = logging.getLevelName(record.levelno)
        level = str(level_name)

        frame: Optional[FrameType] = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class LoggerManager:
    """Manages application-wide logging configuration"""

    def __init__(self) -> None:
        self.log_path: Path = Path("data/logs")
        self.log_level: str = "INFO"
        self._started: bool = False
        self._logging_bridge_installed: bool = False
        self.module_aliases: Dict[str, str] = {
            "deepsearch": "深度搜索平台",
            "deepsearch.core": "核心模块",
            "deepsearch.core.runtime": "运行时调度",
            "deepsearch.core.components": "核心组件",
            "deepsearch.core.managers": "组件管理",
            "deepsearch.observability": "可观测体系",
            "deepsearch.infrastructure": "基础设施",
            "deepsearch.backtest": "回测系统",
            "deepsearch.webui": "Web界面",
            "deepsearch.messaging": "消息总线",
            "deepsearch.gateway": "交易网关",
            "deepsearch.config": "配置中心",
            "deepsearch.constants": "常量定义",
            "deepsearch.data": "数据服务",
            "deepsearch.indicators": "指标计算",
            "deepsearch.tests": "自动化测试",
        }
        self.token_translations: Dict[str, str] = {
            "deepsearch": "深度搜索",
            "core": "核心",
            "runtime": "运行时",
            "engine": "引擎",
            "engine_refactored": "引擎重构",
            "engine_adapter": "引擎适配",
            "adapter": "适配器",
            "async": "异步",
            "component": "组件",
            "components": "组件",
            "manager": "管理器",
            "managers": "管理器",
            "factory": "工厂",
            "state": "状态",
            "config": "配置",
            "settings": "设置",
            "infrastructure": "基础设施",
            "gateway": "网关",
            "webui": "Web界面",
            "frontend": "前端",
            "backend": "后端",
            "observability": "可观测",
            "backtest": "回测",
            "data": "数据",
            "database": "数据库",
            "analytics": "分析",
            "akshare": "AkShare",
            "cache": "缓存",
            "direct": "直连",
            "monitoring": "监控",
            "messaging": "消息",
            "bus": "总线",
            "decorators": "装饰器",
            "error": "错误",
            "errors": "错误",
            "logging": "日志",
            "logger": "日志器",
            "metrics": "指标",
            "event": "事件",
            "events": "事件",
            "service": "服务",
            "services": "服务",
            "worker": "工作器",
            "workers": "工作器",
            "providers": "提供者",
            "provider": "提供者",
            "implementations": "实现",
            "implementation": "实现",
            "integration": "集成",
            "notifications": "通知",
            "notification": "通知",
            "performance": "性能",
            "security": "安全",
            "health": "健康",
            "checkers": "检查器",
            "interfaces": "接口",
            "interface": "接口",
            "context": "上下文",
            "async_runner": "异步运行器",
            "monitor": "监控",
            "metrics_collector": "指标采集",
            "database_service": "数据库服务",
            "analytics_db": "分析数据库",
            "simple": "简单",
            "technical": "技术",
            "indicators": "指标",
            "datafeed": "数据馈送",
            "qmt": "QMT",
            "amazingdata": "AmazingData",
            "cleaner": "清洗",
            "main": "主程序",
            "app": "应用",
            "system": "系统",
            "tools": "工具",
            "scripts": "脚本",
            "validator": "校验器",
            "validation": "校验",
            "defaults": "默认",
            "test": "测试",
            "api": "接口",
            "check": "检查",
            "status": "状态",
        }

        self._level_colors: Dict[str, str] = {
            "TRACE": "cyan",
            "DEBUG": "blue",
            "INFO": "green",
            "SUCCESS": "green",
            "WARN": "yellow",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        }

        self._message_colors: Dict[str, str] = {
            "TRACE": "dim",
            "DEBUG": "dim",
            "INFO": "dim",
            "SUCCESS": "dim",
            "NOTICE": "dim",
            "WARN": "yellow",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        }
        self._default_message_color = "dim"

        self._timestamp_color = "dim"
        self._separator_color = "dim"
        self._thread_color = "dim"
        self._pid_color = "magenta"
        self._logger_color = "cyan"
        self._exception_color = "red"
        self._thread_field_width = 15
        self._logger_field_width = 39
        self._message_prefix_width = (
            len("2000-01-01 00:00:00.000")
            + 2
            + 5
            + 1
            + 5
            + 1
            + 3
            + 1
            + 1
            + self._thread_field_width
            + 1
            + 1
            + self._logger_field_width
            + 1
            + 1
            + 1
        )

    def _normalize_module_name(self, raw_name: Optional[str]) -> str:
        """Normalize module identifier while keeping readable labels"""
        if not raw_name:
            return "默认模块"
        name = str(raw_name).strip()
        if not name:
            return "默认模块"
        if any("\u4e00" <= ch <= "\u9fff" for ch in name):
            return name
        alias = self.module_aliases.get(name)
        if alias:
            return alias
        parts = name.split(".")
        for idx in range(len(parts), 0, -1):
            prefix = ".".join(parts[:idx])
            alias = self.module_aliases.get(prefix)
            if alias:
                return alias
        if "." in name:
            name = name.split(".")[-1]
        tokens: list[str] = []
        for raw_token in MODULE_SPLIT_PATTERN.split(name):
            if not raw_token:
                continue
            lowered = raw_token.lower()
            translation = self.token_translations.get(lowered)
            if translation:
                tokens.append(translation)
            else:
                tokens.append(f"自定义({raw_token})")
        if not tokens:
            return "默认模块"
        seen: set[str] = set()
        ordered_tokens: list[str] = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                ordered_tokens.append(token)
        return "·".join(ordered_tokens)

    def register_module_alias(self, identifier: str, display_name: str) -> None:
        """Allow dynamic registration of module aliases"""

        key = identifier.strip()
        if not key:
            return
        self.module_aliases[key] = display_name.strip() or display_name

    def _resolve_module_tag(self, record: LogRecordDict) -> Optional[str]:
        """Resolve module tag from log record extra if provided"""
        extra_obj = record.get("extra")
        module_value: Optional[str] = None
        if isinstance(extra_obj, MappingABC):
            raw_module = extra_obj.get("module")
            if isinstance(raw_module, str):
                module_value = raw_module
            elif raw_module is not None:
                module_value = str(raw_module)
        if not module_value:
            return None
        return self._normalize_module_name(module_value)

    def _resolve_file_location(self, record: LogRecordDict) -> str:
        """Resolve a concise file location for logging output"""
        file_entry = record.get("file")
        if file_entry is None:
            return "unknown"
        raw_path = getattr(file_entry, "path", None)
        if not raw_path:
            return str(file_entry)
        file_path = Path(str(raw_path))
        try:
            relative = file_path.relative_to(Path(__file__).resolve().parent.parent.parent)
        except ValueError:
            try:
                relative = file_path.relative_to(Path.cwd())
            except ValueError:
                return file_path.name.replace("<", "[").replace(">", "]")
        resolved = str(relative).replace("\\", "/")
        return resolved.replace("<", "[").replace(">", "]")

    @staticmethod
    def _sanitize_markup(text: str) -> str:
        """Escape characters interpreted by loguru markup"""
        if not text:
            return ""
        sanitized = text.replace("{", "{{").replace("}", "}}")
        return sanitized.replace("<", r"\<").replace(">", r"\>")

    def _apply_color(self, style: Optional[str], text: str, colorize: bool) -> str:
        if not colorize or not style:
            return text
        return f"<{style}>{text}</>"

    def _format_thread_field(self, thread_name: Optional[str]) -> str:
        thread = (thread_name or "MainThread").strip() or "MainThread"
        trimmed = thread[-self._thread_field_width :]
        return trimmed.rjust(self._thread_field_width)

    def _abbreviate_logger_name(self, name: str) -> str:
        if not name:
            name = "root"
        segments = [segment for segment in name.split(".") if segment]
        if not segments:
            abbreviated = name
        else:
            abbreviated = ".".join(
                segment if index == len(segments) - 1 else segment[0]
                for index, segment in enumerate(segments)
            )
        if len(abbreviated) > self._logger_field_width and len(segments) >= 2:
            shortened = ".".join(segments[-2:])
            if shortened:
                abbreviated = shortened
        if len(abbreviated) > self._logger_field_width:
            abbreviated = abbreviated[-self._logger_field_width :]
        return abbreviated.ljust(self._logger_field_width)

    def _format_message_with_metadata(
        self,
        message: str,
        metadata: str,
        style: Optional[str],
        colorize: bool,
    ) -> str:
        lines = message.splitlines() if message else [""]
        if not lines:
            lines = [""]
        sanitized_lines = [self._sanitize_markup(line) for line in lines]
        primary = self._apply_color(style, sanitized_lines[0], colorize)
        first_line = f"{primary}{metadata}"
        if len(sanitized_lines) == 1:
            return first_line
        indent = " " * self._message_prefix_width
        continuation: list[str] = []
        for line in sanitized_lines[1:]:
            colored_line = self._apply_color(style, line, colorize)
            continuation.append(f"{indent}{colored_line}")
        return "\n".join([first_line] + continuation)

    def _format_spring_boot_line(self, record: LogRecordDict, *, colorize: bool) -> str:
        time_entry = record.get("time")
        timestamp_dt = time_entry if isinstance(time_entry, datetime) else datetime.now()
        timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        level_obj = record.get("level")
        level_name = str(getattr(level_obj, "name", level_obj or "INFO"))

        process_obj = record.get("process")
        pid = int(getattr(process_obj, "id", 0))

        thread_obj = record.get("thread")
        thread_name = str(getattr(thread_obj, "name", ""))
        thread_field = self._format_thread_field(thread_name)

        module_tag = self._resolve_module_tag(record)
        logger_source = str(record.get("name") or "")
        if module_tag and (not logger_source or logger_source == "loguru"):
            logger_source = module_tag
        if not logger_source:
            logger_source = "root"
        line_obj = record.get("line")
        line_no = int(line_obj) if isinstance(line_obj, int) else 0

        logger_source_display = f"{logger_source}:{line_no}" if line_no else logger_source
        logger_field = self._sanitize_markup(self._abbreviate_logger_name(logger_source_display))

        metadata_parts: list[str] = []
        if module_tag and module_tag != logger_source:
            metadata_parts.append(f"模块={self._sanitize_markup(module_tag)}")
        metadata = ""
        if metadata_parts:
            combined = "| " + " | ".join(metadata_parts)
            metadata = " " + (
                self._apply_color(self._separator_color, combined, colorize)
                if colorize
                else combined
            )

        message_style = self._message_colors.get(level_name.upper(), self._default_message_color)
        message_text = record.get("message")
        message_str = str(message_text) if message_text is not None else ""
        message_block = self._format_message_with_metadata(message_str, metadata, message_style, colorize)

        level_color = self._level_colors.get(level_name.upper(), self._separator_color)
        timestamp_token = self._apply_color(self._timestamp_color, timestamp, colorize)
        level_token = self._apply_color(level_color, f"{level_name:>5}", colorize)
        pid_token = self._apply_color(self._pid_color, f"{pid:>5}", colorize)
        separator_token = self._apply_color(self._separator_color, "---", colorize)
        thread_token = self._apply_color(self._thread_color, thread_field, colorize)
        logger_token = self._apply_color(self._logger_color, logger_field, colorize)
        colon_token = self._apply_color(self._separator_color, ":", colorize)

        line = (
            f"{timestamp_token}  "
            f"{level_token} "
            f"{pid_token} "
            f"{separator_token} "
            f"[{thread_token}] "
            f"{logger_token} "
            f"{colon_token} "
            f"{message_block}"
        )

        exception_obj = record.get("exception")
        if exception_obj:
            exception_text = getattr(exception_obj, "formatted", None)
            if not exception_text:
                traceback_obj = getattr(exception_obj, "traceback", None)
                format_callable = getattr(traceback_obj, "format", None) if traceback_obj else None
                if callable(format_callable):
                    try:
                        exception_text = "".join(format_callable()).rstrip("\n")
                    except Exception:
                        exception_text = None
            if not exception_text:
                exc_type = getattr(exception_obj, "type", None)
                exc_value = getattr(exception_obj, "value", None)
                if exc_type or exc_value:
                    type_name = exc_type.__name__ if isinstance(exc_type, type) else str(exc_type)
                    exception_text = f"{type_name}: {exc_value}" if exc_value is not None else type_name
            if not exception_text:
                exception_text = str(exception_obj)
            if exception_text:
                sanitized_exception = self._sanitize_markup(exception_text)
                formatted_exception = (
                    self._apply_color(self._exception_color, sanitized_exception, colorize)
                    if colorize
                    else sanitized_exception
                )
                return f"{line}\n{formatted_exception}\n"
        return f"{line}\n"

    def _format_console(self, record: LogRecordDict) -> str:
        return self._format_spring_boot_line(record, colorize=True)

    def _format_file(self, record: LogRecordDict) -> str:
        return self._format_spring_boot_line(record, colorize=False)

    def _configure_stdlib_bridge(self) -> None:
        """Ensure all stdlib logging is routed through loguru"""

        if self._logging_bridge_installed:
            logging.root.setLevel(self.log_level)
            return

        handler = InterceptHandler()
        logging.root.handlers = [handler]
        logging.root.setLevel(self.log_level)
        logging.captureWarnings(True)

        logger_dict: Sequence[str] = tuple(logging.root.manager.loggerDict.keys())
        for name in logger_dict:
            std_logger = logging.getLogger(name)
            std_logger.handlers = []
            std_logger.propagate = True

        self._logging_bridge_installed = True

    def _teardown_stdlib_bridge(self) -> None:
        """Reset stdlib logging handlers when stopping"""

        if not self._logging_bridge_installed:
            return

        logging.captureWarnings(False)
        logging.root.handlers = []
        self._logging_bridge_installed = False

    def start(self) -> None:
        """Initialize and start the logging system"""
        if self._started:
            return

        self.log_path.mkdir(parents=True, exist_ok=True)

        self._configure_stdlib_bridge()

        logger.configure(extra={"module": None})
        logger.remove()

        logger.add(
            sys.stderr,
            format=self._format_console,
            level=self.log_level,
            colorize=True,
        )

        log_file = self.log_path / "deepsearch_{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_file),
            rotation="1 day",
            retention="7 days",
            level=self.log_level,
            format=self._format_file,
            encoding="utf-8",
        )

        self._started = True
        self.get_logger("observability").info("logging system started")

    def stop(self) -> None:
        """Stop the logging system"""
        if not self._started:
            return

        self.get_logger("observability").info("logging system stopping")
        self._teardown_stdlib_bridge()
        logger.remove()
        self._started = False

    def set_level(self, level: str) -> None:
        """Set the logging level"""
        self.log_level = level
        if self._started:
            self.stop()
            self.start()

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get a logger instance compatible with stdlib logging"""
        if name:
            return logging.getLogger(name)
        return logging.getLogger()

    def ensure_subdirectory(self, name: str) -> Path:
        """确保日志目录下指定子目录存在"""
        subdir = self.log_path / name
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir



logger_manager = LoggerManager()


__all__ = ["logger_manager", "logger", "LoggerManager", "InterceptHandler"]
