# DeepSearch 架构改进路线图

## 背景

为落实最新架构评审结论，本路线图收敛关键改进项并提供实时进度跟踪框架，确保系统朝“单机部署 + AmazingData 唯一外部数据源”的目标演进，同时提升可观测性与配置治理能力。

## 工作项总览

| 编号 | 改进主题 | 目标状态 | 当前进度 | 里程碑日期 | 依赖/备注 |
| ---- | -------- | -------- | -------- | ---------- | --------- |
| A1 | 数据源策略统一 | 恢复 AmazingData ➜ Cloudflare ➜ AkShare 降级链并保持配置一致性 | ✅ Done | 2025-10-05 | 已同步更新配置模型、示例与文档 |
| A2 | 依赖注入校验恢复 | 容器在启动阶段完成依赖拓扑校验并输出结果 | ☐ TODO | 待定 | 阻塞项：容器依赖分析 bug 需定位 |
| A3 | 单机部署保障 | Redis / PostgreSQL 本地化方案明确，提供 DuckDB 回退策略 | ☐ TODO | 待定 | 与运维文档联动 |
| A4 | 文档与配置清理 | README 与架构文档移除分布式 / Cloudflare 残留描述 | ☐ TODO | 待定 | 同步 CI 文档检查 |
| A5 | 可观测性增强 | 事件引擎、消息总线、缓存暴露指标及可视化方案 | ☐ TODO | 待定 | 需与 MonitorAPI 整合 |

> 进度取值：☐ TODO / ◑ In Progress / ☑ Done。更新时请注明时间与提交哈希。

## 详细说明

### A1 统一数据源策略
- 范围：
  - 限制 deepsearch/infrastructure/providers/ 仅注册 AmazingData；
  - 配置模型 (docs/api/API_MAPPING.md、deepsearch/config/models) 移除 Cloudflare、QMT、AkShare 可选项；
  - CLI 与运维文档仅保留 AmazingData 启动指引。
- 交付物：
  1. 配置与代码同步删除未授权 Provider；
  2. 更新 docs/api 相关文档；
  3. 运行 python tools/generate_api_documentation.py 重新生成文档。
- 验证：
  - 单元测试覆盖数据源选择策略；
  - CLI 启动 AmazingData 自检通过。
- 跟踪：
  - 在本文件记录负责人与最新进展；
  - 每次更新同步 docs/operations/ 下的数据源部署指南。

### A2 恢复依赖注入容器校验
- 范围：
  - 修复 AsyncContainer.validate_dependencies() 逻辑；
  - 在主引擎初始化阶段恢复校验并输出结构化日志；
  - 增加失败时的降级与提示策略。
- 交付物：
  1. 容器单元测试覆盖正常与缺失依赖场景；
  2. 日志标准扩展校验结果模板。
- 验证：
  - 运行 uv run pytest tests/unit/core；
  - 手动启动验证，当依赖缺失时 CLI 能提示具体组件。
- 跟踪：
  - 在此文档更新校验状态；
  - 如需紧急豁免，记录在 docs/operations/KNOWN_ISSUES.md。

### A3 单机部署保障
- 范围：
  - 明确 Windows 环境 Redis / PostgreSQL 安装方式及最小配置；
  - 为无法部署数据库的场景提供 DuckDB 回退（配置项与文档）；
  - 更新 CLI 检查逻辑，提示缺失组件与建议。
- 交付物：
  1. 更新 docs/operations/DEPLOYMENT_WINDOWS.md；
  2. 在 deepsearch/config/settings.*.yaml.example 增加 DuckDB 配置；
  3. 提交 CLI 提示优化。
- 验证：
  - 在干净环境执行 uv run python -m deepsearch run；
  - 回退路径验证 DuckDB 启用成功。
- 跟踪：
  - 在总览表记录依赖工具包版本；
  - 通过 python scripts/run_all_tests.py --quick 验证关键流程。

### A4 文档与配置清理
- 范围：
  - README、docs/architecture/SYSTEM_ARCHITECTURE.md、docs/api/README.md 等清除分布式、Cloudflare、ZeroMQ 描述；
  - 调整架构图与 ASCII 图，反映单机部署与 AmazingData 主体；
  - 添加弃用功能段落说明历史缘由。
- 交付物：
  1. 文档 PR 包含更新清单与测试结果；
  2. 架构图若需重绘，可使用 ASCII 或 PlantUML 方案。
- 验证：
  - 完成文档评审；
  - 运行 python tools/generate_api_documentation.py 确保引用一致。
- 跟踪：
  - 在此文档标记完成度；
  - 同步通知团队弃用功能列表。

### A5 可观测性与指标增强
- 范围：
  - 事件引擎：暴露队列堆积、处理时延、批量效率等指标；
  - 消息总线：统计压缩、去重命中、路由失败计数；
  - 多级缓存：输出命中率、降级比例；
  - 将指标写入现有 MonitorAPI，并在 WebUI 展示。
- 交付物：
  1. 扩展 deepsearch/observability 下的指标采集接口；
  2. WebUI 新增监控面板；
  3. 文档记录指标含义与告警阈值。
- 验证：
  - 运行专用集成测试或手工场景模拟；
  - WebUI 实时显示与日志对齐。
- 跟踪：
  - 在本文件记录指标上线情况；
  - 将监控检查纳入 scripts/run_all_tests.py 可选步骤。

## 进度更新指南

1. 每次提交涉及上述任一工作项，必须更新本文件：
   - 调整总览表中的进度状态；
   - 在相应子章节追加“最新进展 (YYYY-MM-DD)”段落，记录变更与提交哈希。
2. 若新增相关任务，请在总览表追加行并保持编号连续。
3. 与本路线图关联的 Issue 或 PR 在描述中引用 docs/architecture/DEEPSEARCH_ARCH_IMPROVEMENT_PLAN.md 以便追踪。
4. 建议每周在 docs/operations/STATUS_REPORT.md 汇总此路线图的状态。
