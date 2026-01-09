"""
数据库连接配置的读写服务。

该模块封装 database_connections.<env>.yaml 的加载与持久化，
提供基于 Pydantic 的校验以确保配置结构的正确性。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from core.config.models.database_connections import DatabaseConnectionConfigModel
from core.config.settings import Settings
from core.constants import YAML_ENCODING
from loguru import logger


def _read_config(path: Path) -> Dict[str, Any]:
    """读取原始配置字典。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding=YAML_ENCODING) as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:  # pragma: no cover - 防御性处理
        logger.warning("读取数据库连接配置失败: {}", exc)
        data = {}

    if not isinstance(data, dict):
        return {}
    return data


def load_database_connections(
    path: Path,
) -> Tuple[List[DatabaseConnectionConfigModel], Dict[str, Any]]:
    """
    读取数据库连接配置。

    Returns:
        (连接模型列表, 原始配置字典)
    """
    payload = _read_config(path)
    entries = payload.get("database_connections") or []
    models: List[DatabaseConnectionConfigModel] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            models.append(DatabaseConnectionConfigModel.model_validate(entry))
        except Exception as exc:  # pragma: no cover - 保持容错
            logger.warning("数据库连接配置项解析失败: {}", exc)

    return models, payload


def persist_database_connections(
    path: Path,
    connections: Iterable[DatabaseConnectionConfigModel | Dict[str, Any]],
    base_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    持久化数据库连接配置。

    Args:
        path: 配置文件路径
        connections: 要写入的连接列表（Pydantic 模型或原始字典）
        base_payload: 作为写入基础的原始配置字典

    Returns:
        最新写入的完整配置字典
    """
    payload = copy.deepcopy(base_payload) if isinstance(base_payload, dict) else _read_config(path)

    serialized: List[Dict[str, Any]] = []
    for connection in connections:
        if isinstance(connection, DatabaseConnectionConfigModel):
            serialized.append(connection.model_dump(mode="python", exclude_none=True))
        else:
            model = DatabaseConnectionConfigModel.model_validate(connection)
            serialized.append(model.model_dump(mode="python", exclude_none=True))

    payload["database_connections"] = serialized

    # 使用 Settings 校验整体结构，确保写入文件可被配置系统加载
    Settings.model_validate(payload)

    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            backup_path.write_text(path.read_text(encoding=YAML_ENCODING), encoding=YAML_ENCODING)
        except Exception as exc:  # pragma: no cover - 备份失败仅记录日志
            logger.warning("备份数据库连接配置失败: {}", exc)

    with path.open("w", encoding=YAML_ENCODING) as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False)

    return payload
