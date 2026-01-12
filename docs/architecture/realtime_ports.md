# Realtime Ports 设计说明

本文档定义实时行情流水在领域层使用的协议规范，用于隔离具体数据源实现（AmazingData、AkShare 等）并支撑 orchestrator 的能力筛选。

## 设计目标

- **抽象能力**：领域层仅依赖协议（Ports），适配器在 `adapters/` 内部对接具体 SDK。
- **可组合**：不同数据源可以只实现部分端口，由 orchestrator 根据需求组合。
- **类型安全**：避免在领域层出现 `Any` / `dict[str, Any]`，统一使用 TypedDict 或 dataclass。
- **最小依赖**：端口定义不直接 import 第三方库，保证跨源复用。

## 端口列表

| 端口 | 文件 | 说明 |
| --- | --- | --- |
| `RealtimeStreamPort` | `deepsearch/ports/market_data/realtime.py` | 管理订阅、退订、获取最新快照。 |
| `BoardUniversePort` | 同上 | 同步板块/指数成份，供 `BoardUniverse` 使用。 |
| `IndicatorPort` | 同上 | 统一资金脉冲/竞价/委差等指标的输入输出。 |
| `RealtimeAdapterCapabilities` | 同上 | 描述适配器具备的能力，供 orchestrator 选择。 |

## 关键数据结构

```python
@dataclass(slots=True)
class SnapshotPayload:
    code: str
    price: Decimal
    amount: Decimal
    volume: int
    ts: datetime
    data_source: str
    extra: Mapping[str, Any] = field(default_factory=dict)
```

- `SnapshotPayload` 是 `RealtimeStreamPort.fetch_latest()` 的基本单元，后续会被写入 `SnapshotBuffer`。
- `extra` 中可携带各数据源特有字段，但不得在领域层直接依赖。

## 协议草案

```python
class RealtimeStreamPort(Protocol):
    async def subscribe(self, codes: Sequence[str]) -> None: ...
    async def unsubscribe(self, codes: Sequence[str]) -> None: ...
    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[SnapshotPayload]: ...

class BoardUniversePort(Protocol):
    async def fetch_records(self) -> Sequence[StockListRecord]: ...

class IndicatorPort(Protocol):
    async def ensure_warmup(self) -> None: ...
    def supports(self, indicator: IndicatorKind) -> bool: ...
```

实际实现中会拆分为多个协议文件，Indicator 相关接口将返回 `CapitalPulseEntry`、`AuctionQualityEntry` 等强类型数据结构。

## Orchestrator 交互

1. Orchestrator 根据配置读取 adapter 列表，并检查 `RealtimeAdapterCapabilities` 中的布尔字段（对应能力矩阵）。
2. 选中的 adapter 需要暴露：
   - `stream_port: RealtimeStreamPort`
   - `board_port: BoardUniversePort`
   - `indicator_port: IndicatorPort`（可选）
3. `MarketDataRealtimePipeline` 将通过 ports 完成订阅、快照拉取和指标计算，不再直接引用具体 provider。

## 错误与状态

- 端口方法需抛出领域层定义的异常（待补充），由 orchestrator 统一捕获并打标。
- 订阅/退订返回 `None`，如需反馈失败，可抛出 `SubscriptionError`，其中包含 `codes` 与 `reason`。
- `fetch_latest` 需保证即使部分代码失败也能返回成功部分，并在异常中附带失败列表。

## 维护指南

1. 任何端口新增方法时，必须同步更新 `docs/datasources/realtime_capability_matrix.md` 与 orchestrator 选择逻辑。
2. Port 定义应配套 `.pyi` stub，方便 mypy/pyright 校验。
3. 保持文档例子与 `deepsearch/ports/market_data/realtime.py` 中的注释一致，避免知识漂移。
