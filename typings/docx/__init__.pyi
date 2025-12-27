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

class DocumentProtocol(Protocol):
    paragraphs: Sequence[_Paragraph]
    tables: Sequence[_Table]

def Document(docx: str | PathLike[str] | None = ..., **kwargs: object) -> DocumentProtocol: ...

__all__ = ["Document", "DocumentProtocol"]
