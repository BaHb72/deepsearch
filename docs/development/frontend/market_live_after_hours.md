# 市场实时与盘后展示改造方案（前端 + 后端协同）

## 背景与目标

- 背景：当前实时行情接口在休市/离线时直接返回错误（如 503 + `DATA_SOURCE_OFFLINE`），前端出现“获取失败”的提示，体验不佳。
- 目标：在休市（off_day / no_trade）或数据源短暂不可用时，仍然展示“最后一次有效快照”，并在页面明显位置提示“数据为盘后/陈旧”，避免空白与报错。
- 范围：WebUI 前端（React+AntD）与对应 `/api/market/live/*` 后端接口（FastAPI）。不涉及交易撮合、下单等功能。

## 现状问题与成因

- 现状：
  - `/api/market/live/strength`、`/order-imbalance`、`/auction-quality` 在无法获取到缓存时直接 503。
  - `TradingSessionGuard` 因交易日日历缺失（AmazingData 未实现 `get_calendar`）将整天判为 `off_day`，`pipeline.run_once`
      不执行，缓存永远为空。
- 用户感知：页面经常显示“获取失败”，无法了解市场概况。

## 概念与状态模型

- 交易阶段（phase_state）：`off_day`（非交易日）、`no_trade`（闭市时段）、`auction`（集合竞价）、`continuous`（连续竞价）。
- 数据新鲜度：
  - `fresh`：在有效期内（非陈旧）。
  - `stale`：超出缓存有效期或休市后展示的快照。
- 数据来源：`data_source`（如 `amazingdata`、`akshare`），`fallback`（回落链路标识）。

## 页面规划

- 页面角色划分：
  - “实时总览”（现有页，聚合状态与监控）：保留现状，仅加状态条与链接。
  - “市场实时”（现有 Market Live 视图）：在盘中刷新；在盘后展示“最后快照（标记陈旧）”。
  - “市场行情（新）”：可选新页，用于“当日盘后浏览/复盘”，聚焦当日最终快照与排行榜沉淀数据。

### 方案 A：复用现有 Market Live（推荐）

- 不新增页面，仅在现有实时页面：
  - 顶部状态条：显示 `交易阶段` + `上次更新时间 asOf` + `数据新鲜度`。
  - 榜单卡片：当 `stale: true` 时显示灰色徽标“陈旧”，并提供“刷新/回源”按钮。
  - 无数据时：用“占位数据 + 复用最近成功数据（一定时间阈值内）”。
- 优点：改动面小，导航结构不变；用户理解成本低。
- 缺点：盘后复盘的聚合能力较弱（可后续增强）。

### 方案 B：新增“市场行情”页（可选）

- 新增路由 `/market/daily`：
  - 今日盘后：展示当日最终快照（收盘后最后一次缓存）、统计排行（强度/委差/竞价质量）。
  - 历史回看：按日期选择器查看历史日数据（依赖后端存档或持久化）。
- 与实时页的关系：实时页关注“当前瞬时”；行情页关注“当日结果/历史”。
- 可作为迭代 2 的增强目标。

## 前端交互规范（适用于 A/B 两方案）

- 顶部状态条（Status Bar）：
  - 内容：`{phase_state}`（中文映射：休市/盘中/集合竞价/闭市）、`asOf`、`retrieved_at`、`数据源`、`新鲜度`。
  - 视觉：`stale: true` 时状态条与数据卡片显示浅灰/黄色提示；盘中为正常色。
- 自动刷新策略：
  - 盘中（continuous/auction）：按用户选择的 `windows` 周期自动刷新。
  - 闭市/no_trade：降频刷新（例如每 60–120 秒，尝试拉最新快照或确认休市状态）。
  - 休市/off_day：默认不自动刷新，仅允许手动“尝试回源”。
- 回源与回退：
  - 首次无数据 → 尝试一次 `refresh_market_data_once`（已有 API 内部调用）→ 仍无数据 → 返回最后快照（若有）并标记
      `stale: true`；无快照则返回空数组与明确提示。
- 错误与空状态：
  - 统一使用“内嵌提示 + 顶部状态条说明”，不弹窗阻断。
- 列表/图表：
  - `items` 为空时显示空态；有 `stale` 时在标题处展示徽标；行内保留 `ts/asOf`。

## API/数据契约调整（后端）

- 对 `/api/market/live/*` 的响应结构补充：
  - 统一字段：`retrieved_at`、`asOf`（或 `as_of` 兼容）、`stale`（bool）、`data_source`、`cache: { cachedAt, expiresAt }`、
      `phase_state`（可选）。
  - 当缓存缺失：尝试 `refresh_market_data_once`；若仍无数据，返回 `items: []` + `stale: true` + `phase_state` +
      `detail:{code:'DATA_SOURCE_OFFLINE'}`，HTTP 仍返回 200（便于前端一致处理）。
- 示例（strength）：

  ```json
  {
    "windows": ["1m","5m"],
    "boards": ["主板","创业板"],
    "items": [ {"board":"主板","window":"1m","speed_per_min":123.4,"ts":"2025-11-06T14:57:00Z"} ],
    "retrieved_at":"2025-11-06T15:00:05Z",
    "asOf":"2025-11-06T14:57:00Z",
    "stale": true,
    "cache": {"cachedAt":"2025-11-06T14:57:01Z","expiresAt":"2025-11-06T15:00:01Z"},
    "data_source":"amazingdata",
    "phase_state":"off_day"
  }
  ```

- 保持兼容：现有前端读取 `payload.data.items` / 直返 `payload.items` 两种格式已通过封装适配（`request.ts`）。

## 后端改造清单

1. live_api 兜底逻辑：
    - 缓存无记录 → `await refresh_market_data_once(app_state)` → 重取；仍无 → 返回
      `200 + items:[] + stale:true + phase_state`（不再 503）。
2. Guard 与日历：
    - 为 `AmazingDataProvider.get_calendar` 提供最小实现，或新增“外部交易日服务/本地日历文件”作为后备，避免空日历→永久
      off_day。
3. Fallback 数据源：
    - 当主源异常（SDK 登录失败/推送异常）时，按 `settings.*.yaml data_sources.fallback_order` 回退到 `akshare`
      拉一次静态榜单，写入缓存并标记 `data_source: 'akshare'`、`stale:true`。
4. 监控：
    - 记录 `stale 返回次数`、`fallback 命中次数`、`guard 判定分布` 指标，便于运维。

## 配置项建议（settings.*.yaml）

- `market_data.realtime`：
  - `enabled`、`interval_seconds`、`initial_step_timeout_seconds`、`off_day_interval_seconds`、`no_trade_interval_seconds`
      等。
  - `redis.strength_ttl` / `imbalance_ttl` / `auction_ttl`：控制缓存时效。
- 新增可选：
  - `allow_stale_return: true`（默认开）；
  - `fallback_on_off_day: true`（休市也允许展示最后快照）；
  - `fallback_provider: ['akshare']`（回退顺序覆盖）。

## 前端实现要点

- `src/services/request.ts`：已兼容 `code:0/200` 与“裸数据/包一层 data”两种响应，保留。
- `src/api/marketDataLive.ts`：接口类型增加 `stale`、`asOf`、`retrieved_at`、`phase_state`。
- `src/pages/MarketData.tsx`：
  - 顶部状态条组件（PhaseBadge + FreshnessTag + AsOf 显示）。
  - `items.length===0 && stale===true` 时展示“盘后最后快照为空”的友好提示，而非报错。
  - 自动刷新：依据 `phase_state` 调整刷新间隔。
- 可选新增：`/market/daily` 页面与路由；日期选择器；“今日/历史”切换。

## 监控与埋点

- 前端：页面载入/刷新/手动回源事件、`stale` 展示次数、fallback 提示点击率。
- 后端：`stale` 响应计数、fallback 命中率、guard 阶段判定分布、SDK 登录失败次数。

## 性能与容量

- Redis key 约定：
  - `market:strength:{window}`、`market:order-imbalance:{window}`、`market:auction:{board}`、`market:boards`。
- TTL 策略：强度/委差/竞价默认 180s；盘后展示不强制刷新，只标记 `stale:true`。

## 测试计划

- 休市日：应返回 `200 + stale:true + items（可能为空）`，页面不报错。
- 闭市时段：降频刷新，仍展示最后快照；切回盘中自动恢复。
- 主源不可用：触发 fallback，返回 `data_source:'akshare' + stale:true`。
- 时区/跨日：本地时区显示 asOf，跨 00:00 正确滚动。

## 风险与回滚

- 风险：误判交易日、fallback 数据质量偏差。
- 回滚：保留现有 503 行为开关（`allow_stale_return:false`）。

## 里程碑与分工

1. 后端（1d）：live_api 兜底逻辑 + 200 响应；phase_state 注入；日志/指标。
2. 数据（日历）（1–2d）：补交易日日历；或接入外部服务。
3. 前端（1d）：状态条组件、stale 显示与刷新策略、空态文案。
4. 文档（0.5d）：更新 README、API 文档与运维手册。

---
如需增强“盘后复盘”体验，采用方案 B 新建 `/market/daily`，与实时页并行演进。
