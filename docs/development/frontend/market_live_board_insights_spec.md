# 市场实时页面（方案A）— 概念板块洞察与驱动识别设计说明

## 1. 目标与范围

- 目标：在不新增页面的前提下（沿用方案A），让“市场实时”页直观呈现【概念板块/行业板块】的结构化信息：
    - 各板块内“试盘”股票数量与占比。
    - 盘中主力资金净流入与流入速度（含加速度）按板块聚合排名。
    - 识别板块拉升是“单核驱动”（少数/单只龙头拉动）还是“多点开花”（多数成分股共振）。
- 范围：WebUI 前端（展示、交互）+ 后端 `/api/market/live/*` 衍生接口与实时聚合计算（基于现有快照/指标管线）。

## 2. 指标与判定口径

### 2.1 试盘（Probing）检测（股票层）

- 目的：标记“短时间内主动买盘显著增强且价格/成交突变”的股票。
- 判定要素（任一满足即进入候选）：
    - 订单失衡（OBI）阈值：`|obi| ≥ OBI_MIN` 且 `obi > 0`（买方占优）。
    - 资金速度（CapitalPulse.speed_per_min）阈值：`speed ≥ SPEED_MIN`。
    - 资金加速度：`accel_per_min2 ≥ ACCEL_MIN`。
    - 分钟价差：`Δprice%(1m) ≥ PRICE_DELTA_MIN` 且 成交量/笔数相对基线放大（`vol_ratio ≥ VOL_RATIO_MIN`）。
- 消噪与持续性：
    - 在窗口 `W ∈ {1m,5m}` 内需连续 `K` 个切片满足（默认 `K=2`）。
    - 支持“冷却时间”避免重复标记（同标记在 `COOLDOWN_SEC` 内不重复）。
- 输出字段（股票级）：`code,name,obi,speed,accel,price_delta,vol_ratio,window,ts,probing_flag,probing_reason[]`。

### 2.2 板块聚合指标（板块层）

- 成分相关：`stock_count`、`probing_count`、`probing_ratio=probing_count/stock_count`。
- 资金相关：
    - `inflow_net`（净流入金额，累加）、`inflow_speed`（速度，加总/中位数二选一，默认加总）、`inflow_accel`（加速度，加总/中位数）。
- 市场广度（Breadth）：
    - `up_count`、`down_count`、`flat_count`，`breadth_up_ratio = up_count/stock_count`。
- 贡献集中度：
    - 贡献定义：`contrib_i = max(inflow_speed_i, 0)`；
    - `top1_contrib_pct = contrib_max / Σcontrib_i`；`top3_contrib_pct = ΣTop3 / Σcontrib_i`；
    - `hhi = Σ (contrib_i / Σcontrib)^2`（赫芬达尔-赫希曼指数，反映集中度）。
- 拉升驱动分类（Classification）：
    - `single_core`（单核）：`top1_contrib_pct ≥ 0.35` 或 `breadth_up_ratio ≤ 0.3`；
    - `multi_core`（多核）：`top3_contrib_pct ≤ 0.5` 且 `breadth_up_ratio ≥ 0.6`；
    - 其他：`mixed`。
- 输出字段（板块级）：
  `board,stock_count,probing_count,probing_ratio,inflow_net,inflow_speed,inflow_accel,breadth_up_ratio,top1_contrib_pct,top3_contrib_pct,hhi,classification,asOf,stale,data_source`。

### 2.3 窗口与时间

- 支持窗口：`windows ∈ {1m,5m,15m}`；默认 `1m`。
- `asOf` 为指标数据对应的时刻；`retrieved_at` 为接口响应时刻；休市/闭市可返回 `stale:true` 的上次有效快照。

## 3. 页面信息架构与交互

- 顶部状态条（新增）：显示 `phase_state`（休市/闭市/竞价/盘中）、`asOf`、`retrieved_at`、`stale`、`data_source`；`stale:true`
  时展示“陈旧”徽标与说明。
- 左侧/主区块：板块热力与榜单
    - 热力图：按 `inflow_speed` 或 `inflow_net` 映射颜色强度；点击进入板块详情。
    - 榜单（可切换维度：净流入/速度/加速度/试盘占比）：列示
      `board, inflow_speed, probing_count, breadth_up_ratio, classification`。
- 右侧/下方：板块详情抽屉/面板
    - 驱动构成：TopN 股票贡献条形图（含 `contrib%`、是否龙头 `is_leader`）。
    - 试盘列表：本板块被标记为 `probing_flag` 的股票（含原因/关键指标）。
    - 走势/时序（可选）：板块层 `inflow_speed` 曲线（近 N 分钟）。
- 过滤/切换：窗口（1m/5m/15m）、只看资金净流入>0、只看 `single_core`、最低 `probing_count` 等。
- 刷新策略：盘中按窗口刷新；闭市降频（60–120s）；休市仅手动刷新。

## 4. API 设计（/api/market/live/*）

### 4.1 板块总览（概念/行业）

- `GET /api/market/live/board-overview?type=concept&window=1m&limit=100`
- 响应：

```json
{
  "window": "1m",
  "items": [
    {
      "board": "人工智能",
      "stock_count": 512,
      "probing_count": 37,
      "probing_ratio": 0.072,
      "inflow_net": 1.23e9,
      "inflow_speed": 6.5e7,
      "inflow_accel": 2.1e6,
      "breadth_up_ratio": 0.58,
      "top1_contrib_pct": 0.41,
      "top3_contrib_pct": 0.63,
      "hhi": 0.19,
      "classification": "single_core",
      "asOf": "2025-11-06T02:57:00Z",
      "stale": false,
      "data_source": "amazingdata"
    }
  ],
  "retrieved_at": "2025-11-06T02:57:03Z",
  "stale": false,
  "phase_state": "continuous",
  "data_source": "amazingdata"
}
```

- 示例概念建议覆盖 AmazingData 能力范围内的主流主题，如 AI算力、AIGC应用、机器人、低空经济、储能、新能源车、光伏逆变、芯片设计、CPO、算力租赁、华为概念、中药现代化
  等，便于前端在热力/榜单中展示多维对比。

### 4.2 板块驱动构成（概念/行业）

- `GET /api/market/live/board-drivers?type=concept&board=人工智能&window=1m&limit=30`
- 响应：

```json
{
  "board": "人工智能",
  "window": "1m",
  "items": [
    {
      "code": "600000.SH",
      "name": "浦发银行",
      "inflow_contrib": 8.2e6,
      "speed_per_min": 4.1e6,
      "accel_per_min2": 1.2e5,
      "probing_flag": true,
      "is_leader": true,
      "asOf": "2025-11-06T02:57:00Z"
    }
  ],
  "retrieved_at": "2025-11-06T02:57:03Z",
  "stale": false,
  "data_source": "amazingdata"
}
```

### 4.3 板块试盘股票列表（概念/行业）

- `GET /api/market/live/probing?type=concept&board=人工智能&window=1m&limit=100`
- 响应：

```json
{
  "board": "人工智能",
  "window": "1m",
  "items": [
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "obi": 0.68,
      "speed_per_min": 3.2e6,
      "accel_per_min2": 0.8e5,
      "price_delta_pct_1m": 0.9,
      "vol_ratio": 2.3,
      "probing_flag": true,
      "probing_reason": ["OBI>=0.6","speed>=3e6"],
      "asOf": "2025-11-06T02:57:00Z"
    }
  ],
  "retrieved_at": "2025-11-06T02:57:03Z",
  "stale": false,
  "data_source": "amazingdata"
}
```

> 兜底行为：缓存缺失时仍返回 200 + `items:[]` + `stale:true` + `phase_state`；前端据此展示空态/陈旧提示。

## 5. 后端实现要点

- 复用现有 `MarketDataRealtimePipeline`：已产出 per-symbol 的 snapshot 与 CapitalPulse 指标；增加“板块聚合器”。
- 新增实时聚合：
    - `aggregate_board_metrics()`：按板块累计 `inflow_*`、计算 `breadth`、`contrib%`、`hhi` 与 `classification`。
    - `detect_probing()`：按 2.1 的规则标记股票，支持窗口 `1m/5m/15m` 与持续性/冷却时间控制。
- 缓存写入（Redis/in-memory fallback）：
    - `market:board-overview:concept:{window}` / `...:industry:{window}` → 上述 4.1 payload。
    - `market:board-drivers:concept:{board}:{window}` → 上述 4.2。
    - `market:probing:concept:{board}:{window}` → 上述 4.3。
- TTL：默认 180s；接口若拿到 `stale` 也照样返回（方案A）。

### 5.1 概念板块数据来源（重要）

- SDK 1.0.18 并未直接提供“概念板块成分”接口，建议的两种路径：
    1) 使用 AkShare 概念板块接口作为概念成分来源（如同花顺概念）：周期性拉取概念名称与成分股，写入 `board_universe`（概念域）。
    2) 维护本地概念库（CSV/DB），由离线任务同步更新，实时查询直接从缓存读取。
- 统一入口：将概念映射注入 `service.board_universe`，使实时聚合与 REST 均以统一“板块”抽象工作，不感知来源差异。

## 6. 配置项（settings.*.yaml 建议）

```yaml
market_data:
  analysis:
    probing:
      obi_min: 0.6
      speed_min: 3_000_000
      accel_min: 50_000
      price_delta_min_pct: 0.5
      vol_ratio_min: 1.8
      sustain_k: 2
      cooldown_seconds: 60
    classification:
      single_core_top1_pct: 0.35
      multi_core_top3_pct: 0.50
      breadth_up_min: 0.60
      breadth_up_max_for_single: 0.30
```

## 7. 前端交互细则

- 页面顶部状态条：
    - 休市/闭市：展示“休市/闭市，展示最后快照（可能陈旧）”；禁用自动刷新或降频。
- 板块热力/榜单：
    - 度量切换（净流入/速度/加速度/试盘占比）。
    - 排序与分页/虚拟滚动，保障性能。
- 板块详情：
    - 驱动条形图（TopN 股票贡献%）；试盘列表；“龙头/单核/多核”徽标与解释。
- 空态与陈旧：
    - `items:[]` + `stale:true` → 空态说明（不报错），保留手动刷新。

## 8. 验收标准

- 盘中：
    - 榜单按 `inflow_speed` 排序与筛选准确；板块详情 TopN 贡献与“单核/多核”判定与后台数据一致。
- 闭市/休市：
    - 返回 200 + `stale:true`；页面不出现“请求失败”；展示最后快照的 `asOf`。
- 试盘：
    - 满足阈值与持续性规则的股票在对应窗口出现；冷却期内不重复。

## 9. 性能与资源

- 聚合在写缓存时完成，接口仅读缓存 → 降低接口延迟。
- 长列表使用虚拟滚动；热力图/图表延迟加载。

## 10. 后续可扩展

- 资金风格偏好（大盘/小盘、成长/价值）映射到板块热力。
- 事件驱动（公告/新闻）叠加，辅助解释拉升原因。
- 盘后“市场行情”独立页（历史/复盘）作为后续增强。
