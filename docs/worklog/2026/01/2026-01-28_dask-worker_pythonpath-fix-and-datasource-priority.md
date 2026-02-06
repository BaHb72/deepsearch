# Dask Worker: PYTHONPATH 修复与数据源优先级调整

> 日期: 2026-01-28
> 模块: dask-worker-manager, market_data
> 类型: bugfix, config

---

## 为什么要改

### 遇到的问题

启动后端时出现两个层面的问题：

1. **Plugin 注册失败**（阻塞性）：

   ```
   ModuleNotFoundError: No module named 'core.infrastructure.providers.implementations'
   ```

   导致 AmazingData 和 MiniQMT 都无法在 Dask Worker 上初始化。

2. **AkShare 被限流**：Cloudflare Worker 代理返回 520 错误，AkShare 作为 fallback 被调用但失败。

### 现有方案的问题

原有代码（`dask_worker_manager.py:804-821`）：

```python
project_root = Path(__file__).parent.parent.parent.parent  # 到 deepsearch 根目录
pythonpath_parts = [str(project_root)]

# 添加虚拟环境的 site-packages 路径
site_packages = site.getsitepackages()
if site_packages:
    pythonpath_parts.extend(site_packages)
```

问题分析：

1. **缺失 packages 目录**：只添加了项目根目录 `deepsearch/`，但代码结构是 `deepsearch/packages/core/...`，导致 `import core.xxx` 失败
2. **site.getsitepackages() 不可靠**：UV 虚拟环境下可能返回 None 或错误路径

---

## 尝试过的方案

### 方案 A: 只添加 packages 目录

**思路**: 在现有代码中增加一行 `pythonpath_parts.append(packages_dir)`

**问题**:

- 不解决 `site.getsitepackages()` 在 UV 下不可靠的问题
- 没有去重机制，可能导致路径重复
- 代码可维护性差

### 方案 B: 完整重构 PYTHONPATH 构建逻辑

**思路**: 创建专门的方法，使用多重 fallback 策略

**优势**:

- 解决 UV 虚拟环境兼容性问题
- 代码清晰，便于调试
- 支持去重，避免路径冗余

---

## 最终方案

### 选择: 方案 B - 完整重构

**原因**:

1. 一次性解决 PYTHONPATH 相关的所有已知问题
2. 符合项目的"第一性原理"方法论
3. 为未来可能的环境变化（如切换到其他包管理器）提供更好的兼容性

### 关键改动

#### 文件: `packages/core/compute/dask_worker_manager.py`

**新增 `_get_site_packages_paths()` 方法**:

使用 4 重 fallback 策略获取 site-packages：

1. `site.getsitepackages()` - 标准方法
2. `sysconfig.get_path('purelib')` - UV 虚拟环境更可靠
3. 从 `sys.prefix` 推断 - Windows/Unix 通用
4. 从 `sys.path` 提取 - 最后兜底

**新增 `_build_pythonpath()` 方法**:

确保包含：

1. 项目根目录（`deepsearch/`）
2. **packages 目录**（`deepsearch/packages/`）- 关键修复点
3. site-packages 路径（多重 fallback）
4. 已有的 PYTHONPATH（保留用户自定义）

**替换原有代码**:

```python
# 改之前（约 18 行）
project_root = Path(__file__).parent.parent.parent.parent
pythonpath_parts = [str(project_root)]
site_packages = site.getsitepackages()
if site_packages:
    pythonpath_parts.extend(site_packages)
# ...

# 改之后（1 行调用）
env["PYTHONPATH"] = self._build_pythonpath(worker_name)
```

**预期 PYTHONPATH 格式**:

```
D:\Stock\code\deepsearch;D:\Stock\code\deepsearch\packages;D:\Stock\code\deepsearch\.venv\Lib\site-packages
```

#### 文件: `packages/core/config/market_data.dev.yaml`

调整数据源优先级，让 AmazingData 作为主数据源，AkShare 作为 fallback：

| 配置项 | 修改前 | 修改后 |
|--------|--------|--------|
| `kline.scenarios.historical.priority` | `[akshare, amazingdata]` | `[amazingdata, akshare]` |
| `kline.by_timeframe."1d"` | `[akshare, amazingdata]` | `[amazingdata, akshare]` |
| `stock_list.priority` | `[akshare]` | `[miniqmt, amazingdata, akshare]` |

---

## 注意事项

### 这个方案的局限

1. **多重 fallback 增加复杂度**：虽然更健壮，但调试时需要理解 4 种获取路径的方式
2. **日志量增加**：为了便于诊断，增加了较多的 debug/info 日志

### 如果要改回去

1. 如果确认只使用标准 venv（非 UV），可以简化回 `site.getsitepackages()` 单一方法
2. 如果项目结构变化（如 packages 目录改名），需要更新 `_build_pythonpath()` 中的路径计算

### 相关历史

- `2026-01-17_pyproject_package-discovery.md`: 之前遇到过类似的包发现问题，当时是 pyproject.toml 配置问题
- `2026-01-19_dask-worker_nanny-compatibility-fix.md`: 之前修复过 Nanny 无法继承虚拟环境的问题，这次是更根本的 PYTHONPATH 问题

### AkShare 保留理由

虽然 AkShare 被限流，但仍保留作为最后 fallback：

1. AmazingData 只支持单连接，连接中断时需要备用
2. AmazingData 历史数据 365 天，AkShare 3650 天（超长历史仍需 AkShare）
3. 涨停/跌停池等特殊数据 AmazingData 不直接支持

---

## 关键结论

> **PYTHONPATH 问题的本质是 Dask Worker 子进程不继承父进程的动态路径修改**（如 `.pth` 文件）。必须通过环境变量显式传递完整路径，特别是 `packages` 目录。UV 虚拟环境的 site-packages 路径获取需要多重 fallback 策略。

---

---

## 追加修复：DaskWorkerManager 单例问题

在验证 PYTHONPATH 修复后，发现了另一个问题：`AmazingData 代理注册超时`。

### 问题现象

```
等待 AmazingData Plugin 就绪...
等待 AmazingData Plugin 就绪超时 (60.0s)
AmazingData provider 未在 ProviderContainer 中注册
```

### 根因分析

两个模块使用了**不同的 DaskWorkerManager 实例**：

| 模块 | 获取方式 | 实例 |
|------|----------|------|
| `DaskClusterManager._start_workers()` | `DaskWorkerManager()` | 新实例 A |
| `DaskInitStateManager._register_amazingdata_adapter()` | `get_dask_worker_manager()` | 单例实例 B |

这导致：

- 实例 A 的 `_amazingdata_plugin_ready` Event 被 `set()`
- 实例 B 的 Event **从未被 set**，导致永远等待超时

### 修复

**文件**：`packages/core/compute/dask_cluster_manager.py`

```python
# 改之前
async def _start_workers(self) -> bool:
    from core.compute.dask_worker_manager import DaskWorkerManager
    if self._worker_manager is None:
        self._worker_manager = DaskWorkerManager()  # 新实例！
    return await self._worker_manager.start()

# 改之后
async def _start_workers(self) -> bool:
    from core.compute.dask_worker_manager import get_dask_worker_manager
    if self._worker_manager is None:
        self._worker_manager = await get_dask_worker_manager()  # 单例！
    return await self._worker_manager.start()
```

### 验证结果

修复后日志显示：

- `AmazingData Plugin 就绪事件已触发` - Event 立即返回
- `AmazingData Dask 代理已注册到 ProviderContainer`
- `Dask 初始化完成: 完全就绪`

---

## 验证方法

1. 启动后端：`uv run python -m apps.api.server`
2. 检查日志应显示：
   - `PYTHONPATH 构建完成 | paths_count=N | 包含 packages=True`
   - `AmazingData Plugin 就绪事件已触发`（关键：应立即出现）
   - `AmazingData Dask 代理已注册到 ProviderContainer`
   - `Dask 初始化完成: 完全就绪`
3. 测试 API：`GET http://localhost:8000/api/stock/list` 应使用 AmazingData
