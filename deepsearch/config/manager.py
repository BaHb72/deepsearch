"""
配置管理器

提供统一的配置管理接口，支持：
- 多环境配置（开发、测试、生产）
- 配置文件热重载
- 配置验证
- 配置合并和覆盖
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from loguru import logger

from deepsearch.utils.singleton import Singleton


class ConfigManager(metaclass=Singleton):
    """配置管理器（单例）"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._config_path: Optional[Path] = None
        self._env: str = os.getenv("DEEPSEARCH_ENV", "prod")
        self._watchers: list = []

    def load(self, config_path: Optional[Union[str, Path]] = None) -> None:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，如果为 None 则自动查找
        """
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = self._find_config_file()

        if not self._config_path or not self._config_path.exists():
            logger.warning("配置文件未找到，使用默认配置")
            self._load_defaults()
            return

        logger.info(f"加载配置文件: {self._config_path}")

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}

            # 合并环境特定配置
            self._merge_env_config()

            # 验证配置
            self._validate_config()

            logger.info(f"配置加载成功 (环境: {self._env})")

        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            self._load_defaults()

    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        # 查找顺序
        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "config.yml",
            Path.cwd() / "settings" / f"settings.{self._env}.yaml",
            Path.cwd() / "settings" / f"settings.{self._env}.yml",
            Path.home() / ".deepsearch" / "config.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    def _merge_env_config(self) -> None:
        """合并环境特定的配置"""
        env_config_path = self._config_path.parent / f"settings.{self._env}.yaml"
        if env_config_path.exists():
            try:
                with open(env_config_path, 'r', encoding='utf-8') as f:
                    env_config = yaml.safe_load(f) or {}
                    self._config = self._deep_merge(self._config, env_config)
                    logger.info(f"合并环境配置: {env_config_path}")
            except Exception as e:
                logger.error(f"环境配置加载失败: {e}")

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并两个字典"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _validate_config(self) -> None:
        """验证配置的有效性"""
        required_keys = [
            "app.name",
            "log.level",
            "webui.backend_port",
            "message_bus.buses"
        ]

        # 检查必需的配置项
        for key in required_keys:
            value = self.get(key)
            if value is None:
                raise ConfigurationError(f"缺少必需的配置项: {key}")

        # 验证端口范围
        backend_port = self.get("webui.backend_port")
        if backend_port:
            if not isinstance(backend_port, int) or not (1 <= backend_port <= 65535):
                raise ConfigurationError(f"无效的后端端口: {backend_port}")

        frontend_port = self.get("webui.frontend_port")
        if frontend_port:
            if not isinstance(frontend_port, int) or not (1 <= frontend_port <= 65535):
                raise ConfigurationError(f"无效的前端端口: {frontend_port}")

        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = self.get("log.level")
        if log_level and log_level not in valid_log_levels:
            raise ConfigurationError(f"无效的日志级别: {log_level}")

        # 验证消息总线配置
        buses = self.get("message_bus.buses")
        if buses and isinstance(buses, dict):
            for name, bus_config in buses.items():
                if not isinstance(bus_config, dict):
                    raise ConfigurationError(f"无效的消息总线配置: {name}")
                if "type" not in bus_config:
                    raise ConfigurationError(f"消息总线 {name} 缺少类型配置")

    def _load_defaults(self) -> None:
        """加载默认配置"""
        self._config = {
            "system": {
                "name": "DeepSearch",
                "version": "0.1.0",
                "mode": "production"
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "output": "console"
            },
            "webui": {
                "host": "0.0.0.0",
                "port": 8000,
                "frontend_port": 3000
            },
            "monitoring": {
                "enabled": True,
                "interval": 60
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键（如 'webui.port'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """
        保存配置到文件
        
        Args:
            path: 保存路径，如果为 None 则使用当前配置文件路径
        """
        save_path = Path(path) if path else self._config_path

        if not save_path:
            save_path = Path.cwd() / "config.yaml"

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"配置已保存: {save_path}")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")

    def reload(self) -> None:
        """重新加载配置"""
        if self._config_path:
            self.load(self._config_path)
        else:
            logger.warning("没有配置文件路径，无法重新加载")

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()

    def update(self, config: Dict[str, Any]) -> None:
        """更新配置（合并）"""
        self._config = self._deep_merge(self._config, config)

    @property
    def env(self) -> str:
        """当前环境"""
        return self._env

    @env.setter
    def env(self, value: str) -> None:
        """设置环境"""
        self._env = value
        self.reload()


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config(key: str, default: Any = None) -> Any:
    """获取配置值的快捷方法"""
    return config_manager.get(key, default)


def set_config(key: str, value: Any) -> None:
    """设置配置值的快捷方法"""
    config_manager.set(key, value)
