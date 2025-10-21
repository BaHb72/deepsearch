# M2 阶段任务拆解（资金脉冲 / 盘口失衡 / 竞价质量 MVP）

## 1. 目标范围

- 打通从 AmazingData 实时订阅 → 指标计算 → Redis 缓存 → FastAPI 输出的最小链路。
- 覆盖以下 API：
    - `/api/market/live/strength`
    - `/api/market/live/order-imbalance`
    - `/api/market/live/auction-quality`
- 提供基础监控与日志，确保核心指标在盘中持续返回。

## 2. 任务拆解

| 模块            | 任务                                | 说明                                                               | 负责人 | 预计工时 |
|---------------|-----------------------------------|------------------------------------------------------------------|-----|------|
| Ports         | 补充端口方法注释与类型 stub（`.pyi`）          | 完善 `market_data` 端口定义，加注释与类型 stub，便于实现层引用                        | TBD | 0.5d |
| Streaming     | `MarketStreamPort` 实现草稿           | 基于 AmazingData IPC 管道实现订阅、重连、滑窗驱动                                | TBD | 2d   |
| Domain        | 资金脉冲/盘口失衡/竞价实体行为                  | 实现指标计算函数（速度/加速度、OBI/EIS/NTM、竞价价稳性）并配套单元测试                        | TBD | 2d   |
| Cache         | Redis 适配器与 key 规范                 | 设计 Redis key 前缀、TTL 配置，实现写入/读取封装                                 | TBD | 1d   |
| API           | FastAPI Handler + Pydantic Schema | 对接端口，实现 `/strength` `/order-imbalance` `/auction-quality`，补充契约测试 | TBD | 1.5d |
| Observability | 指标、日志与告警基线                        | 记录聚合耗时、队列积压、缓存命中率；落地基础日志结构                                       | TBD | 1d   |
| Infra         | 配置 & 部署脚本调整                       | 更新 `settings.<env>.yaml`，配置 Redis DB/TTL，确认部署流程                  | TBD | 0.5d |
| QA            | 测试计划与数据集                          | 编写测试计划，准备模拟订阅数据集和 API 验收用例                                       | TBD | 1d   |

> 注：工时为初步估算，可根据实现进度和资源准备情况滚动调整。

## 3. 关键交付物

- 运行中的实时链路（可在测试环境回放模拟订阅数据）。
- Redis 中的实时榜单 Key 样例与监控仪表板基线。
- 契约测试脚本（基于 `api_contract_v4.yaml`）及指标计算单元测试。

## 4. 风险与依赖

- AmazingData 订阅限流 → 需提前验证模拟账户权限。
- Redis 资源不足 → 需要基础设施确认 DB 隔离与内存配额。
- 单测数据构造复杂 → 需准备模拟快照序列与边界场景（竞价/停牌/涨停）。

## 5. 验收标准

- API 返回与契约一致，误差范围：金额类 ±0.01%，指标值 ±1e-6。
- 盘中（模拟）压测下，P95 延迟 < 800ms，缓存命中率 > 85%。
- 监控面板展示聚合耗时、缓存命中率、订阅队列长度三项核心指标。
- 文档更新：`blueprint.md`、`progress.md`、`cache_and_resource_plan.md`、Runbook（如涉及运维操作）。

## 6. 下一步

- 将任务录入迭代看板并指派负责人，结合排期动态调整优先级。
- 若需要新增外部依赖（如序列图工具、回放脚本），提前沟通工具链支持。
