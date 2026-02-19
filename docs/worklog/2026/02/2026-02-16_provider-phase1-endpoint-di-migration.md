# Provider 收敛：Phase 1 端点依赖注入迁移（第一批）

> 日期: 2026-02-16
> 模块: apps/api/api/endpoints/data, apps/api/api/proxy
> 类型: architecture-migration

---

## 为什么要改

双主路径收敛需要先从低风险入口开始，把 endpoint 层对 `apps/api/api/providers.py` 的直接依赖迁移到 `provider_deps`。

第一批目标是只替换 Provider 获取入口，不改业务逻辑。

---

## 改动范围

1. `apps/api/api/endpoints/data/data_source.py`
   - 从 `apps.api.api.providers.get_akshare_provider` 切换到
     `apps.api.api.provider_deps.get_akshare_provider`
   - 为兼容新 `AkShareProvider`（可能缺少 `name/worker_urls/worker_health`）增加安全降级处理

2. `apps/api/api/proxy.py`
   - 从旧 helper 切换到 `provider_deps.get_akshare_provider`
   - `GET /api/workers/status` 改为标准 `Depends(...)` 注入，不再手动调用 helper

3. `apps/api/api/endpoints/data/akshare_apis.py`
   - `POST /api/akshare/call` 改为 `Depends(get_akshare_provider)` 注入
   - 去除该端点对 `DataProviderFactory.get_provider_async()` 的直接调用

4. 单测
   - 新增 `tests/unit/api/test_data_source_endpoint_provider_compat.py`
   - 覆盖新旧 Provider 字段差异下的兼容行为

---

## 关键问题与处理

迁移后发现 `data_source.py` 存在隐式假设：

- Provider 一定有 `name/display_name/worker_urls/_cache_ttl`

在容器化路径下不成立，导致 `/api/data-source/config` 抛出属性错误。  
已通过“字段兜底 + 能力探测”修复，保证在不同 Provider 形态下稳定响应。

---

## 验证

```bash
uv run pytest tests/unit/api/test_data_source_endpoint_provider_compat.py tests/unit/cli/test_check_amazingdata_command.py tests/unit/infrastructure/providers/test_fastapi_integration.py -q
```

结果：8 passed。

---

## 下一步

1. 继续迁移 `apps/api/api/endpoints/data/akshare_apis.py` 中残余 `DataProviderFactory` 入口。
2. 梳理 `apps/api/api/providers.py` 的可替换函数，按 endpoint 分批切换。
