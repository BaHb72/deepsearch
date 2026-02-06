"""支持 python -m core 运行

这是 `python -m core` 入口点，确保与 `uv run deepsearch` 行为一致。
"""

# 统一的启动引导，必须在导入其他模块之前调用
from core.bootstrap import bootstrap

bootstrap()

from core.cli.main import main

if __name__ == "__main__":
    main()
