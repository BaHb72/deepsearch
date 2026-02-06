"""DeepSearch 启动引导模块

统一的环境初始化入口，所有入口点都应在模块顶层调用 bootstrap()。
这确保了无论通过哪种方式启动（uv run、python -m、直接运行），
环境配置都是一致的。

使用方法:
    from core.bootstrap import bootstrap
    bootstrap()  # 在导入其他 core 模块之前调用
"""

from __future__ import annotations

import sys

_initialized: bool = False


def bootstrap() -> None:
    """执行启动前的环境初始化（幂等）

    当前执行的初始化:
    - Windows 控制台编码设置为 UTF-8，解决中文显示问题

    此函数设计为幂等的，多次调用不会产生副作用。
    """
    global _initialized
    if _initialized:
        return

    # Windows 控制台编码设置
    if sys.platform == "win32":
        try:
            from core.core.utils.file_encoding import PlatformEncodingHelper

            PlatformEncodingHelper.setup_console_encoding(encoding="utf-8")
        except Exception:
            # 静默失败，不影响程序启动
            # 此时日志系统可能尚未初始化，不使用 logger
            pass

    _initialized = True
