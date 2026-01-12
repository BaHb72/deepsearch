"""配置验证器 - 确保配置与运行时行为一致"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Set, cast

from core.config.models.amazingdata import AmazingDataConfig as AmazingDataConfigModel
from loguru import logger
from pydantic import ValidationError


class ValidationLevel(Enum):
    """验证级别"""

    ERROR = "error"  # 错误 - 必须修复
    WARNING = "warning"  # 警告 - 建议修复
    INFO = "info"  # 信息 - 仅供参考


@dataclass
class ValidationResult:
    """验证结果"""

    level: ValidationLevel
    component: str
    message: str
    suggestion: Optional[str] = None


class ConfigValidator:
    """配置验证器"""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.results: List[ValidationResult] = []

    def validate(self) -> List[ValidationResult]:
        """执行全面配置验证"""
        self.results = []

        # 验证数据源配置
        self._validate_data_sources()

        # 验证QMT配置
        self._validate_qmt_config()

        # 验证冲突配置
        self._validate_conflicts()

        # 验证依赖关系
        self._validate_dependencies()

        return self.results

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        """兼容 Pydantic BaseModel 的通用 dict 提取。"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump()
            except Exception:
                return {}
            if isinstance(dumped, dict):
                return dict(dumped)
            return {}
        if hasattr(value, "__dict__"):
            return dict(getattr(value, "__dict__", {}))
        return {}

    def _validate_data_sources(self) -> None:
        """验证数据源配置"""
        data_sources = self._as_dict(getattr(self.config, "data_sources", None))
        validated_amazing_configs: Set[int] = set()

        if data_sources and data_sources.get("providers"):
            providers = self._as_dict(data_sources.get("providers"))

            enabled_count = 0

            akshare_cfg = cast(Dict[str, Any], providers.get("akshare", {}) or {})
            if isinstance(akshare_cfg, dict) and akshare_cfg.get("enabled", False):
                enabled_count += 1
                logger.info("AKShare数据源已启用")

                try:
                    import akshare  # noqa: F401
                except ImportError:
                    self.results.append(
                        ValidationResult(
                            level=ValidationLevel.ERROR,
                            component="akshare",
                            message="AKShare配置为启用但模块未安装",
                            suggestion="运行: pip install akshare",
                        )
                    )

                proxy_cfg: Dict[str, Any] = {}
                if isinstance(akshare_cfg.get("config"), dict):
                    proxy_cfg = akshare_cfg["config"].get("proxy", {}) or {}
                if isinstance(akshare_cfg.get("proxy"), dict):
                    proxy_cfg.update(
                        {k: v for k, v in akshare_cfg["proxy"].items() if v is not None}
                    )

                if proxy_cfg.get("enabled"):
                    worker_url = proxy_cfg.get("worker_url") or self._get_cloudflare_worker_url()
                    if not worker_url:
                        self.results.append(
                            ValidationResult(
                                level=ValidationLevel.ERROR,
                                component="akshare.proxy",
                                message="AkShare代理启用但未找到可用的 Cloudflare Worker URL",
                                suggestion="在 akshare.proxy.worker_url 或 cloudflare_workers 中配置 Worker 地址",
                            )
                        )

            cloudflare_cfg = cast(Dict[str, Any], providers.get("cloudflare", {}) or {})
            if isinstance(cloudflare_cfg, dict) and cloudflare_cfg.get("enabled", False):
                enabled_count += 1
                worker_url = cloudflare_cfg.get("worker_url")
                if not worker_url and isinstance(cloudflare_cfg.get("config"), dict):
                    worker_url = cloudflare_cfg["config"].get("worker_url")
                if not worker_url:
                    worker_url = self._get_cloudflare_worker_url()
                if not worker_url:
                    self.results.append(
                        ValidationResult(
                            level=ValidationLevel.ERROR,
                            component="cloudflare",
                            message="Cloudflare数据源启用但未配置 Worker URL",
                            suggestion="在 cloudflare.config.worker_url 或 cloudflare_workers 中设置 Worker 地址",
                        )
                    )

            amazing_cfg_raw = providers.get("amazingdata")
            amazing_cfg_model = self._coerce_amazingdata_config(
                amazing_cfg_raw, "data_sources.amazingdata"
            )
            if amazing_cfg_model:
                validated_amazing_configs.add(id(amazing_cfg_model))
                if amazing_cfg_model.enabled:
                    enabled_count += 1
                self._validate_amazingdata_settings(amazing_cfg_model, "data_sources.amazingdata")

            top_level_enabled = self._validate_top_level_amazingdata(validated_amazing_configs)

            if (
                enabled_count == 0
                and not top_level_enabled
                and (
                    not hasattr(self.config, "qmt")
                    or not getattr(self.config.qmt, "enabled", False)
                )
            ):
                self.results.append(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        component="data_sources",
                        message="没有启用任何数据源",
                        suggestion="至少启用一个数据源（QMT、AkShare或Cloudflare）",
                    )
                )

            # legacy 提示
            if hasattr(self.config, "data_providers") and hasattr(
                self.config.data_providers, "cloudflare_proxy"
            ):
                self.results.append(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        component="cloudflare_proxy",
                        message="检测到 legacy cloudflare_proxy 配置，系统会自动迁移为 akshare.proxy",
                        suggestion="请将相关设置迁移到 data_sources.providers.akshare.proxy",
                    )
                )
            return

        # Legacy data_providers 兼容
        if not hasattr(self.config, "data_providers"):
            self.results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    component="data_providers",
                    message="未找到数据源配置",
                    suggestion="添加 data_sources.providers 或升级到新配置结构",
                )
            )
            self._validate_top_level_amazingdata(validated_amazing_configs)
            return

        providers = self.config.data_providers
        enabled_count = 0

        if hasattr(providers, "akshare_proxy") and providers.akshare_proxy.get("enabled", False):
            enabled_count += 1
            logger.info("AKShare数据源已启用 (legacy 配置)")
            try:
                import akshare  # noqa: F401
            except ImportError:
                self.results.append(
                    ValidationResult(
                        level=ValidationLevel.ERROR,
                        component="akshare",
                        message="AKShare配置为启用但模块未安装",
                        suggestion="运行: pip install akshare",
                    )
                )

        if hasattr(providers, "cloudflare_proxy") and providers.cloudflare_proxy.get(
            "enabled", False
        ):
            enabled_count += 1
            self.results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    component="cloudflare_proxy",
                    message="cloudflare_proxy 配置已废弃，系统将自动迁移为 akshare.proxy",
                    suggestion="请迁移到 data_sources.providers.akshare.proxy",
                )
            )

        top_level_enabled = self._validate_top_level_amazingdata(validated_amazing_configs)
        if (
            enabled_count == 0
            and not top_level_enabled
            and (not hasattr(self.config, "qmt") or not getattr(self.config.qmt, "enabled", False))
        ):
            self.results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    component="data_providers",
                    message="没有启用任何数据源",
                    suggestion="至少启用一个数据源（QMT、AkShare或Cloudflare）",
                )
            )

    def _coerce_amazingdata_config(
        self, raw: object, component: str
    ) -> Optional[AmazingDataConfigModel]:
        """将输入对象解析为 AmazingData 配置模型。"""

        if raw is None:
            return None

        if isinstance(raw, AmazingDataConfigModel):
            return raw

        data: Dict[str, Any]
        if hasattr(raw, "model_dump"):
            data = raw.model_dump()
        elif isinstance(raw, Mapping):
            data = dict(raw)
        else:
            data = dict(getattr(raw, "__dict__", {}))

        try:
            validated = AmazingDataConfigModel.model_validate(data)
            return cast(AmazingDataConfigModel, validated)
        except ValidationError as exc:
            issues: List[str] = []
            for error in exc.errors():
                loc = ".".join(str(part) for part in error.get("loc", ()))
                msg = error.get("msg", "配置校验失败")
                issues.append(f"{loc}: {msg}" if loc else msg)

            detail = "；".join(issues) if issues else str(exc)
            self.results.append(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    component=component,
                    message=f"AmazingData 配置解析失败: {detail}",
                    suggestion="请检查 settings.<env>.yaml 中 amazingdata.* 字段的值是否完整且类型正确",
                )
            )
            return None

    def _validate_amazingdata_settings(
        self, config_model: AmazingDataConfigModel, component: str
    ) -> None:
        """针对启用状态的 AmazingData 配置执行连通性检查。"""

        if not config_model.enabled:
            return

        ensure_ready = getattr(config_model, "ensure_connection_ready", None)
        if ensure_ready is None or not callable(ensure_ready):
            return

        try:
            ensure_ready()
        except ValueError as exc:
            self.results.append(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    component=f"{component}.connection",
                    message=f"AmazingData 连接配置无效：{exc}",
                    suggestion="请在 settings.<env>.yaml 的 amazingdata.connection 中填写合法的凭证与主机信息",
                )
            )

    def _validate_top_level_amazingdata(self, validated_ids: Set[int]) -> bool:
        """校验顶层 AmazingData 配置，避免重复记录错误。"""

        amazingdata_attr = getattr(self.config, "amazingdata", None)
        config_model = self._coerce_amazingdata_config(amazingdata_attr, "amazingdata")
        if not config_model or id(config_model) in validated_ids:
            return False

        validated_ids.add(id(config_model))
        self._validate_amazingdata_settings(config_model, "amazingdata")
        return bool(getattr(config_model, "enabled", False))

    def _get_cloudflare_worker_url(self) -> Optional[str]:
        """尝试从配置中解析 Cloudflare Worker URL"""
        workers_cfg = getattr(self.config, "cloudflare_workers", None)
        if not workers_cfg:
            return None

        # 优先调用 get_full_url() 以适配工厂方法
        if hasattr(workers_cfg, "get_full_url"):
            try:
                full_url = workers_cfg.get_full_url()
                if isinstance(full_url, str) and full_url:
                    return full_url
            except Exception as err:
                logger.debug(f"获取 cloudflare_workers 完整 URL 失败: {err}")

        for attr in ("worker_url", "base_url", "url"):
            if hasattr(workers_cfg, attr):
                value = getattr(workers_cfg, attr)
                if isinstance(value, str) and value:
                    return value

        if isinstance(workers_cfg, dict):
            for key in ("worker_url", "base_url", "url"):
                value = workers_cfg.get(key)
                if isinstance(value, str) and value:
                    return value

        return None

    def _validate_qmt_config(self) -> None:
        """验证QMT配置"""
        if not hasattr(self.config, "qmt"):
            return

        qmt = self.config.qmt

        if qmt.enabled:
            logger.info("QMT已启用")

            # 检查端口配置
            if hasattr(qmt, "receiver"):
                tcp_port = qmt.receiver.tcp_port
                if tcp_port < 1024 or tcp_port > 65535:
                    self.results.append(
                        ValidationResult(
                            level=ValidationLevel.ERROR,
                            component="qmt",
                            message=f"QMT TCP端口 {tcp_port} 无效",
                            suggestion="使用1024-65535之间的端口",
                        )
                    )

            # 检查回退配置
            if hasattr(qmt, "fallback_enabled"):
                if qmt.fallback_enabled and not self._has_fallback_sources():
                    self.results.append(
                        ValidationResult(
                            level=ValidationLevel.WARNING,
                            component="qmt",
                            message="QMT启用了回退但没有配置备用数据源",
                            suggestion="启用至少一个备用数据源或禁用fallback_enabled",
                        )
                    )

    def _validate_conflicts(self) -> None:
        """验证配置冲突"""
        # 检查QMT Only Mode与其他数据源的冲突
        qmt_only = False
        if hasattr(self.config, "qmt") and self.config.qmt.enabled:
            if hasattr(self.config.qmt, "only_mode"):
                qmt_only = self.config.qmt.only_mode

        if qmt_only:
            # 检查是否同时启用了其他数据源
            other_sources = []
            if hasattr(self.config, "data_providers"):
                providers = self.config.data_providers
                if hasattr(providers, "akshare_proxy") and providers.akshare_proxy.get("enabled"):
                    other_sources.append("akshare")
                if hasattr(providers, "cloudflare_proxy") and providers.cloudflare_proxy.get(
                    "enabled"
                ):
                    other_sources.append("cloudflare")

            if other_sources:
                self.results.append(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        component="config",
                        message=f"QMT Only Mode启用但同时启用了其他数据源: {', '.join(other_sources)}",
                        suggestion="在QMT Only Mode下禁用其他数据源",
                    )
                )

    def _validate_dependencies(self) -> None:
        """验证依赖关系"""
        # 检查Redis依赖
        if hasattr(self.config, "cache") and self.config.cache.enabled:
            if self.config.cache.type == "redis":
                try:
                    if importlib.util.find_spec("redis") is None:
                        raise ImportError
                except ImportError:
                    self.results.append(
                        ValidationResult(
                            level=ValidationLevel.ERROR,
                            component="cache",
                            message="Redis缓存启用但redis模块未安装",
                            suggestion="运行: pip install redis",
                        )
                    )

    def _has_fallback_sources(self) -> bool:
        """检查是否有可用的备用数据源"""
        if not hasattr(self.config, "data_providers"):
            return False

        providers = self.config.data_providers

        # 检查AKShare
        if hasattr(providers, "akshare_proxy") and providers.akshare_proxy.get("enabled"):
            return True

        # 检查CloudFlare
        if hasattr(providers, "cloudflare_proxy") and providers.cloudflare_proxy.get("enabled"):
            return True

        return False

    def print_report(self) -> None:
        """打印验证报告"""
        if not self.results:
            logger.success("✓ 配置验证通过，没有发现问题")
            return

        # 按级别分组
        errors = [r for r in self.results if r.level == ValidationLevel.ERROR]
        warnings = [r for r in self.results if r.level == ValidationLevel.WARNING]
        infos = [r for r in self.results if r.level == ValidationLevel.INFO]

        if errors:
            logger.error(f"发现 {len(errors)} 个错误:")
            for result in errors:
                logger.error(f"  [{result.component}] {result.message}")
                if result.suggestion:
                    logger.info(f"    建议: {result.suggestion}")

        if warnings:
            logger.warning(f"发现 {len(warnings)} 个警告:")
            for result in warnings:
                logger.warning(f"  [{result.component}] {result.message}")
                if result.suggestion:
                    logger.info(f"    建议: {result.suggestion}")

        if infos:
            logger.info(f"信息 ({len(infos)} 条):")
            for result in infos:
                logger.info(f"  [{result.component}] {result.message}")

    def has_errors(self) -> bool:
        """是否有错误"""
        return any(r.level == ValidationLevel.ERROR for r in self.results)

    def get_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        return {
            "total": len(self.results),
            "errors": len([r for r in self.results if r.level == ValidationLevel.ERROR]),
            "warnings": len([r for r in self.results if r.level == ValidationLevel.WARNING]),
            "infos": len([r for r in self.results if r.level == ValidationLevel.INFO]),
            "has_errors": self.has_errors(),
            "results": [
                {
                    "level": r.level.value,
                    "component": r.component,
                    "message": r.message,
                    "suggestion": r.suggestion,
                }
                for r in self.results
            ],
        }


def validate_config(config: Any) -> ConfigValidator:
    """验证配置的便捷函数"""
    validator = ConfigValidator(config)
    validator.validate()
    return validator
