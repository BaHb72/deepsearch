from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Protocol


class _MemoryInfo(Protocol):
    rss: int
    vms: int


class _VirtualMemory(Protocol):
    total: int
    available: int
    percent: float
    used: int
    free: int


class _DiskUsage(Protocol):
    total: int
    used: int
    free: int
    percent: float


class _DiskIO(Protocol):
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


class _NetIO(Protocol):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


class _Connection(Protocol):
    pid: int | None
    laddr: Any
    raddr: Any
    status: str


class Process:
    pid: int

    def __init__(self, pid: int | None = ...) -> None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = ...) -> None: ...

    def children(self, recursive: bool = ...) -> Sequence[Process]: ...

    def is_running(self) -> bool: ...

    def cpu_percent(self, interval: float | None = ...) -> float: ...

    def cpu_times(self) -> Any: ...

    def memory_info(self) -> _MemoryInfo: ...

    def memory_percent(self) -> float: ...

    def num_threads(self) -> int: ...

    def status(self) -> str: ...

    def name(self) -> str: ...

    def cmdline(self) -> list[str]: ...

    def exe(self) -> str: ...

    def as_dict(self, attrs: Sequence[str] | None = ...) -> dict[str, Any]: ...


class TimeoutExpired(Exception):
    ...


class Error(Exception):
    ...


class NoSuchProcess(Error):
    ...


class AccessDenied(Error):
    ...


class ZombieProcess(Error):
    ...


class _OSModule(Protocol):
    name: str

    def uname(self) -> Any: ...


class _SysModule(Protocol):
    version: str


os: _OSModule
sys: _SysModule
WINDOWS: bool


def cpu_percent(interval: float | None = ..., percpu: bool = ...) -> float: ...


def cpu_count(logical: bool | None = ...) -> int | None: ...


def cpu_freq() -> Any: ...


def cpu_times() -> Any: ...


def getloadavg() -> tuple[float, float, float]: ...


def virtual_memory() -> _VirtualMemory: ...


def swap_memory() -> Any: ...


def disk_usage(path: str) -> _DiskUsage: ...


def disk_io_counters() -> _DiskIO: ...


def net_io_counters() -> _NetIO: ...


def disk_partitions(all: bool = ...) -> Sequence[Any]: ...


def net_connections(kind: str | None = ...) -> Sequence[_Connection]: ...


def pids() -> list[int]: ...


def process_iter(attrs: Sequence[str] | None = ...) -> Iterator[Process]: ...


def boot_time() -> float: ...


def wait_procs(procs: Iterable[Process], timeout: float | None = ...) -> tuple[list[Process], list[Process]]: ...


__all__ = [
    "Process",
    "cpu_percent",
    "cpu_count",
    "cpu_freq",
    "cpu_times",
    "virtual_memory",
    "swap_memory",
    "disk_usage",
    "disk_io_counters",
    "net_io_counters",
    "net_connections",
    "pids",
    "process_iter",
    "boot_time",
    "wait_procs",
    "TimeoutExpired",
    "Error",
    "NoSuchProcess",
    "AccessDenied",
    "ZombieProcess",
    "os",
    "sys",
    "WINDOWS",
]
