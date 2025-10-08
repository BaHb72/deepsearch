# 数据源 API 前端映射关系

更新日期：2025-09-26

## 核心结论
- `/api/data-sources/*` 端点已全部由 `deepsearch/webui/api/endpoints/datasources/datasource_manager.py` 提供，前端 `dataSource.ts` 已对接新的响应封装。
- 旧版 `data_source_status.py` 与 `dataSource.js` 已移除，避免路径和功能重复。
- 后端统一构建监控数据（overview/sources/timeline/alerts），前端 `DataSourceMonitor.tsx` 直接消费标准结构，支持实时趋势图与状态摘要。

## 前后端路径映射

| 功能             | 前端请求路径            | 后端实现                                     | 状态 |
|------------------|-------------------------|----------------------------------------------|------|
| 获取监控视图     | `/data-sources/monitor` | `datasource_manager.get_data_source_monitor` | ✅ 已实现 |
| 获取状态快照     | `/data-sources/status`  | `datasource_manager.get_data_source_status`  | ✅ 已实现 |
| 获取数据源列表   | `/data-sources/list`    | `datasource_manager.list_data_sources`       | ✅ 已实现 |
| 单源自检         | `/data-sources/test/{source}` | `datasource_manager.test_data_source`    | ✅ 已实现 |
| 切换主数据源     | `/data-sources/switch`  | `datasource_manager.switch_primary_source`   | ✅ 已实现 |
| 刷新缓存         | `/data-sources/cache/refresh` | `datasource_manager.refresh_data_source_cache` | ✅ 已实现 |
| 查询配置         | `/data-sources/config/{source}` | `datasource_manager.get_data_source_config` | ✅ 已实现 |
| 更新配置         | `/data-sources/config/{source}` (PUT) | `datasource_manager.update_data_source_config` | ✅ 已实现 |
| 查询指标（可选） | `/data-sources/metrics` | `datasource_manager.get_data_source_metrics` | ✅ 已实现 |
| 访问历史         | `/data-sources/history` | `datasource_manager.get_data_source_history` | ✅ 已实现 |
| 错误记录         | `/data-sources/errors`  | `datasource_manager.get_data_source_errors`  | ✅ 已实现 |

> 说明：旧版 `/api/data/source/*` 路径已下线，不再返回 410，而是直接响应 404。

## 前端改动要点
- `src/api/dataSource.ts` 改为 `async` 调用，统一通过 `unwrapResponse` 解析 API 包装格式。
- `DataSourceMonitor.tsx` 直接消费后端提供的 `overview/sources/timeline/alerts/statusSummary`，并将折线图、请求分布等数据来源统一到后端。
- 删除遗留的 `dataSource.js`，避免 CommonJS/TS 混用导致重复逻辑。

## 后续事项
- [ ] 评估 `/api/monitor/datasource*` 与 `/api/monitor/data-sources*` 历史监控接口，可视化整合后考虑归档。
- [ ] 为 `/api/data-sources/*` 增补更细粒度的权限与速率限制策略。
- [ ] 根据新的响应结构补充 API 文档示例，保持与 `docs/api/README.md` 同步。

## 版本记录

| 版本 | 日期       | 说明 |
|------|------------|------|
| 1.0  | 2025-09-26 | 统一数据源管理路由，实现前后端映射闭环 |
