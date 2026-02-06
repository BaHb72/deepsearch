"""Console entry point bridging to the CLI implementation."""

from __future__ import annotations

# 统一的启动引导，必须在导入其他模块之前调用
from core.bootstrap import bootstrap

bootstrap()

from core.cli.main import cli


def main() -> None:
    """Invoke the DeepSearch CLI."""
    cli(prog_name="deepsearch")
