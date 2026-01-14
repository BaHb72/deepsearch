# 数据源 Provider 架构重构设计文档

> 版本：v2.0
> 日期：2026-01-14
> 状态：设计阶段
> 方法论：第一性原理思维

---

## 一、问题定义

### 1.1 本质问题

**缺乏统一的 Provider 生命周期管理和依赖注入机制**，导致：

- 接口碎片化（三代架构共存）
- God Method（380行复杂工厂）
- 全局单例状态（测试困难）
- 手动资源管理（不可靠）

### 1.2 表面症状

```
症状链：
接口碎片化 ← 渐进式迁移策略
    ↓
God Method ← 没有 Factory Pattern
    ↓
全局状态 ← 没有 IoC 容器
    ↓
手动资源管理 ← 没有统一生命周期
```

---

## 二、目标架构

### 2.1 架构原则

1. **单一职责**：每个类只负责一件事
2. **依赖倒置**：依赖抽象（Protocol）而非具体实现
3. **开放封闭**：对扩展开放，对修改封闭
4. **接口隔离**：不同能力独立定义
5. **依赖注入**：通过构造函数/参数传递依赖

### 2.2 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│ Application Layer（应用层）                                    │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ UnifiedDataFeed                                       │   │
│ │ - 统一数据查询入口                                       │   │
│ │ - 路由到具体 Provider                                   │   │
│ └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ 调用
┌─────────────────────────────────────────────────────────────┐
│ Domain Layer（领域层 - Protocol 接口）                        │
│ ┌───────────────┬───────────────┬────────────────────────┐ │
│ │ILifecycleProvider│IKlineProvider│IRealtimeProvider      │ │
│ │- initialize()    │- query_kline()│- query_realtime()   │ │
│ │- start()         │               │                       │ │
│ │- stop()          │               │                       │ │
│ │- health_check()  │               │                       │ │
│ └───────────────┴───────────────┴────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓ 实现
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer（基础设施层 - Provider 实现）              │
│ ┌──────────────────┬─────────────────┬─────────────────┐   │
│ │AmazingDataProvider│MiniQMTProvider  │AkShareProvider  │   │
│ │- 实现 ILifecycle  │- 实现 ILifecycle│- 实现 ILifecycle│   │
│ │- 实现 IKline      │- 实现 IKline    │- 实现 IKline    │   │
│ │- 实现 IRealtime   │- 实现 IRealtime │                 │   │
│ └──────────────────┴─────────────────┴─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ 管理
┌─────────────────────────────────────────────────────────────┐
│ Container Layer（容器层 - 生命周期管理）                        │
│ ┌──────────────┬──────────────────┬────────────────────┐   │
│ │ProviderFactory│ProviderContainer │LifecycleManager    │   │
│ │- 创建实例      │- 持有实例         │- 启动/停止          │   │
│ │- 验证配置      │- 依赖注入         │- 健康检查          │   │
│ └──────────────┴──────────────────┴────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件设计

### 3.1 Protocol 接口层

#### 3.1.1 生命周期协议

```python
# packages/core/infrastructure/providers/protocols/lifecycle.py

from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] | None = None
    timestamp: float = 0.0


@runtime_checkable
class ILifecycleProvider(Protocol):
    """Provider 生命周期协议

    所有 Provider 必须实现此接口以支持统一的生命周期管理。
    """

    async def initialize(self) -> None:
        """初始化 Provider

        - 加载配置
        - 建立连接（如果需要）
        - 预热缓存

        Raises:
            ProviderInitializationError: 初始化失败
        """
        ...

    async def start(self) -> None:
        """启动 Provider

        - 启动后台任务（如心跳、订阅）
        - 开始接受请求
        """
        ...

    async def stop(self) -> None:
        """停止 Provider

        - 停止后台任务
        - 关闭连接
        - 清理资源

        Note:
            应该是幂等的，可以多次调用
        """
        ...

    async def health_check(self) -> HealthCheckResult:
        """健康检查

        Returns:
            HealthCheckResult: 健康状态
        """
        ...
```

#### 3.1.2 数据能力协议

```python
# packages/core/infrastructure/providers/protocols/capabilities.py

from typing import Protocol, runtime_checkable
from core.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    TickRequest,
    StockListRequest,
)
from core.ports.data.responses import (
    KlineResponse,
    RealtimeQuoteResponse,
    TickResponse,
    StockListResponse,
)


@runtime_checkable
class IKlineProvider(Protocol):
    """K线数据能力"""

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        Args:
            request: K线请求参数

        Returns:
            KlineResponse: K线响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class IRealtimeProvider(Protocol):
    """实时行情能力"""

    async def query_realtime(
        self,
        request: RealtimeQuoteRequest
    ) -> RealtimeQuoteResponse:
        """查询实时行情"""
        ...


@runtime_checkable
class ITickProvider(Protocol):
    """Tick数据能力"""

    async def query_tick(self, request: TickRequest) -> TickResponse:
        """查询Tick数据"""
        ...


@runtime_checkable
class IStockListProvider(Protocol):
    """股票列表能力"""

    async def query_stock_list(
        self,
        request: StockListRequest
    ) -> StockListResponse:
        """查询股票列表"""
        ...
```

### 3.2 Factory 模式

#### 3.2.1 Factory 基类

```python
# packages/core/infrastructure/providers/factory/base.py

from typing import Protocol, Any
from abc import abstractmethod


class ProviderFactoryStrategy(Protocol):
    """Provider 工厂策略接口

    每个数据源实现自己的工厂类，负责：
    1. 验证配置
    2. 创建 Provider 实例
    3. 处理特定数据源的初始化逻辑
    """

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        """验证配置

        Args:
            config: 原始配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        ...

    @abstractmethod
    def create(self, config: dict[str, Any]) -> Any:
        """创建 Provider 实例

        Args:
            config: 已验证的配置

        Returns:
            Provider 实例

        Raises:
            ProviderCreationError: 创建失败
        """
        ...
```

#### 3.2.2 具体工厂实现

```python
# packages/core/infrastructure/providers/factory/amazingdata_factory.py

from typing import Any
from loguru import logger
from .base import ProviderFactoryStrategy
from ..implementations.amazingdata.amazingdata_optimized import (
    OptimizedAmazingDataProvider,
    AmazingDataConfig,
)
from ..exceptions import ConfigValidationError, ProviderCreationError


class AmazingDataFactory(ProviderFactoryStrategy):
    """AmazingData Provider 工厂

    负责创建和配置 AmazingDataProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 AmazingData 配置"""
        try:
            # 使用 Pydantic 验证
            AmazingDataConfig.model_validate(config)
        except Exception as e:
            raise ConfigValidationError(
                provider="amazingdata",
                message=f"配置验证失败: {e}"
            ) from e

    def create(self, config: dict[str, Any]) -> OptimizedAmazingDataProvider:
        """创建 AmazingData Provider"""
        try:
            # 1. 验证配置
            self.validate_config(config)

            # 2. 解析配置（使用 Pydantic）
            validated_config = AmazingDataConfig.model_validate(config)

            # 3. 创建实例
            provider = OptimizedAmazingDataProvider(validated_config)

            logger.info(
                "AmazingData Provider 创建成功",
                extra={
                    "host": validated_config.host,
                    "port": validated_config.port,
                    "username": validated_config.username[:3] + "***",
                }
            )

            return provider

        except Exception as e:
            raise ProviderCreationError(
                provider="amazingdata",
                message=f"创建失败: {e}"
            ) from e
```

```python
# packages/core/infrastructure/providers/factory/provider_factory.py

from typing import Any
from loguru import logger
from .base import ProviderFactoryStrategy
from .amazingdata_factory import AmazingDataFactory
from .miniqmt_factory import MiniQMTFactory
from .akshare_factory import AkShareFactory
from ..exceptions import UnknownProviderError


class ProviderFactory:
    """统一 Provider 工厂

    使用策略模式，将具体创建逻辑委托给各个数据源的专属工厂。
    """

    def __init__(self):
        self._strategies: dict[str, ProviderFactoryStrategy] = {
            "amazingdata": AmazingDataFactory(),
            "miniqmt": MiniQMTFactory(),
            "akshare": AkShareFactory(),
        }

    def create(self, name: str, config: dict[str, Any]) -> Any:
        """创建 Provider 实例

        Args:
            name: Provider 名称
            config: 配置字典

        Returns:
            Provider 实例

        Raises:
            UnknownProviderError: 未知的 Provider
            ConfigValidationError: 配置验证失败
            ProviderCreationError: 创建失败
        """
        strategy = self._strategies.get(name)
        if strategy is None:
            raise UnknownProviderError(
                provider=name,
                available=list(self._strategies.keys())
            )

        logger.debug(f"使用 {strategy.__class__.__name__} 创建 Provider")
        return strategy.create(config)

    def register(self, name: str, factory: ProviderFactoryStrategy) -> None:
        """注册新的 Provider 工厂

        Args:
            name: Provider 名称
            factory: 工厂实例
        """
        self._strategies[name] = factory
        logger.info(f"注册 Provider 工厂: {name}")
```

### 3.3 生命周期管理器

```python
# packages/core/infrastructure/providers/lifecycle/manager.py

from typing import Any, Sequence
import asyncio
from loguru import logger
from ..protocols.lifecycle import ILifecycleProvider, HealthStatus


class ProviderLifecycleManager:
    """Provider 生命周期管理器

    统一管理所有 Provider 的启动、停止和健康检查。
    """

    def __init__(self, *, shutdown_timeout: float = 10.0):
        self.shutdown_timeout = shutdown_timeout

    async def initialize(self, provider: Any) -> None:
        """初始化 Provider

        Args:
            provider: Provider 实例
        """
        if not isinstance(provider, ILifecycleProvider):
            logger.warning(
                f"Provider {provider.__class__.__name__} "
                "未实现 ILifecycleProvider 协议，跳过初始化"
            )
            return

        try:
            logger.info(f"初始化 Provider: {provider.__class__.__name__}")
            await provider.initialize()
            logger.info(f"Provider 初始化成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(
                f"Provider 初始化失败: {provider.__class__.__name__}",
                exc_info=e
            )
            raise

    async def start(self, provider: Any) -> None:
        """启动 Provider"""
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"启动 Provider: {provider.__class__.__name__}")
            await provider.start()
            logger.info(f"Provider 启动成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(
                f"Provider 启动失败: {provider.__class__.__name__}",
                exc_info=e
            )
            raise

    async def stop(self, provider: Any) -> None:
        """停止 Provider（带超时保护）"""
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"停止 Provider: {provider.__class__.__name__}")
            await asyncio.wait_for(
                provider.stop(),
                timeout=self.shutdown_timeout
            )
            logger.info(f"Provider 停止成功: {provider.__class__.__name__}")
        except asyncio.TimeoutError:
            logger.warning(
                f"Provider 停止超时（{self.shutdown_timeout}s）: "
                f"{provider.__class__.__name__}"
            )
        except Exception as e:
            logger.error(
                f"Provider 停止失败: {provider.__class__.__name__}",
                exc_info=e
            )

    async def shutdown_all(self, providers: Sequence[Any]) -> None:
        """批量停止所有 Provider

        Args:
            providers: Provider 列表
        """
        logger.info(f"开始停止 {len(providers)} 个 Provider...")

        # 并发停止，收集异常
        tasks = [self.stop(p) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            logger.warning(f"停止 Provider 时发生 {len(errors)} 个错误")
            for error in errors:
                logger.error(f"  - {error}")

        logger.info("所有 Provider 已停止")

    async def health_check(self, provider: Any) -> HealthStatus:
        """检查 Provider 健康状态

        Returns:
            HealthStatus: 健康状态枚举
        """
        if not isinstance(provider, ILifecycleProvider):
            return HealthStatus.UNKNOWN

        try:
            result = await asyncio.wait_for(
                provider.health_check(),
                timeout=5.0
            )
            return result.status
        except asyncio.TimeoutError:
            logger.warning(
                f"Provider 健康检查超时: {provider.__class__.__name__}"
            )
            return HealthStatus.UNHEALTHY
        except Exception as e:
            logger.error(
                f"Provider 健康检查失败: {provider.__class__.__name__}",
                exc_info=e
            )
            return HealthStatus.UNHEALTHY
```

### 3.4 IoC 容器

```python
# packages/core/infrastructure/providers/container.py

from typing import Any
from loguru import logger
from .factory.provider_factory import ProviderFactory
from .lifecycle.manager import ProviderLifecycleManager
from .exceptions import ProviderNotFoundError


class ProviderContainer:
    """Provider 容器

    职责：
    1. 管理 Provider 实例（单例模式，但不是全局单例）
    2. 协调 Factory 和 LifecycleManager
    3. 提供依赖注入接口

    Note:
        此类不是全局单例，每个应用实例有自己的容器。
        测试时可以创建独立的容器实例。
    """

    def __init__(
        self,
        *,
        factory: ProviderFactory | None = None,
        lifecycle_manager: ProviderLifecycleManager | None = None,
    ):
        self._factory = factory or ProviderFactory()
        self._lifecycle = lifecycle_manager or ProviderLifecycleManager()
        self._instances: dict[str, Any] = {}
        self._initialized: set[str] = set()

    async def get_provider(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        *,
        force_new: bool = False,
    ) -> Any:
        """获取 Provider 实例

        Args:
            name: Provider 名称
            config: 配置（首次获取时必须提供）
            force_new: 是否强制创建新实例

        Returns:
            Provider 实例

        Raises:
            ProviderNotFoundError: Provider 不存在
            ConfigValidationError: 配置验证失败
        """
        # 如果已存在且不强制创建，直接返回
        if not force_new and name in self._instances:
            return self._instances[name]

        # 创建新实例
        if config is None:
            raise ProviderNotFoundError(
                provider=name,
                message="首次获取 Provider 必须提供配置"
            )

        logger.info(f"创建 Provider: {name}")
        provider = self._factory.create(name, config)

        # 初始化
        await self._lifecycle.initialize(provider)
        await self._lifecycle.start(provider)

        # 缓存
        self._instances[name] = provider
        self._initialized.add(name)

        return provider

    async def shutdown(self) -> None:
        """关闭所有 Provider"""
        logger.info("开始关闭 ProviderContainer...")
        await self._lifecycle.shutdown_all(list(self._instances.values()))
        self._instances.clear()
        self._initialized.clear()
        logger.info("ProviderContainer 已关闭")

    def list_providers(self) -> list[str]:
        """列出所有已加载的 Provider"""
        return list(self._instances.keys())
```

### 3.5 FastAPI 集成

```python
# packages/core/infrastructure/providers/integration/fastapi.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from loguru import logger
from ..container import ProviderContainer
from core.config import get_config


@asynccontextmanager
async def provider_lifespan(app: FastAPI):
    """Provider 容器生命周期管理

    在 FastAPI 应用启动时创建容器，关闭时清理。

    Usage:
        app = FastAPI(lifespan=provider_lifespan)
    """
    # 启动
    logger.info("初始化 ProviderContainer...")
    container = ProviderContainer()
    app.state.provider_container = container

    # 预加载配置中的 Provider
    config = get_config()
    if hasattr(config, "data_sources"):
        for name, ds_config in config.data_sources.items():
            if ds_config.get("enabled", False):
                try:
                    await container.get_provider(name, ds_config)
                    logger.info(f"预加载 Provider 成功: {name}")
                except Exception as e:
                    logger.warning(f"预加载 Provider 失败: {name} - {e}")

    logger.info("ProviderContainer 初始化完成")

    yield  # 应用运行中

    # 关闭
    logger.info("关闭 ProviderContainer...")
    await container.shutdown()
    logger.info("ProviderContainer 已关闭")


def get_provider_container(request: Request) -> ProviderContainer:
    """FastAPI 依赖注入函数

    Usage:
        @router.get("/data")
        async def get_data(
            container: ProviderContainer = Depends(get_provider_container)
        ):
            provider = await container.get_provider("amazingdata")
            ...
    """
    return request.app.state.provider_container
```

---

## 四、Provider 实现示例

### 4.1 AmazingDataProvider 重构

```python
# packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_refactored.py

from typing import Any
import asyncio
from loguru import logger
from ...protocols.lifecycle import (
    ILifecycleProvider,
    HealthCheckResult,
    HealthStatus
)
from ...protocols.capabilities import IKlineProvider, IRealtimeProvider
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineResponse, RealtimeQuoteResponse


class AmazingDataProvider:
    """AmazingData 数据提供者（重构版）

    直接实现 Protocol 接口，不继承任何 ABC。

    实现的协议：
    - ILifecycleProvider: 生命周期管理
    - IKlineProvider: K线数据
    - IRealtimeProvider: 实时行情
    """

    def __init__(self, config: AmazingDataConfig):
        self.config = config
        self._sdk: Any = None
        self._connection_manager: ConnectionManager | None = None
        self._query_manager: QueryManager | None = None
        self._subscription_manager: SubscriptionManager | None = None
        self._is_initialized = False
        self._is_started = False

    # ============ ILifecycleProvider 实现 ============

    async def initialize(self) -> None:
        """初始化 Provider"""
        if self._is_initialized:
            logger.warning("AmazingDataProvider 已初始化，跳过")
            return

        logger.info("初始化 AmazingDataProvider...")

        try:
            # 1. 加载 SDK
            self._sdk = await self._load_sdk()

            # 2. 创建管理器
            self._connection_manager = ConnectionManager(self._sdk, self.config)
            self._query_manager = QueryManager(self._sdk)
            self._subscription_manager = SubscriptionManager(self._sdk)

            # 3. 建立连接
            await self._connection_manager.connect()

            self._is_initialized = True
            logger.info("AmazingDataProvider 初始化成功")

        except Exception as e:
            logger.error(f"AmazingDataProvider 初始化失败: {e}")
            raise ProviderInitializationError(
                provider="amazingdata",
                message=str(e)
            ) from e

    async def start(self) -> None:
        """启动 Provider"""
        if not self._is_initialized:
            raise ProviderStateError("Provider 未初始化")

        if self._is_started:
            logger.warning("AmazingDataProvider 已启动，跳过")
            return

        logger.info("启动 AmazingDataProvider...")

        # 启动订阅管理器（如果启用）
        if self.config.subscription_enabled:
            await self._subscription_manager.start()

        self._is_started = True
        logger.info("AmazingDataProvider 启动成功")

    async def stop(self) -> None:
        """停止 Provider"""
        if not self._is_started:
            return

        logger.info("停止 AmazingDataProvider...")

        try:
            # 1. 停止订阅
            if self._subscription_manager:
                await self._subscription_manager.stop()

            # 2. 断开连接
            if self._connection_manager:
                await self._connection_manager.disconnect()

            self._is_started = False
            logger.info("AmazingDataProvider 停止成功")

        except Exception as e:
            logger.error(f"AmazingDataProvider 停止失败: {e}")
            raise

    async def health_check(self) -> HealthCheckResult:
        """健康检查"""
        if not self._is_initialized:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="Provider 未初始化"
            )

        if not self._connection_manager:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="连接管理器未创建"
            )

        # 检查连接状态
        is_connected = await self._connection_manager.is_connected()

        if not is_connected:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="SDK 连接断开"
            )

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="运行正常",
            details={
                "initialized": self._is_initialized,
                "started": self._is_started,
                "connected": is_connected,
            }
        )

    # ============ IKlineProvider 实现 ============

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据"""
        if not self._is_initialized:
            raise ProviderStateError("Provider 未初始化")

        try:
            data = await self._query_manager.fetch_kline(
                symbol=request.asset,
                period=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
            )

            return KlineResponse(
                success=True,
                data=data,
                metadata={
                    "source": "amazingdata",
                    "symbol": request.asset,
                }
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            return KlineResponse(
                success=False,
                error=str(e)
            )

    # ============ IRealtimeProvider 实现 ============

    async def query_realtime(
        self,
        request: RealtimeQuoteRequest
    ) -> RealtimeQuoteResponse:
        """查询实时行情"""
        if not self._is_initialized:
            raise ProviderStateError("Provider 未初始化")

        try:
            data = await self._query_manager.fetch_realtime(
                symbols=request.symbols
            )

            return RealtimeQuoteResponse(
                success=True,
                data=data,
                metadata={
                    "source": "amazingdata",
                    "count": len(data) if data else 0,
                }
            )

        except Exception as e:
            logger.error(f"查询实时行情失败: {e}")
            return RealtimeQuoteResponse(
                success=False,
                error=str(e)
            )

    # ============ Context Manager 支持 ============

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        await self.start()
        return self

    async def __aexit__(self, *args):
        """异步上下文管理器出口"""
        await self.stop()
```

---

## 五、实施计划

### 5.1 Week 1: 基础设施层

#### Day 1-2: Protocol 接口定义

**任务**：

1. 创建 `packages/core/infrastructure/providers/protocols/`
2. 实现 `lifecycle.py` (ILifecycleProvider, HealthStatus, HealthCheckResult)
3. 实现 `capabilities.py` (IKlineProvider, IRealtimeProvider, ...)
4. 编写单元测试 `tests/unit/providers/protocols/test_protocols.py`

**验收标准**：

- [ ] 所有 Protocol 都是 `@runtime_checkable`
- [ ] 测试覆盖率 > 90%
- [ ] 文档注释完整（参数、返回值、异常）

#### Day 3-4: Factory 模式实现

**任务**：

1. 创建 `packages/core/infrastructure/providers/factory/`
2. 实现 `base.py` (ProviderFactoryStrategy)
3. 实现 `amazingdata_factory.py`
4. 实现 `miniqmt_factory.py`
5. 实现 `akshare_factory.py`
6. 实现 `provider_factory.py` (统一入口)
7. 编写单元测试 `tests/unit/providers/factory/test_factories.py`

**验收标准**：

- [ ] 每个工厂类 < 100行
- [ ] 配置验证使用 Pydantic
- [ ] 测试覆盖率 > 95%
- [ ] 可以独立测试（不依赖真实 SDK）

#### Day 5: 生命周期管理器

**任务**：

1. 创建 `packages/core/infrastructure/providers/lifecycle/`
2. 实现 `manager.py` (ProviderLifecycleManager)
3. 实现 `monitor.py` (HealthMonitor，可选）
4. 编写单元测试 `tests/unit/providers/lifecycle/test_manager.py`

**验收标准**：

- [ ] 支持批量停止（并发执行）
- [ ] 有超时保护（默认10秒）
- [ ] 异常不会中断其他 Provider 的停止
- [ ] 测试覆盖率 > 90%

### 5.2 Week 2: Provider 迁移

#### Day 1-2: 迁移 AmazingDataProvider

**任务**：

1. 重构 `amazingdata_optimized.py`
2. 删除 `DataProvider` 继承
3. 实现 `ILifecycleProvider`
4. 实现 `IKlineProvider`
5. 实现 `IRealtimeProvider`
6. 删除 `adapters/amazingdata.py`
7. 更新测试

**验收标准**：

- [ ] 不继承任何 ABC
- [ ] 实现所有 Protocol 方法
- [ ] 支持 async context manager
- [ ] 所有原有测试通过

#### Day 3: 迁移 MiniQMTProvider

**任务**：

1. 重构 `miniqmt.py`
2. 统一资源管理（socket, tasks）
3. 实现新 Protocol 接口
4. 删除 `adapters/miniqmt.py`
5. 更新测试

**验收标准**：

- [ ] 使用 `async with` 管理资源
- [ ] Task 取消逻辑健壮
- [ ] 所有原有测试通过

#### Day 4: 迁移 AkShareProvider

**任务**：

1. 重构 `akshare_refactored.py`
2. 添加 `ILifecycleProvider` 实现
3. 删除 `adapters/akshare.py`
4. 更新测试

**验收标准**：

- [ ] Worker 生命周期可控
- [ ] 健康检查可用
- [ ] 所有原有测试通过

#### Day 5: 容器集成

**任务**：

1. 实现 `container.py` (ProviderContainer)
2. 实现 `integration/fastapi.py` (FastAPI 集成)
3. 编写集成测试 `tests/integration/test_provider_container.py`

**验收标准**：

- [ ] 容器不是全局单例
- [ ] FastAPI lifespan 正确管理生命周期
- [ ] 依赖注入可用
- [ ] 测试可以创建独立容器

### 5.3 Week 3: 切换与清理

#### Day 1: API 层切换

**任务**：

1. 更新 `apps/api/api/providers.py`
2. 替换 `get_registry()` 为 `get_provider_container()`
3. 更新所有 API 端点
4. 运行回归测试

**验收标准**：

- [ ] 所有 API 测试通过
- [ ] 性能无回归
- [ ] 日志正常

#### Day 2: Runtime 层切换

**任务**：

1. 更新 `packages/core/core/runtime/engine.py`
2. 集成 `ProviderContainer`
3. 删除 `DataProviderRegistry` 引用
4. 运行回归测试

**验收标准**：

- [ ] 系统启动/关闭正常
- [ ] Provider 生命周期正确
- [ ] 健康检查可用

#### Day 3: 删除旧代码（Big-Bang Cleanup）

**任务**：

1. 删除 `packages/core/infrastructure/providers/registry.py` (1200行)
2. 删除 `packages/core/infrastructure/providers/interfaces/base.py`
3. 删除 `packages/core/infrastructure/providers/base/provider_base.py`
4. 删除 `packages/core/infrastructure/providers/adapters/*.py` (全部)
5. 删除 `packages/core/domain/data_proxy/adapters/*.py` (已标记删除)
6. 更新文档 `docs/development/provider_architecture.md`
7. 提交：`refactor: 数据源架构完整重构 - 删除 Registry 单例和 Adapter 层`

**验收标准**：

- [ ] 旧代码完全删除（0行残留）
- [ ] 所有测试通过
- [ ] 文档更新完成
- [ ] Git 提交信息清晰

#### Day 4-5: 生产验证

**任务**：

1. 运行完整测试套件（单元 + 集成 + 回归）
2. 性能基准测试（对比旧架构）
3. 发布到 dev 环境验证
4. 监控日志和指标

**验收标准**：

- [ ] 所有测试通过（单元 + 集成 + 回归）
- [ ] 性能无回归（延迟 < 旧架构）
- [ ] 内存使用无明显增长
- [ ] 日志无异常错误

---

## 六、风险管理

### 6.1 风险清单

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|---------|
| 切换后兼容性问题 | 高 | 中 | Week 2 编写完整集成测试 |
| 性能回归 | 中 | 低 | Week 3 Day 4 基准测试 |
| 测试遗漏 | 高 | 中 | Week 1 Day 5 建立测试检查清单 |
| 回滚困难 | 高 | 低 | 保留旧代码分支，可快速 revert |
| 文档不同步 | 低 | 中 | Week 3 Day 3 同时更新文档 |

### 6.2 回滚策略

如果在 Week 3 Day 1 切换时发现重大问题：

1. **立即止损**（2小时内）
   - `git revert` 到旧架构分支
   - 重启服务恢复

2. **立即诊断**（当天完成）
   - 分析根本原因
   - 补充测试用例

3. **立即修复**（3天内）
   - 修复新架构问题
   - 重新验证

4. **再次切换**（1周内）
   - 完整回归测试后再次部署

**绝不做的事**：在生产环境添加兼容层让新旧代码共存

---

## 七、验收标准

### 7.1 代码质量

- [ ] 删除代码 > 1500行（registry + adapters）
- [ ] 新增代码 < 600行（factory + container + lifecycle）
- [ ] 测试覆盖率 > 85%（单元测试）
- [ ] 测试覆盖率 > 70%（集成测试）
- [ ] Mypy 类型检查 0 错误
- [ ] Ruff lint 0 警告

### 7.2 性能指标

- [ ] API 延迟 <= 旧架构（p50, p95, p99）
- [ ] 内存使用 <= 旧架构 + 5%
- [ ] 启动时间 <= 旧架构 + 2秒
- [ ] 关闭时间 <= 10秒（所有 Provider）

### 7.3 功能完整性

- [ ] 所有原有功能正常工作
- [ ] 健康检查可用
- [ ] 日志完整且可读
- [ ] 错误处理健壮
- [ ] 配置向后兼容（或提供迁移脚本）

---

## 八、参考资料

### 8.1 设计模式

- **Factory Pattern**: 将对象创建逻辑封装在工厂类中
- **Strategy Pattern**: 将算法封装在独立的策略类中
- **Dependency Injection**: 通过参数传递依赖，而非全局获取
- **Protocol Pattern**: 使用结构化子类型，避免继承耦合

### 8.2 FastAPI 集成

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)

### 8.3 Python 类型系统

- [PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [typing.Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol)
- [runtime_checkable](https://docs.python.org/3/library/typing.html#typing.runtime_checkable)

---

## 附录：关键代码清单

### A.1 删除的文件

```
packages/core/infrastructure/providers/registry.py (1200行)
packages/core/infrastructure/providers/interfaces/base.py (312行)
packages/core/infrastructure/providers/base/provider_base.py (200行)
packages/core/infrastructure/providers/adapters/ (全部 500行)
  ├─ base.py
  ├─ amazingdata.py
  ├─ miniqmt.py
  └─ akshare.py
packages/core/domain/data_proxy/adapters/ (全部 300行)
  ├─ __init__.py
  ├─ akshare.py
  └─ miniqmt.py

总删除：约 2512 行
```

### A.2 新增的文件

```
packages/core/infrastructure/providers/protocols/ (300行)
  ├─ lifecycle.py (100行)
  └─ capabilities.py (200行)

packages/core/infrastructure/providers/factory/ (400行)
  ├─ base.py (50行)
  ├─ amazingdata_factory.py (100行)
  ├─ miniqmt_factory.py (100行)
  ├─ akshare_factory.py (80行)
  └─ provider_factory.py (70行)

packages/core/infrastructure/providers/lifecycle/ (200行)
  └─ manager.py (200行)

packages/core/infrastructure/providers/container.py (150行)
packages/core/infrastructure/providers/integration/fastapi.py (100行)
packages/core/infrastructure/providers/exceptions.py (100行)

总新增：约 1250 行
```

### A.3 净减少

```
删除：2512 行
新增：1250 行
净减少：1262 行 (-50%)
```

---

**文档状态**：完成
**下一步**：开始实施 Week 1 任务
