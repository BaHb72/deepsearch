"""
测试模块示例

演示如何使用日志系统和配置系统的基本示例
"""

from trader.core.logger import get_logger

log = get_logger(service="test")


def run():
    log.debug("DEBUG")
    log.info("INFO")
