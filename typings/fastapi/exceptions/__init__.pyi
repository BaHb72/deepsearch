from typing import Any, Sequence

class RequestValidationError(Exception):
    def errors(self) -> Sequence[Any]: ...

__all__ = ["RequestValidationError"]
