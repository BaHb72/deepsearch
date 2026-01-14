# AmazingData Dask Client Adapter 实施计划

## 概述

**任务**: 实现完整的 Dask Client Adapter，支持通过 Dask 分布式调用 AmazingDataActor

**预计工作量**: 6-8 小时

**优先级**: P3 (架构完善，非阻塞)

**状态**: 待实施

---

## 背景分析

### 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│                    后端进程 (FastAPI)                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  AmazingDataExtended (Local 模式)                           │
│  ├── 直接调用 AmazingData SDK (54个方法)                    │
│  ├── multiprocessing 进程隔离                                │
│  └── 用于单机部署                                            │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                Dask Worker (Windows 环境)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  AmazingDataWorkerPlugin (已实现)                           │
│  └── AmazingDataActor (已实现)                               │
│      ├── call(method, **kwargs) - RPC 接口                  │
│      ├── 路由到 _base_data / _market_data / _info_data     │
│      └── 保持 SDK 登录状态                                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 缺失的组件

**AmazingDataDaskAdapter** (Client 端) - 桥接 DataProvider 接口到远程 Actor

---

## 架构设计

### 组件关系

```
┌──────────────────────────────────────────────────────────────────┐
│                       后端进程 (FastAPI)                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  DataProviderRegistry                                             │
│  ├── 根据配置选择模式                                             │
│  ├── Local: AmazingDataExtended                                  │
│  └── Distributed: AmazingDataDaskAdapter (新增)                  │
│                                                                    │
│  AmazingDataDaskAdapter (新增)                                   │
│  ├── 实现 35 个 DataProvider 接口方法                            │
│  ├── 通过 Dask Client 调用远程 Actor                             │
│  ├── Worker 选择逻辑 (WIN:1 资源标签)                            │
│  ├── 错误处理和重试                                               │
│  └── 连接池管理                                                   │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ RPC (Dask Client.submit)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Dask Scheduler (localhost:8786)                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ 任务分发
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Dask Worker (Windows, WIN:1)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  worker.actors["amazingdata"]                                     │
│  └── AmazingDataActor.call(method, **kwargs)                     │
│      └── 路由到 SDK 对象方法                                      │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 实施步骤

### Phase 1: 创建核心 Adapter 类 (2-3 小时)

#### 文件路径

```
packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py
```

#### 代码框架

```python
"""AmazingData Dask Client Adapter

通过 Dask Client 远程调用 Windows Worker 上的 AmazingDataActor。
用于分布式部署场景。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from distributed import Client
from loguru import logger

from core.infrastructure.providers.interfaces.base import DataProviderError

if TYPE_CHECKING:
    from distributed import Future


class AmazingDataDaskAdapter:
    """AmazingData Dask Client Adapter

    实现 DataProvider 接口，通过 Dask 分布式调用远程 Actor。

    Features:
    - 自动选择 Windows Worker (WIN:1 资源标签)
    - 连接池管理和复用
    - 错误处理和自动重试
    - 超时保护

    Example:
        >>> from distributed import Client
        >>> dask_client = Client("tcp://localhost:8786")
        >>> adapter = AmazingDataDaskAdapter(dask_client)
        >>> await adapter.initialize()
        >>> result = await adapter.query_kline(code_list=["000001.SZ"])
    """

    def __init__(
        self,
        dask_client: Client,
        timeout: float = 30.0,
        retry_count: int = 3,
    ):
        """初始化 Dask Adapter

        Args:
            dask_client: Dask distributed Client 实例
            timeout: 远程调用超时时间（秒）
            retry_count: 失败重试次数
        """
        self._client = dask_client
        self._timeout = timeout
        self._retry_count = retry_count

        # 缓存 Windows Worker 地址
        self._windows_worker: Optional[str] = None
        self._actor_available = False

        logger.info(
            "[AmazingDataDaskAdapter] 初始化 | scheduler={}",
            dask_client.scheduler.address
        )

    async def initialize(self) -> bool:
        """初始化 Adapter，查找可用的 Windows Worker"""
        try:
            # 查找有 WIN:1 资源的 Worker
            self._windows_worker = await self._find_windows_worker()
            if not self._windows_worker:
                logger.error("[DaskAdapter] 未找到 Windows Worker (WIN:1)")
                return False

            # 验证 Actor 是否已注册
            self._actor_available = await self._check_actor_available()
            if not self._actor_available:
                logger.error(
                    "[DaskAdapter] Worker {} 上未找到 amazingdata Actor",
                    self._windows_worker
                )
                return False

            logger.info(
                "[DaskAdapter] 初始化成功 | worker={} | actor=available",
                self._windows_worker
            )
            return True

        except Exception as e:
            logger.error("[DaskAdapter] 初始化失败: {}", e, exc_info=True)
            return False

    async def _find_windows_worker(self) -> Optional[str]:
        """查找有 WIN:1 资源的 Worker

        Returns:
            Worker 地址，未找到返回 None
        """
        try:
            # 获取所有 Worker 信息
            info = await self._client.scheduler.scheduler_info()
            workers = info.get("workers", {})

            for worker_addr, worker_info in workers.items():
                # 检查资源标签
                resources = worker_info.get("resources", {})
                if resources.get("WIN", 0) >= 1:
                    logger.debug(
                        "[DaskAdapter] 找到 Windows Worker | addr={} | resources={}",
                        worker_addr,
                        resources
                    )
                    return worker_addr

            logger.warning("[DaskAdapter] 未找到 Windows Worker (WIN:1)")
            return None

        except Exception as e:
            logger.error("[DaskAdapter] 查找 Worker 失败: {}", e)
            return None

    async def _check_actor_available(self) -> bool:
        """检查 Actor 是否在 Worker 上可用"""
        try:
            # 提交一个轻量级任务检查 Actor
            future: Future = self._client.submit(
                lambda dask_worker: hasattr(dask_worker, "actors") and
                                   "amazingdata" in getattr(dask_worker, "actors", {}),
                workers=[self._windows_worker],
                pure=False,
            )
            result = await future
            return result
        except Exception as e:
            logger.warning("[DaskAdapter] 检查 Actor 失败: {}", e)
            return False

    async def _call_actor(
        self,
        method: str,
        retry: int = 0,
        **kwargs: Any
    ) -> Any:
        """通用远程调用方法

        Args:
            method: Actor 方法名 (如 "query_kline")
            retry: 当前重试次数
            **kwargs: 方法参数

        Returns:
            Actor 方法返回值

        Raises:
            DataProviderError: 调用失败或超时
        """
        if not self._actor_available:
            raise DataProviderError("Actor 不可用，请先调用 initialize()")

        try:
            # 定义远程执行函数
            def _remote_call(dask_worker):
                """在 Worker 上执行的函数"""
                actor = dask_worker.actors.get("amazingdata")
                if actor is None:
                    raise RuntimeError("amazingdata Actor 未注册")

                # 调用 Actor 的 call() 方法
                # 注意：这是同步调用，因为在 Worker 的线程池中执行
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(actor.call(method, **kwargs))
                finally:
                    loop.close()

            # 提交任务到 Windows Worker
            future: Future = self._client.submit(
                _remote_call,
                workers=[self._windows_worker],
                resources={"WIN": 1},
                pure=False,
            )

            # 等待结果（带超时）
            result = await asyncio.wait_for(
                future,
                timeout=self._timeout
            )

            logger.debug(
                "[DaskAdapter] 调用成功 | method={} | worker={}",
                method,
                self._windows_worker
            )
            return result

        except asyncio.TimeoutError:
            logger.error(
                "[DaskAdapter] 调用超时 | method={} | timeout={}s",
                method,
                self._timeout
            )
            if retry < self._retry_count:
                logger.info("[DaskAdapter] 重试 {}/{}", retry + 1, self._retry_count)
                return await self._call_actor(method, retry=retry + 1, **kwargs)
            raise DataProviderError(f"Actor 调用超时: {method}")

        except Exception as e:
            logger.error(
                "[DaskAdapter] 调用失败 | method={} | error={}",
                method,
                str(e),
                exc_info=True
            )
            if retry < self._retry_count:
                logger.info("[DaskAdapter] 重试 {}/{}", retry + 1, self._retry_count)
                await asyncio.sleep(1)  # 延迟重试
                return await self._call_actor(method, retry=retry + 1, **kwargs)
            raise DataProviderError(f"Actor 调用失败: {method} - {e}")

    # ==================== DataProvider 接口实现 ====================

    async def query_kline(
        self,
        code_list: List[str],
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "none",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """查询 K 线数据（远程调用）

        Args:
            code_list: 股票代码列表
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            **kwargs: 其他参数

        Returns:
            K 线数据字典
        """
        return await self._call_actor(
            "query_kline",
            code_list=code_list,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            **kwargs
        )

    async def query_snapshot(
        self,
        code_list: List[str],
        date: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """查询历史快照（远程调用）"""
        return await self._call_actor(
            "query_snapshot",
            code_list=code_list,
            date=date,
            **kwargs
        )

    async def get_code_list(
        self,
        security_type: str = "stock",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """获取证券代码列表（远程调用）"""
        return await self._call_actor(
            "get_code_list",
            security_type=security_type,
            **kwargs
        )

    # TODO: 实现剩余 32 个 DataProvider 接口方法
    # 参考 AmazingDataExtended 的方法签名
    # 每个方法只需要调用 self._call_actor(method_name, **params)

    async def shutdown(self) -> None:
        """关闭 Adapter"""
        self._actor_available = False
        logger.info("[DaskAdapter] 已关闭")


__all__ = ["AmazingDataDaskAdapter"]
```

#### 关键实现点

1. **Worker 选择逻辑**:
   - 查找 `resources["WIN"] >= 1` 的 Worker
   - 缓存 Worker 地址避免重复查询

2. **远程调用包装**:
   - 使用 `client.submit()` 提交任务
   - 指定 `workers=[...]` 和 `resources={"WIN": 1}`
   - 处理 asyncio 事件循环（Worker 端需要新建 loop）

3. **错误处理**:
   - 超时保护 (`asyncio.wait_for`)
   - 自动重试（最多 3 次）
   - 详细日志记录

---

### Phase 2: 实现剩余 32 个接口方法 (2-3 小时)

#### 方法列表

参考 `amazingdata_extended.py` 中的方法签名，逐个实现远程调用包装：

```python
# 基础数据 (BaseData)
- get_code_info()
- get_calendar()
- get_backward_factor()
- get_adj_factor()
- get_hist_code_list()
- get_stock_basic()
- get_history_stock_status()
- get_bj_code_mapping()
- get_future_code_list()

# 财务数据 (InfoData)
- get_balance_sheet()
- get_cash_flow()
- get_income()
- get_profit_express()
- get_profit_notice()
- get_share_holder()
- get_holder_num()
- get_equity_structure()
- get_equity_pledge_freeze()
- get_equity_restricted()
- get_dividend()
- get_right_issue()
- get_margin_summary()
- get_margin_detail()
- get_long_hu_bang()
- get_block_trading()
- get_industry_daily()
- get_industry_weight()

# 特色数据
- get_option_code_list()
- get_option_basic_info()
- get_option_std_ctr_specs()
- get_option_mon_ctr_spcon()
- get_etf_pcf()
- get_fund_share()
- get_fund_iopv()
- get_index_constituent()
- get_index_weight()
- get_industry_constituent()
- get_industry_base_info()
- get_treasury_yield()
```

#### 实现模板

每个方法遵循相同模式：

```python
async def get_balance_sheet(
    self,
    code_list: List[str],
    report_type: str = "1",
    **kwargs: Any
) -> Dict[str, Any]:
    """获取资产负债表（远程调用）

    Args:
        code_list: 股票代码列表
        report_type: 报表类型
        **kwargs: 其他参数

    Returns:
        资产负债表数据
    """
    return await self._call_actor(
        "get_balance_sheet",
        code_list=code_list,
        report_type=report_type,
        **kwargs
    )
```

---

### Phase 3: 配置集成 (1 小时)

#### 1. 更新配置模型

**文件**: `packages/core/config/models/amazingdata.py`

```python
class AmazingDataConfig(BaseModel):
    """AmazingData 配置"""

    # ... 现有字段 ...

    # 新增字段
    mode: Literal["local", "distributed"] = Field(
        default="local",
        description="运行模式: local=直接SDK调用, distributed=通过Dask调用"
    )

    dask_scheduler_address: Optional[str] = Field(
        default=None,
        description="Dask Scheduler 地址 (distributed 模式必需)"
    )
```

#### 2. 更新 Provider Registry

**文件**: `packages/core/infrastructure/providers/registry.py`

```python
class DataProviderRegistry:
    """数据提供者注册表"""

    async def _create_provider_instance(
        self,
        name: str,
        spec: ProviderSpec
    ) -> BaseDataProvider:
        """创建 Provider 实例"""

        if name == "amazingdata":
            config = spec.config
            mode = getattr(config, "mode", "local")

            if mode == "distributed":
                # 使用 Dask Adapter
                from distributed import Client
                from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
                    AmazingDataDaskAdapter
                )

                scheduler_addr = getattr(
                    config,
                    "dask_scheduler_address",
                    "tcp://localhost:8786"
                )

                dask_client = Client(scheduler_addr, asynchronous=True)
                provider = AmazingDataDaskAdapter(dask_client)
                logger.info(
                    "[Registry] 创建 AmazingData Dask Adapter | scheduler={}",
                    scheduler_addr
                )
            else:
                # 使用 Local 模式
                from core.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
                    AmazingDataExtended
                )
                provider = AmazingDataExtended(config)
                logger.info("[Registry] 创建 AmazingData Local Provider")

            return provider

        # ... 其他 Provider 逻辑 ...
```

#### 3. 配置文件示例

**文件**: `packages/core/config/settings.distributed.yaml.example`

```yaml
data_sources:
  providers:
    amazingdata:
      enabled: true
      priority: 1
      config:
        # 分布式模式配置
        mode: distributed
        dask_scheduler_address: "tcp://localhost:8786"

        # SDK 登录凭证（在 Worker 上使用）
        username: "your_username"
        password: "your_password"
        host: "101.230.159.234"
        port: 8600

        # Redis 配置（分布式会话管理）
        redis_url: "redis://localhost:6379"

# Dask 配置
dask:
  scheduler_address: "tcp://localhost:8786"
  windows_workers:
    enabled: true
    auto_start: true
    num_workers: 2
```

---

### Phase 4: 测试 (1-2 小时)

#### 单元测试

**文件**: `tests/unit/infrastructure/providers/test_amazingdata_dask_adapter.py`

```python
"""AmazingData Dask Adapter 单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
    AmazingDataDaskAdapter,
)


@pytest.fixture
def mock_dask_client():
    """模拟 Dask Client"""
    client = MagicMock()
    client.scheduler.address = "tcp://localhost:8786"

    # 模拟 scheduler_info
    async def mock_scheduler_info():
        return {
            "workers": {
                "tcp://worker1:1234": {
                    "resources": {"WIN": 1.0}
                }
            }
        }
    client.scheduler.scheduler_info = mock_scheduler_info

    return client


@pytest.mark.asyncio
async def test_initialize_success(mock_dask_client):
    """测试初始化成功"""
    adapter = AmazingDataDaskAdapter(mock_dask_client)

    with patch.object(adapter, "_check_actor_available", return_value=True):
        result = await adapter.initialize()

    assert result is True
    assert adapter._windows_worker == "tcp://worker1:1234"
    assert adapter._actor_available is True


@pytest.mark.asyncio
async def test_initialize_no_windows_worker(mock_dask_client):
    """测试无 Windows Worker"""
    async def mock_no_windows():
        return {"workers": {}}

    mock_dask_client.scheduler.scheduler_info = mock_no_windows

    adapter = AmazingDataDaskAdapter(mock_dask_client)
    result = await adapter.initialize()

    assert result is False
    assert adapter._windows_worker is None


@pytest.mark.asyncio
async def test_call_actor_success(mock_dask_client):
    """测试远程调用成功"""
    adapter = AmazingDataDaskAdapter(mock_dask_client)
    adapter._actor_available = True
    adapter._windows_worker = "tcp://worker1:1234"

    # 模拟 Future
    mock_future = AsyncMock()
    mock_future.__await__ = AsyncMock(return_value={"data": [1, 2, 3]})
    mock_dask_client.submit.return_value = mock_future

    result = await adapter._call_actor("query_kline", code_list=["000001.SZ"])

    assert result == {"data": [1, 2, 3]}
    mock_dask_client.submit.assert_called_once()


@pytest.mark.asyncio
async def test_call_actor_timeout_retry(mock_dask_client):
    """测试超时重试"""
    import asyncio

    adapter = AmazingDataDaskAdapter(mock_dask_client, timeout=0.1, retry_count=2)
    adapter._actor_available = True
    adapter._windows_worker = "tcp://worker1:1234"

    # 模拟超时
    async def slow_future():
        await asyncio.sleep(1)
        return {}

    mock_future = MagicMock()
    mock_future.__await__ = slow_future().__await__
    mock_dask_client.submit.return_value = mock_future

    with pytest.raises(Exception):
        await adapter._call_actor("query_kline")

    # 应该重试 2 次
    assert mock_dask_client.submit.call_count == 3


@pytest.mark.asyncio
async def test_query_kline_interface(mock_dask_client):
    """测试 query_kline 接口"""
    adapter = AmazingDataDaskAdapter(mock_dask_client)

    with patch.object(adapter, "_call_actor", return_value={"kline": []}) as mock_call:
        result = await adapter.query_kline(
            code_list=["000001.SZ"],
            period="1d",
            start_date="2024-01-01"
        )

    assert result == {"kline": []}
    mock_call.assert_called_once_with(
        "query_kline",
        code_list=["000001.SZ"],
        period="1d",
        start_date="2024-01-01",
        end_date=None,
        adjust="none"
    )
```

#### 集成测试

**文件**: `tests/integration/amazingdata/test_dask_adapter_integration.py`

```python
"""AmazingData Dask Adapter 集成测试

需要真实的 Dask Scheduler 和 Windows Worker 运行。
"""

import pytest
from distributed import Client

from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
    AmazingDataDaskAdapter,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow():
    """测试完整工作流程（需要真实环境）"""
    # 连接到真实 Scheduler
    async with Client("tcp://localhost:8786", asynchronous=True) as dask_client:
        adapter = AmazingDataDaskAdapter(dask_client)

        # 初始化
        init_ok = await adapter.initialize()
        assert init_ok, "初始化失败"

        # 查询 K 线
        result = await adapter.query_kline(
            code_list=["000001.SZ"],
            period="1d",
            start_date="2024-01-01",
            end_date="2024-01-10"
        )

        assert "data" in result or "kline" in result
        print(f"查询结果: {result}")

        # 关闭
        await adapter.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_requests():
    """测试多次请求（连接复用）"""
    async with Client("tcp://localhost:8786", asynchronous=True) as dask_client:
        adapter = AmazingDataDaskAdapter(dask_client)
        await adapter.initialize()

        # 连续 5 次请求
        for i in range(5):
            result = await adapter.query_kline(
                code_list=["000001.SZ"],
                period="1d",
                start_date="2024-01-01"
            )
            print(f"请求 {i+1} 完成")

        await adapter.shutdown()
```

---

## 验证清单

### 功能验证

- [ ] 能够找到 Windows Worker (WIN:1 资源)
- [ ] 能够验证 Actor 可用性
- [ ] 35 个 DataProvider 方法全部实现
- [ ] 远程调用成功返回数据
- [ ] 超时后能够自动重试
- [ ] 错误能够正确传播到调用方
- [ ] 配置模式切换正常 (local ↔ distributed)

### 性能验证

- [ ] 单次调用延迟 < 2 秒
- [ ] 并发 10 个请求无阻塞
- [ ] 长时间运行无内存泄漏
- [ ] Worker 重启后能够自动恢复

### 兼容性验证

- [ ] 与现有 Local 模式共存
- [ ] API 签名完全一致
- [ ] Registry 自动选择模式
- [ ] 配置文件向后兼容

---

## 依赖项

### Python 包

```toml
# pyproject.toml
[project]
dependencies = [
    "distributed>=2024.12.0",  # Dask 分布式
    # ... 现有依赖 ...
]
```

### 外部服务

1. **Dask Scheduler** (必需)
   - 地址: tcp://localhost:8786
   - 启动: `dask scheduler`

2. **Dask Worker** (必需)
   - Windows 环境
   - 资源标签: `--resources WIN=1`
   - 启动: `dask worker tcp://localhost:8786 --resources WIN=1`

3. **Redis** (必需)
   - 用于分布式会话管理
   - 地址: redis://localhost:6379

---

## 风险与缓解

### 风险 1: Worker 端事件循环问题

**问题**: Worker 端调用 async Actor 需要新建事件循环

**缓解**:

```python
def _remote_call(dask_worker):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(actor.call(method, **kwargs))
    finally:
        loop.close()
```

### 风险 2: Dask Client 连接失败

**问题**: Scheduler 不可用时初始化失败

**缓解**:

- Registry 捕获异常，降级到 Local 模式
- 添加健康检查，定期重连

### 风险 3: 方法签名不一致

**问题**: Adapter 方法签名与 AmazingDataExtended 不同

**缓解**:

- 使用相同的类型提示
- 编写接口兼容性测试
- 参考现有实现逐个验证

---

## 文档更新

### 需要更新的文档

1. **架构文档**
   - `docs/architecture/distributed_providers.md` (新建)
   - 说明 Local vs Distributed 模式

2. **配置指南**
   - `docs/configuration/data_sources.md`
   - 添加 `mode` 字段说明

3. **部署文档**
   - `docs/deployment/dask_setup.md` (新建)
   - Dask Scheduler 和 Worker 启动步骤

4. **API 文档**
   - `docs/api/amazingdata_adapter.md`
   - Dask Adapter 使用示例

---

## 时间估算

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| Phase 1 | 创建核心 Adapter 类 | 2-3 小时 |
| Phase 2 | 实现 32 个接口方法 | 2-3 小时 |
| Phase 3 | 配置集成 | 1 小时 |
| Phase 4 | 测试和验证 | 1-2 小时 |
| **总计** | | **6-9 小时** |

---

## 成功标准

### 必须达成 (P0)

- ✅ 所有 35 个方法实现并通过单元测试
- ✅ 能够成功连接 Dask Scheduler
- ✅ 能够找到并调用 Windows Worker 上的 Actor
- ✅ 配置模式切换正常工作

### 期望达成 (P1)

- ✅ 集成测试通过（需要真实环境）
- ✅ 性能满足要求（< 2s 延迟）
- ✅ 错误处理完善

### 可选达成 (P2)

- 🔲 连接池优化
- 🔲 监控指标集成
- 🔲 自动降级逻辑

---

## 参考资料

### 代码参考

- **AmazingDataExtended**: `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
- **AmazingDataActor**: `packages/core/compute/actors/amazingdata_actor.py`
- **Dask Plugin**: `packages/core/infrastructure/providers/implementations/amazingdata/dask_plugin.py`

### Dask 官方文档

- [Dask Actors](https://distributed.dask.org/en/stable/actors.html)
- [Worker Plugins](https://distributed.dask.org/en/stable/plugins.html)
- [Asynchronous Computing](https://distributed.dask.org/en/stable/asynchronous.html)

### 架构设计参考

- Circuit Breaker Router: `packages/core/infrastructure/providers/circuit_breaker_router.py`
- Capability Router: `packages/core/infrastructure/providers/capability_router.py`

---

## 联系方式

**负责人**: [待指派]

**问题反馈**: 在实施过程中遇到问题，请在 GitHub Issues 中创建 Issue，标签: `enhancement`, `dask-adapter`

**文档路径**: `docs/development/dask_adapter_implementation_plan.md`

---

**最后更新**: 2026-01-13
**版本**: 1.0
**状态**: 待实施
