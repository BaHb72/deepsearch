# 档案文档说明

档案目录用于存放历史方案、停用数据源文档及阶段性评估，供回溯参考之用，不代表当前推荐做法。

## 目录
- `config/`：存放配置相关的历史文档，如一次性的清理记录。
  - [2025-11-16-settings-dev-cleanup.md](./config/2025-11-16-settings-dev-cleanup.md)：关于 `settings.dev.yaml` 的一次性清理和整改说明。
- `datasources/`：AkShare、Cloudflare Proxy、QMT 相关资料，以及旧版 AmazingData 隔离/降级评估。
- `maintenance/`：历史清理记录与维护总结。
- `mockups/`：存放 UI 原型和概念设计的 HTML 文件。
- `operations/`：存放一次性的运维相关文档，如故障复盘、设计草案等。
  - [market_statistic_phase_update.md](./operations/market_statistic_phase_update.md)：市场统计阶段调度更新的摘记。
  - [amazingdata_login_issue_progress.md](./operations/amazingdata_login_issue_progress.md)：AmazingData 登录异常的排查进展记录。
  - [market_statistic_postmortem_followup.md](./operations/market_statistic_postmortem_followup.md)：市场统计分支的 Postmortem 跟踪。
  - [data_source_prefetch_scheduler_design.md](./operations/data_source_prefetch_scheduler_design.md)：数据源后台预取调度器的设计文档。
- `reports/`：阶段性评估、代码审计与故障分析报告。
  - [system_webui_code_review.md](./reports/system_webui_code_review.md)：WebUI 模块的代码评估报告。
  - [amazingdata_sdk_crash_report.md](./reports/amazingdata_sdk_crash_report.md)：AmazingData SDK 异常退出的情况报告。
  - [system_webui_encoding_report.md](./reports/system_webui_encoding_report.md)：WebUI 编码巡检报告。
  - [bug_2025-11-07_market_data_runtime.md](./reports/bug_2025-11-07_market_data_runtime.md)：市场行情运行异常的记录。
  - [amazingdata_info_get_stock_basic_blocking.md](./reports/amazingdata_info_get_stock_basic_blocking.md)：AmazingData InfoData.get_stock_basic 阻塞问题的复盘。

> 如果后续需要重新启用档案中的方案，请先评估其与现行架构的兼容性，并在主目录撰写最新设计文档。
