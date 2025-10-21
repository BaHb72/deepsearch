# 市场行情模块建设进度

- 创建日期：2025-10-21
- 维护人：待指派
- 参考文档：
    - [market_data_page_plan_v4_amazingdata_live.md](./market_data_page_plan_v4_amazingdata_live.md)
    - [api_contract_v4.yaml](./api_contract_v4.yaml)
    - [indicator_spec_v4.md](./indicator_spec_v4.md)

## 建设目标

围绕 AmazingData 实时行情数据源，交付一套覆盖后端服务、指标计算、前端展示的完整市场行情模块，满足多市场、多标的的实时展示、历史回看与指标联动需求，并与现有
DeepSearch 架构解耦。

## 里程碑与交付

| 里程碑       | 主要交付                       | 预计完成时间     | 状态  | 备注                              |
|-----------|----------------------------|------------|-----|---------------------------------|
| M1 模块蓝图定稿 | 明确域模型、端口定义、数据流与关键用例        | 2025-10-28 | 未开始 | 基于三份规范文档输出设计结论                  |
| M2 后端基础能力 | 完成行情数据拉取、缓存与 API 对接的最小可行链路 | 2025-11-11 | 未开始 | 需完成 ports/adapters 设计与单元测试      |
| M3 指标体系落地 | 实现首批核心指标计算链路与校验流程          | 2025-11-25 | 未开始 | 以 `indicator_spec_v4.md` 作为验收标准 |
| M4 前端首版页面 | 交付市场行情页面 MVP，支持基础交互        | 2025-12-09 | 未开始 | 与 WebUI 组件库标准保持一致               |
| M5 联调与验收  | 覆盖端到端联调、性能测试与运营手册          | 2025-12-16 | 未开始 | 通过 docs/operations 流程审查         |

## 当前进展

- 2025-10-21：在 `docs/modules/market_data/` 建立模块文档目录，并归档产品规划、接口契约与指标规范。
- 2025-10-21：输出《[市场行情模块架构草案 v1](./blueprint.md)》，明确目录结构、端口协议与数据流设计。
- 2025-10-21：落地 `deepsearch/ports/market_data/` 端口与数据模型草稿，覆盖实时、日频与扩展能力定义。
- 2025-10-21：形成《[市场行情模块缓存与资源方案（初稿）](./cache_and_resource_plan.md)》，明确实时/日频链路的 Redis、DuckDB
  复用策略。

## 关键约束摘要

- **产品规划（market_data_page_plan_v4_amazingdata_live.md）**：强调“Real-time First”，基于 AmazingData
  现有接口构建资金脉冲、竞价质量、盘口失衡、ETF 溢价、两融 T‑1、供给约束与（可选）外部资产映射，要求统一指标口径与缓存策略。
- **API 契约（api_contract_v4.yaml）**：定义 `/api/market/live/*` 与 `/api/market/margin|supply|fundamental/*` 等 10
  个终端，输出字段需保持 `data_source=amazingdata`、窗口/时间戳字段与指标一一对应。
- **指标白皮书（indicator_spec_v4.md）**：给出了资金速度/加速度、OBI/EIS/NTM、封单稳定度、竞价价稳性、ETF
  溢价率、承载力评分等计算公式，要求使用分钟滑窗与统一复权/过滤规则。

## 下一步计划

1. 基于架构草案完善端口实现计划，细化 streaming/缓存落地步骤。
2. 结合缓存方案结论，准备 Redis/DuckDB 配置草稿并确认资源配额与调优选项。
3. 按 `m2_mvp_tasklist.md` 细化任务拆解，补充监控与测试需求并排定执行顺序。

## 风险与依赖

- AmazingData 实时接口质量需持续监控，必要时准备备选数据源适配。
- 行情指标计算链存在性能与精度风险，需要针对大规模品种提前压测。
- WebUI 开发排期与组件复用情况尚未对齐，需协调前端资源。
