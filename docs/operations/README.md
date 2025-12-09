# 运维文档索引

> 更新时间：2025-11-16

## 目录结构
- `runbooks/`
  ：常见问题处理手册，目前收录 [实时数据源故障切换 Runbook](./runbooks/realtime_source_failover.md)、[前端超时应急方案](./runbooks/frontend_timeout_solution.md)、[Redis 启动排查](./runbooks/redis_startup.md)、[实时看板断流/数据缺失处理指南](./runbooks/realtime_board_subscription.md)
  以及 [AmazingData 进程崩溃与日志排查指南](./runbooks/amazingdata_process_troubleshooting.md)。

## 使用建议
1. 发布前先执行发布清单，确认监控、日志、通知通道正常。
2. 数据源相关故障请搭配 `docs/datasources/amazingdata/*` 与监控手册一并查阅。
3. 新增应急手册后，记得更新本索引和 `docs/overview/document_index.md`。
