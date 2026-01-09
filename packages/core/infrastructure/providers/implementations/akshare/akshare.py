"""
AkShare数据提供者 - 重构版本
通过模块化设计提高可维护性，保持向后兼容性
"""

# 导入重构后的实现
from .akshare_refactored import AkShareProxyProvider

# 导出主类（保持向后兼容）
__all__ = ["AkShareProxyProvider"]
