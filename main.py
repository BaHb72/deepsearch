#!/usr/bin/env python3
"""
DeepSearch - 量化交易系统

这是一个兼容性入口文件，推荐使用新的命令行接口：
  python -m deepsearch run          # 运行完整系统
  python -m deepsearch webui        # 运行 WebUI
  python -m deepsearch --help       # 查看所有命令

旧的使用方法（仍然支持）：
  python main.py                    # 默认模式
  python main.py --webui            # WebUI 模式
  python main.py --engine           # 引擎模式
"""
import sys
import warnings

# 显示迁移提示
warnings.warn(
    "直接运行 main.py 的方式已经过时，推荐使用 'python -m deepsearch' 命令。\n"
    "查看帮助：python -m deepsearch --help",
    DeprecationWarning,
    stacklevel=2
)

# 导入并运行 CLI
from deepsearch.cli import main

if __name__ == "__main__":
    # 兼容旧的命令行参数
    if len(sys.argv) > 1:
        if "--webui" in sys.argv:
            sys.argv = ["deepsearch", "webui"]
        elif "--engine" in sys.argv:
            sys.argv = ["deepsearch", "run", "--mode", "engine"]
        else:
            sys.argv = ["deepsearch", "run", "--mode", "full"]
    else:
        sys.argv = ["deepsearch", "run"]

    main()
