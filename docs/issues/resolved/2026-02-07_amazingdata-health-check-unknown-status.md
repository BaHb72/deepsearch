# AmazingData ProviderContainer 健康检查始终显示 "状态未知"

- **发现日期**: 2026-02-07
- **严重程度**: 低
- **影响范围**: `/api/providers/amazingdata/health`

## 问题描述

通过 `/api/providers/amazingdata/health` 查询 AmazingData 的健康状态时，始终返回：

```json
{
  "provider": "amazingdata",
  "status": "unknown",
  "healthy": false,
  "message": "状态未知"
}
```

而实际上 AmazingData 通过 Dask Worker 路径正常工作（启动日志和 Dask 状态均确认就绪）。

## 根本原因

AmazingData 在 ProviderContainer 中注册的是 `DaskAdapter`（代理模式），而非直连的 SDK Provider。`DaskAdapter` 的健康检查实现可能没有正确反映底层 Worker 的实际健康状态。

Dask 初始化状态（`/api/system/dask/init-status`）正确显示 `amazingdata.ready: true`，但这个信息没有传递到 ProviderContainer 的健康检查中。

## 影响

- 运维监控可能错误地将 AmazingData 标记为不可用
- 不影响实际数据获取功能

## 建议修复

让 `DaskAdapter` 的 `health_check()` 方法检查 Dask Worker 的实际状态（通过 `DaskInitManager.get_status()` 或 Redis 连通性测试）。

## 相关问题

- `2026-02-07_amazingdata-api-endpoint-timeout.md` -- 同属 AmazingData Dask adapter 双轨问题
- `2026-01-18_datasource-access-failures.md` -- 数据源健康状态降级

**关键文件**：

- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py` (health_check 实现)
- `packages/core/compute/dask_init_state.py` (实际状态管理)
- `packages/core/infrastructure/providers/container.py` (ProviderContainer 健康检查)
