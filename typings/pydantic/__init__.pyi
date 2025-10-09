from typing import Any, Callable, ClassVar, Dict, Generic, Iterable, Mapping, Optional, Sequence, Type, TypeVar

_T = TypeVar("_T", bound="BaseModel")

class BaseModel:
    model_config: ClassVar[dict[str, Any]]
    def __init__(self, **data: Any) -> None: ...
    def model_dump(self, *, mode: str | None = ..., by_alias: bool | None = ..., exclude_none: bool | None = ...) -> Dict[str, Any]: ...
    def dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]: ...
    def model_copy(self, *, update: Optional[Mapping[str, Any]] = ...) -> "BaseModel": ...
    def model_json_schema(self) -> Dict[str, Any]: ...
    @classmethod
    def model_validate(cls: Type[_T], obj: Any, *, strict: bool | None = ...) -> _T: ...
    @classmethod
    def model_construct(cls: Type[_T], _fields_set: Optional[Iterable[str]] = ..., **data: Any) -> _T: ...

class BaseSettings(BaseModel):
    pass

class FieldInfo:
    annotation: Any
    default: Any
    metadata: Mapping[str, Any]

class _FieldDescriptor:
    def __call__(self, default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...

Field = _FieldDescriptor()

class ValidationError(Exception):
    errors: Callable[[], Sequence[Mapping[str, Any]]]
    def __init__(self, errors: Sequence[Mapping[str, Any]], model: Type[BaseModel]) -> None: ...

class ConfigDict(dict[str, Any]):
    ...

class PositiveInt(int):
    ...

class _ValidatorDescriptor:
    def __call__(self, *fields: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

field_validator = _ValidatorDescriptor()
model_validator = _ValidatorDescriptor()
validator = field_validator

class SecretStr(str):
    pass

__all__ = [
    "BaseModel",
    "BaseSettings",
    "Field",
    "ValidationError",
    "ConfigDict",
    "field_validator",
    "model_validator",
    "PositiveInt",
    "SecretStr",
]
