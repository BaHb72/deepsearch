"""
配置验证器 - 确保配置与运行时行为一致
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

from loguru import logger


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

    def __init__(self, config):
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

    def _validate_data_sources(self):
        """验证数据源配置"""
        if not hasattr(self.config, 'data_providers'):
            self.results.append(ValidationResult(
                level=ValidationLevel.WARNING,
                component="data_providers",
                message="未找到数据源配置",
                suggestion="添加 data_providers 配置节"
            ))
            return

        providers = self.config.data_providers
        enabled_count = 0

        # 检查AKShare
        if hasattr(providers, 'akshare_proxy'):
            if providers.akshare_proxy.get('enabled', False):
                enabled_count += 1
                logger.info("AKShare数据源已启用")

                # 检查AKShare是否安装
                try:
                    import akshare
                except ImportError:
                    self.results.append(ValidationResult(
                        level=ValidationLevel.ERROR,
                        component="akshare",
                        message="AKShare配置为启用但模块未安装",
                        suggestion="运行: pip install akshare"
                    ))

        # 检查CloudFlare
        if hasattr(providers, 'cloudflare_proxy'):
            if providers.cloudflare_proxy.get('enabled', False):
                enabled_count += 1
                logger.info("CloudFlare代理已启用")

                # 检查Worker URL
                if not providers.cloudflare_proxy.get('worker_url'):
                    self.results.append(ValidationResult(
                        level=ValidationLevel.ERROR,
                        component="cloudflare",
                        message="CloudFlare启用但未配置worker_url",
                        suggestion="设置 cloudflare_proxy.worker_url"
                    ))

        # 检查是否至少有一个数据源启用
        if enabled_count == 0 and (not hasattr(self.config, 'qmt') or not self.config.qmt.enabled):
            self.results.append(ValidationResult(
                level=ValidationLevel.WARNING,
                component="data_sources",
                message="没有启用任何数据源",
                suggestion="至少启用一个数据源（QMT、AKShare或CloudFlare）"
            ))

    def _validate_qmt_config(self):
        """验证QMT配置"""
        if not hasattr(self.config, 'qmt'):
            return

        qmt = self.config.qmt

        if qmt.enabled:
            logger.info("QMT已启用")

            # 检查端口配置
            if hasattr(qmt, 'receiver'):
                tcp_port = qmt.receiver.tcp_port
                if tcp_port < 1024 or tcp_port > 65535:
                    self.results.append(ValidationResult(
                        level=ValidationLevel.ERROR,
                        component="qmt",
                        message=f"QMT TCP端口 {tcp_port} 无效",
                        suggestion="使用1024-65535之间的端口"
                    ))

            # 检查回退配置
            if hasattr(qmt, 'fallback_enabled'):
                if qmt.fallback_enabled and not self._has_fallback_sources():
                    self.results.append(ValidationResult(
                        level=ValidationLevel.WARNING,
                        component="qmt",
                        message="QMT启用了回退但没有配置备用数据源",
                        suggestion="启用至少一个备用数据源或禁用fallback_enabled"
                    ))

    def _validate_conflicts(self):
        """验证配置冲突"""
        # 检查QMT Only Mode与其他数据源的冲突
        qmt_only = False
        if hasattr(self.config, 'qmt') and self.config.qmt.enabled:
            if hasattr(self.config.qmt, 'only_mode'):
                qmt_only = self.config.qmt.only_mode

        if qmt_only:
            # 检查是否同时启用了其他数据源
            other_sources = []
            if hasattr(self.config, 'data_providers'):
                providers = self.config.data_providers
                if hasattr(providers, 'akshare_proxy') and providers.akshare_proxy.get('enabled'):
                    other_sources.append('akshare')
                if hasattr(providers, 'cloudflare_proxy') and providers.cloudflare_proxy.get('enabled'):
                    other_sources.append('cloudflare')

            if other_sources:
                self.results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    component="config",
                    message=f"QMT Only Mode启用但同时启用了其他数据源: {', '.join(other_sources)}",
                    suggestion="在QMT Only Mode下禁用其他数据源"
                ))

    def _validate_dependencies(self):
        """验证依赖关系"""
        # 检查Redis依赖
        if hasattr(self.config, 'cache') and self.config.cache.enabled:
            if self.config.cache.type == 'redis':
                try:
                    import redis
                except ImportError:
                    self.results.append(ValidationResult(
                        level=ValidationLevel.ERROR,
                        component="cache",
                        message="Redis缓存启用但redis模块未安装",
                        suggestion="运行: pip install redis"
                    ))

    def _has_fallback_sources(self) -> bool:
        """检查是否有可用的备用数据源"""
        if not hasattr(self.config, 'data_providers'):
            return False

        providers = self.config.data_providers

        # 检查AKShare
        if hasattr(providers, 'akshare_proxy') and providers.akshare_proxy.get('enabled'):
            return True

        # 检查CloudFlare
        if hasattr(providers, 'cloudflare_proxy') and providers.cloudflare_proxy.get('enabled'):
            return True

        return False

    def print_report(self):
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
                    "suggestion": r.suggestion
                }
                for r in self.results
            ]
        }


def validate_config(config) -> ConfigValidator:
    """验证配置的便捷函数"""
    validator = ConfigValidator(config)
    validator.validate()
    return validator
