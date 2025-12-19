"""
统一的数据源管理器 - 重构版本
配置驱动、策略模式、依赖注入
"""

import asyncio
import inspect
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NotRequired,
    Optional,
    Sequence,
    Type,
    TypedDict,
    Union,
    cast,
)

from loguru import logger

from deepsearch.config import get_config
from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.providers.executor import DataSourceExecutor


# Lazy import to avoid requiring amazingdata SDK when disabled
def get_global_pool():
    """Lazy import of get_global_pool from amazingdata_process_pool."""
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
        get_global_pool as _get_global_pool,
    )
    return _get_global_pool()
from deepsearch.infrastructure.providers.interfaces.base import IDataSource
from deepsearch.infrastructure.providers.interfaces.runtime import (
    ProviderMessageEnvelope,
    RealtimeCallback,
)
from deepsearch.infrastructure.providers.managers.module_source_config import (
    ModuleSourceResolver,
    create_resolver_from_config,
)
from deepsearch.infrastructure.providers.registry import get_registry
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

SUPPORTED_SOURCE_TYPES = {
    DataSourceType.AMAZINGDATA,
    DataSourceType.AKSHARE,
    DataSourceType.MINIQMT,
}

DEFAULT_SOURCE_PRIORITY = {
    DataSourceType.AMAZINGDATA: 10,
    DataSourceType.AKSHARE: 30,
    DataSourceType.MINIQMT: 5,
}

# 注意：用户名需要在前端表单中回显，因此不要加入到敏感字段过滤列表中
_SENSITIVE_CONFIG_MARKERS = (
    "password",
    "secret",
    "secret_key",
    "private_key",
    "token",
    "access_token",
    "refresh_token",
    "apikey",
    "api_key",
)


def _sanitize_config_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, sub_value in value.items():
            key_str = str(key)
            lowered = key_str.lower()
            if any(marker in lowered for marker in _SENSITIVE_CONFIG_MARKERS):
                continue
            sanitized_value = _sanitize_config_snapshot(sub_value)
            if sanitized_value is None:
                continue
            sanitized[key_str] = sanitized_value
        return sanitized
    if isinstance(value, list):
        sanitized_list = []
        for item in value:
            sanitized_item = _sanitize_config_snapshot(item)
            if sanitized_item is None:
                continue
            sanitized_list.append(sanitized_item)
        return sanitized_list
    if isinstance(value, Enum):
        return value.value
    return value


# Backward compatibility for cached call sites that still reference the old helper name.
_strip_sensitive_keys = _sanitize_config_snapshot


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, sub_value in value.items():
            cleaned_value = _prune_empty(sub_value)
            if cleaned_value in (None, ""):
                continue
            if isinstance(cleaned_value, dict) and not cleaned_value:
                continue
            if isinstance(cleaned_value, list) and not cleaned_value:
                continue
            cleaned[key] = cleaned_value
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = _prune_empty(item)
            if cleaned_item in (None, ""):
                continue
            if isinstance(cleaned_item, dict) and not cleaned_item:
                continue
            if isinstance(cleaned_item, list) and not cleaned_item:
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    return value


@dataclass(frozen=True)
class StockListFetchResult:
    """封装股票列表双写结果，便于上层消费领域对象。"""

    source: str
    records: tuple[StockListRecord, ...]
    legacy: tuple[dict[str, Any], ...]
    mismatch: int = 0

    def as_legacy(self) -> list[dict[str, Any]]:
        """返回旧结构数据。"""

        return [dict(item) for item in self.legacy]

    def as_records(self) -> tuple[StockListRecord, ...]:
        """返回领域对象视图。"""

        return self.records


def _iter_stock_payload(payload: Any) -> Iterable[Any]:
    """将 Provider 返回的各种结构展开为统一迭代器。"""

    if payload is None:
        return ()

    if hasattr(payload, "to_dict") and callable(getattr(payload, "to_dict")):
        try:
            as_list = payload.to_dict("records")
            if isinstance(as_list, list):
                return as_list
        except Exception:  # pragma: no cover - DataFrame to_dict 失败
            return ()

    if isinstance(payload, Mapping):
        return (dict(payload),)

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return payload

    if isinstance(payload, Iterable) and not isinstance(payload, (str, bytes, bytearray)):
        return list(payload)

    return (payload,)


def build_stock_list_result(
        payload: Any,
        source: str,
        *,
        limit: Optional[int] = None,
) -> Optional[StockListFetchResult]:
    """归一化股票列表响应，产出领域与旧结构并存的结果。"""

    if payload is None:
        return None

    if isinstance(payload, StockListFetchResult):
        records: Sequence[StockListRecord] = payload.records
        legacy: Sequence[dict[str, Any]] = payload.legacy
        if limit is not None and limit > 0:
            records = records[:limit]
            legacy = legacy[:limit]
        mismatch = payload.mismatch or abs(len(records) - len(legacy))
        return StockListFetchResult(
            source=source,
            records=tuple(records),
            legacy=tuple(dict(item) for item in legacy),
            mismatch=mismatch,
        )

    records: list[StockListRecord] = []
    legacy_entries: list[dict[str, Any]] = []
    mismatch_extra = 0

    for entry in _iter_stock_payload(payload):
        if isinstance(entry, StockListRecord):
            record = entry
            legacy_map = dict(record.as_mapping())
            if record.boards:
                legacy_map.setdefault("board", record.boards[0])
            records.append(record)
            legacy_entries.append(legacy_map)
            continue

        mapping: dict[str, Any] | None = None
        if isinstance(entry, Mapping):
            mapping = dict(entry)
        elif hasattr(entry, "as_mapping") and callable(getattr(entry, "as_mapping")):
            try:
                mapping = dict(entry.as_mapping())
            except Exception:  # pragma: no cover - 非预期对象
                mapping = None

        if mapping is None:
            try:
                mapping = dict(entry)  # type: ignore[arg-type]
            except Exception:
                mismatch_extra += 1
                continue

        record = StockListRecord.from_payload(mapping)
        if record.symbol:
            records.append(record)
        else:
            mismatch_extra += 1

        if record.boards and "board" not in mapping:
            mapping.setdefault("board", record.boards[0])
        legacy_entries.append(mapping)

    if not records and not legacy_entries:
        return None

    if limit is not None and limit > 0:
        records = records[:limit]
        legacy_entries = legacy_entries[:limit]

    mismatch = abs(len(records) - len(legacy_entries)) + mismatch_extra

    return StockListFetchResult(
        source=source,
        records=tuple(records),
        legacy=tuple(dict(item) for item in legacy_entries),
        mismatch=mismatch,
    )


class SourceStatusEntry(TypedDict, total=False):
    """数据源运行时状态结构。"""

    status: str
    available: bool
    reason: str
    degraded_reason: NotRequired[str]
    last_transition: float
    last_health_check: NotRequired[float]
    last_test_time: Optional[float]
    test_summary: Optional[str]
    has_saved_credential: bool
    metrics: NotRequired[Dict[str, object]]
    config: NotRequired[Dict[str, object]]
    loginThrottle: NotRequired[Dict[str, Any]]
    pendingLogin: NotRequired[bool]
    lastLoginStartedAt: NotRequired[str]
    lastLoginCompletedAt: NotRequired[str]
    lastLoginSuccessAt: NotRequired[str]
    lastLoginErrorAt: NotRequired[str]
    lastLoginErrorReason: NotRequired[str]


@dataclass
class DataSourceConfig:
    """数据源配置"""

    enabled: bool
    priority: int = 100
    timeout: float = 10.0
    retry_count: int = 3
    fallback_enabled: bool = False
    fallback_sources: List[DataSourceType] = field(default_factory=list)
    has_saved_credential: Optional[bool] = None
    config: Dict[str, Any] = field(default_factory=dict)
    provider_name: Optional[str] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.provider_name:
            self.provider_name = str(self.provider_name).strip() or None


class DataSourceLifecycleStatus(str, Enum):
    """数据源生命周期状态"""

    DRAFT = "draft"
    PENDING_TEST = "pending_test"
    TESTING = "testing"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"
    OFFLINE = "offline"


class DataSourceRegistry:
    """数据源注册表 - 单例模式"""

    _instance = None
    _providers: Dict[DataSourceType, Any] = {}
    _configs: Dict[DataSourceType, DataSourceConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_provider(self, source_type: DataSourceType, provider_class: Type):
        """注册数据提供者类"""
        if source_type not in SUPPORTED_SOURCE_TYPES:
            logger.warning(
                f"忽略注册数据提供者 {source_type.value}：当前仅支持 AmazingData、AkShare 及 CloudFlare 代理数据源"
            )
            return

        self._providers[source_type] = provider_class
        # 获取类名，处理Mock对象
        class_name = getattr(provider_class, "__name__", str(provider_class))
        logger.info(f"注册数据提供者: {source_type.value} -> {class_name}")

    def get_provider_class(self, source_type: DataSourceType) -> Optional[Type]:
        """获取数据提供者类"""
        return self._providers.get(source_type)

    def set_config(self, source_type: DataSourceType, config: DataSourceConfig):
        """设置数据源配置"""
        if source_type not in SUPPORTED_SOURCE_TYPES:
            logger.warning("忽略不受支持的数据源配置: {}" % source_type.value)
            return

        self._configs[source_type] = config

    def get_config(self, source_type: DataSourceType) -> Optional[DataSourceConfig]:
        """获取数据源配置"""
        return self._configs.get(source_type)


class DataSourceManager:
    """
    数据源管理器 - 核心组件
    负责根据配置管理所有数据源
    """

    _instance = None  # 单例实例

    def __init__(self, config=None):
        """
        初始化数据源管理器

        Args:
            config: 配置对象，如果为None则从全局配置获取
        """
        self.config = config or get_config()
        self.registry = DataSourceRegistry()
        self.providers: Dict[DataSourceType, IDataSource] = {}
        self.initialized = False
        self._executor = DataSourceExecutor()
        self._provider_names: Dict[DataSourceType, str] = {}
        self._fallback_order: List[DataSourceType] = []
        self._default_source: Optional[DataSourceType] = None
        self._module_resolver: Optional[ModuleSourceResolver] = None

        # 数据源状态
        self._source_status: Dict[DataSourceType, SourceStatusEntry] = {}

        # 策略模式 - 数据源选择策略
        self._selection_strategy = None

        # 最近一次成功使用的来源
        self._last_success_source: Optional[DataSourceType] = None

        # 初始化过程并发控制
        self._init_lock = asyncio.Lock()
        self._initializing = False

        # 初始化配置
        self._load_configs()
        self._initialize_status_table()

    @classmethod
    def get_instance(cls, config=None):
        """
        获取数据源管理器单例实例

        Args:
            config: 配置对象，仅在第一次创建时使用

        Returns:
            DataSourceManager实例
        """
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试）"""
        cls._instance = None

    @staticmethod
    def _ensure_dict(value):
        """��ȷ������Ϊ dict ������֧�� Pydantic/����ʵ��"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return {k: value[k] for k in value}
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass
        if hasattr(value, "dict"):
            try:
                return value.dict()
            except Exception:
                pass
        result = {}
        known_keys = (
            "enabled",
            "priority",
            "timeout",
            "config",
            "proxy",
            "mode",
            "worker_url",
            "name",
        )
        for key in known_keys:
            if hasattr(value, key):
                attr_value = getattr(value, key)
                result[key] = attr_value
        config_value = result.get("config")
        if config_value is None:
            result["config"] = {}
        elif config_value is not value and not isinstance(config_value, dict):
            result["config"] = DataSourceManager._ensure_dict(config_value)
        proxy_value = result.get("proxy")
        if proxy_value is None:
            result["proxy"] = {}
        elif proxy_value is not value and not isinstance(proxy_value, dict):
            result["proxy"] = DataSourceManager._ensure_dict(proxy_value)
        return result

    @staticmethod
    def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """����ϲ� dict �����ȼ������� override"""
        result = dict(base or {})
        for key, value in (override or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = DataSourceManager._deep_merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _resolve_source_type(source: Union[str, DataSourceType, None]) -> Optional[DataSourceType]:
        """将外部传入的数据源标识统一转换为 DataSourceType。"""
        if isinstance(source, DataSourceType):
            return source
        if source is None:
            return None

        name = str(source).lower().strip()
        if not name:
            return None

        alias_map = {
            "amazing": DataSourceType.AMAZINGDATA,
            "amazingdata": DataSourceType.AMAZINGDATA,
            "default": DataSourceType.DEFAULT,
            "cloudflare": DataSourceType.AKSHARE,
            "cloudflare_proxy": DataSourceType.AKSHARE,
            "akshare_proxy": DataSourceType.AKSHARE,
            "akshare": DataSourceType.AKSHARE,
            "akshare_direct": DataSourceType.AKSHARE,
            "miniqmt": DataSourceType.MINIQMT,
            "qmt": DataSourceType.MINIQMT,
        }

        mapped = alias_map.get(name)
        if mapped:
            return (
                mapped
                if mapped in SUPPORTED_SOURCE_TYPES or mapped is DataSourceType.DEFAULT
                else None
            )

        try:
            candidate = DataSourceType(name)
        except ValueError:
            return None

        if candidate in SUPPORTED_SOURCE_TYPES or candidate is DataSourceType.DEFAULT:
            return candidate

        return None

    def _initialize_status_table(self):
        """Initialize runtime status table for all data sources."""
        for source_type in SUPPORTED_SOURCE_TYPES:
            config = self.registry.get_config(source_type)
            existing = self._source_status.get(source_type)
            if config is None:
                entry = self._transition_status(
                    source_type,
                    existing.get("status") if existing else DataSourceLifecycleStatus.DRAFT,
                    available=existing.get("available") if existing else False,
                    reason=existing.get("reason") if existing else "not_configured",
                )
                entry.setdefault("last_test_time", None)
                entry.setdefault("test_summary", None)
                entry.setdefault("has_saved_credential", False)
                continue

            default_status = (
                DataSourceLifecycleStatus.PENDING_TEST
                if config.enabled
                else DataSourceLifecycleStatus.DEGRADED
            )
            default_reason = "awaiting_test" if config.enabled else "disabled_by_config"
            entry = self._transition_status(
                source_type,
                existing.get("status") if existing else default_status,
                available=existing.get("available") if existing else False,
                reason=existing.get("reason") if existing else default_reason,
            )
            if config.enabled and entry.get("status") in {
                DataSourceLifecycleStatus.DRAFT.value,
                DataSourceLifecycleStatus.OFFLINE.value,
                DataSourceLifecycleStatus.DEGRADED.value,
            }:
                entry = self._transition_status(
                    source_type, default_status, available=False, reason=default_reason
                )
            if not config.enabled:
                entry = self._transition_status(
                    source_type,
                    DataSourceLifecycleStatus.DEGRADED,
                    available=False,
                    reason=default_reason,
                )
                entry["degraded_reason"] = default_reason
            entry.setdefault("last_test_time", None)
            entry.setdefault("test_summary", None)
            has_saved = self._resolve_has_saved_credential(config, entry)
            if has_saved is not None:
                entry["has_saved_credential"] = bool(has_saved)

    @staticmethod
    def _infer_saved_credential_from_config(config_section):
        if not isinstance(config_section, dict):
            return False
        candidates = []
        connection = config_section.get("connection")
        if isinstance(connection, dict):
            candidates.append(connection)
        candidates.append(config_section)
        sensitive_keys = ("username", "password", "secret", "token", "api_key", "apikey", "key")
        for block in candidates:
            if not isinstance(block, dict):
                continue
            for key, value in block.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in sensitive_keys):
                    if isinstance(value, str):
                        if value.strip():
                            return True
                    elif value:
                        return True
        return False

    def _resolve_has_saved_credential(self, config, status_entry=None):
        if status_entry and status_entry.get("has_saved_credential") is not None:
            return bool(status_entry["has_saved_credential"])
        if config is None:
            return None
        if config.has_saved_credential is not None:
            return bool(config.has_saved_credential)
        return self._infer_saved_credential_from_config(config.config)

    def _transition_status(self, source_type, status, *, available=None, reason=None, **updates):
        if isinstance(status, DataSourceLifecycleStatus):
            status_value = status.value
        else:
            status_value = status or DataSourceLifecycleStatus.DRAFT.value
        entry = self._source_status.setdefault(source_type, {})
        if entry.get("status") != status_value:
            entry["status"] = status_value
            entry["last_transition"] = time.time()
        else:
            entry.setdefault("status", status_value)
            entry.setdefault("last_transition", time.time())
        if available is not None:
            entry["available"] = bool(available)
        else:
            entry.setdefault("available", False)
        if reason is not None:
            entry["reason"] = reason
        else:
            entry.setdefault("reason", "")
        for key, value in updates.items():
            entry[key] = value
        has_saved = self._resolve_has_saved_credential(self.registry.get_config(source_type), entry)
        if has_saved is not None:
            entry["has_saved_credential"] = bool(has_saved)
        entry.setdefault("last_test_time", entry.get("last_test_time"))
        entry.setdefault("test_summary", entry.get("test_summary"))
        return entry

    @staticmethod
    def _format_timestamp(value):
        if not value:
            return None
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except Exception:
            return None

    def _load_configs(self):
        """加载数据源配置并初始化注册信息。"""

        self._provider_names.clear()
        self._fallback_order = []
        self._default_source = None

        raw_data_sources = getattr(self.config, "data_sources", None)
        if raw_data_sources:
            if hasattr(raw_data_sources, "model_dump"):
                data_sources = cast(Dict[str, Any], raw_data_sources.model_dump())
            elif isinstance(raw_data_sources, dict):
                data_sources = dict(raw_data_sources)
            else:
                data_sources = dict(getattr(raw_data_sources, "__dict__", {}))
        else:
            data_sources = {}

        if data_sources:
            self._load_data_sources_config(data_sources)
        else:
            self._load_legacy_configs()

        if not self._fallback_order:
            default_chain = [
                DataSourceType.AMAZINGDATA,
                DataSourceType.AKSHARE,
            ]
            self._fallback_order = [st for st in default_chain if st in SUPPORTED_SOURCE_TYPES]
        else:
            unique: list[DataSourceType] = []
            for item in self._fallback_order:
                if item in SUPPORTED_SOURCE_TYPES and item not in unique:
                    unique.append(item)
            self._fallback_order = unique

        if not self._default_source and self._fallback_order:
            self._default_source = self._fallback_order[0]

        self._update_fallback_order_config()

        # 初始化模块级数据源解析器
        if data_sources:
            self._module_resolver = create_resolver_from_config(data_sources)
        else:
            self._module_resolver = None

    def _load_data_sources_config(self, data_sources: Dict[str, Any]) -> None:
        """解析 data_sources.providers 配置并注册数据源。"""

        providers_raw = data_sources.get("providers") or {}
        if hasattr(providers_raw, "model_dump"):
            providers_dict = providers_raw.model_dump()
        elif isinstance(providers_raw, dict):
            providers_dict = dict(providers_raw)
        else:
            providers_dict = dict(getattr(providers_raw, "__dict__", {}))

        self._merge_proxy_provider(providers_dict)

        fallback_order_raw = data_sources.get("fallback_order")
        normalized_order = self._normalize_type_list(fallback_order_raw)
        if normalized_order:
            self._fallback_order = normalized_order

        default_source_raw = data_sources.get("default")
        resolved_default = self._resolve_source_type(default_source_raw)
        if resolved_default in SUPPORTED_SOURCE_TYPES:
            self._default_source = resolved_default

        supported_found = False
        for provider_key, provider_config in providers_dict.items():
            source_type = self._resolve_source_type(provider_key)
            if source_type not in SUPPORTED_SOURCE_TYPES:
                allowed = " / ".join(sorted(t.value for t in SUPPORTED_SOURCE_TYPES))
                logger.warning(f"忽略不受支持的数据源 {provider_key}，仅支持 {allowed}")
                continue

            normalized = self._ensure_dict(provider_config)
            self._register_provider_config(source_type, provider_key, normalized)
            supported_found = True

        if not supported_found:
            logger.warning(
                "data_sources.providers 中未找到受支持的数据源配置，已回退到 AmazingData 默认配置"
            )
            self._register_provider_config(
                    DataSourceType.AMAZINGDATA, "amazingdata", {"enabled": False}
                )

    def _load_legacy_configs(self) -> None:
        """兼容旧版配置结构，仅注册 AmazingData。"""

        amazing_config = getattr(self.config, "amazingdata", None)
        payload: Dict[str, Any] = {}
        if amazing_config:
            if hasattr(amazing_config, "model_dump"):
                payload = cast(Dict[str, Any], amazing_config.model_dump())
            else:
                payload = self._ensure_dict(amazing_config)

        normalized = self._ensure_dict(payload)
        normalized.setdefault("enabled", normalized.get("enabled", True))
        normalized.setdefault(
            "priority", DEFAULT_SOURCE_PRIORITY.get(DataSourceType.AMAZINGDATA, 10)
        )
        connection_cfg = normalized.get("connection") or {}
        if isinstance(connection_cfg, dict):
            normalized.setdefault("timeout", connection_cfg.get("timeout", 10.0))
            normalized.setdefault("retry_count", connection_cfg.get("max_retries", 3))
        normalized.setdefault("fallback_enabled", True)

        self._register_provider_config(DataSourceType.AMAZINGDATA, "amazingdata", normalized)
        self._fallback_order = [
            DataSourceType.AMAZINGDATA,
            DataSourceType.AKSHARE,
        ]
        self._default_source = DataSourceType.AMAZINGDATA

    def _merge_proxy_provider(self, providers_dict: Dict[str, Any]) -> None:
        """将独立的 Cloudflare 代理配置合并到 AkShare 配置中。"""

        proxy_keys = ("cloudflare", "cloudflare_proxy", "akshare_proxy")
        proxy_enabled: Optional[bool] = None
        proxy_payload: Dict[str, Any] = {}

        for key in proxy_keys:
            entry = providers_dict.pop(key, None)
            if not entry:
                continue
            normalized = self._ensure_dict(entry)
            if proxy_enabled is None and "enabled" in normalized:
                proxy_enabled = bool(normalized.get("enabled"))
            config_block = normalized.get("config")
            if config_block:
                proxy_payload = self._deep_merge_dicts(proxy_payload, self._ensure_dict(config_block))

        if proxy_enabled is None and not proxy_payload:
            return

        akshare_entry = providers_dict.setdefault("akshare", {})
        akshare_normalized = self._ensure_dict(akshare_entry)
        akshare_config = self._ensure_dict(akshare_normalized.get("config"))

        if proxy_payload:
            existing_proxy = self._ensure_dict(akshare_config.get("proxy"))
            akshare_config["proxy"] = self._deep_merge_dicts(existing_proxy, proxy_payload)

        if proxy_enabled is True:
            akshare_config["mode"] = "proxy"
            akshare_normalized["enabled"] = True
        else:
            akshare_config.setdefault("mode", akshare_config.get("mode", "direct"))

        akshare_normalized["config"] = akshare_config
        providers_dict["akshare"] = akshare_normalized

    def _update_fallback_order_config(self) -> None:
        """���� runtime config �е� fallback_order �� default ����"""
        fallback_values = [item.value for item in self._fallback_order]
        default_value = self._default_source.value if self._default_source else None

        data_sources_section = getattr(self.config, "data_sources", None)
        if isinstance(data_sources_section, dict):
            if fallback_values:
                data_sources_section["fallback_order"] = fallback_values
            else:
                data_sources_section.pop("fallback_order", None)
            if default_value:
                data_sources_section["default"] = default_value
            else:
                data_sources_section.pop("default", None)
            return

        if data_sources_section is None:
            return

        if hasattr(data_sources_section, "fallback_order"):
            try:
                data_sources_section.fallback_order = list(fallback_values)
            except Exception:  # pragma: no cover - ���ͱ����쳣
                logger.debug("�� runtime config д�� fallback_order ʱ�����쳣", exc_info=True)

        if hasattr(data_sources_section, "default"):
            try:
                data_sources_section.default = default_value
            except Exception:  # pragma: no cover - ���ͱ����쳣
                logger.debug("�� runtime config д�� default ʱ�����쳣", exc_info=True)

    def _update_provider_snapshot(self, source_type: DataSourceType, config: DataSourceConfig) -> None:
        """ͬ���� runtime config �е�����Դ������� fallback ���ã�����������ͨ�� UI ����ʾ"""
        data_sources_section = getattr(self.config, "data_sources", None)
        fallback_sources_raw = list(config.fallback_sources or [])
        fallback_sources_str = [item.value if isinstance(item, DataSourceType) else str(item) for item in
                                fallback_sources_raw]
        enabled_flag = bool(config.enabled)
        fallback_enabled_flag = bool(fallback_sources_raw)

        def _apply(entry: Any) -> None:
            if isinstance(entry, dict):
                entry["fallback_sources"] = fallback_sources_str
                entry["fallback_enabled"] = fallback_enabled_flag
                entry["enabled"] = enabled_flag
                return
            if hasattr(entry, "fallback_sources"):
                try:
                    entry.fallback_sources = list(fallback_sources_raw)
                except Exception:
                    entry.fallback_sources = list(fallback_sources_str)
            if hasattr(entry, "fallback_enabled"):
                entry.fallback_enabled = fallback_enabled_flag
            if hasattr(entry, "enabled"):
                entry.enabled = enabled_flag

        if isinstance(data_sources_section, dict):
            providers_section = data_sources_section.setdefault("providers", {})
            entry = providers_section.setdefault(source_type.value, {})
            _apply(entry)
            return

        if data_sources_section is None:
            return

        providers_attr = getattr(data_sources_section, "providers", None)
        if providers_attr is None:
            setattr(data_sources_section, "providers", {source_type.value: {}})
            providers_attr = getattr(data_sources_section, "providers")

        if isinstance(providers_attr, dict):
            entry = providers_attr.setdefault(source_type.value, {})
            _apply(entry)
        else:
            existing_entry = getattr(providers_attr, source_type.value, None)
            if existing_entry is None:
                try:
                    setattr(providers_attr, source_type.value, {})
                    existing_entry = getattr(providers_attr, source_type.value)
                except Exception:
                    logger.debug(
                        "providers �ṹ�����ɱ� dict ���޷��Զ�ͬ���ڴ�� config ������� fallback ���ð�",
                        exc_info=True,
                    )
                    return
            _apply(existing_entry)

    def _handle_akshare_disabled(self, config: DataSourceConfig) -> None:
        """���������� AkShare ����ʱ��Ҫ�����߼�"""
        config.fallback_sources = []
        config.fallback_enabled = False

        if isinstance(config.config, dict):
            proxy_cfg = config.config.get("proxy")
            if isinstance(proxy_cfg, dict):
                proxy_cfg["enabled"] = False
            config.config["mode"] = "direct"

        removed = False
        if DataSourceType.AKSHARE in self._fallback_order:
            self._fallback_order = [
                source for source in self._fallback_order if source != DataSourceType.AKSHARE
            ]
            removed = True

        if self._default_source == DataSourceType.AKSHARE:
            self._default_source = self._fallback_order[0] if self._fallback_order else None
            removed = True

        for other_type, other_config in list(self.registry._configs.items()):
            if other_type == DataSourceType.AKSHARE:
                continue
            if DataSourceType.AKSHARE in other_config.fallback_sources:
                other_config.fallback_sources = [
                    source for source in other_config.fallback_sources if source != DataSourceType.AKSHARE
                ]
                if not other_config.fallback_sources:
                    other_config.fallback_enabled = False
                self._update_provider_snapshot(other_type, other_config)
                removed = True

        self._update_provider_snapshot(DataSourceType.AKSHARE, config)

        if removed:
            self._update_fallback_order_config()

    def _handle_akshare_enabled(self, config: DataSourceConfig) -> None:
        """�������� AkShare ����ʱ���� fallback ��ͬ���߼�"""
        if DataSourceType.AKSHARE not in self._fallback_order:
            self._fallback_order.append(DataSourceType.AKSHARE)

        if not self._default_source:
            self._default_source = self._fallback_order[0]

        if config.fallback_enabled and not config.fallback_sources:
            config.fallback_sources = [
                source for source in self._fallback_order if source != DataSourceType.AKSHARE
            ]
        elif not config.fallback_enabled:
            config.fallback_sources = []

        self._update_provider_snapshot(DataSourceType.AKSHARE, config)
        self._update_fallback_order_config()

    def _normalize_type_list(self, values: Any) -> List[DataSourceType]:
        result: List[DataSourceType] = []
        if not values:
            return result
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        for item in values:
            source_type = self._resolve_source_type(item)
            if source_type and source_type in SUPPORTED_SOURCE_TYPES and source_type not in result:
                result.append(source_type)
        return result

    def _coerce_float(
            self,
            value: Any,
            *,
            default: float,
            field: str,
            provider: str,
    ) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return default
            try:
                return float(stripped)
            except ValueError:
                pass
        logger.warning(
            f"���Դ {provider} �ֶ� {field} ֵ {value!r} ����ת��Ϊ float����ʹ��Ĭ��ֵ {default}"
        )
        return default

    def _coerce_int(
            self,
            value: Any,
            *,
            default: int,
            field: str,
            provider: str,
    ) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return default
            try:
                return int(stripped)
            except ValueError:
                pass
        logger.warning(
            f"���Դ {provider} �ֶ� {field} ֵ {value!r} ����ת��Ϊ int����ʹ��Ĭ��ֵ {default}"
        )
        return default

    def is_provider_enabled(self, source: Union[str, DataSourceType]) -> bool:
        """判断指定数据源在当前配置中是否启用。"""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            return False

        config = self.registry.get_config(source_type)
        return bool(config and config.enabled)

    @staticmethod
    def _extract_config_payload(normalized: Dict[str, Any]) -> Dict[str, Any]:
        if not normalized:
            return {}
        config_block = normalized.get("config")
        if isinstance(config_block, dict):
            return dict(config_block)

        meta_keys = {
            "enabled",
            "priority",
            "timeout",
            "retry_count",
            "fallback_enabled",
            "fallback_sources",
            "has_saved_credential",
            "provider_name",
        }
        return {k: v for k, v in normalized.items() if k not in meta_keys}

    def _resolve_akshare_provider_config(
        self, config: DataSourceConfig
    ) -> tuple[str, Dict[str, Any]]:
        """根据 AkShare 配置决定使用直连还是 Cloudflare 代理。"""

        payload = self._ensure_dict(config.config)
        mode = str(payload.get("mode", "direct")).lower()
        proxy_payload = self._ensure_dict(payload.get("proxy"))

        direct_payload = {
            k: v for k, v in payload.items() if k not in {"mode", "proxy"}
        }

        proxy_enabled = proxy_payload.get("enabled")
        if isinstance(proxy_enabled, str):
            proxy_enabled = proxy_enabled.lower() in {"1", "true", "yes", "on"}

        use_proxy = mode == "proxy" or bool(proxy_enabled)
        
        # 检查 Worker URL 是否为有效配置（非占位符）
        if use_proxy:
            worker_url = str(proxy_payload.get("worker_url", "")).lower()
            is_placeholder = (
                not worker_url
                or "your-cloudflare-worker" in worker_url
                or "example.com" in worker_url
                or worker_url.endswith("your-worker.example.com")
            )
            if is_placeholder:
                logger.warning(
                    "AkShare 代理启用但未配置有效的 Worker URL，将回退直连模式"
                )
                use_proxy = False

        if use_proxy:
            resolved_proxy = {k: v for k, v in proxy_payload.items() if k != "enabled"}
            return "cloudflare", resolved_proxy

        return "akshare", direct_payload

    def _register_provider_config(
        self, source_type: DataSourceType, provider_name: str, normalized: Dict[str, Any]
    ) -> None:
        data = self._ensure_dict(normalized)
        enabled = bool(data.get("enabled", True))
        priority = int(data.get("priority", DEFAULT_SOURCE_PRIORITY.get(source_type, 100)))
        timeout = self._coerce_float(data.get("timeout"), default=10.0, field="timeout", provider=provider_name)
        retry_count = self._coerce_int(
            data.get("retry_count"),
            default=3,
            field="retry_count",
            provider=provider_name,
        )
        fallback_enabled = bool(data.get("fallback_enabled", True))
        fallback_sources = self._normalize_type_list(data.get("fallback_sources"))
        if fallback_enabled and not fallback_sources and self._fallback_order:
            fallback_sources = [st for st in self._fallback_order if st != source_type]

        config_payload = self._extract_config_payload(data)
        if isinstance(config_payload, dict) and "implementation_mode" not in config_payload:
            config_payload["implementation_mode"] = "process"
        has_saved = data.get("has_saved_credential")
        if has_saved is None:
            has_saved = self._infer_saved_credential_from_config(config_payload)

        ds_config = DataSourceConfig(
            enabled=enabled,
            priority=priority,
            timeout=timeout,
            retry_count=retry_count,
            fallback_enabled=fallback_enabled,
            fallback_sources=fallback_sources,
            has_saved_credential=has_saved,
            config=config_payload,
            provider_name=provider_name,
        )
        self.registry.set_config(source_type, ds_config)
        self._provider_names[source_type] = provider_name

    async def initialize(self) -> None:
        """初始化数据源提供者。"""

        if self.initialized:
            return

        async with self._init_lock:
            if self.initialized:
                return

            self._initializing = True
            try:
                self.providers.clear()
                ordered_sources = self._determine_initialization_order()

                for source_type in ordered_sources:
                    config = self.registry.get_config(source_type)
                    if not config:
                        self._transition_status(
                            source_type,
                            DataSourceLifecycleStatus.DRAFT,
                            available=False,
                            reason="not_configured",
                        )
                        continue

                    if not config.enabled:
                        entry = self._transition_status(
                            source_type,
                            DataSourceLifecycleStatus.DEGRADED,
                            available=False,
                            reason="disabled_by_config",
                        )
                        entry["degraded_reason"] = "disabled_by_config"
                        continue

                    try:
                        provider = await self._create_provider(source_type, config)
                    except Exception as exc:  # pragma: no cover - 初始化失败路径
                        logger.error(f"初始化数据源 {source_type.value} 失败: {exc}")
                        self._transition_status(
                            source_type,
                            DataSourceLifecycleStatus.ERROR,
                            available=False,
                            reason=str(exc),
                        )
                        continue

                    if provider:
                        self.providers[source_type] = provider
                        self._transition_status(
                            source_type,
                            DataSourceLifecycleStatus.ACTIVE,
                            available=True,
                            reason="initialized",
                        )

                self.initialized = True
            finally:
                self._initializing = False

    def _determine_initialization_order(self) -> List[DataSourceType]:
        order: List[DataSourceType] = []
        for source_type in self._fallback_order:
            if source_type in SUPPORTED_SOURCE_TYPES and source_type not in order:
                order.append(source_type)
        for source_type in SUPPORTED_SOURCE_TYPES:
            if source_type not in order:
                order.append(source_type)
        return order

    async def _create_provider(
        self, source_type: DataSourceType, config: DataSourceConfig
    ) -> Optional[IDataSource]:
        registry = get_registry()

        if source_type == DataSourceType.AKSHARE:
            provider_name, provider_payload = self._resolve_akshare_provider_config(config)
        else:
            provider_name = self._provider_names.get(source_type, source_type.value)
            provider_payload = dict(config.config or {})

        provider_info = registry.get_provider_info(provider_name)
        if not provider_info:
            logger.warning(f"未在注册表中找到数据源 {provider_name}，跳过")
            return None

        if provider_payload:
            registry.update_provider_config(provider_name, provider_payload)

        provider_instance = registry.get_provider_instance(provider_name, force_new=True)
        if not provider_instance:
            raise RuntimeError(f"无法实例化数据源 {provider_name}")

        provider = cast(IDataSource, provider_instance)
        await provider.initialize()

        entry = self._transition_status(
            source_type,
            DataSourceLifecycleStatus.ACTIVE,
            available=True,
            reason="initialized",
            config={"priority": config.priority, "timeout": config.timeout},
        )
        entry.pop("degraded_reason", None)
        entry.pop("pending_reactivation", None)
        entry["last_health_check"] = time.time()
        return provider

    def get_available_sources(self) -> List[DataSourceType]:
        """获取所有可用的数据源"""
        available = [
            source_type
            for source_type, status in self._source_status.items()
            if status.get("available", False)
        ]
        if not available and self.providers:
            available = list(self.providers.keys())
        return available

    def get_sources_for_context(
            self,
            module: Optional[str] = None,
            access_type: Optional[DataAccessType] = None,
    ) -> List[DataSourceType]:
        """
        获取特定模块/访问类型的数据源顺序。
        
        按以下优先级查找：
        1. module_overrides[module] - 模块级配置
        2. access_type_overrides[access_type] - 访问类型配置
        3. 全局 fallback_order / available sources
        
        Args:
            module: 模块名称（如 "market_strength"）
            access_type: 数据访问类型
            
        Returns:
            数据源类型列表（按优先级排序）
        """
        # 使用模块解析器获取配置的数据源顺序
        if self._module_resolver:
            resolved = self._module_resolver.resolve(module=module, access_type=access_type)
            if resolved:
                # 过滤出当前可用的数据源
                available_set = set(self.get_available_sources())
                filtered = [s for s in resolved if s in available_set or s in self.providers]
                if filtered:
                    return filtered

        # 回退到全局可用数据源
        return self.get_available_sources()

    def get_last_success_source(self) -> Optional[DataSourceType]:
        """获取最近一次成功返回数据的源类型。"""

        return self._last_success_source

    def is_source_available(self, source_type: DataSourceType) -> bool:
        """检查数据源是否可用"""
        return self._source_status.get(source_type, {}).get("available", False)

    async def get_data(
        self,
        data_type: str,
        symbol: str,
        preferred_source: Optional[DataSourceType] = None,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        统一的数据获取接口

        Args:
            data_type: 数据类型 (realtime_quote, orderbook, kline等)
            symbol: 股票代码
            preferred_source: 首选数据源
            **kwargs: 其他参数

        Returns:
            数据字典，包含source字段标识来源
        """
        # 检查是否初始化
        if not self.initialized:
            await self.initialize()

        # 重置最近一次成功的数据源
        self._last_success_source = None

        # 获取可用数据源
        available_sources = self.get_available_sources()
        if not available_sources:
            logger.error("没有可用的数据源")
            return None

        preferred_type = self._resolve_source_type(preferred_source)

        # 选择数据源
        sources_to_try = self._select_sources(available_sources, preferred_type)

        if preferred_type is None:
            hinted_provider = self._get_provider_for_request(data_type)
            if hinted_provider:
                for hinted_type, provider_instance in self.providers.items():
                    if provider_instance is hinted_provider:
                        if hinted_type in sources_to_try:
                            sources_to_try = [hinted_type] + [
                                s for s in sources_to_try if s != hinted_type
                            ]
                        else:
                            sources_to_try = [hinted_type] + sources_to_try
                        break

        # 依次尝试数据源
        for source_type in sources_to_try:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            try:
                # 根据数据类型调用相应方法
                if data_type == "realtime_quote":
                    data = await self._get_realtime_quote(provider, symbol)
                elif data_type == "orderbook":
                    data = await self._get_orderbook(provider, symbol)
                elif data_type == "kline":
                    data = await self._get_kline(provider, symbol, **kwargs)
                else:
                    logger.warning(f"不支持的数据类型: {data_type}")
                    continue

                if data:
                    if isinstance(data, dict):
                        data.setdefault("source", source_type.value)
                        data.setdefault("timestamp", time.time())
                        return data
                    return {"data": data, "source": source_type.value, "timestamp": time.time()}

            except Exception as e:
                logger.error(f"从 {source_type.value} 获取数据失败: {e}")
                continue

        logger.warning(f"所有数据源都无法获取 {symbol} 的 {data_type} 数据")
        return None

    def _select_sources(
        self,
        available_sources: List[DataSourceType],
        preferred_source: Optional[DataSourceType] = None,
    ) -> List[DataSourceType]:
        """
        选择数据源顺序

        Args:
            available_sources: 可用数据源列表
            preferred_source: 首选数据源

        Returns:
            按优先级排序的数据源列表
        """
        result = []

        # 如果有首选源且可用，放在第一位
        if preferred_source and preferred_source in available_sources:
            result.append(preferred_source)
            available_sources = [s for s in available_sources if s != preferred_source]

        # 按配置的优先级排序剩余数据源
        priorities = {}
        for source_type in available_sources:
            config = self.registry.get_config(source_type)
            if config:
                priorities[source_type] = config.priority
            else:
                priorities[source_type] = 999

        # 按优先级排序（数字越小优先级越高）
        sorted_sources = sorted(available_sources, key=lambda x: priorities[x])
        result.extend(sorted_sources)

        return result

    async def _get_realtime_quote(
        self, provider: Any, symbol: str
    ) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        getter = getattr(provider, "get_realtime_quote", None)
        if callable(getter):
            bound = cast(
                Callable[[str], Awaitable[Optional[Dict[str, Any]]]],
                getter,
            )
            return await bound(symbol)
        return None

    async def _get_orderbook(
        self, provider: Any, symbol: str
    ) -> Optional[Dict[str, Any]]:
        """获取盘口数据"""
        async_getter = getattr(provider, "get_orderbook", None)
        if callable(async_getter):
            bound_async = cast(
                Callable[[str], Awaitable[Optional[Dict[str, Any]]]],
                async_getter,
            )
            return await bound_async(symbol)
        sync_getter = getattr(provider, "get_latest_orderbook", None)
        if callable(sync_getter):
            bound_sync = cast(Callable[[str], Optional[Dict[str, Any]]], sync_getter)
            return bound_sync(symbol)
        return None

    async def _get_kline(self, provider: Any, symbol: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """获取K线数据"""
        kline_getter = getattr(provider, "get_kline_data", None)
        if callable(kline_getter):
            bound_kline = cast(
                Callable[..., Awaitable[Optional[Dict[str, Any]]]],
                kline_getter,
            )
            return await bound_kline(symbol, **kwargs)
        hist_getter = getattr(provider, "get_stock_hist", None)
        if callable(hist_getter):
            bound_hist = cast(
                Callable[..., Awaitable[Optional[Dict[str, Any]]]],
                hist_getter,
            )
            return await bound_hist(symbol, **kwargs)
        return None

    def get_status_report(self) -> Dict[str, Any]:
        """获取状态报告"""
        status_snapshot: Dict[DataSourceType, SourceStatusEntry] = dict(self._source_status)

        # 先根据配置状态标记禁用的数据源，避免被后续连接状态覆盖
        for source_type in SUPPORTED_SOURCE_TYPES:
            config = self.registry.get_config(source_type)
            if config and not config.enabled:
                existing_entry = self._source_status.get(source_type, {})
                if existing_entry.get("pending_reactivation"):
                    status_snapshot[source_type] = existing_entry
                    continue
                entry = self._transition_status(
                    source_type,
                    DataSourceLifecycleStatus.DEGRADED,
                    available=False,
                    reason="disabled_by_config",
                )
                entry["degraded_reason"] = "disabled_by_config"
                status_snapshot[source_type] = self._source_status[source_type]
                continue

        # 再根据实际连接信息进行补充
        for source_type, provider in self.providers.items():
            config = self.registry.get_config(source_type)
            if config and not config.enabled:
                continue

            is_available = True
            reason = "from_provider"
            connected_attr = getattr(provider, "is_connected", None)
            if callable(connected_attr):
                try:
                    connected_state = connected_attr()
                    if asyncio.iscoroutine(connected_state):
                        logger.debug("is_connected 返回协程，跳过等待并默认视为可用")
                        connected_state = True
                    is_available = bool(connected_state)
                    reason = "provider_connected" if is_available else "provider_not_connected"
                except Exception as error:
                    logger.debug(f"检测数据源 {source_type.value} 连接状态失败: {error}")
                    is_available = False
                    reason = "connection_check_failed"
            target_status = (
                DataSourceLifecycleStatus.ACTIVE
                if is_available
                else DataSourceLifecycleStatus.ERROR
            )
            self._transition_status(
                source_type,
                target_status,
                available=is_available,
                reason=reason,
            )
            status_snapshot[source_type] = self._source_status[source_type]

        sources_report: Dict[str, Dict[str, Any]] = {}
        try:
            pool_status = get_global_pool().get_status()
        except Exception as exc:  # pragma: no cover - diagnostics only
            logger.debug(f"Failed to fetch AmazingData process pool status: {exc}")
            pool_status = None
        if pool_status:
            processes = pool_status.get("processes", {})
            for source_type in SUPPORTED_SOURCE_TYPES:
                if source_type is not DataSourceType.AMAZINGDATA:
                    continue
                provider = self.providers.get(source_type)
                if provider is None:
                    continue
                datasource_id = getattr(provider, "_datasource_id", None)
                if not datasource_id:
                    continue
                pool_entry = processes.get(datasource_id)
                if not pool_entry:
                    continue
                status_entry = status_snapshot.setdefault(source_type, {})
                throttle_payload = pool_entry.get("throttle")
                if throttle_payload:
                    status_entry["loginThrottle"] = throttle_payload
                status_entry["pendingLogin"] = bool(pool_entry.get("pending_login", False))
                value_started = pool_entry.get("last_login_started_at")
                if value_started is not None:
                    status_entry["lastLoginStartedAt"] = value_started
                value_completed = pool_entry.get("last_login_completed_at")
                if value_completed is not None:
                    status_entry["lastLoginCompletedAt"] = value_completed
                value_success = pool_entry.get("last_login_success_at")
                if value_success is not None:
                    status_entry["lastLoginSuccessAt"] = value_success
                value_error_time = pool_entry.get("last_login_error_at")
                if value_error_time is not None:
                    status_entry["lastLoginErrorAt"] = value_error_time
                value_error_reason = pool_entry.get("last_login_error_reason")
                if value_error_reason is not None:
                    status_entry["lastLoginErrorReason"] = value_error_reason

        for source_type in SUPPORTED_SOURCE_TYPES:
            status = status_snapshot.get(source_type, {})
            config = self.registry.get_config(source_type)
            has_saved = self._resolve_has_saved_credential(config, status)
            entry = {
                "status": status.get("status", DataSourceLifecycleStatus.DRAFT.value),
                "available": status.get("available", False),
                "reason": status.get("reason", ""),
                "lastTransition": self._format_timestamp(status.get("last_transition")),
                "lastTestTime": self._format_timestamp(status.get("last_test_time")),
                "testSummary": status.get("test_summary"),
                "hasSavedCredential": bool(has_saved) if has_saved is not None else False,
                "config": {
                    "enabled": bool(config.enabled) if config else False,
                    "priority": config.priority if config else 999,
                },
            }
            throttle_info = status.get("loginThrottle")
            if throttle_info:
                entry["loginThrottle"] = throttle_info
            if status.get("pendingLogin") is not None:
                entry["pendingLogin"] = bool(status.get("pendingLogin"))
            for field_name in (
                    "lastLoginStartedAt",
                    "lastLoginCompletedAt",
                    "lastLoginSuccessAt",
                    "lastLoginErrorAt",
            ):
                field_value = status.get(field_name)
                if field_value:
                    entry[field_name] = field_value
            if status.get("lastLoginErrorReason"):
                entry["lastLoginErrorReason"] = status.get("lastLoginErrorReason")
            if config and isinstance(config.config, dict):
                detailed_config = _sanitize_config_snapshot(config.config)
                detailed_config = _prune_empty(detailed_config)
                if detailed_config:
                    entry["config"].update(detailed_config)
            if status.get("test_details") is not None:
                entry["testDetails"] = status.get("test_details")
            if status.get("degraded_reason"):
                entry["degradedReason"] = status.get("degraded_reason")
            if status.get("pending_reactivation"):
                entry["pendingReactivation"] = True
            if status.get("last_health_check"):
                entry["lastHealthCheck"] = self._format_timestamp(status.get("last_health_check"))
            if status.get("metrics"):
                entry["metrics"] = status.get("metrics")
            sources_report[source_type.value] = entry

        available_count = sum(1 for entry in sources_report.values() if entry.get("available"))

        return {
            "initialized": self.initialized,
            "sources": sources_report,
            "availableCount": available_count,
            "available_count": available_count,
        }

    async def get_stock_list(
            self,
            limit: Optional[int] = None,
            **kwargs,
    ) -> Optional[StockListFetchResult]:
        """获取股票列表，同时返回领域结构与旧结构。"""

        if not self.initialized:
            await self.initialize()

        for source_type in self.providers:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            source_label = (
                source_type.value if hasattr(source_type, "value") else str(source_type)
            )

            try:
                payload: Optional[Any] = None
                get_records = getattr(provider, "get_stock_list_records", None)
                if callable(get_records):
                    maybe_records = get_records(limit=limit, **kwargs)
                    payload = (
                        await maybe_records
                        if inspect.isawaitable(maybe_records)
                        else maybe_records
                    )
                    result = build_stock_list_result(payload, source_label, limit=limit)
                    if result and (result.records or result.legacy):
                        logger.info(
                            "从%s获取股票列表成功 records=%d legacy=%d",
                            source_label,
                            len(result.records),
                            len(result.legacy),
                        )
                        if result.mismatch:
                            logger.warning(
                                "股票列表双写存在差异 source=%s mismatch=%d",
                                source_label,
                                result.mismatch,
                            )
                        return result

                get_list = getattr(provider, "get_stock_list", None)
                if callable(get_list):
                    payload = await get_list(limit=limit, **kwargs)
                    result = build_stock_list_result(payload, source_label, limit=limit)
                    if result and (result.records or result.legacy):
                        logger.info(
                            "从%s获取股票列表成功 records=%d legacy=%d",
                            source_label,
                            len(result.records),
                            len(result.legacy),
                        )
                        if result.mismatch:
                            logger.warning(
                                "股票列表双写存在差异 source=%s mismatch=%d",
                                source_label,
                                result.mismatch,
                            )
                        return result
            except Exception as error:
                logger.error(f"从{source_label}获取股票列表失败: {error}")
                continue

        logger.error("所有数据源均无法获取股票列表")
        return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            **kwargs: 其他参数

        Returns:
            K线数据列表
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.providers:
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, "get_kline_data"):
                    method = getattr(provider, "get_kline_data")
                    if callable(method):
                        bound_method = cast(
                            Callable[..., Awaitable[Optional[List[Dict[str, Any]]]]],
                            method,
                        )
                        result = await bound_method(
                            symbol=symbol,
                            period=period,
                            start_date=start_date,
                            end_date=end_date,
                            limit=limit,
                            **kwargs,
                        )
                        if result:
                            logger.info(f"从{source_type}获取K线数据成功: {symbol}")
                            return result
            except Exception as e:
                logger.error(f"从{source_type}获取K线数据失败: {e}")
                continue

        logger.error(f"所有数据源均无法获取K线数据: {symbol}")
        return None

    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        preferred_source: Optional[Union[str, DataSourceType]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """兼容旧接口，返回带来源标识的历史K线数据。"""

        if not self.initialized:
            await self.initialize()

        preferred_type = self._resolve_source_type(preferred_source)
        available_sources = self.get_available_sources()
        if not available_sources:
            logger.error("没有可用的数据源以获取历史K线数据")
            return {"data": [], "source": "none", "error": "no_available_source"}

        sources_to_try = self._select_sources(available_sources, preferred_type)

        for source_type in sources_to_try:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            try:
                result: Any = None

                if hasattr(provider, "get_kline_data"):
                    method = getattr(provider, "get_kline_data")
                    if not callable(method):
                        continue
                    result = await cast(
                        Callable[..., Awaitable[Any]],
                        method,
                    )(
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                        **kwargs,
                    )
                elif hasattr(provider, "get_stock_hist"):
                    method = getattr(provider, "get_stock_hist")
                    if not callable(method):
                        continue
                    result = await cast(
                        Callable[..., Awaitable[Any]],
                        method,
                    )(
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        **kwargs,
                    )
                else:
                    continue

                if not result:
                    continue

                if isinstance(result, dict):
                    result.setdefault("source", source_type.value)
                    if "data" not in result:
                        if isinstance(result.get("result"), list):
                            result["data"] = result["result"]
                        else:
                            payload = {
                                k: v for k, v in result.items() if k not in {"data", "source"}
                            }
                            result["data"] = [payload] if payload else []
                    return result

                return {"data": result, "source": source_type.value}
            except Exception as error:
                logger.error(f"从{source_type.value}获取历史数据失败: {error}")
                continue

        logger.error(f"所有数据源均无法获取K线数据: {symbol}")
        return {"data": [], "source": "none", "error": "no_data"}

    async def get_realtime_quote(
        self, symbol: str, preferred_source: Optional[Union[str, DataSourceType]] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """获取单个标的的实时行情。"""

        if not self.initialized:
            await self.initialize()

        preferred_type = self._resolve_source_type(preferred_source)
        available_sources = self.get_available_sources()
        if not available_sources:
            logger.error("没有可用的数据源以获取实时行情")
            return None

        sources_to_try = self._select_sources(available_sources, preferred_type)

        for source_type in sources_to_try:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            try:
                result: Any = None

                if hasattr(provider, "get_realtime_quote"):
                    method = getattr(provider, "get_realtime_quote")
                    if not callable(method):
                        continue
                    result = await cast(
                        Callable[..., Awaitable[Optional[Dict[str, Any]]]],
                        method,
                    )(symbol, **kwargs)
                elif hasattr(provider, "get_realtime_quotes"):
                    method = getattr(provider, "get_realtime_quotes")
                    if not callable(method):
                        continue
                    batch = await cast(
                        Callable[..., Awaitable[Any]],
                        method,
                    )([symbol], **kwargs)
                    if isinstance(batch, dict):
                        result = batch.get(symbol)
                    elif isinstance(batch, list) and batch:
                        result = batch[0]
                    else:
                        result = batch
                else:
                    continue

                if not result:
                    continue

                if isinstance(result, dict):
                    result.setdefault("source", source_type.value)
                    return result
                return {"source": source_type.value, "data": result}
            except Exception as error:
                logger.error(f"从{source_type.value}获取实时行情失败: {error}")
                continue

        logger.error(f"所有数据源均无法获取实时行情: {symbol}")
        return None

    async def fetch_stock_info(
        self, symbol: str, preferred_source: Optional[Union[str, DataSourceType]] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """获取股票基础信息，兼容旧接口命名。"""

        if not self.initialized:
            await self.initialize()

        preferred_type = self._resolve_source_type(preferred_source)
        available_sources = self.get_available_sources()
        if not available_sources:
            logger.error("没有可用的数据源以获取股票信息")
            return None

        sources_to_try = self._select_sources(available_sources, preferred_type)

        for source_type in sources_to_try:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            for method_name in ("get_stock_info", "fetch_stock_info"):
                if not hasattr(provider, method_name):
                    continue

                try:
                    method = getattr(provider, method_name)
                    if not callable(method):
                        continue
                    bound_method = cast(
                        Callable[..., Awaitable[Optional[Dict[str, Any]]]],
                        method,
                    )
                    result = await bound_method(symbol, **kwargs)

                    if result:
                        if isinstance(result, dict):
                            result.setdefault("source", source_type.value)
                        return result
                except Exception as error:
                    logger.error(f"从{source_type.value}获取股票信息失败: {error}")
                    break

        logger.error(f"所有数据源均无法获取股票信息: {symbol}")
        return None

    async def get_stock_info(
        self, symbol: str, preferred_source: Optional[Union[str, DataSourceType]] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """获取股票基础信息，fetch_stock_info 的别名方法。"""
        return await self.fetch_stock_info(symbol, preferred_source=preferred_source, **kwargs)

    async def get_realtime_quotes(
        self, symbols: List[str], **kwargs
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表
            **kwargs: 其他参数

        Returns:
            实时行情字典 {symbol: quote_data}
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.providers:
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, "get_realtime_quotes"):
                    method = getattr(provider, "get_realtime_quotes")
                    if callable(method):
                        # 直接使用位置参数调用，不使用 symbols= 关键字参数
                        result = await method(symbols, **kwargs)
                        if result:
                            # 如果返回的是列表，转换为字典格式
                            if isinstance(result, list):
                                result_dict: Dict[str, Dict[str, Any]] = {}
                                for item in result:
                                    if isinstance(item, dict) and "symbol" in item:
                                        result_dict[item["symbol"]] = item
                                if result_dict:
                                    logger.info(f"从{source_type}获取实时行情成功")
                                    return result_dict
                            elif isinstance(result, dict):
                                logger.info(f"从{source_type}获取实时行情成功")
                                return result
            except Exception as e:
                logger.error(f"从{source_type}获取实时行情失败: {e}")
                continue

        logger.error("所有数据源均无法获取实时行情")
        return None

    def _get_provider_for_request(self, request_type: Optional[str] = None) -> Optional[Any]:
        """
        根据请求类型获取合适的数据提供者

        Args:
            request_type: 请求类型

        Returns:
            数据提供者实例
        """
        # 按优先级排序的可用数据源
        available_sources = self.get_available_sources()

        for source_type in available_sources:
            provider = self.providers.get(source_type)
            if provider:
                return provider

        return None

    def get_provider(self, source_type: Optional[DataSourceType] = None) -> Optional[Any]:
        """
        获取指定的数据提供者

        Args:
            source_type: 数据源类型

        Returns:
            数据提供者实例
        """
        if source_type is None:
            # 返回优先级最高的可用提供者
            return self._get_provider_for_request()

        return self.providers.get(source_type)

    async def execute_with_fallback(
        self,
        method_name: str,
        *args,
        access_type: DataAccessType = DataAccessType.REALTIME_QUOTE,
        monitor_context: Optional[Dict[str, Any]] = None,
        result_validator: Optional[Callable[[Any], bool]] = None,
        require_result: bool = False,
        **kwargs,
    ) -> Optional[Any]:
        """
        执行方法，带故障转移并自动打点。
        """

        if not self.initialized:
            await self.initialize()

        result, source = await self._executor.execute(
            providers=self.providers,
            source_order=self.get_sources_for_context(
                module=(monitor_context or {}).get("module"),
                access_type=access_type,
            ),
            method_name=method_name,
            args=args,
            kwargs=kwargs,
            access_type=access_type,
            monitor_symbol=(monitor_context or {}).get("symbol"),
            monitor_module=(monitor_context or {}).get("module"),
            validator=result_validator,
            require_result=require_result,
        )
        if source:
            self._last_success_source = source
        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查

        Returns:
            健康状态报告
        """
        health_status = {}

        for source_type, provider in self.providers.items():
            try:
                # 检查provider是否有health_check方法
                if hasattr(provider, "health_check"):
                    status = (
                        await provider.health_check()
                        if asyncio.iscoroutinefunction(provider.health_check)
                        else provider.health_check()
                    )
                    health_status[source_type.value] = {
                        "status": "healthy" if status else "unhealthy",
                        "details": status,
                    }
                else:
                    # 基础健康检查：检查provider是否可用
                    health_status[source_type.value] = {
                        "status": "healthy" if provider else "unhealthy",
                        "details": {"available": bool(provider)},
                    }
            except Exception as e:
                health_status[source_type.value] = {"status": "error", "details": {"error": str(e)}}

        return {
            "overall": (
                "healthy"
                if any(s["status"] == "healthy" for s in health_status.values())
                else "unhealthy"
            ),
            "sources": health_status,
            "available_count": len([s for s in health_status.values() if s["status"] == "healthy"]),
        }

    async def close(self):
        """
        关闭数据源管理器，释放资源
        """
        logger.info("正在关闭数据源管理器...")

        for source_type, provider in self.providers.items():
            try:
                if hasattr(provider, "close"):
                    if asyncio.iscoroutinefunction(provider.close):
                        await provider.close()
                    else:
                        provider.close()
                    logger.info(f"已关闭数据源: {source_type}")
            except Exception as e:
                logger.error(f"关闭数据源{source_type}时出错: {e}")

        self.providers.clear()
        self.initialized = False
        logger.info("数据源管理器已关闭")

    async def subscribe_realtime(
        self, symbols: List[str], callback: RealtimeCallback
    ) -> bool:
        """
        订阅实时数据

        Args:
            symbols: 股票代码列表
            callback: 回调函数

        Returns:
            订阅是否成功
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.get_available_sources():
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, "subscribe_realtime"):
                    method = getattr(provider, "subscribe_realtime")
                    if callable(method):
                        wrapped_callback = self._wrap_realtime_callback(source_type, callback)
                        bound_method = cast(
                            Callable[[List[str], Callable[[object], None]], Awaitable[bool] | bool],
                            method,
                        )
                        call_result = bound_method(symbols, wrapped_callback)
                        result_flag = (
                            await call_result
                            if asyncio.iscoroutine(call_result)
                            else bool(call_result)
                        )
                        if result_flag:
                            logger.info(f"通过{source_type}订阅实时数据成功")
                            return True
            except Exception as e:
                logger.error(f"通过{source_type}订阅实时数据失败: {e}")
                continue

        logger.error("所有数据源均无法订阅实时数据")
        return False

    def _wrap_realtime_callback(
        self, source_type: DataSourceType, callback: RealtimeCallback
    ) -> Callable[[object], None]:
        """
        将底层数据源推送转换为统一的消息信封，统一输出类型。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def _ensure_envelope(raw: object) -> ProviderMessageEnvelope:
            if isinstance(raw, dict) and {"topic", "timestamp"} <= raw.keys():
                return cast(ProviderMessageEnvelope, raw)
            return {
                "topic": "providers.realtime.quote",
                "type": source_type.value,
                "timestamp": time.time(),
                "payload": raw,
                "metadata": {"source": source_type.value},
            }

        async def _await_result(awaitable: Awaitable[None]) -> None:
            await awaitable

        def _dispatch(raw: object) -> None:
            envelope = _ensure_envelope(raw)
            result = callback(envelope)
            if inspect.isawaitable(result):
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                awaitable = cast(Awaitable[None], result)
                if current_loop is not None:
                    current_loop.create_task(_await_result(awaitable))  # 在当前事件循环调度
                elif loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(_await_result(awaitable), loop)
                else:
                    asyncio.run(_await_result(awaitable))

        return _dispatch

    def set_primary_source(self, source_type: DataSourceType) -> bool:
        """
        设置主数据源

        Args:
            source_type: 数据源类型

        Returns:
            bool: 是否设置成功
        """
        # 检查数据源是否可用
        if not self.is_source_available(source_type):
            logger.error(f"数据源 {source_type.value} 不可用，无法设置为主数据源")
            return False

        # 更新配置优先级，将指定数据源设为最高优先级
        config = self.registry.get_config(source_type)
        if config:
            # 将所有其他数据源优先级降低
            for other_type in self.get_available_sources():
                if other_type != source_type:
                    other_config = self.registry.get_config(other_type)
                    if other_config and other_config.priority < 100:
                        other_config.priority += 10

            # 设置主数据源优先级为最高
            config.priority = 1
            logger.info(f"已设置 {source_type.value} 为主数据源")
            return True
        else:
            logger.error(f"无法获取数据源 {source_type.value} 的配置")
            return False

    def get_provider_info(self, source: Union[str, DataSourceType]) -> Optional[Dict[str, Any]]:
        """获取指定数据源的配置信息与运行状态。"""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            logger.warning(f"未知的数据源标识: {source}")
            return None

        config = self.registry.get_config(source_type)
        status = self._source_status.get(source_type, {})
        provider = self.providers.get(source_type)

        if not config and not status and provider is None:
            return None

        config_dict = asdict(config) if isinstance(config, DataSourceConfig) else {}
        if config:
            config_dict["enabled"] = config.enabled
            config_dict["priority"] = config.priority
            config_dict["timeout"] = config.timeout

        return {
            "name": source_type.value,
            "config": config_dict or None,
            "available": status.get("available", provider is not None),
            "status": status,
        }

    def enable_provider(
        self,
        source: Union[str, DataSourceType],
        reinitialize: bool = True,
    ) -> bool:
        """启用数据源并在必要时重新初始化。"""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            logger.warning(f"无法启用未知的数据源: {source}")
            return False

        config = self.registry.get_config(source_type)
        if not config:
            logger.warning(f"数据源 {source_type.value} 尚未在注册表中配置")
            return False

        entry = self._source_status.get(source_type) or {}
        status_value = entry.get("status")
        reason_value = entry.get("reason")
        available_value = entry.get("available", True)
        was_disabled = bool(
            reason_value == "disabled_by_config"
            or not available_value
            or status_value
            in (
                DataSourceLifecycleStatus.OFFLINE.value,
                DataSourceLifecycleStatus.ERROR.value,
                DataSourceLifecycleStatus.DRAFT.value,
                "offline",
            )
        )
        if config.enabled and not was_disabled:
            return True

        config.enabled = True
        if source_type == DataSourceType.AKSHARE:
            self._handle_akshare_enabled(config)
        else:
            self._update_provider_snapshot(source_type, config)
            self._update_fallback_order_config()

        if reinitialize and self.initialized:
            self.initialized = False

        entry = self._transition_status(
            source_type,
            DataSourceLifecycleStatus.PENDING_TEST,
            available=False,
            reason="pending_initialization",
        )
        entry.pop("degraded_reason", None)
        entry.pop("pending_reactivation", None)
        logger.info(f"已启用数据源 {source_type.value}，等待重新初始化")

        return True

    def disable_provider(
        self,
        source: Union[str, DataSourceType],
        reinitialize: bool = True,
    ) -> bool:
        """禁用数据源并释放对应实例。"""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            logger.warning(f"无法禁用未知的数据源: {source}")
            return False

        config = self.registry.get_config(source_type)
        if not config:
            logger.warning(f"数据源 {source_type.value} 尚未在注册表中配置")
            return False

        if not config.enabled:
            return True

        config.enabled = False
        if source_type == DataSourceType.AKSHARE:
            self._handle_akshare_disabled(config)
        else:
            self._update_provider_snapshot(source_type, config)
            self._update_fallback_order_config()

        provider = self.providers.pop(source_type, None)
        if provider and hasattr(provider, "close"):
            try:
                close_result = provider.close()
                if asyncio.iscoroutine(close_result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.run(close_result)
                    else:
                        if loop.is_running():
                            loop.create_task(close_result)
                        else:
                            loop.run_until_complete(close_result)
            except Exception as error:
                logger.debug(f"关闭数据源 {source_type.value} 时出现异常: {error}")

        entry = self._transition_status(
            source_type,
            DataSourceLifecycleStatus.DEGRADED,
            available=False,
            reason="disabled_by_config",
        )
        entry["degraded_reason"] = "disabled_by_config"
        entry.pop("pending_reactivation", None)

        if reinitialize and self.initialized:
            self.initialized = False

        logger.info(f"已禁用数据源 {source_type.value}")
        return True

    def mark_test_reactivation_pending(self, source: Union[str, DataSourceType]) -> bool:
        """Mark pending reactivation state for test-mode enable toggles."""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            logger.warning(f"无法解析测试重启的数据源: {source}")
            return False

        config = self.registry.get_config(source_type)
        if not config:
            logger.warning(f"数据源 {source_type.value} 尚未注册配置")
            return False

        entry = self._transition_status(
            source_type,
            DataSourceLifecycleStatus.PENDING_TEST,
            available=False,
            reason="test_mode_pending_activation",
        )
        entry["pending_reactivation"] = True
        entry.setdefault("degraded_reason", "disabled_by_config")
        return True

    def set_provider_priority(self, source: Union[str, DataSourceType], priority: int) -> bool:
        """更新数据源优先级。"""

        source_type = self._resolve_source_type(source)
        if source_type is None:
            logger.warning(f"无法更新未知数据源的优先级: {source}")
            return False

        config = self.registry.get_config(source_type)
        if not config:
            logger.warning(f"数据源 {source_type.value} 尚未在注册表中配置")
            return False

        try:
            config.priority = int(priority)
        except (TypeError, ValueError):
            logger.warning(f"无效的优先级: {priority}")
            return False

        status = self._source_status.setdefault(source_type, {})
        config_section = status.setdefault("config", {})
        config_section["priority"] = config.priority
        logger.info(f"已将数据源 {source_type.value} 优先级设置为 {config.priority}")
        return True

    def get_available_providers(self) -> List[DataSourceType]:
        """获取所有可用的数据提供者（别名方法）"""
        return self.get_available_sources()

    def get_providers_by_priority(self) -> List[DataSourceType]:
        """按优先级排序获取所有数据提供者"""
        available_sources = self.get_available_sources()

        # 按配置的优先级排序
        priorities = {}
        for source_type in available_sources:
            config = self.registry.get_config(source_type)
            if config:
                priorities[source_type] = config.priority
            else:
                priorities[source_type] = 999

        # 按优先级排序（数字越小优先级越高）
        sorted_sources = sorted(available_sources, key=lambda x: priorities[x])
        return sorted_sources


# 全局实例
_data_source_manager: Optional[DataSourceManager] = None


def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _data_source_manager
    if _data_source_manager is None:
        _data_source_manager = DataSourceManager()
    return _data_source_manager


async def initialize_data_sources():
    """初始化数据源系统"""
    manager = get_data_source_manager()
    await manager.initialize()
    return manager


async def get_data_manager() -> DataSourceManager:
    """获取已初始化的数据管理器实例
    
    这是一个向后兼容的别名函数，供从 enhanced_manager 迁移的代码使用。
    等同于调用 initialize_data_sources()。
    
    Returns:
        初始化后的 DataSourceManager 实例
    """
    return await initialize_data_sources()
