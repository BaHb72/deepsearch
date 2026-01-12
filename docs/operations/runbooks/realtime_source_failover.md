# 实时数据源故障切换 Runbook

> 适用范围：WebUI 实时链路 + `MarketDataRealtimePipeline`

## 1. 快速预检

1. 运行 `uv run deepsearch check-realtime --env <env>`，检查每个 adapter 的 `status`。
2. 若状态为 `failed/skipped`，记录 `error` 字段并同步至运维群。
3. 登录目标机器，确认 `logs/webui/server.log`、`logs/providers/amazingdata*.log` 是否存在新的报警。

## 2. 人工切换流程

1. 编辑 `deepsearch/config/settings.<env>.yaml`：
   - 在 `data_sources.realtime.adapters` 中将待启用 adapter 的 `enabled` 改为 `true`，必要时调整 `priority`。
   - 若需临时下线 adapter，将 `enabled` 置为 `false`，或提升其他 adapter 的优先级。
   - `alert_policy.channels` 更新为当前值班渠道，确保告警可达。
2. 执行 `uv run deepsearch check-realtime --env <env>`，确认新的 adapter 能通过探活。
3. 重启 WebUI/后台进程：
   - `uv run deepsearch run <env> --mode webui --no-frontend`（或使用现有进程管理脚本）。
   - 观察启动日志中 `Realtime adapter ...` 是否显示为期望值。
4. 登录前端页面，访问 `/api/market/live/board-overview`，确认 `data_source` 字段已经更新。

## 3. 回滚策略

1. 若切换后的 adapter 出现异常，将配置文件恢复为原先的 `priority/enable` 状态。
2. 重新执行 `check-realtime` 与进程重启步骤。
3. 在 `docs/development/realtime_data_source_unification.md` 中登记此次切换原因与影响面。

## 4. 常见排障

| 症状 | 排查步骤 | 解决方案 |
| --- | --- | --- |
| `check-realtime` 一直返回 `skipped` | 检查 `data_sources.realtime.adapters` 是否全部 `enabled=false` | 至少启用一个 adapter 并重新探活 |
| `failed` 且 `error` 为网络超时 | 核对服务器到数据源的网络（Telnet、`Test-NetConnection`） | 切换到 AkShare/Cloudflare，或调整 `health_check_interval` 延长探活时间 |
| WebUI API 仍报 `DATA_SOURCE_OFFLINE` | 确认 Redis 中缓存是否更新，必要时执行 `uv run deepsearch check-realtime` 并重启 | 清理 Redis 6 号库后重启实时进程 |

## 5. 参考

- 适配器能力矩阵：`docs/datasources/realtime_capability_matrix.md`
- 端口规范：`docs/architecture/realtime_ports.md`
- 配置结构：`README.md` → “实时数据源编排” 小节
