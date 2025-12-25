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

        # 加载独立的 data_sources.yaml（替换原有的 providers.yaml 逻辑）
        config = _load_data_sources_config(config, config_dir)

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


def _load_data_sources_config(config: Dict[str, Any], config_dir: Path) -> Dict[str, Any]:
    """加载独立的数据源配置文件。

    优先级：
    1. data_sources.yaml - 新的独立配置文件（推荐）
    2. providers.yaml - 旧的配置文件（向后兼容）
    3. settings.*.yaml 中的 data_sources 节 - 保持现有配置

    Args:
        config: 已加载的主配置字典
        config_dir: 配置文件目录

    Returns:
        合并后的配置字典
    """
    # 尝试加载 data_sources.yaml（新格式）
    data_sources_path = config_dir / "data_sources.yaml"
    if data_sources_path.exists():
        try:
            with data_sources_path.open("r", encoding=YAML_ENCODING) as f:
                raw_config = yaml.safe_load(f) or {}

            if raw_config:
                # 转换新格式为内部格式
                transformed = _transform_data_sources_config(raw_config)

                # 合并到主配置（data_sources.yaml 优先级高于 settings.*.yaml）
                if "data_sources" not in config:
                    config["data_sources"] = {}

                # 深度合并 data_sources 配置
                _deep_merge(config["data_sources"], transformed)

                print("[INFO] Loaded data sources config: data_sources.yaml")
                return config
        except Exception as e:
            print(f"[WARNING] Failed to load data_sources.yaml: {e}", file=sys.stderr)

    # 向后兼容：尝试加载 providers.yaml（旧格式）
    providers_config_path = config_dir / "providers.yaml"
    if providers_config_path.exists():
        try:
            with providers_config_path.open("r", encoding=YAML_ENCODING) as f:
                providers_config = yaml.safe_load(f) or {}

            if "providers" in providers_config:
                # 旧格式：直接放入 config["providers"]
                # 注意：这是向后兼容，新代码应使用 data_sources.yaml
                if "data_sources" not in config:
                    config["data_sources"] = {}
                if "providers" not in config["data_sources"]:
                    config["data_sources"]["providers"] = {}

                # 将 providers.yaml 中的 providers 列表转换为字典格式
                providers_list = providers_config["providers"]
                if isinstance(providers_list, list):
                    for provider in providers_list:
                        name = provider.get("name")
                        if name:
                            config["data_sources"]["providers"][name] = provider
                elif isinstance(providers_list, dict):
                    config["data_sources"]["providers"].update(providers_list)

                print("[INFO] Loaded legacy providers config: providers.yaml")
        except Exception as e:
            print(f"[WARNING] Failed to load providers.yaml: {e}", file=sys.stderr)

    return config


def _transform_data_sources_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """转换 data_sources.yaml 格式为内部格式。

    新格式（data_sources.yaml）:
        version: "1.0"
        global: { default, fallback_order, circuit_breaker, failover }
        providers: { amazingdata: {...}, akshare: {...} }
        module_overrides: {...}
        access_type_overrides: {...}

    内部格式（兼容现有代码）:
        default: ...
        fallback_order: [...]
        circuit_breaker: {...}
        failover: {...}
        providers: {...}
        module_overrides: {...}
        access_type_overrides: {...}

    Args:
        raw_config: 原始配置字典

    Returns:
        转换后的配置字典
    """
    result: Dict[str, Any] = {}

    # 展开 global 配置到顶层
    global_config = raw_config.get("global", {})
    for key in ("default", "fallback_order", "circuit_breaker", "failover", "health_check"):
        if key in global_config:
            result[key] = global_config[key]

    # 直接复制其他配置
    for key in ("providers", "module_overrides", "access_type_overrides", "realtime"):
        if key in raw_config:
            result[key] = raw_config[key]

    return result


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """深度合并两个字典，将 override 合并到 base。

    Args:
        base: 基础字典（会被修改）
        override: 覆盖字典
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
