# AmazingData 直连 API 端点 90 秒超时

- **发现日期**: 2026-02-07
- **严重程度**: 严重
- **影响范围**: `/api/amazingdata/*` 所有端点

## 问题描述

AmazingData 的所有直连 API 端点（如 `/api/amazingdata/basic/code-list`, `/api/amazingdata/basic/calendar`）均超时 90 秒后返回 504 错误：

```json
{
  "success": false,
  "error": "504: AmazingData provider 获取超时 (90s)，可能是 TGW 连接问题"
}
```

而同一时间，AmazingData 通过 Dask Worker 路径（启动时使用的）仍然正常工作（SDK 调用成功，耗时 ~1s）。

## 根本原因

AmazingData API 端点使用 `get_provider_async()` 获取 Provider 实例，这条路径尝试创建新的 AmazingData Provider 连接，而非复用 Dask Worker 中已有的连接。由于 AmazingData SDK 有单连接限制，新连接创建会被阻塞或失败。

**两条代码路径**：

1. **Dask 路径 (正常)**: `DaskAdapter` -> Redis 队列 -> Worker Actor -> SDK 调用 -> 成功
2. **直连路径 (超时)**: `get_provider_async()` -> 尝试直接创建 Provider -> 超时

## 日志证据

```
[DEBUG] get_provider_async 超时 (90s)     # API 端点路径
[AmazingData/Dask] 调用成功 | method=get_calendar | 耗时=1.06s   # Dask 路径同时正常
```

## 影响

- `/api/amazingdata/basic/calendar` -> 90s 超时
- `/api/amazingdata/basic/code-list` -> 90s 超时
- 所有 `/api/amazingdata/*` 端点均受影响

## 建议修复

统一 AmazingData 的 Provider 获取路径：API 端点应通过 Dask adapter 路径获取数据，而非尝试创建新的直连 Provider。

## 相关问题

- `2026-01-18_amazingdata-timeout-config-unused.md` -- 超时配置未传递到 DaskAdapter
- `2026-01-18_amazingdata-first-call-timeout.md` -- 首次调用 SDK 登录超时
- `2026-02-07_amazingdata-health-check-unknown-status.md` -- 同属 Dask adapter 双轨问题

**关键文件**：

- `apps/api/api/endpoints/amazingdata/base.py:61` (get_provider_async 超时点)
- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py` (正常工作的路径)
