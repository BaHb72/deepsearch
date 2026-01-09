"""Console entry point bridging to the CLI implementation."""

from __future__ import annotations

from core.cli.main import cli


def main() -> None:
    """Invoke the DeepSearch CLI."""
    cli(prog_name="deepsearch")
