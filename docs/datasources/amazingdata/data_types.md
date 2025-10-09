# 星耀数智（AmazingData）数据类型定义

> 本文件整理自 `docs/datasources/amazingdata/AmazingData_API.md`（2025-09-11，文档版本 V1.0.8），补充 DeepSearch 使用过程中常见的枚举值、数据结构与字段分组，便于快速查阅。对于未列出的长表字段，请查阅官方 PDF 原文。  
> 更新时间：2025-10-10

## 目录
1. [枚举类型](#枚举类型)
2. [数据结构](#数据结构)
3. [字段分组与数据集说明](#字段分组与数据集说明)
4. [参考资料](#参考资料)

---

## 枚举类型

### security_type（沪深北）

| 枚举值 | 说明 |
| ------ | ---- |
| `EXTRA_STOCK_A` | 上交所、深交所、北交所股票列表 |
| `EXTRA_STOCK_A_SH_SZ` | 沪深 A 股 |
| `EXTRA_INDEX_A` | 沪深北指数 |
| `EXTRA_INDEX_A_SH_SZ` | 沪深指数 |
| `SH_INDEX` | 上交所指数 |
| `SZ_INDEX` | 深交所指数 |
| `BJ_INDEX` | 北交所指数 |
| `EXTRA_ETF` | 沪深 ETF |
| `SH_ETF` | 上交所 ETF |
| `SZ_ETF` | 深交所 ETF |
| `EXTRA_KZZ` | 沪深可转债 |
| `SH_KZZ` | 上交所可转债 |
| `SZ_KZZ` | 深交所可转债 |
| `EXTRA_HKT` | 沪深港通 |
| `SH_HKT` | 沪港通标的 |
| `SZ_HKT` | 深港通标的 |

### security_type（期货交易所）

| 枚举值 | 说明 |
| ------ | ---- |
| `EXTRA_FUTURE` | 中金所、上期所、大商所、郑商所、上期所能源 |
| `ZJ_FUTURE` | 中金所期货 |
| `SQ_FUTURE` | 上期所期货 |
| `DS_FUTURE` | 大商所期货 |
| `ZS_FUTURE` | 郑商所期货 |
| `SN_FUTURE` | 上海国际能源交易中心期货 |

### market

| 枚举值 | 说明 |
| ------ | ---- |
| `SH` | 上海证券交易所 |
| `SZ` | 深圳证券交易所 |
| `BJ` | 北京证券交易所 |

### trading_phase_code（节选）

- 上海现货：8 位字符数组，包含启动、集合竞价、连续交易、闭市、停牌等标记；
- 深圳现货：`S` 启动、`O` 开盘集合、`T` 连续竞价、`B` 休市、`C` 收盘集合、`E` 已闭市、`H` 临停、`A` 盘后、`V` 波动性中断；第二位 `0` 正常、`1` 全天停牌；
- 港股通：`1` 正常交易，`2` 停牌，`3` 复牌。

### Period（数据周期）

| 枚举值 | 说明 |
| ------ | ---- |
| `Period.tick.value` | 逐笔数据 |
| `Period.snapshot.value` | Level-1 快照 |
| `Period.snapshot_future.value` | 期货快照 |
| `Period.snapshot_hkt.value` | 港股通快照 |
| `Period.min1.value` | 1 分钟线 |
| `Period.min3.value` | 3 分钟线 |
| `Period.min5.value` | 5 分钟线 |
| `Period.min10.value` | 10 分钟线 |
| `Period.min15.value` | 15 分钟线 |
| `Period.min30.value` | 30 分钟线 |
| `Period.min60.value` | 60 分钟线 |
| `Period.min120.value` | 120 分钟线 |
| `Period.day.value` | 日线 |
| `Period.week.value` | 周线 |
| `Period.month.value` | 月线 |
| `Period.season.value` | 季度线 |
| `Period.year.value` | 年线 |

### STATEMENT_TYPE（常用报表类型）

| 代码 | 说明 |
| ---- | ---- |
| `1` | 合并报表（最新口径） |
| `2` | 合并报表（单季度） |
| `3` | 合并报表（单季度调整） |
| `4` | 合并报表（调整） |
| `5` | 合并报表（更正前） |
| `6` | 母公司报表 |
| `7` | 母公司报表（单季度） |
| `8` | 母公司报表（单季度调整） |
| `9` | 母公司报表（调整） |
| `10` | 母公司报表（更正前） |
| `11`-`37` | 未公开、借壳前与多次更正等扩展口径，详见官方 PDF 4.1.6 |

### DIV_PROGRESS（分红进度）

| 代码 | 描述 |
| ---- | ---- |
| `10` | 股东提议 |
| `20` | 董事会预案 |
| `30` | 股东大会通过 |
| `40` | 实施 |
| `50` | 已完成 |
| `13` | 分红方案待定 |
| 其余取值 | 请参考官方文档 4.1.7 |

### PROGRESS（配股进度）

| 代码 | 描述 |
| ---- | ---- |
| `10` | 董事会预案 |
| `20` | 股东大会通过 |
| `30` | 证监会受理 |
| `40` | 证监会核准 |
| `50` | 实施 |
| `60` | 完成 |
| 其余取值 | 参考官方文档 4.1.8 |

---

## 数据结构

### Snapshot（Level-1 股票 / ETF / 可转债）

常用字段：
- `code`：证券代码
- `name`：证券简称
- `time`：时间戳（`YYYY-MM-DD HH:MM:SS`）
- `last_price` / `open` / `high` / `low` / `prev_close`
- `volume` / `amount`
- 五档委托：`bid1`~`bid5`、`bid1_volume`~`bid5_volume`、`ask1`~`ask5`
- 涨跌指标：`change`、`change_percent`、`amplitude`、`turnover`
- 涨跌停价格：`limit_up`、`limit_down`
- `status`：交易状态

### SnapshotIndex（指数快照）

- 与股票快照结构相近，额外字段包括 `pre_settle`、`open_interest`、`up_down_count` 等。
- 订阅时通过 `onSnapshot_index` 回调，历史查询由 `query_snapshot` 返回。

### SnapshotFuture（期货快照）

- 提供 `last_price`、`open`、`high`、`low`、`volume`、`amount`；
- 包含 `pre_settle`、`settle_price`、`open_interest` 等期货特有字段；
- 订阅回调 `onSnapshot_future`。

### SnapshotHKT（港股通快照）

- 字段覆盖港股通特有的交易状态、涨跌幅限制；
- 订阅回调 `onSnapshot_hkt`，历史查询同 `query_snapshot`。

### Kline（K 线结构）

- `open`、`high`、`low`、`close`、`volume`、`amount`
- `turnover_rate`、`amplitude`、`change`、`change_percent`
- `trade_time`：时间戳（分钟或日粒度）

> 以上结构在官方文档 4.2.1~4.2.5 有完整字段列表，可结合 pandas 表头进行比对。

---

## 字段分组与数据集说明

- **基础数据**：`get_code_info`、`get_code_list`、`get_stock_basic`、`get_history_stock_status`、`get_bj_code_mapping`。主要字段描述位于 PDF 3.5.2.*
- **复权因子**：`get_backward_factor`、`get_adj_factor` 返回以交易日为索引的 DataFrame，列为证券代码，值为因子。
- **财务报表**：`get_balance_sheet`、`get_cash_flow`、`get_income`、`get_profit_express`、`get_profit_notice`。字段命名遵循英文缩写，结合 `STATEMENT_TYPE`、`REPORT_TYPE`、`ANN_DATE` 等元信息。
- **股东股本**：`get_share_holder`、`get_holder_num`、`get_equity_structure`、`get_equity_pledge_freeze`、`get_equity_restricted`。包含股东名称、持股数量、股份性质、解禁日期等字段。
- **权益与分红**：`get_dividend`、`get_right_issue` 配合 `DIV_PROGRESS`、`PROGRESS` 枚举描述方案进度。
- **融资融券**：`get_margin_summary`、`get_margin_detail`，提供融资买入、融券卖出、余额、偿还等指标。
- **龙虎榜**：`get_long_hu_bang`，包含营业部名称、买入/卖出金额、占比等信息。

调用这些接口时建议：
- 先确认 `code_list`、`start_date`、`end_date`、`local_path` 等参数；
- 对照 `STATEMENT_TYPE`、`DIV_PROGRESS` 等枚举解析语义；
- 将 DataFrame 字段映射在本地保存，以便后续数据校验。

---

## 参考资料

- `docs/datasources/amazingdata/AmazingData_API.md`：官方 PDF 全量展开。
- `docs/datasources/amazingdata/api_reference.md`：接口分组、参数与示例。
- `docs/datasources/amazingdata/api_guide.md`：使用流程、缓存策略与最佳实践。
- `docs/datasources/amazingdata/quick_start.md`：入门示例与常见问题。

如需新增枚举或字段，请先更新源 PDF/Markdown，再同步本文件与其他文档。
