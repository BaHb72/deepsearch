"""Minimal Symbol value object for legacy compatibility."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Symbol:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("Symbol cannot be empty")
        object.__setattr__(self, "value", normalized.upper())

    def __str__(self) -> str:
        return self.value
