"""
美化的日志输出模块

提供更清晰、更美观的日志格式
"""
import sys
from datetime import datetime

from loguru import logger


class PrettyLogger:
    """美化的日志输出器"""

    # 日志级别对应的颜色和符号
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
    }

    @classmethod
    def format_time(cls, record) -> str:
        """格式化时间"""
        return datetime.now().strftime("%H:%M:%S")

    @classmethod
    def format_module(cls, record) -> str:
        """格式化模块名"""
        module = record["name"]

        # 查找匹配的模块名
        for key, value in cls.MODULE_NAMES.items():
            if module.startswith(key):
                return value

        # 默认返回简化的模块名
        parts = module.split(".")
        if len(parts) > 2:
            return parts[-1]
        return module

    @classmethod
    def format_message(cls, record) -> str:
        """格式化日志消息"""
        level = record["level"].name
        style = cls.LEVEL_STYLES.get(level, {"color": "<white>", "icon": "•"})

        # 构建格式化的消息
        time_str = cls.format_time(record)
        module_str = cls.format_module(record)
        message = record["message"]

        # 根据级别使用不同的格式
        if level == "DEBUG":
            # DEBUG 信息使用灰色，不显眼
            return f"<dim>{style['icon']} [{time_str}] [{module_str}] {message}</dim>"
        elif level in ["INFO", "SUCCESS"]:
            # INFO 和 SUCCESS 使用简洁格式
            return f"{style['color']}{style['icon']} [{time_str}] {message}</>"
        elif level == "WARNING":
            # WARNING 突出显示
            return f"{style['color']}{style['icon']} [{time_str}] [{module_str}] {message}</>"
        elif level in ["ERROR", "CRITICAL"]:
            # ERROR 和 CRITICAL 使用醒目格式
            return f"{style['color']}<bold>{style['icon']} [{time_str}] [{module_str}] {message}</bold></>"
        else:
            return f"{style['icon']} [{time_str}] [{module_str}] {message}"

    @classmethod
    def setup_logger(cls):
        """设置美化的日志格式"""
        # 移除默认的处理器
        logger.remove()

        # 添加控制台输出（带颜色）
        logger.add(
            sys.stdout,
            format=cls.format_message,
            level="INFO",
            colorize=True,
            backtrace=False,
            diagnose=False
        )

        # 添加文件输出（完整格式）
        logger.add(
            "logs/deepsearch_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="00:00",
            retention="7 days",
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )

        # 添加错误日志文件
        logger.add(
            "logs/errors_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="00:00",
            retention="30 days",
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )


def setup_pretty_logging():
    """设置美化的日志系统"""
    PrettyLogger.setup_logger()

    # 设置第三方库的日志级别
    import logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    return logger
