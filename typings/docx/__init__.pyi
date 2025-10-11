from __future__ import annotations

from os import PathLike
from typing import Protocol, Sequence


class _Paragraph(Protocol):
    text: str


class _Cell(Protocol):
    text: str


class _Row(Protocol):
    cells: Sequence[_Cell]


class _Table(Protocol):
    rows: Sequence[_Row]


class Document:
    paragraphs: Sequence[_Paragraph]
    tables: Sequence[_Table]

    def __init__(self, docx: str | PathLike[str] | None = ..., **kwargs: object) -> None: ...


def Document(docx: str | PathLike[str] | None = ..., **kwargs: object) -> Document: ...


__all__ = ["Document"]
