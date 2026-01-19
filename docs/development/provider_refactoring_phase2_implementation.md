# Provider 架构重构 Phase 2 实施文档

> 版本：v1.0
> 日期：2026-01-15
> 状态：实施指南 - Provider 迁移
> 依据：provider_refactoring_implementation.md

---

## 一、Phase 2 概览

### 1.1 目标

将现有的三个 Provider 实现迁移到新的 Protocol 接口：

1. OptimizedAmazingDataProvider - 实现 ILifecycleProvider, IKlineProvider, IRealtimeProvider
2. MiniQMTProvider - 实现 ILifecycleProvider, IKlineProvider, IRealtimeProvider
3. AkShareProxyProvider - 实现 ILifecycleProvider, IKlineProvider

### 1.2 迁移策略

**最小侵入式迁移**：

- 保留现有的 `connect/disconnect` 方法
- 添加新的 Protocol 方法（`initialize/start/stop/health_check`）
- 新方法内部调用现有方法，避免重复实现
- 逐步删除对旧 DataProvider 基类的依赖

---

## 二、OptimizedAmazingDataProvider 迁移

### 2.1 当前状态分析

```python
# 当前实现
class OptimizedAmazingDataProvider(DataProvider):
    def __init__(self, config): ...
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def get_kline(self, ...): ...
    async def get_stock_list(self, ...): ...
```

### 2.2 迁移后实现

**关键修改点**：

1. 保留继承 DataProvider（暂时，Phase 3 删除）
2. 添加 ILifecycleProvider 方法
3. 添加 IKlineProvider, IRealtimeProvider 方法
4. 添加 health_check 方法

#### 完整代码（仅显示修改部分）

在文件 `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py` 中：

**1. 在文件开头添加导入**：

```python
# 在第 29 行后添加
from core.infrastructure.providers.protocols.lifecycle import (
    HealthCheckResult,
    HealthStatus,
    ILifecycleProvider,
)
from core.infrastructure.providers.protocols.capabilities import (
    IKlineProvider,
    IRealtimeProvider,
)
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineResponse, RealtimeQuoteResponse
```

**2. 在类定义后添加 Protocol 方法**（在 `__init__` 方法后，约 760 行）：

```python
    # ============ ILifecycleProvider 实现 ============

    async def initialize(self) -> None:
        """初始化 Provider

        内部调用现有的初始化逻辑。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 初始化...")

            # 如果已经连接，跳过
            if self._connected:
                logger.info("Provider 已初始化，跳过")
                return

            # 执行登录（内部会初始化 SDK）
            # 注意：不启动心跳，由 start() 方法启动
            result = await self._login()
            if not result:
                from core.infrastructure.providers.exceptions import ProviderInitializationError
                raise ProviderInitializationError(
                    provider="amazingdata",
                    message="登录失败"
                )

            logger.info("OptimizedAmazingDataProvider 初始化成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 初始化失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderInitializationError
            raise ProviderInitializationError(
                provider="amazingdata",
                message=str(e)
            ) from e

    async def start(self) -> None:
        """启动 Provider

        启动心跳等后台任务。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 启动...")

            # 如果心跳任务已启动，跳过
            if self._heartbeat_task and not self._heartbeat_task.done():
                logger.info("心跳任务已运行，跳过")
                return

            # 启动心跳
            self._heartbeat_task = cast(
                asyncio.Task[None],
                asyncio.create_task(self.heartbeat.heartbeat_loop())
            )

            logger.info("OptimizedAmazingDataProvider 启动成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 启动失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderStateError
            raise ProviderStateError(
                provider="amazingdata",
                message=f"启动失败: {e}"
            ) from e

    async def stop(self) -> None:
        """停止 Provider

        停止心跳，登出，清理资源。
        内部调用现有的 disconnect() 方法。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 停止...")

            # 调用现有的 disconnect 方法
            await self.disconnect()

            logger.info("OptimizedAmazingDataProvider 停止成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 停止失败: {e}")
            # 不抛出异常，确保优雅关闭

    async def health_check(self) -> HealthCheckResult:
        """健康检查

        检查连接状态、心跳状态、SDK 状态。
        """
        try:
            # 检查连接状态
            if not self._connected:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="未连接到 AmazingData",
                    details={"connected": False}
                )

            # 检查心跳任务
            heartbeat_alive = (
                self._heartbeat_task is not None
                and not self._heartbeat_task.done()
            )

            # 检查登录时间
            login_duration = 0.0
            if self._login_time:
                login_duration = (datetime.now() - self._login_time).total_seconds()

            # 组装详情
            details = {
                "connected": self._connected,
                "heartbeat_alive": heartbeat_alive,
                "login_duration_seconds": login_duration,
                "consecutive_heartbeat_failures": self.heartbeat.consecutive_failures,
            }

            # 判断健康状态
            if not heartbeat_alive:
                status = HealthStatus.DEGRADED
                message = "心跳任务未运行"
            elif self.heartbeat.consecutive_failures > 5:
                status = HealthStatus.DEGRADED
                message = f"心跳连续失败 {self.heartbeat.consecutive_failures} 次"
            else:
                status = HealthStatus.HEALTHY
                message = "运行正常"

            return HealthCheckResult(
                status=status,
                message=message,
                details=details
            )

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {e}",
                details={}
            )

    # ============ IKlineProvider 实现 ============

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        适配现有的 get_kline_data 方法。
        """
        try:
            # 调用现有方法
            result = await self.get_kline_data(
                symbol=request.asset,
                period=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                adjust=request.adjust,
            )

            # 转换为标准响应
            return KlineResponse(
                success=True,
                data=result,
                metadata={
                    "source": "amazingdata",
                    "symbol": request.asset,
                    "timeframe": request.timeframe,
                }
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError
            raise ProviderDataError(
                provider="amazingdata",
                message=f"查询K线失败: {e}"
            ) from e

    # ============ IRealtimeProvider 实现 ============

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情

        注意：OptimizedAmazingDataProvider 当前可能没有实时行情方法，
        这里提供一个占位实现或抛出 NotImplementedError。
        """
        # 如果有实时行情方法，调用它
        # 如果没有，抛出未实现异常
        raise NotImplementedError("AmazingData Provider 暂不支持实时行情查询")
```

**3. 保留现有的 connect/disconnect 方法**（无需修改）

#### 修改摘要

| 修改类型 | 位置 | 说明 |
|---------|------|------|
| 添加导入 | 文件开头 | 导入 Protocol 接口和 Request/Response 类型 |
| 添加方法 | 类定义后 | 添加 7 个新方法（initialize, start, stop, health_check, query_kline, query_realtime, 等） |
| 代码行数 | +约150行 | 新增代码不影响现有功能 |

---

## 三、MiniQMTProvider 迁移

### 3.1 当前状态分析

```python
# 当前实现
class MiniQMTProvider(DataProvider):
    def __init__(self, config): ...
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    # ... 其他方法
```

### 3.2 迁移后实现

在文件 `packages/core/infrastructure/providers/implementations/qmt/miniqmt.py` 中：

**1. 在文件开头添加导入**（在第 28 行后）：

```python
from core.infrastructure.providers.protocols.lifecycle import (
    HealthCheckResult,
    HealthStatus,
    ILifecycleProvider,
)
from core.infrastructure.providers.protocols.capabilities import (
    IKlineProvider,
    IRealtimeProvider,
)
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineResponse, RealtimeQuoteResponse
```

**2. 在类定义后添加 Protocol 方法**（在 `__init__` 后）：

```python
    # ============ ILifecycleProvider 实现 ============

    async def initialize(self) -> None:
        """初始化 Provider"""
        try:
            logger.info("MiniQMTProvider 初始化...")

            # 检查 xtdata 是否可用
            if not XTDATA_AVAILABLE:
                from core.infrastructure.providers.exceptions import ProviderInitializationError
                raise ProviderInitializationError(
                    provider="miniqmt",
                    message="xtquant 库未安装"
                )

            # MiniQMT 的初始化逻辑（如果有）
            # 注意：MiniQMT 可能不需要显式初始化，只需要在查询时连接

            logger.info("MiniQMTProvider 初始化成功")

        except Exception as e:
            logger.error(f"MiniQMTProvider 初始化失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderInitializationError
            raise ProviderInitializationError(
                provider="miniqmt",
                message=str(e)
            ) from e

    async def start(self) -> None:
        """启动 Provider

        启动心跳和数据接收任务。
        """
        try:
            logger.info("MiniQMTProvider 启动...")

            # 如果已启动，跳过
            if self.heartbeat_task and not self.heartbeat_task.done():
                logger.info("心跳任务已运行，跳过")
                return

            # 启动心跳任务
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # 启动数据接收任务（如果有连接）
            if self.connected and not self.receive_task:
                self.receive_task = asyncio.create_task(self._receive_data())

            logger.info("MiniQMTProvider 启动成功")

        except Exception as e:
            logger.error(f"MiniQMTProvider 启动失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderStateError
            raise ProviderStateError(
                provider="miniqmt",
                message=f"启动失败: {e}"
            ) from e

    async def stop(self) -> None:
        """停止 Provider

        停止所有后台任务，断开连接。
        """
        try:
            logger.info("MiniQMTProvider 停止...")

            # 取消心跳任务
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                self.heartbeat_task = None

            # 取消数据接收任务
            if self.receive_task:
                self.receive_task.cancel()
                try:
                    await self.receive_task
                except asyncio.CancelledError:
                    pass
                self.receive_task = None

            # 断开连接
            await self.disconnect()

            logger.info("MiniQMTProvider 停止成功")

        except Exception as e:
            logger.error(f"MiniQMTProvider 停止失败: {e}")
            # 不抛出异常，确保优雅关闭

    async def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            # 检查 xtdata 是否可用
            if not XTDATA_AVAILABLE:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="xtquant 库未安装",
                    details={"xtdata_available": False}
                )

            # 检查连接状态
            if not self.connected:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="未连接到 MiniQMT",
                    details={"connected": False}
                )

            # 检查心跳任务
            heartbeat_alive = (
                self.heartbeat_task is not None
                and not self.heartbeat_task.done()
            )

            # 检查数据接收任务
            receive_alive = (
                self.receive_task is not None
                and not self.receive_task.done()
            )

            details = {
                "connected": self.connected,
                "heartbeat_alive": heartbeat_alive,
                "receive_alive": receive_alive,
                "reconnect_attempts": self.reconnect_attempts,
                "subscribed_symbols": len(self.subscribed_symbols),
            }

            # 判断健康状态
            if not heartbeat_alive:
                status = HealthStatus.DEGRADED
                message = "心跳任务未运行"
            elif self.reconnect_attempts > 3:
                status = HealthStatus.DEGRADED
                message = f"重连次数过多: {self.reconnect_attempts}"
            else:
                status = HealthStatus.HEALTHY
                message = "运行正常"

            return HealthCheckResult(
                status=status,
                message=message,
                details=details
            )

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {e}",
                details={}
            )

    # ============ IKlineProvider 实现 ============

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        使用 xtdata 查询历史K线。
        """
        try:
            # 调用 xtdata 查询K线
            # 注意：需要根据 MiniQMT 的实际 API 调整
            if not XTDATA_AVAILABLE:
                raise RuntimeError("xtquant 库未安装")

            # 示例调用（需要根据实际 API 调整）
            df = xtdata.get_market_data(
                stock_list=[request.asset],
                period=request.timeframe,
                start_time=request.start_date,
                end_time=request.end_date,
            )

            return KlineResponse(
                success=True,
                data=df,
                metadata={
                    "source": "miniqmt",
                    "symbol": request.asset,
                    "timeframe": request.timeframe,
                }
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError
            raise ProviderDataError(
                provider="miniqmt",
                message=f"查询K线失败: {e}"
            ) from e

    # ============ IRealtimeProvider 实现 ============

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情

        使用 xtdata 查询实时行情。
        """
        try:
            # 调用 xtdata 查询实时行情
            if not XTDATA_AVAILABLE:
                raise RuntimeError("xtquant 库未安装")

            # 示例调用（需要根据实际 API 调整）
            quotes = xtdata.get_full_tick(request.symbols)

            return RealtimeQuoteResponse(
                success=True,
                data=quotes,
                metadata={
                    "source": "miniqmt",
                    "count": len(request.symbols),
                }
            )

        except Exception as e:
            logger.error(f"查询实时行情失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError
            raise ProviderDataError(
                provider="miniqmt",
                message=f"查询实时行情失败: {e}"
            ) from e
```

---

## 四、AkShareProxyProvider 迁移

### 4.1 当前状态分析

```python
# 当前实现
class AkShareProxyProvider:  # 注意：不继承 DataProvider
    def __init__(self): ...
    # 没有 connect/disconnect 方法
```

### 4.2 迁移后实现

在文件 `packages/core/infrastructure/providers/implementations/akshare/akshare_refactored.py` 中：

**1. 在文件开头添加导入**（在第 21 行后）：

```python
from core.infrastructure.providers.protocols.lifecycle import (
    HealthCheckResult,
    HealthStatus,
    ILifecycleProvider,
)
from core.infrastructure.providers.protocols.capabilities import IKlineProvider
from core.ports.data.requests import KlineRequest
from core.ports.data.responses import KlineResponse
```

**2. 在类定义后添加 Protocol 方法**（在 `__init__` 后，约 95 行）：

```python
    # ============ ILifecycleProvider 实现 ============

    async def initialize(self) -> None:
        """初始化 Provider

        AkShare 不需要连接，但需要初始化组件。
        """
        try:
            logger.info("AkShareProxyProvider 初始化...")

            # 如果已初始化，跳过
            if self._initialized:
                logger.info("Provider 已初始化，跳过")
                return

            # 应用 AkShare 补丁（如果需要）
            if not self._patch_applied:
                patch_akshare()
                self._patch_applied = True

            # 获取异步包装器
            if not self._async_wrapper:
                self._async_wrapper = get_async_wrapper()

            self._initialized = True
            self.status = "active"

            logger.info("AkShareProxyProvider 初始化成功")

        except Exception as e:
            logger.error(f"AkShareProxyProvider 初始化失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderInitializationError
            raise ProviderInitializationError(
                provider="akshare",
                message=str(e)
            ) from e

    async def start(self) -> None:
        """启动 Provider

        启动 Worker 健康监控任务。
        """
        try:
            logger.info("AkShareProxyProvider 启动...")

            # 如果监控任务已启动，跳过
            if self._monitor_task and not self._monitor_task.done():
                logger.info("监控任务已运行，跳过")
                return

            # 启动 Worker 健康监控
            self._monitor_task = asyncio.create_task(
                self.worker_manager.start_health_monitor()
            )

            logger.info("AkShareProxyProvider 启动成功")

        except Exception as e:
            logger.error(f"AkShareProxyProvider 启动失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderStateError
            raise ProviderStateError(
                provider="akshare",
                message=f"启动失败: {e}"
            ) from e

    async def stop(self) -> None:
        """停止 Provider

        停止监控任务。
        """
        try:
            logger.info("AkShareProxyProvider 停止...")

            # 取消监控任务
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            self.status = "inactive"

            logger.info("AkShareProxyProvider 停止成功")

        except Exception as e:
            logger.error(f"AkShareProxyProvider 停止失败: {e}")
            # 不抛出异常，确保优雅关闭

    async def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            # 检查初始化状态
            if not self._initialized:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Provider 未初始化",
                    details={"initialized": False}
                )

            # 检查 Worker 状态
            worker_stats = self.worker_manager.get_stats()
            healthy_workers = sum(
                1 for w in worker_stats.get("workers", [])
                if w.get("status") == "healthy"
            )
            total_workers = len(worker_stats.get("workers", []))

            # 检查监控任务
            monitor_alive = (
                self._monitor_task is not None
                and not self._monitor_task.done()
            )

            details = {
                "initialized": self._initialized,
                "status": self.status,
                "monitor_alive": monitor_alive,
                "healthy_workers": healthy_workers,
                "total_workers": total_workers,
                "strategy": self.strategy,
            }

            # 判断健康状态
            if healthy_workers == 0:
                status = HealthStatus.UNHEALTHY
                message = "所有 Worker 不可用"
            elif healthy_workers < total_workers:
                status = HealthStatus.DEGRADED
                message = f"{healthy_workers}/{total_workers} Worker 可用"
            else:
                status = HealthStatus.HEALTHY
                message = "运行正常"

            return HealthCheckResult(
                status=status,
                message=message,
                details=details
            )

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {e}",
                details={}
            )

    # ============ IKlineProvider 实现 ============

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        使用 AkShare API 查询K线。
        """
        try:
            # 调用现有的 API 方法
            # 注意：需要根据实际方法名调整
            df = await self.api_methods.stock_zh_a_hist(
                symbol=request.asset,
                period=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                adjust=request.adjust,
            )

            return KlineResponse(
                success=True,
                data=df,
                metadata={
                    "source": "akshare",
                    "symbol": request.asset,
                    "timeframe": request.timeframe,
                }
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError
            raise ProviderDataError(
                provider="akshare",
                message=f"查询K线失败: {e}"
            ) from e
```

---

## 五、实施步骤

### Step 1: 备份现有文件

```bash
# 创建备份
cp packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py \
   packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py.backup

cp packages/core/infrastructure/providers/implementations/qmt/miniqmt.py \
   packages/core/infrastructure/providers/implementations/qmt/miniqmt.py.backup

cp packages/core/infrastructure/providers/implementations/akshare/akshare_refactored.py \
   packages/core/infrastructure/providers/implementations/akshare/akshare_refactored.py.backup
```

### Step 2: 逐个修改 Provider

按照以下顺序修改：

1. AmazingDataProvider（最复杂）
2. MiniQMTProvider
3. AkShareProxyProvider（最简单）

### Step 3: 验证语法

```bash
python -m py_compile <modified_file>.py
```

### Step 4: 创建简单的测试脚本

```python
# test_protocol_implementation.py
import asyncio
from core.infrastructure.providers.protocols.lifecycle import ILifecycleProvider
from core.infrastructure.providers.implementations.amazingdata.amazingdata_optimized import OptimizedAmazingDataProvider

async def test_provider():
    # 验证 Protocol 实现
    provider = OptimizedAmazingDataProvider(config)
    assert isinstance(provider, ILifecycleProvider), "必须实现 ILifecycleProvider"

    print("Protocol 验证通过")

if __name__ == "__main__":
    asyncio.run(test_provider())
```

---

## 六、验证清单

### 代码质量验证

- [ ] 所有 Provider 都实现了 ILifecycleProvider 协议
- [ ] 语法检查通过
- [ ] 现有功能未破坏（connect/disconnect 方法仍可用）

### 功能验证

- [ ] `initialize()` 方法可以正常初始化
- [ ] `start()` 方法可以启动后台任务
- [ ] `stop()` 方法可以优雅停止
- [ ] `health_check()` 方法返回正确的健康状态
- [ ] `query_kline()` 等数据查询方法可用

### Protocol 验证

```python
# 运行验证脚本
from core.infrastructure.providers.protocols.lifecycle import ILifecycleProvider
from core.infrastructure.providers.implementations.amazingdata.amazingdata_optimized import OptimizedAmazingDataProvider

provider = OptimizedAmazingDataProvider(config)
assert isinstance(provider, ILifecycleProvider), "必须实现 ILifecycleProvider"
```

---

## 七、注意事项

### 7.1 向后兼容

- 保留所有现有的 `connect/disconnect` 方法
- 新旧方法可以并存
- 逐步迁移调用方到新方法

### 7.2 错误处理

- 所有 Protocol 方法都应该有完善的异常处理
- 使用新的异常类型（`ProviderInitializationError`, `ProviderStateError` 等）
- `stop()` 方法不应该抛出异常（优雅关闭）

### 7.3 幂等性

- `initialize()` 应该是幂等的（多次调用无副作用）
- `start()` 应该是幂等的
- `stop()` 应该是幂等的

---

## 八、下一步（Phase 3）

Phase 2 完成后，Phase 3 将进行：

1. 删除对 DataProvider 基类的继承
2. 更新所有调用方使用新容器
3. 删除 registry.py
4. 删除 adapters/ 目录

---

**实施文档状态**：完成
**预计代码行数**：+约 400 行（3个 Provider 各约 130-150 行）
