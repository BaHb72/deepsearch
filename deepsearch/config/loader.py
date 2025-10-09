"""
配置加载工具。

本模块处理从各种来源加载配置，
特别是基于环境的 YAML 文件。
"""

import shutil
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

from deepsearch.config.migrations import migrate_data_source_config
from deepsearch.constants import YAML_ENCODING


def load_yaml_config() -> Dict[str, Any]:
    """
    加载特定环境的 YAML 配置。

    返回：
        包含加载的配置的字典

    异常：
        SystemExit: 如果配置文件缺失或无效
    """
    # 从环境变量获取环境设置，默认使用生产环境
    import os

    env = os.getenv("APP__ENV", "prod")

    # 构建特定环境的配置文件路径
    config_dir = Path(__file__).parent
    env_config_path = config_dir / f"settings.{env}.yaml"

    # 检查配置文件是否存在
    if not env_config_path.exists():
        # 尝试查找包安装后的配置文件位置
        try:
            import deepsearch

            package_dir = Path(deepsearch.__file__).parent
            alt_config_path = package_dir / "config" / f"settings.{env}.yaml"
            if alt_config_path.exists():
                env_config_path = alt_config_path
            else:
                print(
                    f"[ERROR] Environment config file not found: {env_config_path}", file=sys.stderr
                )
                print(f"[INFO] Please ensure settings.{env}.yaml exists", file=sys.stderr)
                raise FileNotFoundError(f"Config file not found: {env_config_path}")
        except ImportError:
            print(f"[ERROR] Environment config file not found: {env_config_path}", file=sys.stderr)
            raise FileNotFoundError(f"Config file not found: {env_config_path}")

    try:
        with env_config_path.open("r", encoding=YAML_ENCODING) as f:
            config = yaml.safe_load(f) or {}

        config, migrated = migrate_data_source_config(config, source_path=env_config_path)
        if migrated:
            _write_migrated_config(env_config_path, config)

        print(f"[INFO] Loaded environment config: {env_config_path.name} (env: {env})")
        return config
    except Exception as exc:
        print(f"[ERROR] Failed to parse config file {env_config_path}: {exc}", file=sys.stderr)
        raise ValueError(f"Config file parsing failed: {exc}")


def _write_migrated_config(path: Path, config: Dict[str, Any]) -> None:
    """在检测到旧配置时写回迁移后的结果，并保留备份。"""
    try:
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        print(f"[INFO] Legacy config backed up as {backup_path.name}", file=sys.stderr)
    except Exception as backup_error:
        print(f"[WARNING] Failed to backup legacy config: {backup_error}", file=sys.stderr)

    try:
        with path.open("w", encoding=YAML_ENCODING) as out_file:
            yaml.safe_dump(
                config,
                out_file,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        print(f"[INFO] Migrated data source config written to {path.name}", file=sys.stderr)
    except Exception as write_error:
        print(f"[WARNING] Failed to write migrated config: {write_error}", file=sys.stderr)
