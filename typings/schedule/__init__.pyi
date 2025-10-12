from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class Job(Protocol):
    def do(self, job_func: Callable[..., object], *args: object, **kwargs: object) -> Job: ...


class Scheduler(Protocol):
    def every(self, interval: int | float = ..., unit: str | None = ...) -> Job: ...

    def run_pending(self) -> None: ...


def every(interval: int | float = ..., unit: str | None = ...) -> Job: ...


def run_pending() -> None: ...


__all__ = ["every", "run_pending", "Job", "Scheduler"]
