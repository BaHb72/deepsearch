from typing import Any

class JWTError(Exception):
    ...

class _JWTModule:
    def encode(self, claims: dict[str, Any], key: str, algorithm: str = ...) -> str: ...
    def decode(self, token: str, key: str, algorithms: list[str] | tuple[str, ...]) -> dict[str, Any]: ...

jwt: _JWTModule

__all__ = ["JWTError", "jwt"]
