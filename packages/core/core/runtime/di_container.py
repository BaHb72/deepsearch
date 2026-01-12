"""
声明式依赖注入容器

基于 dependency-injector 库，提供：
- 自动依赖解析
- 启动时依赖验证
- 构造函数注入
- 生命周期管理
"""

from typing import Any, Dict

from core.config import get_config
from core.observability import get_logger
from dependency_injector import containers, providers

logger = get_logger("deepsearch.di_container")


def _get_config_value(path: str, default: Any = None) -> Any:
    """安全获取配置值"""
    try:
        config = get_config()
        parts = path.split(".")
        value: Any = config
        for part in parts:
            value = getattr(value, part, None)
            if value is None:
                return default
        return value
    except Exception:
        return default


def _create_event_engine():
    """创建事件引擎"""
    from ..components import EventEngineComponent

    return EventEngineComponent(
        queue_size=_get_config_value("performance.queue_size", 10000),
        max_workers=_get_config_value("performance.max_workers", 32),
        batch_size=_get_config_value("performance.batch_size", 100),
    )


def _create_message_bus():
    """创建消息总线"""
    from ..components import MessageBusComponent

    return MessageBusComponent()


def _create_database():
    """创建数据库组件"""
    from ..components import DatabaseComponent

    return DatabaseComponent()


def _create_cache():
    """创建缓存组件"""
    from ..components import CacheComponent

    return CacheComponent()


def _create_analytics():
    """创建分析组件"""
    from ..components import AnalyticsComponent

    return AnalyticsComponent()


def _create_gateway():
    """创建网关组件"""
    from ..components import GatewayComponent

    return GatewayComponent()


def _create_qmt_gateway():
    """创建 QMT 网关组件"""
    from ..components import QMTGatewayComponent

    return QMTGatewayComponent()


def _create_backtest():
    """创建回测组件"""
    from ..components import BacktestComponent

    return BacktestComponent()


def _create_webui():
    """创建 WebUI 组件"""
    from ..components import WebUIComponent

    return WebUIComponent()


def _get_amazingdata_config() -> dict:
    """
    获取 AmazingData 连接配置

    Returns:
        配置字典，包含 username/password/host/port/timeout
    """
    from core.config import get_config

    try:
        app_config = get_config()
        data_sources_cfg = getattr(app_config, "data_sources", {})

        if data_sources_cfg:
            if hasattr(data_sources_cfg, "model_dump"):
                data_sources_payload = data_sources_cfg.model_dump()
            elif isinstance(data_sources_cfg, dict):
                data_sources_payload = dict(data_sources_cfg)
            else:
                data_sources_payload = dict(getattr(data_sources_cfg, "__dict__", {}))
        else:
            data_sources_payload = {}

        providers_cfg = data_sources_payload.get("providers", {})
        if hasattr(providers_cfg, "model_dump"):
            providers_cfg = providers_cfg.model_dump()
        elif not isinstance(providers_cfg, dict):
            providers_cfg = dict(getattr(providers_cfg, "__dict__", {}))

        provider_entry = providers_cfg.get("amazingdata", {})
        if hasattr(provider_entry, "model_dump"):
            provider_entry = provider_entry.model_dump()
        elif not isinstance(provider_entry, dict):
            provider_entry = dict(getattr(provider_entry, "__dict__", {}))

        raw_config = provider_entry.get("config", {})
        connection_cfg = raw_config.get("connection", {})

        config_dict = {
            "username": connection_cfg.get("username", ""),
            "password": connection_cfg.get("password", ""),
            "host": connection_cfg.get("host", "101.230.159.234"),
            "port": connection_cfg.get("port", 8600),
            "timeout": float(connection_cfg.get("timeout", 10)),
        }

        logger.debug("[DI] AmazingData 配置已加载")
        return config_dict

    except Exception as e:
        logger.error(f"[DI] 加载 AmazingData 配置失败: {e}")
        raise


class ApplicationContainer(containers.DeclarativeContainer):
    """
    应用主容器

    使用 dependency-injector 管理所有组件的依赖关系。
    采用 Singleton 模式确保每个组件只创建一次。

    特性：
    - 自动 Wiring：支持 @inject 装饰器自动注入依赖
    - 组件依赖图：可视化组件间依赖关系
    - 拓扑排序：按依赖顺序初始化组件
    """

    # Wiring 配置 - 自动扫描并注入这些模块中的 @inject 函数
    wiring_config = containers.WiringConfiguration(
        modules=[
            "core.core.runtime.bootstrap",
            "core.core.runtime.lifecycle",
            # "apps.webui.dependencies",  # 暂时注释，需确认 webui 路径
        ],
        auto_wire=True,
    )

    # 配置
    config = providers.Configuration()

    # =========================================================================
    # 基础设施层 - 所有模式都加载（无依赖）
    # =========================================================================
    event_engine = providers.Singleton(_create_event_engine)
    message_bus = providers.Singleton(_create_message_bus)
    database = providers.Singleton(_create_database)
    cache = providers.Singleton(_create_cache)

    # =========================================================================
    # 业务层 - engine/all 模式加载（依赖基础设施层）
    # =========================================================================
    analytics = providers.Singleton(_create_analytics)
    gateway = providers.Singleton(_create_gateway)
    qmt_gateway = providers.Singleton(_create_qmt_gateway)
    backtest = providers.Singleton(_create_backtest)

    # =========================================================================
    # 界面层 - webui/all 模式加载（依赖业务层）
    # =========================================================================
    webui = providers.Singleton(_create_webui)

    # =========================================================================
    # 数据提供者配置 - 按需加载（实际 Actor 由 DataProviderFactory 创建）
    # =========================================================================
    amazingdata_config = providers.Singleton(_get_amazingdata_config)


# 组件依赖定义（用于拓扑排序）
COMPONENT_DEPENDENCIES = {
    # 基础设施层 - 无依赖
    "event_engine": [],
    "message_bus": [],
    "database": [],
    "cache": [],
    # 数据提供者配置 - 无依赖（实际 Actor 由 DataProviderFactory 创建）
    "amazingdata_config": [],
    # 业务层 - 依赖基础设施
    "analytics": ["database"],
    "gateway": ["event_engine", "message_bus"],
    "qmt_gateway": ["event_engine", "message_bus"],
    "backtest": ["event_engine", "message_bus"],
    # 界面层 - 可选依赖业务层
    "webui": [],
}


def get_initialization_order() -> list[str]:
    """
    获取组件初始化顺序（拓扑排序）

    Returns:
        按依赖顺序排列的组件名称列表
    """
    from collections import deque

    # Kahn's algorithm for topological sort
    in_degree = {name: 0 for name in COMPONENT_DEPENDENCIES}
    graph: dict[str, list[str]] = {name: [] for name in COMPONENT_DEPENDENCIES}

    # 构建反向依赖图
    for name, deps in COMPONENT_DEPENDENCIES.items():
        for dep in deps:
            if dep in graph:
                graph[dep].append(name)
                in_degree[name] += 1

    # 找出入度为 0 的节点
    queue = deque([name for name, degree in in_degree.items() if degree == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)

        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result


def get_dependency_graph() -> dict[str, list[str]]:
    """
    获取组件依赖图

    Returns:
        组件名称到其依赖列表的映射
    """
    return COMPONENT_DEPENDENCIES.copy()


def create_application_container(mode: str = "all") -> ApplicationContainer:
    """
    创建应用容器

    Args:
        mode: 运行模式 (all, engine, webui)

    Returns:
        配置好的 ApplicationContainer
    """
    container = ApplicationContainer()

    # 记录初始化顺序供调试
    init_order = get_initialization_order()
    logger.debug(f"Component initialization order: {init_order}")

    logger.info(f"ApplicationContainer created with mode: {mode}")
    return container


def get_all_components(container: ApplicationContainer, mode: str = "all") -> Dict[str, Any]:
    """
    从容器获取所有组件实例

    Args:
        container: 应用容器
        mode: 运行模式

    Returns:
        组件名称到实例的映射
    """
    import time

    components: Dict[str, Any] = {}
    load_times: Dict[str, float] = {}

    def _load_component(name: str, provider_func) -> None:
        """加载单个组件并记录时间"""
        start = time.perf_counter()
        try:
            components[name] = provider_func()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            load_times[name] = elapsed
            if elapsed > 100:  # 超过 100ms 记录警告
                logger.warning(f"Component '{name}' loaded slowly: {elapsed:.1f}ms")
        except Exception as e:
            logger.error(f"Failed to load component '{name}': {e}")

    # 基础设施组件（始终加载）
    _load_component("event_engine", container.event_engine)
    _load_component("message_bus", container.message_bus)
    _load_component("database", container.database)
    _load_component("cache", container.cache)

    # 业务组件（engine 或 all 模式）
    if mode in ["all", "engine"]:
        _load_component("analytics", container.analytics)
        _load_component("gateway", container.gateway)
        _load_component("qmt_gateway", container.qmt_gateway)
        _load_component("backtest", container.backtest)

    # 界面组件（webui 或 all 模式）
    if mode in ["all", "webui"]:
        _load_component("webui", container.webui)

    # 汇总加载统计
    total_time = sum(load_times.values())
    logger.info(
        f"Loaded {len(components)} components in {total_time:.1f}ms "
        f"(avg: {total_time/len(components):.1f}ms)"
    )

    # 存储加载时间供调试
    container._load_times = load_times  # type: ignore

    return components


def setup_component_dependencies(
    container: ApplicationContainer, components: Dict[str, Any]
) -> None:
    """
    设置组件间依赖（用于需要后期注入的组件）

    Args:
        container: 应用容器
        components: 组件映射
    """
    # 设置分析组件的数据库依赖
    analytics = components.get("analytics")
    database = components.get("database")
    if analytics and database and hasattr(analytics, "set_database_component"):
        analytics.set_database_component(database)
        logger.debug("Analytics database dependency set")

    # 设置 QMT 网关依赖
    qmt_gateway = components.get("qmt_gateway")
    event_engine = components.get("event_engine")
    message_bus = components.get("message_bus")
    if qmt_gateway and hasattr(qmt_gateway, "set_dependencies"):
        ee_instance = (
            event_engine._instance if event_engine and hasattr(event_engine, "_instance") else None
        )
        mb_instance = (
            message_bus._instance if message_bus and hasattr(message_bus, "_instance") else None
        )
        if ee_instance and mb_instance:
            qmt_gateway.set_dependencies(ee_instance, mb_instance)
            logger.debug("QMT gateway dependencies set")
