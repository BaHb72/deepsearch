# Provider 双路径收敛计划（2026-02-16）

## 目标

将 `apps/api/api/providers.py` 旧工厂链路逐步收敛到 `ProviderContainer + provider_deps`，消除双轨并存。

## 当前盘点

基于代码检索，仍存在大量旧入口引用，包括但不限于：

- `apps/api/api/endpoints/data/data_source.py`
- `apps/api/api/endpoints/data/akshare_apis.py`
- `apps/api/api/endpoints/trading/market.py`
- `apps/api/api/endpoints/trading/chart.py`
- `apps/api/api/endpoints/amazingdata/amazingdata_api.py`
- `apps/api/api/endpoints/qmt/qmt.py`
- `apps/api/api/endpoints/qmt/miniqmt.py`
- `apps/api/api/proxy.py`
- `packages/core/infrastructure/providers/implementations/qmt/miniqmt.py`

## 分阶段执行

### Phase 1（低风险替换）

1. 统一 endpoint 依赖注入：
   - 读操作路由优先替换到 `apps/api/api/provider_deps.py`
   - 不改业务逻辑，只替换 provider 获取入口
2. 对 `apps/api/api/providers.py` 添加明确 deprecate 注释与告警日志

### Phase 2（兼容层收口）

1. 将 `packages/core/infrastructure/providers/integration/compat.py` 设为唯一过渡入口
2. 旧 `DataProviderFactory.get_provider_async()` 内部改为优先代理到容器实现

### Phase 3（退役旧链路）

1. 删除不再被引用的旧 Provider 构建/缓存代码
2. 合并重复健康检查与状态缓存逻辑
3. 以端到端测试覆盖关键 API 后下线 legacy 分支

## 验收标准

1. `rg "from apps\\.api\\.api\\.providers"` 仅剩兼容层或测试文件
2. 统一由容器负责创建、健康检查、关闭
3. `apps/api/api/providers.py` 不再承担主路径职责
