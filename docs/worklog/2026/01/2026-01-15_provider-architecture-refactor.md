# Provider: 架构重构 - 引入容器+协议模式

> 日期: 2026-01-15
> 模块: packages/core/infrastructure/providers/
> 类型: architecture

---

## 为什么要改

### 遇到的问题

1. **资源泄漏**: Provider 关闭时资源没有正确释放，导致连接池耗尽
2. **状态混乱**: 多处代码都在创建 Provider 实例，状态难以追踪
3. **测试困难**: 全局工厂模式导致无法 mock，单元测试覆盖率低
4. **耦合严重**: API 层直接依赖具体 Provider 实现，换数据源要改大量代码

### 现有方案的问题

原有的 `DataProviderFactory` 设计：

```python
# 问题代码示例
class DataProviderFactory:
    _instances = {}  # 全局状态，难以清理

    @classmethod
    def get_provider(cls, name):
        if name not in cls._instances:
            cls._instances[name] = create_provider(name)  # 创建逻辑散落各处
        return cls._instances[name]
```

问题：

- 全局 `_instances` 字典，生命周期不受控
- 没有关闭机制，进程结束才释放资源
- 无法注入不同实现进行测试

---

## 尝试过的方案

### 方案 A: 添加 cleanup 方法

**思路**: 在现有工厂上添加 `cleanup()` 方法，手动调用清理

**问题**:

- 需要记住在所有退出路径调用
- 异常时可能跳过清理
- 本质上还是手动管理，治标不治本

### 方案 B: 使用 atexit 注册清理

**思路**: 用 `atexit.register()` 自动在进程退出时清理

**问题**:

- atexit 在异步上下文中不可靠
- 无法处理 Provider 需要在应用生命周期内重启的场景
- 仍然无法解决测试问题

### 方案 C: 容器 + 协议模式（最终选择）

**思路**:

- 用 Protocol 定义接口，解耦具体实现
- 用 Container 管理实例生命周期
- 通过依赖注入获取 Provider

**优势**:

- 生命周期由容器统一管理
- 支持热重载
- 易于测试（注入 mock）
- 符合六边形架构原则

---

## 最终方案

### 选择: 容器 + 协议模式

**原因**:

1. 从根本上解决生命周期管理问题
2. 符合现代 Python 最佳实践（Protocol + DI）
3. 与 FastAPI 的依赖注入机制天然契合
4. 为未来支持多实例、动态配置打下基础

### 关键改动

#### 文件: `providers/protocols/base.py` (新增)

```python
@runtime_checkable
class DataProviderProtocol(Protocol):
    """数据提供者协议 - 定义必须实现的接口"""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def health_check(self) -> HealthStatus: ...
```

**为什么这样改**:

- 使用 Protocol 而非 ABC，不强制继承关系
- `@runtime_checkable` 支持 isinstance 检查
- 只定义最小必要接口

#### 文件: `providers/container.py` (新增)

```python
class ProviderContainer:
    def __init__(self):
        self._providers: dict[str, DataProviderProtocol] = {}
        self._lock = asyncio.Lock()

    async def shutdown_all(self) -> None:
        """统一关闭所有 Provider"""
        for provider in self._providers.values():
            await provider.disconnect()
```

**为什么这样改**:

- 单一职责：只管理 Provider 实例
- asyncio.Lock 保证并发安全
- shutdown_all 确保资源释放

#### 文件: `apps/api/api/provider_deps.py` (新增)

```python
async def get_amazingdata_provider(
    container: ProviderContainer = Depends(get_provider_container)
) -> AmazingDataProvider:
    provider = await container.get("amazingdata")
    if not await provider.health_check():
        raise HTTPException(503, "服务不可用")
    return provider
```

**为什么这样改**:

- 利用 FastAPI Depends 实现依赖注入
- 获取时自动健康检查
- 失败时返回明确的 HTTP 错误

---

## 注意事项

### 这个方案的局限

1. **迁移成本**: 现有 26+ 个 API 端点需要逐步迁移
2. **兼容层开销**: 过渡期需要维护兼容层代码
3. **学习曲线**: 团队需要理解 Protocol 和 DI 模式

### 如果要改回去

**不建议改回去**。如果必须：

1. 需要处理好异步资源的关闭
2. 考虑使用 contextlib.asynccontextmanager 管理生命周期
3. 至少保留 Protocol 定义，不要回到具体类依赖

### 相关历史

这是该模块第一次架构级重构，无历史记录。

---

## 关键结论

> **为什么是容器+协议模式**: 全局工厂无法解决生命周期管理问题，需要从架构层面引入控制反转。容器模式是管理有状态依赖的标准做法，Protocol 是 Python 3.8+ 推荐的接口定义方式。两者结合，既解决当前问题，又为未来扩展打下基础。
