# amazingdata/dask: Redis 初始化链路统一与 shutdown 异常修复

> 日期: 2026-02-16
> 模块: providers/amazingdata, providers/registry, issues
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

1. `AmazingDataDaskAdapter.shutdown()` 在 Redis 模式下触发 `NameError: _DASK_PROCESS_POOL is not defined`。
2. `DataProviderRegistry` 的 `distributed` 分支仍按旧 Dask Client 构造 Adapter，与 Redis 队列模式不一致，存在初始化失败风险。
3. 问题追踪文档与实际状态漂移，已实施问题仍停留在 backlog。

### 现有方案的问题

- 运行时异常会打断生命周期清理。
- 两套初始化语义并存，排查成本高。
- issue 索引失真会误导优先级排序。

---

## 最终方案

### 选择

统一到 Redis 队列架构，并同步修正文档归档链路。

### 关键改动

- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
  - 删除过时 `_DASK_PROCESS_POOL` 清理逻辑
  - `_find_windows_worker()` 增加 bytes->str 兼容处理
- `packages/core/infrastructure/providers/registry.py`
  - distributed 分支改为 `redis.asyncio.from_url(...)` 构造
  - 不再创建 Dask Client
- `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py`
  - 全量迁移到 Redis 队列语义测试
  - 修正 SDK v1.0.4 周期参数断言（`day -> 10008`）
- `docs/issues/*`
  - 已实施问题从 backlog 归档至 resolved
  - 新增本次 shutdown 异常的已解决 issue
  - 更新 `docs/issues/README.md` 统计与索引

---

## 验证记录

```bash
uv run --python ./.venv/Scripts/python.exe pytest tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py -q
uv run --python ./.venv/Scripts/python.exe pytest tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py tests/unit/infrastructure/providers/implementations/test_amazingdata_param_guards.py tests/unit/infrastructure/providers/test_amazingdata_helpers.py tests/unit/webui/api/test_amazingdata_endpoints_signatures.py tests/unit/workers/test_proxy_manager.py tests/unit/providers/test_akshare_capabilities.py -q
```

结果：46 passed, 8 skipped；适配器专测 18 passed。

---

## 注意事项

- `docs/issues/backlog` 当前仍保留 2 个中优先级问题，需后续继续追踪。
- Distributed 链路虽然已统一构造方式，仍建议结合容器重建做一次端到端联调验证。

---

## 关键结论

> 先消除确定性运行时异常，再统一初始化协议，最后让问题文档与真实状态对齐，系统可维护性会显著提升。
