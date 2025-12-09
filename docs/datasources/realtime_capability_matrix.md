# 实时数据源能力矩阵

## 目的

- 统一描述各数据源在实时行情链路中的可用能力，作为 orchestrator 选择/降级的依据。
- 为研发、运维提供“启用前需具备哪些条件”的检查清单，降低临时排障成本。
- 与 `docs/development/realtime_data_source_unification.md` 方案联动，后续每次适配器改动需同步更新本表。

## 能力定义

| 能力 | 说明 |
| --- | --- |
| streaming | 是否支持长连推流及订阅管理（subscribe/unsubscribe/fetch_latest）。 |
| snapshot | 能否在推流不可用时通过轮询方式获取最新快照。 |
| board_universe | 是否能提供板块成份 / 证券列表及增量更新。 |
| capital_pulse | 是否具备支撑资金脉冲计算所需的字段频率与精度。 |
| auction | 是否具备集合竞价指标所需字段。 |
| order_imbalance | 是否具备委托差指标所需字段。 |
| throttle | 官方/自建限流机制，是否支持速率控制与负载保护。 |
| auth | 鉴权方式（账号、密钥、IP 白名单等），用于快速判断接入复杂度。 |

## 能力矩阵

| 数据源 | streaming | snapshot | board_universe | capital_pulse | auction | order_imbalance | throttle | auth | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AmazingData (process) | 完全支持 | 支持（通过流式缓存） | 完全支持 | 完全支持 | 完全支持 | 完全支持 | SDK 内置 + 连接池 | 账户/密码 + 进程令牌 | 当前唯一正式接入的实时流水，实现位于 `infrastructure/providers/implementations/amazingdata`。 |
| AkShare 直连 | 不支持推流 | 支持（HTTP 轮询） | 部分支持（需自建映射） | 部分支持（字段需换算） | 不支持 | 不支持 | 自行实现（需节流） | 无鉴权或基于代理 | 已通过 `AkSharePollingAdapter` 接入 orchestrator，轮询快照并写入缓存。 |
| AkShare Cloudflare 代理 | 不支持推流 | 支持（HTTP 轮询） | 部分支持 | 部分支持 | 不支持 | 不支持 | Cloudflare Worker 限流 | Worker 密钥 | 通过 `AkSharePollingAdapter(use_proxy=True)` 复用 AkShare Worker，需在 `settings.*.yaml` 中配置 `akshare.proxy.worker_url`。 |
| QMT / MiniQMT | 支持（内网推流） | 支持 | 完全支持 | 完全支持 | 完全支持 | 完全支持 | 终端限流 | 终端授权 | 目前仅在回测/仿真环境使用，尚未纳入 WebUI 实时流水。 |
| Cloudflare 实时接口 | 不支持推流 | 支持 | 不支持 | 不支持 | 不支持 | 不支持 | Cloudflare 限流 | Token | 仅用于简单行情兜底，不适配复杂指标。 |

> 状态含义：**完全支持** = 即插即用；**支持** = 满足主要场景但需与其他能力配合；**部分支持** = 需要额外转换或字段补齐；**不支持** = 现阶段无法覆盖。

## 维护指引

1. 任何适配器新增/下线时，先更新本文件，再变更代码。
2. `Streaming` 能力必须给出订阅策略（全量/增量）与可靠性说明，避免 orchestrator 误判。
3. 若某能力为计划中状态，可在备注列附上“预计支持版本/阻塞问题”。
4. 文档编码统一 UTF-8，避免在 QMT 相关章节混入 GBK。

## 数据源补充说明

### AmazingData

- 需要独立 Python 3.13 环境，通过进程隔离的 `AmazingDataProcessProxy` 访问官方 SDK。
- `InfoData.get_stock_basic` 长时间阻塞会影响板块成份同步，详见 `docs/reports/amazingdata_info_get_stock_basic_blocking.md`。
- 作为默认源时，`ensure_market_data_runtime()` 会直接创建 provider 并启动 `MarketDataStreamingRunner`。

### AkShare

- 推荐通过 `AkShareRealtimeAdapter`（待实现）封装轮询逻辑，并结合 `MarketDataCacheWriter` 写入 Redis。
- 若使用 Cloudflare Worker 代理，需在配置中打开 `akshare.proxy.enabled` 并设置 `worker_url`。
- `board_universe` 能力需要依赖本地 CSV 或其他数据源填补。

### QMT / MiniQMT

- 具备推流能力，但接入需要证券终端授权，适合作为后续扩展。
- 若启用，需确保 `TradingSessionGuard` 能识别对应市场的交易时段。

### Cloudflare 实时接口

- 主要作为 HTTP 级别的兜底数据源，不具备板块级或指标级数据。
- 可在 fallback 场景中向用户标记 `data_source: "cloudflare"` 并告知数据陈旧。
