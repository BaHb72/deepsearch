# 数据提供者架构设计（2025 版）

DeepSearch 的数据提供层统一管理所有受支持的数据源。当前默认使用 AmazingData API 作为外部数据源，必要时可回退至 AkShare（含 CloudFlare 代理）补齐缺失数据，本地 QMT 终端仍作为补充输入。本文档记录最新的分层架构、核心组件以及扩展约束。

## 架构总览

    ┌───────────────────────────────────────────┐
    │                数据消费者                 │
    │ ChartService / MarketService / Engine 等  │
    └───────────────────────────────────────────┘
                      │ 统一入口 (async)
                      ▼
    ┌───────────────────────────────────────────┐
    │ DataSourceManager                         │
    │ deepsearch.infrastructure.providers.managers │
    │  • 提供 async API（行情、K 线、指标等）     │
    │  • 基于优先级的自动选择                    │
    │  • 断路器 / 熔断与健康度监控               │
    │  • 统一缓存与结果归一                      │
    └───────────────┬───────────────────────────┘
                    │ 调用 ProviderFactory + Registry
            ┌───────┴─────────────┬─────────────────────┐
            ▼                     ▼                     ▼
    ┌────────────────┐   ┌───────────────────┐   ┌──────────────────┐
    │ AmazingData    │   │ UnifiedQMTProvider│   │ Mock/Fallback     │
    │ Provider（P1） │   │ （P5，本地终端）   │   │ Provider（P99）   │
    │ implementations│   │ implementations/qmt │ │ mock/error        │
    └────────────────┘   └───────────────────┘   └──────────────────┘

> 新增数据源必须遵守单机部署约束，并在 docs/datasources/ 下补充文档后才可引入此架构。

## 核心组件说明

### DataSourceManager
- 位置：deepsearch/infrastructure/providers/managers/data_source_manager.py
- 责任：根据请求上下文（数据类型、实时/历史需求、可靠性要求）选择合适 Provider；结合 ProviderFactory 与健康度缓存实现熔断与恢复；对外提供协程接口。
- 示意：

        class DataSourceManager:
            async def get_kline(self, symbol: str, period: str, *, limit: int = 500):
                provider = await self._select_provider(DataCapability.KLINE)
                return await provider.get_kline(symbol, period, limit=limit)

### ProviderFactory 与 Registry
- 位置：deepsearch/infrastructure/providers/factory.py、deepsearch/infrastructure/providers/registry.py
- 功能：注册所有 Provider、维护优先级与能力矩阵、按 DataCapability 查询候选列表，并结合配置决定启用状态。

### AmazingDataProvider（主数据源）
- 路径：deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py
- 特点：负责 SDK 登录、订阅与批量查询；启动时执行凭证校验与 SystemExit 防护；集成 monitor_data_source 装饰器输出监控指标；配置位于 settings.*.yaml 的 infrastructure.providers.amazingdata 节点。

### UnifiedQMTProvider（本地补充数据源）
- 路径：deepsearch/infrastructure/providers/implementations/qmt/unified_qmt_provider.py
- 用途：提供本地行情与撮合回放能力，主要服务于终端部署或 AmazingData 抖动时的只读兜底，通过进程间通信获取数据，不对外暴露网络接口。

### Mock / Fallback Provider
- 路径：deepsearch/infrastructure/providers/mock/error_provider.py
- 用途：在主备数据源全部熔断时返回结构化错误，保证上层能识别异常并触发降级。

## 能力优先级与断路器

| 能力 | 优先级顺序 | 断路器策略 |
|------|------------|------------|
| 实时行情 | AmazingData → QMT → Mock | 请求超时 3 次触发短熔断，30 秒后自动探活 |
| 日/周/月线 | AmazingData → Mock | 出现数据完整性校验失败时切换 Mock |
| 账户/交易 | AmazingData（仅认证接口） | 暂无兜底，直接向上游抛出错误 |

断路器逻辑封装在 deepsearch/infrastructure/providers/managers/enhanced_manager.py，监控输出对接 docs/operations/monitoring/data_source_monitoring.md 描述的流程。

## 数据流示意

    Client → DataSourceManager → ProviderFactory → AmazingDataProvider → Client

若主数据源不可用：
1. Manager 将错误上报监控并对该 Provider 熔断；
2. Factory 返回下一个候选（QMT），若仍失败则走 MockProvider；
3. 监控中心 data-source-monitor 子代理会标记降级事件并提示人工干预。

## 扩展指引
1. 新增数据源：在 implementations/<provider>/ 下实现 Provider 并继承 BaseProvider，更新 registry.py 注册能力、优先级与健康度阈值，同时补充 docs/datasources/<provider>/ 文档。
2. 新增数据能力：扩展 DataCapability 枚举，并在 Manager 中补充路由实现，同时更新监控指标与 API 文档。
3. 监控接入：务必使用 monitor_data_source 或 MonitoringIntegration 装饰器，确保监控数据写入 data/logs/datasources/* 目录，供监控流程消费。

## 相关文档
- 数据源监控体系：docs/operations/monitoring/data_source_monitoring.md
- AmazingData 文档合集：docs/datasources/amazingdata/README.md
- QMT 数据馈送指南：docs/archive/datasources/qmt/README.md
