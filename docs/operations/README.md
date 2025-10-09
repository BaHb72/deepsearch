# 运维文档索引

> 更新时间：2025-10-04

## 目录结构
- `monitoring/`：监控与指标采集方案，例如 [数据源监控手册](./monitoring/data_source_monitoring.md)。
- `runbooks/`：常见问题处理手册，目前收录 [前端超时应急方案](./runbooks/frontend_timeout_solution.md) 与 [Redis 启动排查](./runbooks/redis_startup.md)。
- 根目录文档：
  - [资源管理改进记录](./resource_management_improvements.md)
  - [发布前检查清单（2025-10-02）](./pre_submission_status_20251002.md)

## 使用建议
1. 发布前先执行发布清单，确认监控、日志、通知通道正常。
2. 数据源相关故障请搭配 `docs/datasources/amazingdata/*` 与监控手册一并查阅。
3. 新增应急手册后，记得更新本索引和 `docs/overview/document_index.md`。
