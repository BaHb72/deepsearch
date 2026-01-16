# AmazingData ActorWrapper 方法代理设计缺陷

> 发现日期: 2026-01-16
> 发现位置: apps/api/api/providers.py:455-486
> 类型: architecture
> 严重程度: high
> 状态: resolved
> 解决日期: 2026-01-16

---

## 问题描述

`ActorWrapper.__getattr__` 方法直接委托调用到 Actor 对象，但 Dask Actor 不支持直接方法调用，需要通过 `actor.call(method_name, **kwargs)` 方式调用。

### 现象

所有 AmazingData API 接口返回错误：`AmazingDataActor has no attribute 'xxx'`

### 影响

- 所有需要 AmazingData Provider 的 API 接口无法正常工作
- 导致 API 测试成功率极低（约 12%）

---

## 发现上下文

> 在执行 AmazingData API 全接口测试时发现此问题

运行 API 测试脚本时，发现除了少数不依赖 Actor 的接口外，其他所有接口都返回 500 错误。

---

## 相关代码

```python
# 文件: apps/api/api/providers.py
# 行号: 455-460

# 原有问题代码：
def __getattr__(self, name: str):
    # 委托所有其他调用到 Actor
    return getattr(self._actor, name)  # 错误！Dask Actor 不支持直接方法调用
```

---

## 已实施修复方案

```python
def __getattr__(self, name: str):
    # 将方法调用转换为 Actor.call() 调用
    FIRST_ARG_NAMES = {
        # BaseData 方法
        "get_code_info": "security_type",
        "get_code_list": "security_type",
        # ... 更多映射
    }

    async def method_proxy(*args, **kwargs):
        if args:
            first_arg_name = FIRST_ARG_NAMES.get(name, "arg0")
            kwargs[first_arg_name] = args[0]
            for i, arg in enumerate(args[1:], 1):
                kwargs[f"arg{i}"] = arg
        return await asyncio.wait_for(
            self._actor.call(name, **kwargs),
            timeout=30.0,
        )
    return method_proxy
```

### 待完善

- [ ] 需要完善 `FIRST_ARG_NAMES` 映射表，确保覆盖所有 SDK 方法
- [ ] 考虑从 SDK 动态获取方法签名，而非硬编码映射

### 相关文件

- `apps/api/api/providers.py`
- `packages/core/compute/actors/amazingdata_actor.py`

---

## 备注

此问题的根本原因是 Dask Actor 的调用机制与普通 Python 对象不同，需要通过 `call()` 方法间接调用。这是 Dask 分布式计算框架的设计特点。

---

## 解决记录

> 解决日期: 2026-01-16
> 解决方式: 使用 inspect.signature() 自动转换参数，消除硬编码映射表

### 最终解决方案

**核心思路**：将参数转换逻辑从 ActorWrapper（客户端）移到 Actor（服务端），使用 `inspect.signature()` 动态绑定参数。

**修改内容**：

1. **Actor 端**（`packages/core/compute/actors/amazingdata_actor.py`）
   - 修改 `call()` 方法签名支持位置参数：`async def call(self, method: str, *args, **kwargs)`
   - 使用 `inspect.signature()` 自动将位置参数转换为关键字参数
   - 容错处理：如果签名提取失败，降级到原始参数传递

2. **ActorWrapper 端**（`apps/api/api/providers.py`）
   - 删除 43 行硬编码的 `FIRST_ARG_NAMES` 映射表
   - 简化 `method_proxy`，直接传递参数：`self._actor.call(name, *args, **kwargs)`
   - 代码从 65 行缩减到 20 行（减少 69%）

### 技术亮点

- 自动化：使用 Python 内省机制，无需手动维护映射
- 健壮性：支持位置参数、关键字参数、默认值、可变参数
- 向后兼容：即使签名提取失败也能正常工作
- 可维护性：SDK 升级后无需修改代码

### 相关提交

本次修复涉及 2 个文件的改动。
