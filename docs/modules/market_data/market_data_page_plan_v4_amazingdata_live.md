# 市场数据页面与系统方案规划 · V4（为实盘而生｜仅 AmazingData 现有接口）

> **定位**：A股股票为主，盘中实时订阅为核心；**保留 ETF 与融资融券**；若 **AmazingData 提供外部资产（期货）接口**，则作为**参考层
**参与“驱动/映射分析”。**不引入第三方兜底**。  
> **仅引用 AmazingData 手册中的现有接口**（快照/订阅、历史快照、K线、基础与信息、股东股本、股东权益、融资融券、（可选）期货快照）。

---

## 1. 核心目标（Real‑time First）

- **实时**：基于 **SubscribeData** 的 Level‑1 快照订阅（股票/ETF），5–10s 节流聚合，形成“资金强度/速度/质量”指标；竞价阶段（9:
  15–9:25）2–5s。
- **可解释**：五档盘口、涨跌停价、成交笔数 → **资金质量（OBI/EIS/NTM）** 与 **封单强度/稳定度**。
- **参考层**：ETF（溢价/概念代理）与 融资融券（T‑1 方向），以及（可选）**期货**对相关行业的驱动映射。
- **约束层**：解禁/质押/分红/配股 + 股东/股本 + 财务/业绩 → **承载力/风格偏好**。

---

## 2. 接口 → 指标 → 视图（全部为 AmazingData 现有接口）

### 2.1 盘中资金脉冲（股票）

- **接口**：`SubscribeData.register(..., period=snapshot)`（股票），`query_kline`（分钟线）；`get_stock_basic`（上市板块）
- **指标**：`amount`（强度）、`speed/accel`（差分/差分的差分）、`num_trades`；板块聚合（主板/创业/科创）
- **视图**：资金温度计（强度/速度/加速度）、板块速度榜、分钟曲线

### 2.2 竞价质量（9:15–9:25）

- **接口**：快照订阅 + `trading_phase_code`（集合竞价识别）；`query_snapshot`（历史竞价复盘）
- **指标**：竞价累计额/量、竞价速度、末2分钟价稳性（低频方差）
- **视图**：竞价热力+质量评分

### 2.3 盘口失衡与封单（股票）

- **接口**：Level‑1 五档价量、涨跌停价、`num_trades`（快照）；`query_kline`（用作分时回看）
- **指标**：OBI / EIS / NTM、封单金额 `bid_volume1 × high_limited`、封单稳定度、炸板概率（本地模型）
- **视图**：资金质量雷达、封单强度榜、炸板预警

### 2.4 ETF（被动/套利参考 + 概念代理）

- **接口**：ETF 快照（含 `iopv` 字段）、ETF 分钟 K线
- **指标**：溢价率 `premium = last/iopv - 1`、ETF 资金速度；**概念代理**：`S(ETF)=TopK{ corr(stock, ETF) }`
- **视图**：ETF 溢价温度、ETF‑驱动的“概念交叉/资金关联度”（本地计算）

### 2.5 融资融券（T‑1，方向参考）

- **接口**：`get_margin_summary`、`get_margin_detail`（日频）
- **指标**：融资/融券余额、买入/偿还/卖出/余量；与盘中资金脉冲做共振/背离分析
- **视图**：两融方向看板（市场/个股 TopN）

### 2.6 外部资产参考层（**可选**，仅当手册提供期货接口）

- **接口**：`SnapshotFuture`（期货快照）、`query_kline`（期货分/日），并按手册夜盘切分算法处理
- **指标**：期货收益/速度 ↔ A股行业/个股的相关/交叉相关/滞后传导；事件冲击（窗口内强度差）
- **视图**：外部资产→行业驱动矩阵、冲击复盘

### 2.7 供给/约束 & 风格/筹码（日频/事件）

- **接口**：
    - 供给/约束：`get_equity_restricted`、`get_equity_pledge_freeze`、`get_dividend`、`get_right_issue`
    - 风格：`get_balance_sheet`、`get_cash_flow`、`get_income`、`get_profit_express`、`get_profit_notice`
    - 筹码：`get_holder_num`、`get_equity_structure`、`get_share_holder`
- **指标**：承载力评分（事件强度 × 近端流动性）、风格偏好雷达、筹码集中度/流通盘约束
- **视图**：供给/约束与风格/筹码仪表

### 2.8 概念/板块关联与热点迁移（本地计算）

- **输入**：股票/ETF（以及可选期货）的分钟时间序列（本地缓存）
- **产出**：概念交叉、概念资金关联度、板块相关/Granger、指数大跌触发的“撤出→流入”迁移图

---

## 3. 端口（Ports）与适配器（Adapters）

- `MarketCapitalPulsePort`（股票订阅→资金强度/速度/加速度）
- `AuctionQualityPort`（集合竞价质量评分）
- `OrderImbalancePort`（OBI/EIS/NTM）
- `LimitStrengthPort`（封单/炸板）
- `ETFReferencePort`（溢价/速度/概念代理）
- `MarginFlowPort`（两融）
- `ExternalAssetOverlayPort`（期货→行业/个股；**可选**）
- `SupplyConstraintPort`（解禁/质押/分红/配股）
- `StyleAndOwnershipPort`（三表/业绩/股东/股本）
- `BoardAndConceptAssocPort`（本地计算）

**适配器**：`market_stream_adapter.py`、`etf_adapter.py`、`margin_adapter.py`、`futures_overlay_adapter.py`（可选）、
`supply_adapter.py`、`fundamental_adapter.py`。  
**类型**：全部 `dataclasses/TypedDict`；禁止裸字典。

---

## 4. API 资源（与 OpenAPI 契约一致）

- 实时：`/api/market/live/strength`、`/api/market/live/auction-quality`、`/api/market/live/order-imbalance`、
  `/api/market/live/limit-strength`、`/api/market/live/etf-temp`、`/api/market/live/external-overlay`（可选）
- 日频：`/api/market/margin/*`、`/api/market/supply`、`/api/market/fundamental/style-preference`
- 本地计算：`/api/market/assoc/*`、`/api/market/rotation/report`
- 公共字段：`{ ts, data_source:'amazingdata', calc:'none|local', window, note? }`

---

## 5. 指标口径（关键）

- 资金速度：`(amount_t – amount_{t-Δ}) / Δ分钟`；加速度为速度一阶差分
- 盘口失衡（OBI）：`(ΣBid1..5Vol – ΣAsk1..5Vol) / (ΣBid1..5Vol + ΣAsk1..5Vol)`
- 价差冲击（EIS）：`(Ask1 – Bid1)/Mid × speed`
- 成交笔数动量（NTM）：`num_trades` 的滚动增速
- 封单金额：当 `last≈high_limited` 且卖侧无效时，`lock = bid_volume1 × high_limited`；稳定度=多窗口保持率
- ETF 溢价率：`premium = last/iopv - 1`
- 外部资产驱动强度：`corr/xcorr(ret_or_speed_stock, ret_or_speed_future)`（**可选**）
- 承载力评分：事件强度 × 近端流动性（近 10/20 日资金速度均值/方差）
- 概念资金关联度：`w1*corr(ret) + w2*corr(speed)`（默认 `w1=w2=0.5`）

---

## 6. 缓存/性能/风控

- 订阅聚合：统一通道节流，滑窗差分缓存；分钟K线用于曲线平滑
- HDF5 本地缓存：历史快照/K线/事件接口启用 `local_path/is_local` 增量
- 夜盘处理（可选期货）：遵循手册窗口切分与跨日对齐
- 单位与口径：指数 `volume` 与股票单位差异需统一；金额统一“元”，前端显示换算
- 风控：`get_history_stock_status` 的停牌/ST/除权过滤白名单，避免异常样本污染实时榜单

---

## 7. 覆盖的 AmazingData 接口清单（均为现有接口）

- 基础：`login/logout`、`get_calendar`、`get_code_list/get_code_info/get_hist_code_list`、`get_stock_basic`、
  `get_history_stock_status`、`get_backward_factor/get_adj_factor`
- 行情：`SubscribeData`（股票/ETF/指数）、`query_snapshot`（历史快照）、`query_kline`（K线）
- ETF：ETF 快照（含 `iopv`）
- 两融：`get_margin_summary`、`get_margin_detail`
- 股东/股本/权益：`get_share_holder`、`get_holder_num`、`get_equity_structure`、`get_equity_pledge_freeze`、
  `get_equity_restricted`、`get_dividend`、`get_right_issue`
- （可选）期货参考：`SnapshotFuture`、`query_kline`（分/日；含夜盘规则）

---

## 8. 行动项

1) 订阅聚合层接入：股票/ETF 快照 → 资金脉冲/质量指标
2) 加入竞价质量、封单稳定度、OBI/EIS/NTM 的实时计算
3) 两融 T‑1 拉取与共振看板
4) 供给/约束与风格/筹码的日频计算与缓存
5) （可选）期货参考层对齐与行业映射
6) 指标口径白皮书与 OpenAPI 契约输出，联调前端/测试