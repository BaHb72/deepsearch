from typing import Any


class Connection:
    def cursor(self) -> Any: ...
    def close(self) -> None: ...


def connect(dsn: str, *args: Any, **kwargs: Any) -> Connection: ...


__all__ = ["Connection", "connect"]
