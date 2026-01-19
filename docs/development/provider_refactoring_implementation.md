# Provider 架构重构实施文档

> 版本：v1.0
> 日期：2026-01-14
> 状态：实施指南
> 依据：provider_architecture_refactoring_design.md

---

## 一、实施概览

### 1.1 目标

基于设计文档和最佳实践分析，一次性完成 Provider 架构重构：

- 创建纯 Protocol 接口层（无 ABC 混用）
- 实现 Factory 策略模式
- 实现生命周期管理器
- 实现轻量级 IoC 容器
- 集成 FastAPI lifespan

### 1.2 文件清单

#### 新增文件（约 1250 行）

```
packages/core/infrastructure/providers/
├── protocols/
│   ├── __init__.py (30行)
│   ├── lifecycle.py (120行)
│   └── capabilities.py (180行)
├── factory/
│   ├── __init__.py (30行)
│   ├── base.py (40行)
│   ├── amazingdata_factory.py (110行)
│   ├── miniqmt_factory.py (110行)
│   ├── akshare_factory.py (90行)
│   └── provider_factory.py (80行)
├── lifecycle/
│   ├── __init__.py (20行)
│   └── manager.py (220行)
├── container.py (180行)
├── integration/
│   ├── __init__.py (20行)
│   └── fastapi.py (120行)
└── exceptions.py (100行)
```

#### 修改文件

- `implementations/amazingdata/amazingdata_optimized.py` - 实现新 Protocol 接口
- `implementations/qmt/miniqmt.py` - 实现新 Protocol 接口
- `implementations/akshare/akshare_refactored.py` - 实现新 Protocol 接口

#### 待删除文件（Phase 2）

- `registry.py` (741行) - 替换为 Container
- `adapters/*.py` - 已被标记删除

---

## 二、完整代码实现

### 2.1 异常定义

#### `packages/core/infrastructure/providers/exceptions.py`

```python
"""
Provider 异常定义
"""

from typing import Any


class ProviderError(Exception):
    """Provider 基础异常"""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ConfigValidationError(ProviderError):
    """配置验证失败"""

    pass


class ProviderCreationError(ProviderError):
    """Provider 创建失败"""

    pass


class ProviderInitializationError(ProviderError):
    """Provider 初始化失败"""

    pass


class ProviderStateError(ProviderError):
    """Provider 状态错误"""

    pass


class ProviderNotFoundError(ProviderError):
    """Provider 不存在"""

    def __init__(self, provider: str, message: str = "Provider 不存在"):
        super().__init__(provider, message)


class UnknownProviderError(ProviderError):
    """未知的 Provider 类型"""

    def __init__(self, provider: str, available: list[str]):
        self.available = available
        message = f"未知的 Provider 类型，可用的类型: {', '.join(available)}"
        super().__init__(provider, message)


class ProviderDataError(ProviderError):
    """数据查询失败"""

    pass


class ProviderTimeoutError(ProviderError):
    """查询超时"""

    pass
```

### 2.2 Protocol 接口层

#### `packages/core/infrastructure/providers/protocols/__init__.py`

```python
"""
Provider 协议接口
"""

from .capabilities import IKlineProvider, IRealtimeProvider, IStockListProvider, ITickProvider
from .lifecycle import HealthCheckResult, HealthStatus, ILifecycleProvider

__all__ = [
    # Lifecycle
    "ILifecycleProvider",
    "HealthStatus",
    "HealthCheckResult",
    # Capabilities
    "IKlineProvider",
    "IRealtimeProvider",
    "ITickProvider",
    "IStockListProvider",
]
```

#### `packages/core/infrastructure/providers/protocols/lifecycle.py`

```python
"""
Provider 生命周期协议

使用纯 Protocol 实现，不混用 ABC。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


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
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        """是否健康"""
        return self.status == HealthStatus.HEALTHY

    def is_degraded(self) -> bool:
        """是否降级"""
        return self.status == HealthStatus.DEGRADED

    def is_unhealthy(self) -> bool:
        """是否不健康"""
        return self.status == HealthStatus.UNHEALTHY


@runtime_checkable
class ILifecycleProvider(Protocol):
    """Provider 生命周期协议

    所有 Provider 必须实现此接口以支持统一的生命周期管理。

    注意：这是纯 Protocol，不使用 @abstractmethod 装饰器。
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

#### `packages/core/infrastructure/providers/protocols/capabilities.py`

```python
"""
Provider 数据能力协议

定义各种数据查询能力接口。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# 导入现有的 Request/Response 类型
from core.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from core.ports.data.responses import (
    KlineResponse,
    RealtimeQuoteResponse,
    StockListResponse,
    TickResponse,
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

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情

        Args:
            request: 实时行情请求参数

        Returns:
            RealtimeQuoteResponse: 实时行情响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class ITickProvider(Protocol):
    """Tick数据能力"""

    async def query_tick(self, request: TickRequest) -> TickResponse:
        """查询Tick数据

        Args:
            request: Tick请求参数

        Returns:
            TickResponse: Tick响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class IStockListProvider(Protocol):
    """股票列表能力"""

    async def query_stock_list(self, request: StockListRequest) -> StockListResponse:
        """查询股票列表

        Args:
            request: 股票列表请求参数

        Returns:
            StockListResponse: 股票列表响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...
```

### 2.3 Factory 层

#### `packages/core/infrastructure/providers/factory/__init__.py`

```python
"""
Provider 工厂
"""

from .base import ProviderFactoryStrategy
from .provider_factory import ProviderFactory

__all__ = [
    "ProviderFactoryStrategy",
    "ProviderFactory",
]
```

#### `packages/core/infrastructure/providers/factory/base.py`

```python
"""
Provider 工厂基础接口

使用纯 Protocol，不混用 @abstractmethod。
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProviderFactoryStrategy(Protocol):
    """Provider 工厂策略接口

    每个数据源实现自己的工厂类，负责：
    1. 验证配置
    2. 创建 Provider 实例
    3. 处理特定数据源的初始化逻辑

    注意：这是纯 Protocol，不使用 @abstractmethod。
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证配置

        Args:
            config: 原始配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        ...

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

#### `packages/core/infrastructure/providers/factory/amazingdata_factory.py`

```python
"""
AmazingData Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from ..implementations.amazingdata.amazingdata_optimized import (
    OptimizedAmazingDataProvider,
)
from ..implementations.amazingdata.config import AmazingDataConfig
from .base import ProviderFactoryStrategy


class AmazingDataFactory:
    """AmazingData Provider 工厂

    负责创建和配置 AmazingDataProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 AmazingData 配置"""
        try:
            # 使用 Pydantic 验证
            AmazingDataConfig.model_validate(config)
        except Exception as e:
            raise ConfigValidationError(provider="amazingdata", message=f"配置验证失败: {e}") from e

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
                    "username": validated_config.username[:3] + "***" if validated_config.username else "N/A",
                },
            )

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="amazingdata", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":
    import inspect

    factory = AmazingDataFactory()
    assert isinstance(factory, ProviderFactoryStrategy), "AmazingDataFactory 必须实现 ProviderFactoryStrategy 协议"
```

#### `packages/core/infrastructure/providers/factory/miniqmt_factory.py`

```python
"""
MiniQMT Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from .base import ProviderFactoryStrategy


class MiniQMTFactory:
    """MiniQMT Provider 工厂

    负责创建和配置 MiniQMTProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 MiniQMT 配置"""
        try:
            # 基础验证
            required_fields = []  # MiniQMT 配置较简单，可能无必需字段
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"缺少必需字段: {field}")

        except Exception as e:
            raise ConfigValidationError(provider="miniqmt", message=f"配置验证失败: {e}") from e

    def create(self, config: dict[str, Any]) -> Any:
        """创建 MiniQMT Provider"""
        try:
            # 1. 验证配置
            self.validate_config(config)

            # 2. 动态导入（避免循环依赖）
            from ..implementations.qmt.miniqmt import MiniQMTProvider

            # 3. 创建实例
            provider = MiniQMTProvider(config)

            logger.info("MiniQMT Provider 创建成功")

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="miniqmt", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":
    factory = MiniQMTFactory()
    assert isinstance(factory, ProviderFactoryStrategy), "MiniQMTFactory 必须实现 ProviderFactoryStrategy 协议"
```

#### `packages/core/infrastructure/providers/factory/akshare_factory.py`

```python
"""
AkShare Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from .base import ProviderFactoryStrategy


class AkShareFactory:
    """AkShare Provider 工厂

    负责创建和配置 AkShareProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 AkShare 配置"""
        try:
            # AkShare 配置较简单，基础验证即可
            pass
        except Exception as e:
            raise ConfigValidationError(provider="akshare", message=f"配置验证失败: {e}") from e

    def create(self, config: dict[str, Any]) -> Any:
        """创建 AkShare Provider"""
        try:
            # 1. 验证配置
            self.validate_config(config)

            # 2. 动态导入
            from ..implementations.akshare.akshare_refactored import AkShareProvider

            # 3. 创建实例
            provider = AkShareProvider(config)

            logger.info("AkShare Provider 创建成功")

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="akshare", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":
    factory = AkShareFactory()
    assert isinstance(factory, ProviderFactoryStrategy), "AkShareFactory 必须实现 ProviderFactoryStrategy 协议"
```

#### `packages/core/infrastructure/providers/factory/provider_factory.py`

```python
"""
统一 Provider 工厂

使用策略模式，将具体创建逻辑委托给各个数据源的专属工厂。
"""

from typing import Any

from loguru import logger

from ..exceptions import UnknownProviderError
from .akshare_factory import AkShareFactory
from .amazingdata_factory import AmazingDataFactory
from .base import ProviderFactoryStrategy
from .miniqmt_factory import MiniQMTFactory


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
            raise UnknownProviderError(provider=name, available=list(self._strategies.keys()))

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

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider 类型"""
        return list(self._strategies.keys())
```

### 2.4 Lifecycle Manager

#### `packages/core/infrastructure/providers/lifecycle/__init__.py`

```python
"""
Provider 生命周期管理
"""

from .manager import ProviderLifecycleManager

__all__ = ["ProviderLifecycleManager"]
```

#### `packages/core/infrastructure/providers/lifecycle/manager.py`

```python
"""
Provider 生命周期管理器
"""

import asyncio
from typing import Any, Sequence

from loguru import logger

from ..protocols.lifecycle import HealthStatus, ILifecycleProvider


class ProviderLifecycleManager:
    """Provider 生命周期管理器

    统一管理所有 Provider 的启动、停止和健康检查。
    """

    def __init__(self, *, shutdown_timeout: float = 10.0):
        """初始化生命周期管理器

        Args:
            shutdown_timeout: 停止超时时间（秒）
        """
        self.shutdown_timeout = shutdown_timeout

    async def initialize(self, provider: Any) -> None:
        """初始化 Provider

        Args:
            provider: Provider 实例

        Raises:
            ProviderInitializationError: 初始化失败
        """
        if not isinstance(provider, ILifecycleProvider):
            logger.warning(
                f"Provider {provider.__class__.__name__} " "未实现 ILifecycleProvider 协议，跳过初始化"
            )
            return

        try:
            logger.info(f"初始化 Provider: {provider.__class__.__name__}")
            await provider.initialize()
            logger.info(f"Provider 初始化成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Provider 初始化失败: {provider.__class__.__name__}", exc_info=e)
            raise

    async def start(self, provider: Any) -> None:
        """启动 Provider

        Args:
            provider: Provider 实例

        Raises:
            ProviderStateError: 启动失败
        """
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"启动 Provider: {provider.__class__.__name__}")
            await provider.start()
            logger.info(f"Provider 启动成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Provider 启动失败: {provider.__class__.__name__}", exc_info=e)
            raise

    async def stop(self, provider: Any) -> None:
        """停止 Provider（带超时保护）

        Args:
            provider: Provider 实例
        """
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"停止 Provider: {provider.__class__.__name__}")
            await asyncio.wait_for(provider.stop(), timeout=self.shutdown_timeout)
            logger.info(f"Provider 停止成功: {provider.__class__.__name__}")
        except asyncio.TimeoutError:
            logger.warning(
                f"Provider 停止超时（{self.shutdown_timeout}s）: " f"{provider.__class__.__name__}"
            )
        except Exception as e:
            logger.error(f"Provider 停止失败: {provider.__class__.__name__}", exc_info=e)

    async def shutdown_all(self, providers: Sequence[Any]) -> None:
        """批量停止所有 Provider

        Args:
            providers: Provider 列表
        """
        if not providers:
            logger.info("没有 Provider 需要停止")
            return

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

        Args:
            provider: Provider 实例

        Returns:
            HealthStatus: 健康状态枚举
        """
        if not isinstance(provider, ILifecycleProvider):
            return HealthStatus.UNKNOWN

        try:
            result = await asyncio.wait_for(provider.health_check(), timeout=5.0)
            return result.status
        except asyncio.TimeoutError:
            logger.warning(f"Provider 健康检查超时: {provider.__class__.__name__}")
            return HealthStatus.UNHEALTHY
        except Exception as e:
            logger.error(f"Provider 健康检查失败: {provider.__class__.__name__}", exc_info=e)
            return HealthStatus.UNHEALTHY

    async def health_check_all(self, providers: dict[str, Any]) -> dict[str, HealthStatus]:
        """批量健康检查

        Args:
            providers: Provider 字典 {name: instance}

        Returns:
            dict[str, HealthStatus]: 健康状态字典
        """
        tasks = {name: self.health_check(provider) for name, provider in providers.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {
            name: result if isinstance(result, HealthStatus) else HealthStatus.UNKNOWN
            for name, result in zip(tasks.keys(), results)
        }
```

### 2.5 Container 层

#### `packages/core/infrastructure/providers/container.py`

```python
"""
Provider 容器

职责：
1. 管理 Provider 实例（单例模式，但不是全局单例）
2. 协调 Factory 和 LifecycleManager
3. 提供依赖注入接口

Note:
    此类不是全局单例，每个应用实例有自己的容器。
    测试时可以创建独立的容器实例。
"""

from typing import Any

from loguru import logger

from .exceptions import ProviderNotFoundError
from .factory.provider_factory import ProviderFactory
from .lifecycle.manager import ProviderLifecycleManager
from .protocols.lifecycle import HealthStatus


class ProviderContainer:
    """Provider 容器

    管理 Provider 的创建、初始化和生命周期。
    """

    def __init__(
        self,
        *,
        factory: ProviderFactory | None = None,
        lifecycle_manager: ProviderLifecycleManager | None = None,
    ):
        """初始化容器

        Args:
            factory: Provider 工厂（可选，默认创建新实例）
            lifecycle_manager: 生命周期管理器（可选，默认创建新实例）
        """
        self._factory = factory or ProviderFactory()
        self._lifecycle = lifecycle_manager or ProviderLifecycleManager()
        self._instances: dict[str, Any] = {}
        self._initialized: set[str] = set()

    async def get(self, name: str) -> Any:
        """获取已注册的 Provider

        Args:
            name: Provider 名称

        Returns:
            Provider 实例

        Raises:
            ProviderNotFoundError: Provider 不存在
        """
        if name not in self._instances:
            raise ProviderNotFoundError(provider=name, message=f"Provider '{name}' 未注册，请先调用 create_and_register()")

        return self._instances[name]

    async def create_and_register(
        self,
        name: str,
        config: dict[str, Any],
        *,
        force_new: bool = False,
    ) -> Any:
        """创建、初始化并注册新 Provider

        Args:
            name: Provider 名称
            config: 配置字典
            force_new: 是否强制创建新实例（替换旧实例）

        Returns:
            Provider 实例

        Raises:
            UnknownProviderError: 未知的 Provider 类型
            ConfigValidationError: 配置验证失败
            ProviderCreationError: 创建失败
            ProviderInitializationError: 初始化失败
        """
        # 如果已存在且不强制创建，直接返回
        if not force_new and name in self._instances:
            logger.debug(f"Provider '{name}' 已存在，返回现有实例")
            return self._instances[name]

        # 如果强制创建，先停止旧实例
        if force_new and name in self._instances:
            logger.info(f"强制创建新实例，停止旧的 Provider: {name}")
            old_provider = self._instances[name]
            await self._lifecycle.stop(old_provider)
            del self._instances[name]
            self._initialized.discard(name)

        # 创建新实例
        logger.info(f"创建 Provider: {name}")
        provider = self._factory.create(name, config)

        # 初始化
        await self._lifecycle.initialize(provider)
        await self._lifecycle.start(provider)

        # 注册
        self._instances[name] = provider
        self._initialized.add(name)

        logger.info(f"Provider '{name}' 已创建并注册")
        return provider

    def has(self, name: str) -> bool:
        """检查 Provider 是否存在

        Args:
            name: Provider 名称

        Returns:
            bool: 是否存在
        """
        return name in self._instances

    async def health_check(self, name: str) -> HealthStatus:
        """检查指定 Provider 的健康状态

        Args:
            name: Provider 名称

        Returns:
            HealthStatus: 健康状态

        Raises:
            ProviderNotFoundError: Provider 不存在
        """
        provider = await self.get(name)
        return await self._lifecycle.health_check(provider)

    async def health_check_all(self) -> dict[str, HealthStatus]:
        """检查所有 Provider 的健康状态

        Returns:
            dict[str, HealthStatus]: 健康状态字典
        """
        return await self._lifecycle.health_check_all(self._instances)

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

    def list_available_types(self) -> list[str]:
        """列出所有可用的 Provider 类型"""
        return self._factory.list_providers()
```

### 2.6 FastAPI 集成

#### `packages/core/infrastructure/providers/integration/__init__.py`

```python
"""
Provider 集成模块
"""

from .fastapi import get_provider_container, provider_lifespan

__all__ = [
    "provider_lifespan",
    "get_provider_container",
]
```

#### `packages/core/infrastructure/providers/integration/fastapi.py`

```python
"""
FastAPI 集成

提供 lifespan 上下文管理器和依赖注入函数。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from loguru import logger

from ..container import ProviderContainer


@asynccontextmanager
async def provider_lifespan(app: FastAPI):
    """Provider 容器生命周期管理

    在 FastAPI 应用启动时创建容器，关闭时清理。

    Usage:
        app = FastAPI(lifespan=provider_lifespan)

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 应用运行中
    """
    # 启动
    logger.info("初始化 ProviderContainer...")
    container = ProviderContainer()
    app.state.provider_container = container

    # 预加载配置中的 Provider
    try:
        from core.config import get_config

        config = get_config()
        if hasattr(config, "data_sources"):
            for name, ds_config in config.data_sources.items():
                if ds_config.get("enabled", False):
                    try:
                        await container.create_and_register(name, ds_config)
                        logger.info(f"预加载 Provider 成功: {name}")
                    except Exception as e:
                        logger.warning(f"预加载 Provider 失败: {name} - {e}")
    except Exception as e:
        logger.warning(f"无法加载配置: {e}")

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
            provider = await container.get("amazingdata")
            ...

    Args:
        request: FastAPI Request 对象

    Returns:
        ProviderContainer: 容器实例
    """
    return request.app.state.provider_container
```

---

## 三、实施步骤

### Step 1: 创建基础设施层

```bash
# 创建目录
mkdir -p packages/core/infrastructure/providers/protocols
mkdir -p packages/core/infrastructure/providers/factory
mkdir -p packages/core/infrastructure/providers/lifecycle
mkdir -p packages/core/infrastructure/providers/integration

# 创建文件（使用 Write 工具逐个创建）
# 1. exceptions.py
# 2. protocols/__init__.py, lifecycle.py, capabilities.py
# 3. factory/__init__.py, base.py, *_factory.py
# 4. lifecycle/__init__.py, manager.py
# 5. container.py
# 6. integration/__init__.py, fastapi.py
```

### Step 2: 运行类型检查

```bash
cd packages/core
mypy infrastructure/providers/protocols
mypy infrastructure/providers/factory
mypy infrastructure/providers/lifecycle
mypy infrastructure/providers/container.py
mypy infrastructure/providers/integration
```

### Step 3: 验证 Protocol 实现

创建简单的验证脚本：

```python
# test_protocols.py
from core.infrastructure.providers.protocols import ILifecycleProvider, IKlineProvider
from core.infrastructure.providers.factory import ProviderFactoryStrategy
from core.infrastructure.providers.factory.amazingdata_factory import AmazingDataFactory

# 验证 Factory 符合 Protocol
factory = AmazingDataFactory()
assert isinstance(factory, ProviderFactoryStrategy), "Factory 必须实现 ProviderFactoryStrategy"

print("所有 Protocol 验证通过")
```

### Step 4: 编写单元测试

```python
# tests/unit/providers/test_container.py
import pytest
from core.infrastructure.providers.container import ProviderContainer
from core.infrastructure.providers.exceptions import ProviderNotFoundError


@pytest.mark.asyncio
async def test_container_lifecycle():
    """测试容器生命周期"""
    container = ProviderContainer()

    # 测试获取不存在的 Provider
    with pytest.raises(ProviderNotFoundError):
        await container.get("nonexistent")

    # 测试关闭
    await container.shutdown()
    assert len(container.list_providers()) == 0
```

### Step 5: 集成测试

在测试环境中启动 FastAPI 应用，验证 lifespan 正常工作：

```python
# tests/integration/test_fastapi_integration.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.infrastructure.providers.integration import provider_lifespan


def test_lifespan():
    """测试 FastAPI lifespan 集成"""
    app = FastAPI(lifespan=provider_lifespan)

    with TestClient(app) as client:
        # lifespan 启动
        assert hasattr(app.state, "provider_container")
        container = app.state.provider_container
        assert container is not None

    # lifespan 关闭后，容器应该为空
    assert len(container.list_providers()) == 0
```

---

## 四、验证清单

### 代码质量验证

- [ ] 所有 Protocol 都有 `@runtime_checkable` 装饰器
- [ ] 没有在 Protocol 中使用 `@abstractmethod`
- [ ] 所有 Factory 类都实现了 `ProviderFactoryStrategy` 协议
- [ ] Mypy 类型检查 0 错误
- [ ] Ruff lint 0 警告

### 功能验证

- [ ] `ProviderContainer.create_and_register()` 可以创建 Provider
- [ ] `ProviderContainer.get()` 可以获取已注册的 Provider
- [ ] `ProviderContainer.shutdown()` 正确停止所有 Provider
- [ ] `provider_lifespan` 正确管理容器生命周期
- [ ] `get_provider_container` 依赖注入可用

### 性能验证

- [ ] 容器创建开销 < 10ms
- [ ] Provider 启动时间 < 旧架构
- [ ] 健康检查响应 < 5s

---

## 五、后续工作

### Phase 2: Provider 实现迁移（下一步）

修改现有 Provider 实现以支持新协议：

1. `implementations/amazingdata/amazingdata_optimized.py`
   - 实现 `ILifecycleProvider` 接口
   - 实现 `IKlineProvider`, `IRealtimeProvider` 接口
   - 添加 `async def initialize()`, `start()`, `stop()`, `health_check()`

2. `implementations/qmt/miniqmt.py`
   - 同上

3. `implementations/akshare/akshare_refactored.py`
   - 同上

### Phase 3: 切换与清理（最后）

1. 更新 `apps/api/api/providers.py` 使用新容器
2. 删除 `registry.py`
3. 删除 `adapters/` 目录
4. 更新文档

---

## 六、回滚策略

如果实施过程中发现问题：

1. **代码已提交但未部署**：直接 `git revert`
2. **已部署到测试环境**：
   - 回滚到上一个稳定版本
   - 修复问题
   - 重新部署
3. **保留新旧代码共存**：不推荐，会增加技术债

---

## 七、参考资料

- [PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Factory Method Pattern](https://refactoring.guru/design-patterns/factory-method/python/example)
- [Modern Python Interfaces: ABC, Protocol, or Both?](https://tconsta.medium.com/python-interfaces-abc-protocol-or-both-3c5871ea6642)
