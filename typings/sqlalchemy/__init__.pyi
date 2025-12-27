from typing import Any, Callable, Mapping, Protocol, TypeVar

T = TypeVar("T", bound=Callable[..., Any])

class _Executable(Protocol):
    def execute(self, *args: Any, **kwargs: Any) -> Any: ...

class text:
    def __init__(self, statement: str) -> None: ...

class _EventModule:
    def listens_for(
        self, target: Any, identifier: str, *args: Any, **kwargs: Any
    ) -> Callable[[T], T]: ...

event: _EventModule

class Engine:
    dialect: Any
    pool: Any

    def connect(self, *args: Any, **kwargs: Any) -> _Executable: ...
    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any: ...

class Inspector:
    def get_table_names(self, *args: Any, **kwargs: Any) -> list[str]: ...
    def get_columns(
        self, table_name: str, *args: Any, **kwargs: Any
    ) -> list[Mapping[str, Any]]: ...

class _FuncModule:
    def now(self) -> Any: ...
    def count(self, *args: Any) -> Any: ...
    def sum(self, *args: Any) -> Any: ...
    def max(self, *args: Any) -> Any: ...
    def min(self, *args: Any) -> Any: ...
    def __getattr__(self, name: str) -> Any: ...

func: _FuncModule

def create_engine(url: str, *args: Any, **kwargs: Any) -> Engine: ...
def inspect(target: Any, *args: Any, **kwargs: Any) -> Inspector: ...
def select(*entities: Any) -> Any: ...
def Column(*args: Any, **kwargs: Any) -> Any: ...
def ForeignKey(*args: Any, **kwargs: Any) -> Any: ...
def UniqueConstraint(*args: Any, **kwargs: Any) -> Any: ...
def LargeBinary(length: int | None = ...) -> Any: ...
def insert(table: Any) -> Any: ...
def update(table: Any) -> Any: ...
def delete(table: Any) -> Any: ...

class _ScalarType(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

Boolean: _ScalarType
DateTime: _ScalarType
Integer: _ScalarType
Numeric: _ScalarType
String: _ScalarType
Text: _ScalarType
JSON: _ScalarType

__all__ = [
    "Boolean",
    "Column",
    "DateTime",
    "ForeignKey",
    "Integer",
    "JSON",
    "LargeBinary",
    "Numeric",
    "String",
    "Text",
    "UniqueConstraint",
    "create_engine",
    "event",
    "func",
    "insert",
    "inspect",
    "select",
    "text",
    "update",
    "delete",
]
