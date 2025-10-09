# 数据源策略修正记录

## 背景
- 日期：2025-10-04
- 负责人：自动化回溯
- 变更范围：数据源注册/配置/文档

## 问题起因
- 在 2025-10-04 的一次重构中，误将策略理解为“仅允许 AmazingData 数据源”。
- 依据错误理解删除/屏蔽了 AkShare 相关配置、测试与文档描述，并将 README / SYSTEM_ARCHITECTURE.md 标记为“其他数据源已退役”。
- 实际策略应为：优先使用 AmazingData → AmazingData 不可用时降级到 Cloudflare/AkShare 代理 → 最终直连 AkShare。

## 当前状态
- 2025-10-04 文档已恢复正确描述（AmazingData → AkShare Proxy → AkShare Direct）。
- 2025-10-05 代码层已恢复 AmazingData → Cloudflare → AkShare 的降级链，并同步更新 ProviderRegistry / DataSourceManager。
- 2025-10-05 settings.template.yaml、settings.dev.yaml.example、settings.prod.yaml、settings.test.yaml 示例均新增 Cloudflare/AkShare 配置与 fallback_order。
- 改进路线图 A1 节点已记录本次修正并进入“Done”。

## 最新进展（2025-10-05）
- ProviderRegistry 重新注册 cloudflare、kshare 等默认提供者，允许外部/直连两级备用链路。
- DataSourceManager 恢复对多数据源的配置解析、初始化与状态管理，异步接口统一支持降级重试。
- 新增测试覆盖（tests/test_providers.py、tests/unit/infrastructure/test_data_source_manager.py）验证降级链与熔断行为。
- async_timeout 工具支持装饰器/函数双用，run_with_timeout 能同时处理协程或同步调用，避免降级链阻塞。

## 后续关注点
1. **监控验证**：补充 Cloudflare/AkShare 指标上报与报警阈值，观察生产降级触发情况。
2. **集成测试**：持续补充对 Cloudflare worker 代理和直连 AkShare 的端到端回归，防止配置漂移。
3. **团队同步**：在下一次变更说明中提醒同步拉取最新配置模板，避免再次出现“单数据源”误解。

## 注
- 如需参考本次修复的具体 diff，可在当前分支查看 2025-10-05 提交记录。
- 文档体系（README、SYSTEM_ARCHITECTURE.md、DEEPSEARCH_ARCH_IMPROVEMENT_PLAN.md）已更新为最新策略。
