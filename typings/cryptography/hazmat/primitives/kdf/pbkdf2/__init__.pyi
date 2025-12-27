from typing import Any

from ...hashes import HashAlgorithm

class PBKDF2HMAC:
    def __init__(
        self,
        algorithm: HashAlgorithm,
        length: int,
        salt: bytes,
        iterations: int,
    ) -> None: ...
    def derive(self, data: bytes) -> bytes: ...

__all__ = ["PBKDF2HMAC"]
