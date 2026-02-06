# AmazingData: 单连接约束与配置覆盖问题修复

> 日期: 2026-01-23
> 模块: amazingdata, dask, config
> 类型: bugfix, documentation

---

## 为什么要改

### 遇到的问题

启动服务时出现两个错误：

```
AmazingData 初始化超时，将使用其他数据源
AmazingData provider 未在 ProviderContainer 中注册
```

导致 AmazingData 数据源无法正常使用，系统降级到其他数据源。

### 现有方案的问题

1. **配置覆盖**：`infrastructure.dev.yaml` 的 `num_workers: 2` 覆盖了 `settings.dev.yaml` 的 `num_workers: 1`
2. **超时不足**：30 秒超时无法覆盖 Dask 集群初始化的 25-35 秒

---

## 根本原因分析

### AmazingData SDK 单连接限制

AmazingData SDK 在初始化时建立与服务器的长连接，该连接是**有状态的**且绑定到特定账号。当多个 Dask Worker 同时尝试初始化 SDK 时：

```
Worker-0: 初始化 SDK -> 建立连接 A
Worker-1: 初始化 SDK -> 建立连接 B -> 服务器踢掉连接 A
Worker-0: Actor 调用失败（连接已断开）
```

这是一个 **SDK 设计约束**，不是我们代码的 bug。

### 配置加载顺序

配置加载器（`packages/core/config/loader.py`）使用深度合并：

```
1. 加载 settings.dev.yaml      -> num_workers: 1
2. 加载 infrastructure.dev.yaml -> num_workers: 2 (覆盖!)
最终配置: num_workers: 2
```

这导致即使 `settings.dev.yaml` 正确配置为 1，最终仍然启动了 2 个 Worker。

---

## 尝试过的方案

### 方案 A: 只改 settings.dev.yaml

**思路**: 在 settings.dev.yaml 中设置 num_workers: 1

**问题**: 无效，会被 infrastructure.dev.yaml 覆盖

### 方案 B: 添加配置冲突检测

**思路**: 在配置加载时检测关键配置被覆盖的情况并警告

**问题**: 增加复杂度，当前问题可以用更简单的方式解决

---

## 最终方案

### 选择: 直接修复 infrastructure.dev.yaml + 增加超时 + 文档化约束

**原因**:

1. 最小改动原则：只改必要的配置
2. 防止再犯：在 CLAUDE.md 中文档化约束，确保每次都能看到

### 关键改动

#### 文件: `packages/core/config/infrastructure.dev.yaml:114`

```yaml
# 改之前
num_workers: 2

# 改之后
num_workers: 1  # AmazingData SDK 只支持单连接，多 Worker 会导致竞争
```

**为什么这样改**: 确保只有一个 Worker 初始化 AmazingData SDK

#### 文件: `apps/api/services/market_data_runtime.py:385`

```python
# 改之前
ready = await dask_manager.wait_amazingdata_ready(timeout=30.0)

# 改之后
ready = await dask_manager.wait_amazingdata_ready(timeout=60.0)
```

**为什么这样改**: Dask 集群初始化需要 25-35 秒，60 秒超时留出 1.5-2 倍缓冲

#### 文件: `CLAUDE.md`

添加了 "数据源限制与注意事项" 章节，包含：

- AmazingData SDK 单连接限制的技术背景
- 配置要求（num_workers 必须为 1）
- 超时配置表
- 常见错误及解决方案
- 验证方法

---

## 注意事项

### 这个方案的局限

1. **单 Worker 是性能瓶颈**：所有 AmazingData 请求都串行处理，如果 SDK 支持多连接可以优化
2. **配置分散在两个文件**：需要同时检查 settings.yaml 和 infrastructure.yaml

### 如果要改回去

**永远不要把 num_workers 改回 2 或更大**，除非 AmazingData SDK 升级支持多连接。

如果确实需要多个 Worker（例如分离计算任务），应该：

1. 只让一个 Worker 初始化 AmazingData Actor
2. 其他 Worker 专门用于无状态计算任务
3. 通过 `resources` 标签区分任务路由

### 相关历史

- `2026-01-17_amazingdata_dask-proxy-registration.md` - Dask 代理注册架构
- `2026-01-17_amazingdata_redis-result-passing.md` - 使用 Redis 传递结果

---

## 关键结论

> AmazingData SDK 的单连接限制是硬性约束，必须通过 `num_workers: 1` 保证。配置分层加载时要注意覆盖顺序，关键约束应文档化到 CLAUDE.md 确保不会被遗忘。
