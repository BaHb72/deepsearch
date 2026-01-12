from typing import Any, MutableMapping

rcParams: MutableMapping[str, Any]

def use(backend: str, *, force: bool = ...) -> None: ...

__all__ = ["pyplot", "use", "rcParams"]
