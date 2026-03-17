# Provider 架构重构 - Phase 4 实施计划

## 规划日期

2026-01-15

## Phase 4 目标

逐步将现有 API 从旧的 `DataProviderFactory` 迁移到新的 `ProviderContainer`

## 当前状况分析

### 1. 旧架构分析

**核心文件**: `apps/api/api/providers.py`

**设计模式**: 全局单例 Factory

```python
class DataProviderFactory:
    _instances: MutableMapping[str, Any] = {}  # 全局单例
    _lock: Lock = Lock()  # 线程锁

    @classmethod
    async def get_provider_async(cls, provider_type: ProviderKey = "akshare") -> Any:
        # 单例创建逻辑...
```

**问题**:

1. **全局可变状态**: `_instances` 是类变量，所有请求共享
2. **测试困难**: 全局状态导致测试间相互污染
3. **生命周期管理不明确**: 依赖 `atexit.register` 清理资源
4. **与新架构重复**: 新的 `ProviderContainer` 已经实现了更好的管理

### 2. 使用情况统计

通过代码搜索发现：

- **22 个文件**使用 `from.*providers.*import|get_provider`
- **26 个文件**直接使用 Provider 类（AmazingData, MiniQMT, AkShare）

**关键使用模式**:

```python
# 模式 1: 直接调用 Factory
provider = await DataProviderFactory.get_provider_async("amazingdata")

# 模式 2: 使用依赖注入辅助函数
from apps.api.api.providers import get_akshare_provider

@router.get("/endpoint")
async def endpoint(provider = Depends(get_akshare_provider)):
    ...

# 模式 3: 自定义 Provider 获取函数
async def get_amazingdata_provider():
    provider = await DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)
    # 额外逻辑...
```

## Phase 4 实施策略

### 策略选择: 渐进式迁移（推荐）

**不采用**:

- ❌ 一次性全部替换 - 风险太高
- ❌ 完全重写 API - 工作量太大

**采用**:

- ✅ 双轨运行 - 新旧架构共存
- ✅ 逐步迁移 - 从低风险 API 开始
- ✅ 兼容层 - 提供过渡期支持

### 实施步骤

#### Step 1: 创建兼容层（优先级：高）

**目标**: 让 `ProviderContainer` 可以作为 `DataProviderFactory` 的替代品

**文件**: `packages/core/infrastructure/providers/integration/compat.py`

**实现**:

```python
"""
向后兼容层 - 允许旧代码逐步迁移到新架构
"""
from typing import Any

from ..container import ProviderContainer
from .fastapi import get_provider_container

class ProviderFactoryCompat:
    """DataProviderFactory 兼容层"""

    @classmethod
    async def get_provider_async(
        cls,
        provider_type: str,
        container: ProviderContainer | None = None
    ) -> Any:
        """兼容旧的 get_provider_async 接口"""
        if container is None:
            # 尝试从 FastAPI app.state 获取容器
            # 如果失败，fallback 到旧的 DataProviderFactory
            from apps.api.api.providers import DataProviderFactory as OldFactory
            return await OldFactory.get_provider_async(provider_type)

        # 使用新容器
        normalized_type = provider_type.lower().strip()
        try:
            return await container.get(normalized_type)
        except Exception:
            # 如果容器中没有，尝试创建
            from core.config import get_config
            config = get_config()
            if hasattr(config, "data_sources"):
                ds_config = config.data_sources.get(normalized_type)
                if ds_config:
                    return await container.create_and_register(
                        normalized_type, ds_config
                    )
            raise
```

#### Step 2: 更新 FastAPI 依赖注入函数（优先级：高）

**目标**: 提供新的依赖注入函数，使用 `ProviderContainer`

**文件**: `apps/api/api/deps.py` （已存在）或创建新文件 `apps/api/api/provider_deps.py`

**实现**:

```python
"""
Provider 依赖注入（新架构）
"""
from fastapi import Depends, Request, HTTPException
from packages.core.infrastructure.providers.container import ProviderContainer

async def get_provider_container(request: Request) -> ProviderContainer:
    """获取 Provider 容器"""
    container = getattr(request.app.state, "provider_container", None)
    if container is None:
        raise HTTPException(
            status_code=503,
            detail="ProviderContainer 未初始化"
        )
    return container

async def get_amazingdata_provider_new(
    container: ProviderContainer = Depends(get_provider_container)
):
    """获取 AmazingData Provider（新架构）"""
    try:
        return await container.get("amazingdata")
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AmazingData Provider 不可用: {e}"
        )

async def get_akshare_provider_new(
    container: ProviderContainer = Depends(get_provider_container)
):
    """获取 AkShare Provider（新架构）"""
    try:
        return await container.get("akshare")
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AkShare Provider 不可用: {e}"
        )

async def get_miniqmt_provider_new(
    container: ProviderContainer = Depends(get_provider_container)
):
    """获取 MiniQMT Provider（新架构）"""
    try:
        return await container.get("miniqmt")
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"MiniQMT Provider 不可用: {e}"
        )
```

#### Step 3: 迁移示范 API 端点（优先级：中）

**选择标准**:

- 使用频率低（降低影响范围）
- 逻辑简单（减少迁移风险）
- 代表性强（作为迁移模板）

**候选端点**:

1. `/api/providers` - 列出所有 Provider（新增）
2. `/api/providers/{name}/health` - Provider 健康检查（新增）
3. `/api/data/stock/list` - 股票列表（迁移现有）

**迁移模板**:

```python
# 旧代码
from apps.api.api.providers import get_akshare_provider

@router.get("/stocks")
async def get_stocks(provider = Depends(get_akshare_provider)):
    data = await provider.get_stock_list()
    return data

# 新代码
from apps.api.api.provider_deps import get_akshare_provider_new

@router.get("/stocks")
async def get_stocks(provider = Depends(get_akshare_provider_new)):
    data = await provider.get_stock_list()
    return data
```

#### Step 4: 添加监控和健康检查 API（优先级：中）

**新增端点**:

**文件**: `apps/api/api/endpoints/providers/management.py` (新建)

```python
"""
Provider 管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from packages.core.infrastructure.providers.container import ProviderContainer
from packages.core.infrastructure.providers.protocols.lifecycle import HealthStatus
from apps.api.api.provider_deps import get_provider_container

router = APIRouter(prefix="/api/providers", tags=["Providers"])

@router.get("")
async def list_providers(
    container: ProviderContainer = Depends(get_provider_container)
):
    """列出所有已加载的 Provider"""
    providers = container.list_providers()
    return {
        "providers": providers,
        "count": len(providers)
    }

@router.get("/{name}/health")
async def check_provider_health(
    name: str,
    container: ProviderContainer = Depends(get_provider_container)
):
    """检查指定 Provider 的健康状态"""
    try:
        status = await container.health_check(name)
        return {
            "provider": name,
            "status": status.value,
            "healthy": status == HealthStatus.HEALTHY
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{name}/reload")
async def reload_provider(
    name: str,
    container: ProviderContainer = Depends(get_provider_container)
):
    """重新加载指定 Provider"""
    try:
        # 停止现有 Provider
        provider = await container.get(name)
        await container._lifecycle.stop(provider)

        # 重新创建
        from core.config import get_config
        config = get_config()
        ds_config = config.data_sources.get(name)

        if not ds_config:
            raise HTTPException(
                status_code=400,
                detail=f"配置中未找到 Provider: {name}"
            )

        await container.create_and_register(name, ds_config)

        return {"status": "success", "provider": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Step 5: 更新文档和示例（优先级：低）

**更新内容**:

1. API 文档 - 说明新的依赖注入方式
2. 迁移指南 - 提供迁移步骤和示例
3. 最佳实践 - 推荐使用新架构

## 风险评估

### 高风险点

1. **向后兼容性破坏**
   - **风险**: 现有 API 停止工作
   - **缓解**: 双轨运行，旧代码继续使用 `DataProviderFactory`

2. **性能退化**
   - **风险**: 新架构性能不如旧架构
   - **缓解**: 性能测试，必要时优化

3. **未预见的依赖**
   - **风险**: 某些代码依赖 `DataProviderFactory` 的特定行为
   - **缓解**: 充分测试，逐步迁移

### 中风险点

1. **配置不一致**
   - **风险**: 新旧架构使用不同配置
   - **缓解**: 统一配置源（`data_sources.yaml`）

2. **状态管理差异**
   - **风险**: 新旧架构的 Provider 实例状态不同步
   - **缓解**: 在迁移期间，优先使用一种架构

## 成功标准

### Phase 4 完成标准

- [ ] 兼容层实现完成
- [ ] 新的依赖注入函数可用
- [ ] 至少 3 个示范 API 迁移成功
- [ ] Provider 管理 API 端点可用
- [ ] 所有测试通过
- [ ] 文档更新完成

### 质量标准

- [ ] 新代码测试覆盖率 > 80%
- [ ] 迁移后的 API 性能无退化
- [ ] 旧 API 继续正常工作（向后兼容）

## 实施时间线

| 步骤 | 预计工作量 | 优先级 |
|------|-----------|--------|
| Step 1: 兼容层 | 2 小时 | 高 |
| Step 2: 依赖注入 | 1 小时 | 高 |
| Step 3: 迁移示范 | 2 小时 | 中 |
| Step 4: 管理 API | 1 小时 | 中 |
| Step 5: 文档 | 1 小时 | 低 |
| **总计** | **7 小时** | |

## 下一步行动

1. 创建兼容层 (`packages/core/infrastructure/providers/integration/compat.py`)
2. 创建新的依赖注入函数 (`apps/api/api/provider_deps.py`)
3. 创建 Provider 管理 API (`apps/api/api/endpoints/providers/management.py`)
4. 迁移 1-2 个示范 API 端点
5. 运行端到端测试验证

## 备注

**重要**: Phase 4 是**渐进式迁移**，不是**全面重写**。目标是让新旧架构共存，逐步迁移，最终完全替换旧架构。

**时间规划**: 建议分多次迭代完成，每次迭代迁移少量 API，确保稳定性。
