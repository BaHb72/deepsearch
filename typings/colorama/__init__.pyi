from __future__ import annotations

from typing import Protocol


class _ColorAttributes(Protocol):
    RESET: str
    RED: str
    GREEN: str
    YELLOW: str
    BLUE: str
    MAGENTA: str
    CYAN: str
    WHITE: str


class _StyleAttributes(Protocol):
    BRIGHT: str
    DIM: str
    NORMAL: str
    RESET_ALL: str


Fore: _ColorAttributes
Style: _StyleAttributes


def init(autoreset: bool = ..., strip: bool | None = ..., convert: bool | None = ..., wrap: bool | None = ...) -> None: ...


__all__ = ["Fore", "Style", "init"]
