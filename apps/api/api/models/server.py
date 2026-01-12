"""
WebUI 服务器相关的类型定义。

集中维护 server_manager 等模块需要的配置类型，避免散落的 Dict[str, object]。
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from configparser import RawConfigParser
from dataclasses import dataclass, field
from typing import IO, Any, Final, Literal, MutableMapping, TypeAlias, cast

# Uvicorn/TCP 配置所能接受的基础类型
_ScalarValue: TypeAlias = str | int | float | bool | None

# 允许拓展的配置值类型（列表、元组等）
ConfigValue: TypeAlias = _ScalarValue | list[_ScalarValue] | tuple[_ScalarValue, ...]

LogLevelLiteral = Literal["critical", "error", "warning", "info", "debug", "trace"]
WebSocketImplementationLiteral = Literal["auto", "none", "websockets", "wsproto"]
LoopImplementationLiteral = Literal["auto", "asyncio", "uvloop"]
LifespanModeLiteral = Literal["auto", "on", "off"]

LogConfigType: TypeAlias = dict[str, Any] | str | RawConfigParser | IO[Any] | None
ServerConfigOverrides: TypeAlias = dict[str, object]

_LOG_LEVEL_CHOICES: Final[set[str]] = {"critical", "error", "warning", "info", "debug", "trace"}
_WS_CHOICES: Final[set[str]] = {"auto", "none", "websockets", "wsproto"}
_LOOP_CHOICES: Final[set[str]] = {"auto", "asyncio", "uvloop"}
_LIFESPAN_CHOICES: Final[set[str]] = {"auto", "on", "off"}


@dataclass(slots=True)
class WebServerConfig:
    """结构化的 WebUI 服务器配置，避免使用裸字典传递配置项。"""

    host: str
    port: int
    log_level: LogLevelLiteral = "info"
    access_log: bool = False
    ws: WebSocketImplementationLiteral = "websockets"
    loop: LoopImplementationLiteral = "asyncio"
    lifespan: LifespanModeLiteral = "on"
    timeout_graceful_shutdown: int | None = 5
    reload: bool = False
    log_config: LogConfigType = None
    ssl_certfile: str | os.PathLike[str] | None = None
    ssl_keyfile: str | os.PathLike[str] | None = None
    ssl_keyfile_password: str | None = None
    headers: tuple[tuple[str, str], ...] | None = None
    extras: MutableMapping[str, object] = field(default_factory=dict)

    def apply_overrides(self, overrides: Mapping[str, object]) -> None:
        """根据传入的配置覆盖默认值，并保留无法识别的参数。"""
        for key, value in overrides.items():
            if key == "host" and isinstance(value, str):
                self.host = value
            elif key == "port" and isinstance(value, int):
                self.port = value
            elif key == "log_level" and isinstance(value, str) and value in _LOG_LEVEL_CHOICES:
                self.log_level = cast(LogLevelLiteral, value)
            elif key == "access_log" and isinstance(value, bool):
                self.access_log = value
            elif key == "ws" and isinstance(value, str) and value in _WS_CHOICES:
                self.ws = cast(WebSocketImplementationLiteral, value)
            elif key == "loop" and isinstance(value, str) and value in _LOOP_CHOICES:
                self.loop = cast(LoopImplementationLiteral, value)
            elif key == "lifespan" and isinstance(value, str) and value in _LIFESPAN_CHOICES:
                self.lifespan = cast(LifespanModeLiteral, value)
            elif key == "timeout_graceful_shutdown" and isinstance(value, (int, type(None))):
                # 允许显式传入 None 使用 uvicorn 默认值
                self.timeout_graceful_shutdown = value if isinstance(value, int) else None
            elif key == "reload" and isinstance(value, bool):
                self.reload = value
            elif key == "log_config" and self._is_valid_log_config(value):
                self.log_config = cast(LogConfigType, value)
            elif key == "ssl_certfile" and (path := self._normalize_path(value)) is not None:
                self.ssl_certfile = path
            elif key == "ssl_keyfile" and (path := self._normalize_path(value)) is not None:
                self.ssl_keyfile = path
            elif key == "ssl_keyfile_password" and (isinstance(value, str) or value is None):
                self.ssl_keyfile_password = value
            elif key == "headers":
                normalized = self._normalize_headers(value)
                if normalized is not None:
                    self.headers = normalized
                else:
                    self.extras[key] = value
            else:
                self.extras[key] = value

    def to_uvicorn_kwargs(self) -> ServerConfigOverrides:
        """输出可直接传入 uvicorn.Config 的参数字典。"""
        config: ServerConfigOverrides = {
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "access_log": self.access_log,
            "ws": self.ws,
            "loop": self.loop,
            "lifespan": self.lifespan,
            "timeout_graceful_shutdown": self.timeout_graceful_shutdown,
            "reload": self.reload,
        }
        if self.log_config is not None:
            config["log_config"] = self.log_config
        if self.ssl_certfile is not None:
            config["ssl_certfile"] = self.ssl_certfile
        if self.ssl_keyfile is not None:
            config["ssl_keyfile"] = self.ssl_keyfile
        if self.ssl_keyfile_password is not None:
            config["ssl_keyfile_password"] = self.ssl_keyfile_password
        if self.headers is not None:
            config["headers"] = [tuple(pair) for pair in self.headers]
        if self.extras:
            config.update(self.extras)
        return config

    @staticmethod
    def _normalize_path(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, os.PathLike):
            return cast(str, os.fspath(value))
        return None

    @staticmethod
    def _is_valid_log_config(value: object) -> bool:
        if value is None:
            return True
        return isinstance(value, (dict, str, RawConfigParser)) or hasattr(value, "read")

    @staticmethod
    def _normalize_headers(value: object) -> tuple[tuple[str, str], ...] | None:
        if value is None:
            return None
        if isinstance(value, Mapping):
            return tuple((str(key), str(val)) for key, val in value.items())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            normalized: list[tuple[str, str]] = []
            for item in value:
                if isinstance(item, Sequence) and len(item) == 2:
                    header_key = str(item[0])
                    header_value = str(item[1])
                    normalized.append((header_key, header_value))
                else:
                    return None
            return tuple(normalized)
        return None


__all__ = [
    "ConfigValue",
    "ServerConfigOverrides",
    "LogLevelLiteral",
    "WebSocketImplementationLiteral",
    "LoopImplementationLiteral",
    "LifespanModeLiteral",
    "WebServerConfig",
]
