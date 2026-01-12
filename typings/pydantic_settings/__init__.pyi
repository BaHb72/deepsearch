from typing import Any, Callable, ClassVar, Dict, Tuple, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound="BaseSettings")
SettingsSourceCallable = Callable[[], Dict[str, Any]]
SettingsConfigDict = Dict[str, Any]

class BaseSettings(BaseModel):
    model_config: ClassVar[SettingsConfigDict]

    @classmethod
    def settings_customise_sources(
        cls: Type[T],
        settings_cls: Type[BaseModel],
        init_settings: SettingsSourceCallable,
        env_settings: SettingsSourceCallable,
        dotenv_settings: SettingsSourceCallable,
        file_secret_settings: SettingsSourceCallable,
    ) -> Tuple[SettingsSourceCallable, ...]: ...
