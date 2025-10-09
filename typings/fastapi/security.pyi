from typing import Optional

from starlette.requests import Request


class HTTPAuthorizationCredentials:
    scheme: str
    credentials: str


class HTTPBearer:
    def __init__(self, *, auto_error: bool = True) -> None: ...

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]: ...
