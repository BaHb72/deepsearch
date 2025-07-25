"""
DeepSearch 配置管理。

本模块为应用程序提供配置加载和管理功能。
"""
import sys

from pydantic import ValidationError

from .settings import Settings

# 创建单例配置实例
try:
    settings = Settings()
except ValidationError as e:
    print(f"[错误] 配置验证失败：\n{e}", file=sys.stderr)
    raise SystemExit(1)

__all__ = ["settings", "Settings"]
