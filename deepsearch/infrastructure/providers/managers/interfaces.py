"""
数据源管理器接口定义

本模块定义了数据源管理器的核心接口和协议，
用于确保不同实现之间的一致性和可替换性。

设计原则：
- 使用 Protocol 而非 ABC 以支持结构化子类型
- 接口专注于行为定义，不包含实现
- 支持异步操作
"""

from abc import ABC, abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)

from deepsearch.ports.data_sources import DataAccessType, DataSourceType

# 类型变量定义
T = TypeVar("T")
ProviderT = TypeVar("ProviderT")


@runtime_checkable
class IDataSource(Protocol):
    """数据源提供者协议

    定义所有数据源提供者必须实现的接口。
    使用 Protocol 以支持 duck typing 和结构化子类型。

    Attributes:
        config: 数据源配置对象

    Example:
        >>> class MyProvider:
        ...     def __init__(self):
        ...         self.config = MyConfig()
        ...     async def initialize(self) -> None: ...
        ...     async def close(self) -> None: ...
        ...     def is_healthy(self) -> bool: return True
        >>> isinstance(MyProvider(), IDataSource)
        True
    """

    config: Any

    async def initialize(self) -> None:
        """初始化数据源连接"""
        ...

    async def close(self) -> None:
        """关闭数据源连接"""
        ...

    def is_healthy(self) -> bool:
        """检查数据源是否健康"""
        ...


@runtime_checkable
class IDataSourceManager(Protocol):
    """数据源管理器协议

    定义数据源管理器的核心接口。
    所有管理器实现（包括使用混入的组合类）都应符合此协议。
    """

    @property
    def initialized(self) -> bool:
        """是否已初始化"""
        ...

    @property
    def providers(self) -> Dict[DataSourceType, Any]:
        """已注册的数据提供者"""
        ...

    async def initialize(self) -> None:
        """初始化管理器及所有数据提供者"""
        ...

    async def get_data(
        self,
        data_type: str,
        symbol: str,
        preferred_source: Optional[DataSourceType] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """统一的数据获取接口

        Args:
            data_type: 数据类型 (realtime_quote, orderbook, kline等)
            symbol: 股票代码
            preferred_source: 首选数据源
            **kwargs: 其他参数

        Returns:
            数据字典，包含source字段标识来源；失败返回None
        """
        ...

    def get_available_sources(self) -> List[DataSourceType]:
        """获取所有可用的数据源

        Returns:
            可用数据源类型列表
        """
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """获取管理器统计信息

        Returns:
            包含提供者数量、状态等信息的字典
        """
        ...


class ISelectionStrategy(ABC):
    """数据源选择策略接口

    使用策略模式，允许替换数据源选择算法。
    不同的策略可以实现不同的选择逻辑：
    - 基于优先级
    - 基于响应时间
    - 基于负载均衡
    - 基于地理位置

    Example:
        >>> class RoundRobinStrategy(ISelectionStrategy):
        ...     def select(self, available_sources, **kwargs):
        ...         # 轮询选择
        ...         return available_sources
    """

    @abstractmethod
    def select(
        self,
        available_sources: List[DataSourceType],
        preferred_source: Optional[DataSourceType] = None,
        access_type: Optional[DataAccessType] = None,
        module: Optional[str] = None,
    ) -> List[DataSourceType]:
        """选择数据源顺序

        Args:
            available_sources: 当前可用的数据源列表
            preferred_source: 用户指定的首选数据源
            access_type: 数据访问类型（如实时行情、历史K线等）
            module: 调用模块名称（用于模块级覆盖）

        Returns:
            按优先级排序的数据源列表
        """
        pass


class PrioritySelectionStrategy(ISelectionStrategy):
    """基于优先级的选择策略（默认策略）

    按照配置的优先级顺序选择数据源。
    数字越小优先级越高。

    Attributes:
        _priorities: 数据源类型到优先级的映射
        _module_overrides: 模块级优先级覆盖
        _access_type_overrides: 访问类型级优先级覆盖

    Example:
        >>> strategy = PrioritySelectionStrategy({
        ...     DataSourceType.AMAZINGDATA: 1,
        ...     DataSourceType.AKSHARE: 2,
        ... })
        >>> strategy.select([DataSourceType.AKSHARE, DataSourceType.AMAZINGDATA])
        [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]
    """

    def __init__(
        self,
        priorities: Dict[DataSourceType, int],
        module_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        access_type_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """初始化策略

        Args:
            priorities: 数据源优先级映射
            module_overrides: 模块级覆盖配置
            access_type_overrides: 访问类型级覆盖配置
        """
        self._priorities = priorities
        self._module_overrides = module_overrides or {}
        self._access_type_overrides = access_type_overrides or {}

    def select(
        self,
        available_sources: List[DataSourceType],
        preferred_source: Optional[DataSourceType] = None,
        access_type: Optional[DataAccessType] = None,
        module: Optional[str] = None,
    ) -> List[DataSourceType]:
        """选择数据源顺序"""
        result: List[DataSourceType] = []
        remaining = list(available_sources)

        # 1. 检查模块级覆盖
        if module and module in self._module_overrides:
            override = self._module_overrides[module]
            primary = self._resolve_source_type(override.get("primary"))
            if primary and primary in remaining:
                result.append(primary)
                remaining.remove(primary)
            # 添加模块配置的 fallback
            for fb in override.get("fallback", []):
                fb_type = self._resolve_source_type(fb)
                if fb_type and fb_type in remaining:
                    result.append(fb_type)
                    remaining.remove(fb_type)

        # 2. 检查访问类型级覆盖
        if access_type and access_type.value in self._access_type_overrides:
            override = self._access_type_overrides[access_type.value]
            primary = self._resolve_source_type(override.get("primary"))
            if primary and primary in remaining:
                result.append(primary)
                remaining.remove(primary)

        # 3. 用户指定的首选源
        if preferred_source and preferred_source in remaining:
            result.append(preferred_source)
            remaining.remove(preferred_source)

        # 4. 按优先级排序剩余数据源
        sorted_remaining = sorted(remaining, key=lambda x: self._priorities.get(x, 999))
        result.extend(sorted_remaining)

        return result

    def _resolve_source_type(self, value: Any) -> Optional[DataSourceType]:
        """解析数据源类型"""
        if value is None:
            return None
        if isinstance(value, DataSourceType):
            return value
        if isinstance(value, str):
            try:
                return DataSourceType(value.upper())
            except ValueError:
                # 尝试按名称匹配
                for st in DataSourceType:
                    if st.value.upper() == value.upper() or st.name.upper() == value.upper():
                        return st
        return None


# 类型别名
ProviderFactory = Callable[..., Awaitable[Optional[IDataSource]]]
"""提供者工厂函数类型"""

SelectionStrategyType = Union[ISelectionStrategy, PrioritySelectionStrategy]
"""选择策略类型"""

__all__ = [
    "IDataSource",
    "IDataSourceManager",
    "ISelectionStrategy",
    "PrioritySelectionStrategy",
    "ProviderFactory",
    "SelectionStrategyType",
]
