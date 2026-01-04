"""
WebUI API 通用类型定义。

这些类型用于约束 FastAPI 接口与前端之间的 JSON 数据结构，
避免在代码中频繁出现 `dict[str, Any]` 或 `object`。
"""

from __future__ import annotations

from typing import TypeAlias

JSONScalar: TypeAlias = str | int | float | bool | None
JSONArray: TypeAlias = list["JSONValue"]
JSONDict: TypeAlias = dict[str, "JSONValue"]
JSONValue: TypeAlias = JSONScalar | JSONArray | JSONDict

__all__ = ["JSONScalar", "JSONValue", "JSONArray", "JSONDict"]
