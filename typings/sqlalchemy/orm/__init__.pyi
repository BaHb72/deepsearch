from typing import Any

class Query:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Session:
    def execute(self, statement: Any, params: Any = ...) -> Any: ...
    def get_bind(self) -> Any: ...

class sessionmaker:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __call__(self, *args: Any, **kwargs: Any) -> Session: ...

class DeclarativeBase:
    metadata: Any

def declarative_base(*args: Any, **kwargs: Any) -> type[Any]: ...
def relationship(entity: str | type[Any], *args: Any, **kwargs: Any) -> Any: ...

__all__ = [
    "Query",
    "Session",
    "sessionmaker",
    "DeclarativeBase",
    "declarative_base",
    "relationship",
]
