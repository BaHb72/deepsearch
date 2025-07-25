"""
日志配置管理模块

提供动态日志级别控制和过滤功能
"""
import sys
from datetime import datetime
from typing import Dict, Set, Optional

from loguru import logger


class LoggerConfig:
    """日志配置管理器"""

    # 默认日志级别
    DEFAULT_LEVEL = "INFO"

    # 模块级别配置
    module_levels: Dict[str, str] = {}

    # 静默的模块（完全不输出）
    silenced_modules: Set[str] = {
        "websockets",
        "urllib3",
        "asyncio",
        "watchfiles"
    }

    # 日志级别权重（用于比较）
    LEVEL_WEIGHTS = {
        "TRACE": 5,
        "DEBUG": 10,
        "INFO": 20,
        "SUCCESS": 25,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }

    # 日志级别样式
    LEVEL_STYLES = {
        "TRACE": {"color": "dim white", "prefix": "    ", "symbol": "·"},
        "DEBUG": {"color": "dim cyan", "prefix": "    ", "symbol": "○"},
        "INFO": {"color": "green", "prefix": "", "symbol": "●"},
        "SUCCESS": {"color": "bold green", "prefix": "", "symbol": "✓"},
        "WARNING": {"color": "yellow", "prefix": "  ", "symbol": "▲"},
        "ERROR": {"color": "red", "prefix": "", "symbol": "✗"},
        "CRITICAL": {"color": "bold white on red", "prefix": "", "symbol": "█"}
    }

    @classmethod
    def set_level(cls, level: str, module: Optional[str] = None):
        """设置日志级别"""
        if module:
            cls.module_levels[module] = level.upper()
        else:
            cls.DEFAULT_LEVEL = level.upper()

    @classmethod
    def silence_module(cls, module: str):
        """静默指定模块"""
        cls.silenced_modules.add(module)

    @classmethod
    def unsilence_module(cls, module: str):
        """取消静默指定模块"""
        cls.silenced_modules.discard(module)

    @classmethod
    def should_log(cls, record: Dict) -> bool:
        """判断是否应该输出日志"""
        module = record["name"]
        level = record["level"].name

        # 检查是否被静默
        for silenced in cls.silenced_modules:
            if module.startswith(silenced):
                return False

        # 获取该模块的日志级别
        module_level = cls.DEFAULT_LEVEL
        for mod, lvl in cls.module_levels.items():
            if module.startswith(mod):
                module_level = lvl
                break

        # 比较级别
        return cls.LEVEL_WEIGHTS.get(level, 0) >= cls.LEVEL_WEIGHTS.get(module_level, 20)

    @classmethod
    def format_record(cls, record: Dict) -> str:
        """格式化日志记录"""
        if not cls.should_log(record):
            return None

        level = record["level"].name
        style = cls.LEVEL_STYLES.get(level, {"color": "white", "prefix": ""})

        # 时间
        time_str = datetime.now().strftime("%H:%M:%S")

        # 模块名简化
        module = record["name"]
        module_parts = module.split(".")
        if "deepsearch" in module_parts:
            idx = module_parts.index("deepsearch")
            if idx + 1 < len(module_parts):
                module = module_parts[idx + 1]
            else:
                module = module_parts[-1]
        else:
            module = module_parts[-1] if module_parts else module

        # 构建消息
        message = record["message"]

        # 根据级别决定显示格式
        prefix = style["prefix"]
        symbol = style["symbol"]

        if level == "DEBUG":
            # DEBUG 信息更加低调
            return f"<dim>{prefix}{symbol} {time_str} {module:<8} {message}</dim>"
        elif level in ["INFO", "SUCCESS"]:
            # INFO 简洁明了
            return f"<{style['color']}>{prefix}{symbol} {time_str} {message}</{style['color']}>"
        elif level == "WARNING":
            # WARNING 适度突出
            return f"<{style['color']}>{prefix}{symbol} {time_str} [{module}] {message}</{style['color']}>"
        else:
            # ERROR 和 CRITICAL 完整显示
            func = record.get("function", "?")
            line = record.get("line", "?")
            return f"<{style['color']}><bold>{prefix}{symbol} {time_str} [{module}:{func}:{line}] {message}</bold></{style['color']}>"


def setup_hierarchical_logging():
    """设置分层的日志系统"""
    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    def console_filter(record):
        """控制台过滤器"""
        formatted = LoggerConfig.format_record(record)
        if formatted is None:
            return False
        record["formatted"] = formatted
        return True

    logger.add(
        sys.stdout,
        format="{formatted}",
        filter=console_filter,
        level="TRACE",  # 让过滤器决定实际级别
        colorize=True,
        backtrace=False,
        diagnose=False
    )

    # 文件日志（保存所有级别）
    logger.add(
        "logs/deepsearch_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8"
    )

    # 错误日志（只保存错误）
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}\n{exception}",
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )

    # 设置第三方库静默
    import logging
    for module in LoggerConfig.silenced_modules:
        logging.getLogger(module).setLevel(logging.ERROR)

    # 设置一些默认的模块级别
    LoggerConfig.set_level("DEBUG", "deepsearch.core.engine")
    LoggerConfig.set_level("INFO", "deepsearch.webui")
    LoggerConfig.set_level("WARNING", "deepsearch.monitoring")

    return logger
