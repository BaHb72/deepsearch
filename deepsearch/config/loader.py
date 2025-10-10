"""
配置加载工具。

本模块处理从各种来源加载配置，
特别是基于环境的 YAML 文件。
"""

import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from deepsearch.config.migrations import migrate_data_source_config
from deepsearch.constants import YAML_ENCODING


def ensure_env_config_file(env: str, config_dir: Optional[Path] = None) -> Path:
    """确保指定环境的配置文件存在。

    若实际配置缺失且存在 `.example` 模板，则自动复制一份供运行时使用。
    """

    base_dir = config_dir or Path(__file__).parent
    target_path = base_dir / f"settings.{env}.yaml"

    if target_path.exists():
        return target_path

    example_path = base_dir / f"settings.{env}.yaml.example"
    if example_path.exists():
        shutil.copy2(example_path, target_path)
        print(
            f"[INFO] settings.{env}.yaml 不存在，已由模板自动生成",
            file=sys.stderr,
        )
        return target_path

    raise FileNotFoundError(
        f"Config file not found: {target_path}. Please create it based on {example_path.name}"
    )


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
    try:
        env_config_path = ensure_env_config_file(env, config_dir=config_dir)
    except FileNotFoundError:
        # 尝试查找包安装后的配置文件位置
        env_config_path = config_dir / f"settings.{env}.yaml"
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
