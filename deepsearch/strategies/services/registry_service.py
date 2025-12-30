"""
Strategy Registry Service

Manages strategy discovery, registration, and dynamic loading.
Supports hot reload for development workflow.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, cast

import yaml
from loguru import logger

from deepsearch.strategies.interfaces.base import BaseStrategy
from deepsearch.strategies.interfaces.models import StrategyCategory, StrategyMeta, StrategyParamDef


class StrategyRegistryService:
    """策略注册服务 - 管理策略发现、注册和动态加载"""

    def __init__(
        self,
        strategies_dir: Optional[Path] = None,
        registry_path: Optional[Path] = None,
    ):
        # 默认路径
        if strategies_dir is None:
            strategies_dir = Path(__file__).parent.parent
        if registry_path is None:
            registry_path = strategies_dir / "config" / "registry.yaml"

        self.strategies_dir = strategies_dir
        self.registry_path = registry_path
        self.implementations_dir = strategies_dir / "implementations"

        # 缓存
        self._registry_cache: Dict[str, StrategyMeta] = {}
        self._class_cache: Dict[str, Type[BaseStrategy]] = {}
        self._last_load_time: Optional[datetime] = None

        logger.info(f"StrategyRegistryService: strategies_dir={strategies_dir}")

    # ============================================
    # Registry Loading
    # ============================================

    def load_registry(self, force_reload: bool = False) -> Dict[str, StrategyMeta]:
        """加载策略注册表"""
        if self._registry_cache and not force_reload:
            return self._registry_cache

        if not self.registry_path.exists():
            logger.warning(f"Registry file not found: {self.registry_path}")
            return {}

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            strategies_data = data.get("strategies", [])
            self._registry_cache = {}

            for item in strategies_data:
                try:
                    # 处理 class -> class_name 的别名
                    if "class" in item:
                        item["class_name"] = item.pop("class")

                    # 转换 params 格式
                    if "params" in item:
                        params = {}
                        for key, val in item["params"].items():
                            if isinstance(val, dict):
                                params[key] = StrategyParamDef(**val)
                            else:
                                params[key] = StrategyParamDef(default=val)
                        item["params"] = params

                    # 转换 category
                    if "category" in item:
                        try:
                            item["category"] = StrategyCategory(item["category"])
                        except ValueError:
                            item["category"] = StrategyCategory.CUSTOM

                    meta = StrategyMeta(**item)
                    self._registry_cache[meta.id] = meta
                except Exception as e:
                    logger.error(f"Failed to parse strategy: {item.get('id', 'unknown')}: {e}")

            self._last_load_time = datetime.now()
            logger.info(f"Loaded {len(self._registry_cache)} strategies from registry")
            return self._registry_cache

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return {}

    def save_registry(self) -> bool:
        """保存策略注册表"""
        try:
            # 读取现有配置保留其他字段
            existing_data: Dict[str, Any] = {}
            if self.registry_path.exists():
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    existing_data = yaml.safe_load(f) or {}

            # 转换策略列表
            strategies_list = []
            for meta in self._registry_cache.values():
                item = meta.model_dump(by_alias=True)
                # 转换 params 回简单格式
                if "params" in item:
                    params = {}
                    for key, val in item["params"].items():
                        if isinstance(val, dict):
                            params[key] = val
                        else:
                            params[key] = {"default": val}
                    item["params"] = params
                strategies_list.append(item)

            existing_data["strategies"] = strategies_list
            existing_data["updated_at"] = datetime.now().strftime("%Y-%m-%d")

            # 确保目录存在
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.registry_path, "w", encoding="utf-8") as f:
                yaml.dump(existing_data, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"Saved {len(strategies_list)} strategies to registry")
            return True

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            return False

    # ============================================
    # Strategy Discovery
    # ============================================

    def scan_implementations(self) -> List[Dict[str, Any]]:
        """扫描 implementations 目录，发现新策略"""
        discovered: List[Dict[str, Any]] = []

        if not self.implementations_dir.exists():
            logger.warning(f"Implementations dir not found: {self.implementations_dir}")
            return discovered

        # 扫描 .py 文件
        for py_file in self.implementations_dir.rglob("*.py"):
            # 跳过 __init__.py 和 __pycache__
            if py_file.name.startswith("_") or "__pycache__" in str(py_file):
                continue

            try:
                info = self._analyze_strategy_file(py_file)
                if info:
                    discovered.extend(info)
            except Exception as e:
                logger.error(f"Failed to analyze {py_file}: {e}")

        logger.info(f"Discovered {len(discovered)} strategy classes")
        return discovered

    def _analyze_strategy_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """分析策略文件，提取策略类信息"""
        results: List[Dict[str, Any]] = []

        # 计算相对路径
        try:
            rel_path = file_path.relative_to(self.strategies_dir)
        except ValueError:
            rel_path = file_path

        # 动态加载模块
        module_name = f"deepsearch.strategies.{rel_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return results

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 查找 BaseStrategy 子类
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseStrategy)
                    and attr is not BaseStrategy
                ):
                    # 生成策略ID
                    strategy_id = self._generate_strategy_id(attr_name, file_path)

                    results.append(
                        {
                            "id": strategy_id,
                            "file": str(rel_path).replace("\\", "/"),
                            "class": attr_name,
                            "name": self._class_name_to_display_name(attr_name),
                            "description": attr.__doc__ or "",
                            "category": "custom",
                            "enabled": True,
                        }
                    )

        except Exception as e:
            logger.debug(f"Could not load module {file_path}: {e}")

        return results

    def _generate_strategy_id(self, class_name: str, file_path: Path) -> str:
        """生成策略ID"""
        # 使用类名的 snake_case 形式
        import re

        name = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
        # 移除 _strategy 后缀
        name = re.sub(r"_strategy$", "", name)
        return name

    def _class_name_to_display_name(self, class_name: str) -> str:
        """将类名转换为显示名称"""
        import re

        # 移除 Strategy 后缀
        name = re.sub(r"Strategy$", "", class_name)
        # 添加空格
        name = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        return name + " 策略"

    # ============================================
    # Strategy Loading
    # ============================================

    def get_strategy_class(self, strategy_id: str) -> Optional[Type[BaseStrategy]]:
        """获取策略类"""
        # 检查缓存
        if strategy_id in self._class_cache:
            return self._class_cache[strategy_id]

        # 从注册表获取
        registry = self.load_registry()
        if strategy_id not in registry:
            logger.warning(f"Strategy not found in registry: {strategy_id}")
            return None

        meta = registry[strategy_id]

        # 动态加载
        try:
            file_path = self.strategies_dir / meta.file
            if not file_path.exists():
                logger.error(f"Strategy file not found: {file_path}")
                return None

            module_name = f"deepsearch.strategies.{file_path.stem}_{strategy_id}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 获取类
            strategy_class = getattr(module, meta.class_name, None)
            if strategy_class is None:
                logger.error(f"Class {meta.class_name} not found in {file_path}")
                return None

            # 验证是 BaseStrategy 子类
            if not issubclass(strategy_class, BaseStrategy):
                logger.error(f"{meta.class_name} is not a BaseStrategy subclass")
                return None

            self._class_cache[strategy_id] = strategy_class
            # 返回 strategy_class: getattr 返回 Any，但我们已验证它是 BaseStrategy 子类
            return cast(type[BaseStrategy], strategy_class)

        except Exception as e:
            logger.error(f"Failed to load strategy class {strategy_id}: {e}")
            return None

    def create_strategy_instance(
        self,
        strategy_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseStrategy]:
        """创建策略实例"""
        strategy_class = self.get_strategy_class(strategy_id)
        if strategy_class is None:
            return None

        try:
            # 合并默认参数和用户参数
            registry = self.load_registry()
            default_params = {}
            if strategy_id in registry:
                for key, param_def in registry[strategy_id].params.items():
                    default_params[key] = param_def.default

            merged_params = {**default_params, **(params or {})}
            return strategy_class(strategy_id=strategy_id, params=merged_params)

        except Exception as e:
            logger.error(f"Failed to create strategy instance {strategy_id}: {e}")
            return None

    # ============================================
    # Query Methods
    # ============================================

    def list_strategies(
        self,
        category: Optional[StrategyCategory] = None,
        enabled_only: bool = False,
    ) -> List[StrategyMeta]:
        """获取策略列表"""
        registry = self.load_registry()
        strategies = list(registry.values())

        if category:
            strategies = [s for s in strategies if s.category == category]

        if enabled_only:
            strategies = [s for s in strategies if s.enabled]

        return strategies

    def get_strategy(self, strategy_id: str) -> Optional[StrategyMeta]:
        """获取单个策略信息"""
        registry = self.load_registry()
        return registry.get(strategy_id)

    def update_strategy_status(self, strategy_id: str, enabled: bool) -> bool:
        """更新策略启用状态"""
        registry = self.load_registry()
        if strategy_id not in registry:
            return False

        registry[strategy_id].enabled = enabled
        return self.save_registry()

    def get_strategy_code_hash(self, strategy_id: str) -> Optional[str]:
        """获取策略代码哈希（用于版本追踪）"""
        registry = self.load_registry()
        if strategy_id not in registry:
            return None

        meta = registry[strategy_id]
        file_path = self.strategies_dir / meta.file

        if not file_path.exists():
            return None

        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()[:16]
        except Exception:
            return None

    # ============================================
    # Statistics
    # ============================================

    def get_category_counts(self) -> Dict[str, int]:
        """获取各分类策略数量"""
        registry = self.load_registry()
        counts: Dict[str, int] = {}

        for strategy in registry.values():
            cat = strategy.category.value
            counts[cat] = counts.get(cat, 0) + 1

        return counts


# ============================================
# Global Instance
# ============================================

_registry_service: Optional[StrategyRegistryService] = None


def get_registry_service() -> StrategyRegistryService:
    """获取全局策略注册服务实例"""
    global _registry_service
    if _registry_service is None:
        _registry_service = StrategyRegistryService()
    return _registry_service
