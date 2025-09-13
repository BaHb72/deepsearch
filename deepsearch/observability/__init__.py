"""
DeepSearch Observability Module

统一的可观测性模块，包含日志、监控、指标和分析功能。
"""

from .logger import logger, logger_manager, LoggerManager

# Convenience functions for backward compatibility
def configure_logger(level: str = "INFO"):
    """Configure logger with specified level"""
    logger_manager.set_level(level)
    logger_manager.start()

def get_logger(name: str = None):
    """Get a logger instance"""
    return logger_manager.get_logger(name)

def setup_logging(level: str = "INFO"):
    """Setup logging system"""
    configure_logger(level)

__all__ = [
    'logger',
    'logger_manager',
    'LoggerManager',
    'configure_logger',
    'get_logger',
    'setup_logging'
]