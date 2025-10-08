from typing import Any, Sequence

class RequestValidationError(Exception):
    errors: Sequence[Any]

__all__ = ["RequestValidationError"]
