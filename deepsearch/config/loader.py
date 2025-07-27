"""
配置加载工具。

本模块处理从各种来源加载配置，
特别是基于环境的 YAML 文件。
"""
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

from deepsearch.constants import YAML_ENCODING


def load_yaml_config() -> Dict[str, Any]:
    """
    加载特定环境的 YAML 配置。
    
    返回：
        包含加载的配置的字典
        
    异常：
        SystemExit: 如果配置文件缺失或无效
    """
    # 默认使用开发环境
    env = "dev"

    # 构建特定环境的配置文件路径
    config_dir = Path(__file__).parent
    env_config_path = config_dir / f"settings.{env}.yaml"

    # 检查配置文件是否存在
    if not env_config_path.exists():
        print(f"[错误] 未找到环境配置文件：{env_config_path}", file=sys.stderr)
        print(f"[信息] 请确保 settings.{env}.yaml 存在", file=sys.stderr)
        raise FileNotFoundError(f"配置文件不存在: {env_config_path}")

    try:
        with env_config_path.open("r", encoding=YAML_ENCODING) as f:
            config = yaml.safe_load(f) or {}
        print(f"[信息] 已加载环境配置：{env_config_path.name}")
        return config
    except Exception as exc:
        print(f"[错误] 解析配置文件失败 {env_config_path}：{exc}", file=sys.stderr)
        raise ValueError(f"配置文件解析失败: {exc}")
