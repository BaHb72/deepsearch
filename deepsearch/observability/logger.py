"""
Logger Manager for DeepSearch

Provides centralized logging management using loguru.
"""

import logging
import os
import re
import sys
import threading
import zipfile
from collections.abc import Mapping as MappingABC
from datetime import datetime, timedelta
from pathlib import Path
from types import FrameType
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Sequence, TYPE_CHECKING, cast

from loguru import logger

from deepsearch.constants import (
    DEFAULT_LOG_ARCHIVE_AFTER_DAYS,
    DEFAULT_LOG_ARCHIVE_DIRECTORY,
    DEFAULT_LOG_MODULE_DIRECTORY,
    DEFAULT_LOG_MODULE_MAX_DEPTH,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_LOG_ROTATION_TIME,
)

if TYPE_CHECKING:
    from deepsearch.config.models.log import LogConfig
    from loguru import Logger, Record as LogRecordDict
else:
    FormatFunction = Callable[[MutableMapping[str, object]], str]
    LogRecordDict = MutableMapping[str, object]

MODULE_SPLIT_PATTERN = re.compile(r"[._]+")
ARCHIVE_COMPRESSION_LEVEL = 9

ModuleFilter = Callable[[LogRecordDict], bool]


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

        logger.opt(depth=depth, exception=record.exc_info).bind(module=record.name).log(
            level, record.getMessage()
        )


class LoggerManager:
    """Manages application-wide logging configuration"""

    def __init__(self) -> None:
        self.log_path: Path = Path("data/logs")
        self.log_level: str = "INFO"
        self._started: bool = False
        self._logging_bridge_installed: bool = False
        self._datasource_sinks: Dict[str, int] = {}
        self._datasource_configs: Dict[str, None] = {}
        self._module_sinks: Dict[str, int] = {}
        self._module_lock = threading.Lock()
        self._rotation_rule: str = DEFAULT_LOG_ROTATION_TIME
        self._retention_days: int = DEFAULT_LOG_RETENTION_DAYS
        self._json_enabled: bool = False
        self._archive_enabled: bool = True
        self._archive_format: str = "zip"
        self._archive_after_days: int = DEFAULT_LOG_ARCHIVE_AFTER_DAYS
        self._archive_purge_days: Optional[int] = None
        self._archive_directory_name: str = DEFAULT_LOG_ARCHIVE_DIRECTORY
        self._module_logging_enabled: bool = False
        self._module_directory_name: str = DEFAULT_LOG_MODULE_DIRECTORY
        self._module_max_depth: int = DEFAULT_LOG_MODULE_MAX_DEPTH
        self._module_rotation_rule: Optional[str] = None
        self._module_retention_days: Optional[int] = None
        self._level_override: bool = False
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

    def _load_log_configuration(self) -> None:
        """从全局设置加载并应用日志配置。"""

        try:
            from deepsearch.config import get_config

            settings_obj = get_config()
        except Exception:
            return

        log_config = getattr(settings_obj, "log", None)
        if log_config is None:
            return

        log_dir_candidate = getattr(settings_obj, "log_dir", None)
        if isinstance(log_dir_candidate, Path):
            self.log_path = log_dir_candidate
        elif isinstance(log_dir_candidate, str) and log_dir_candidate:
            self.log_path = Path(log_dir_candidate)

        self._apply_log_config(log_config)

    def _apply_log_config(self, config: "LogConfig") -> None:
        """应用 Settings.log 中的详细配置。"""

        self._rotation_rule = config.rotation or DEFAULT_LOG_ROTATION_TIME
        self._retention_days = int(config.retention_days)
        self._json_enabled = bool(config.enable_json)
        if not self._level_override:
            self.log_level = config.level

        archive_config = config.archive
        self._archive_enabled = archive_config.enabled
        self._archive_format = archive_config.format
        self._archive_after_days = int(archive_config.archive_after_days)
        self._archive_directory_name = archive_config.directory or DEFAULT_LOG_ARCHIVE_DIRECTORY
        self._archive_purge_days = (
            int(archive_config.purge_after_days)
            if archive_config.purge_after_days is not None
            else None
        )

        modules_config = config.modules
        self._module_logging_enabled = modules_config.enabled
        self._module_directory_name = modules_config.directory or DEFAULT_LOG_MODULE_DIRECTORY
        self._module_max_depth = int(modules_config.max_depth)
        self._module_rotation_rule = modules_config.rotation
        self._module_retention_days = (
            int(modules_config.retention_days)
            if modules_config.retention_days is not None
            else None
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

    def _module_key_from_name(self, logger_name: Optional[str]) -> Optional[str]:
        """根据 logger 名称提取用于分模块的键。"""
        if not logger_name or not isinstance(logger_name, str):
            return None
        segments = [segment for segment in logger_name.split(".") if segment]
        if not segments:
            return None
        limited = segments[: self._module_max_depth]
        return ".".join(limited)

    def _module_filter_factory(self, module_key: str) -> ModuleFilter:
        """构造模块日志过滤器，仅接受匹配模块的记录。"""

        def _filter(record: LogRecordDict) -> bool:
            extra = record.get("extra")
            if isinstance(extra, MappingABC):
                extra_key = extra.get("module_key")
                if isinstance(extra_key, str):
                    return extra_key == module_key
            name = record.get("name")
            return isinstance(name, str) and self._module_key_from_name(name) == module_key

        return _filter

    def _module_directory_for_key(self, module_key: str) -> Path:
        """返回指定模块日志所在目录，并确保路径存在。"""
        segments = [segment.strip() or "default" for segment in module_key.split(".")]
        relative_path = Path(self._module_directory_name, *segments)
        full_path = self.log_path / relative_path
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path

    def _ensure_module_sink(self, module_key: Optional[str]) -> None:
        """确保为模块创建独立日志 sink。"""
        if not self._module_logging_enabled or not module_key:
            return
        if module_key in self._module_sinks:
            return

        with self._module_lock:
            if module_key in self._module_sinks:
                return
            module_dir = self._module_directory_for_key(module_key)
            pattern = module_dir / f"{module_key.replace('.', '_')}_{{time:YYYY-MM-DD}}.log"
            rotation_rule = self._module_rotation_rule or self._rotation_rule
            archive_days = self._module_retention_days or self._archive_after_days
            archive_dir = module_dir / self._archive_directory_name
            retention_handler = self._build_retention_handler(
                archive_base=archive_dir,
                retention_days=archive_days,
            )
            filter_callable = self._module_filter_factory(module_key)
            sink_id = logger.add(
                str(pattern),
                rotation=rotation_rule,
                retention=retention_handler,
                level=self.log_level,
                format=self._format_file,
                encoding="utf-8",
                filter=cast(Any, filter_callable),
            )
            self._module_sinks[module_key] = sink_id

    def _build_retention_handler(
            self,
            *,
            archive_base: Path,
            retention_days: Optional[int],
    ) -> Callable[[Sequence[str]], None]:
        """创建处理过期日志的回调。"""
        effective_days = retention_days or self._archive_after_days
        effective_days = max(effective_days, 1)
        archive_enabled = self._archive_enabled and self._archive_format == "zip"

        def _handler(files: Sequence[str]) -> None:
            now = datetime.now()
            cutoff = now - timedelta(days=effective_days)
            for file_name in files:
                file_path = Path(file_name)
                if not file_path.exists():
                    continue
                if file_path.suffix.lower() == ".zip":
                    continue
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                except OSError:
                    continue
                if mtime <= cutoff:
                    if archive_enabled:
                        self._compress_log_file(file_path, archive_base)
                    else:
                        file_path.unlink(missing_ok=True)

            if archive_enabled and self._archive_purge_days is not None and archive_base.exists():
                purge_cutoff = now - timedelta(days=self._archive_purge_days)
                for archive_file in archive_base.glob("*.zip"):
                    try:
                        archive_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                    except OSError:
                        continue
                    if archive_mtime <= purge_cutoff:
                        archive_file.unlink(missing_ok=True)

        return _handler

    def _ensure_datasource_sink(self, datasource_name: str) -> None:
        """Ensure datasource sink exists by creating it on demand."""
        self.get_datasource_logger(datasource_name)

    def _compress_log_file(self, source: Path, archive_dir: Path) -> None:
        """将日志压缩为 zip 存档并删除原文件。"""
        if not source.exists():
            return
        archive_dir.mkdir(parents=True, exist_ok=True)
        base_name = source.stem
        target = archive_dir / f"{base_name}.zip"
        counter = 1
        while target.exists():
            target = archive_dir / f"{base_name}_{counter:02d}.zip"
            counter += 1

        try:
            stat_info = source.stat()
        except OSError:
            stat_info = None

        with zipfile.ZipFile(
                target,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=ARCHIVE_COMPRESSION_LEVEL,
        ) as archive:
            archive.write(source, arcname=source.name)

        if stat_info is not None:
            os.utime(target, (stat_info.st_atime, stat_info.st_mtime))

        source.unlink(missing_ok=True)

    def _patch_record_for_modules(self, record: LogRecordDict) -> LogRecordDict:
        """在日志记录中补充模块信息并触发 sink 创建。"""
        if not self._module_logging_enabled:
            return record

        module_key = None
        name_obj = record.get("name")
        if isinstance(name_obj, str):
            module_key = self._module_key_from_name(name_obj)

        extra = record.get("extra")
        if module_key is None and isinstance(extra, MappingABC):
            module_candidate = extra.get("module")
            if isinstance(module_candidate, str):
                module_key = self._module_key_from_name(module_candidate)

        if module_key:
            self._ensure_module_sink(module_key)
            if not isinstance(extra, dict):
                extra = {}
                record["extra"] = extra
            extra.setdefault("module", self._normalize_module_name(module_key))
            extra["module_key"] = module_key

        return record

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

    def _apply_logger_configuration(
            self,
            *,
            extra: Mapping[str, object] | None = None,
            patcher: Callable[[LogRecordDict], object] | None = None,
    ) -> None:
        """Thin wrapper around loguru.configure with permissive typing."""
        configure_kwargs: dict[str, object] = {}
        if extra is not None:
            configure_kwargs["extra"] = extra
        if patcher is not None:
            configure_kwargs["patcher"] = patcher
        configure_callable = cast(Callable[..., object], logger.configure)
        configure_callable(**configure_kwargs)

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

        self._load_log_configuration()

        self.log_path.mkdir(parents=True, exist_ok=True)

        self._configure_stdlib_bridge()

        logger.remove()
        patcher = self._patch_record_for_modules if self._module_logging_enabled else None
        self._apply_logger_configuration(
            extra={"module": None, "module_key": None},
            patcher=patcher,
        )

        logger.add(
            sys.stderr,
            format=self._format_console,
            level=self.log_level,
            colorize=True,
        )

        log_file = self.log_path / "deepsearch_{time:YYYY-MM-DD}.log"
        archive_root = self.log_path / self._archive_directory_name
        primary_retention = self._build_retention_handler(
            archive_base=archive_root,
            retention_days=self._archive_after_days,
        )
        logger.add(
            str(log_file),
            rotation=self._rotation_rule,
            retention=primary_retention,
            level=self.log_level,
            format=self._format_file,
            encoding="utf-8",
        )

        self._datasource_sinks = {}
        self._module_sinks = {}
        for datasource_name in self._datasource_configs.keys():
            self._ensure_datasource_sink(datasource_name)

        self._started = True
        self.get_logger("observability").info("logging system started")

    def stop(self) -> None:
        """Stop the logging system"""
        if not self._started:
            return

        self.get_logger("observability").info("logging system stopping")
        self._teardown_stdlib_bridge()
        logger.remove()
        self._apply_logger_configuration(
            extra={"module": None, "module_key": None},
            patcher=None,
        )
        self._datasource_sinks = {}
        self._module_sinks = {}
        self._started = False

    def set_level(self, level: str) -> None:
        """Set the logging level"""
        self.log_level = level
        self._level_override = True
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

    def get_datasource_logger(self, name: str) -> "Logger":
        """为指定数据源提供专用 logger，并确保开启独立 sink。"""
        from loguru import logger as loguru_logger

        if name not in self._datasource_sinks:
            subdir = self.ensure_subdirectory("datasource")
            sink_path = subdir / f"{name}_{{time:YYYY-MM-DD}}.log"
            archive_dir = subdir / self._archive_directory_name
            retention_handler = self._build_retention_handler(
                archive_base=archive_dir,
                retention_days=self._archive_after_days,
            )

            def _filter(record: LogRecordDict) -> bool:
                extra = record.get("extra")
                if isinstance(extra, MappingABC):
                    return extra.get("datasource") == name
                return False

            sink_id = loguru_logger.add(
                str(sink_path),
                rotation="50 MB",
                retention=retention_handler,
                level="DEBUG",
                format=self._format_file,
                encoding="utf-8",
                filter=cast(Any, _filter),
            )
            self._datasource_sinks[name] = sink_id
        return loguru_logger.bind(datasource=name, module=f"datasource.{name}")



logger_manager = LoggerManager()


__all__ = ["logger_manager", "logger", "LoggerManager", "InterceptHandler"]
