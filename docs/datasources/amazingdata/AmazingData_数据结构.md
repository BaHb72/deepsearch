# AmazingData 数据结构（提取）

> 来源：《中国银河证券星耀数智 AmazingData 开发手册》4.2
> “数据结构说明”；文档版本：V1.0.14（最新发布日期：2025-09-11）。本文件仅整理“数据结构”定义（不含接口示例与算法说明），用于快速查阅。

---

## 命名与排版说明

- 文档中出现的 `ask _volumeX` / `bid _volumeX`（中间多余空格）为排版问题，等效字段名为 `ask_volumeX` / `bid_volumeX`。
- 文档中 `underlying_security_cod` 疑似为 `underlying_security_code` 的排版/截断问题，以下保持原文字段名并在说明中特别标注。

---

## 4.2.1 Level‑1 快照 `Snapshot`

适用：股票、ETF、可转债等 Level‑1 快照。

| 字段名                | 类型       | 说明            |
|--------------------|----------|---------------|
| code               | str      | 证券代码+市场       |
| trade_time         | datetime | 交易所行情数据时间     |
| pre_close          | float    | 昨收价           |
| last               | float    | 最新价           |
| open               | float    | 开盘价           |
| high               | float    | 最高价           |
| low                | float    | 最低价           |
| close              | float    | 收盘价           |
| volume             | float    | 成交总量          |
| amount             | float    | 成交总金额         |
| num_trades         | float    | 成交笔数          |
| high_limited       | float    | 涨停价           |
| low_limited        | float    | 跌停价           |
| ask_price1         | float    | 卖1档价格         |
| ask_price2         | float    | 卖2档价格         |
| ask_price3         | float    | 卖3档价格         |
| ask_price4         | float    | 卖4档价格         |
| ask_price5         | float    | 卖5档价格         |
| ask_volume1        | int      | 卖1档量          |
| ask_volume2        | int      | 卖2档量          |
| ask_volume3        | int      | 卖3档量          |
| ask_volume4        | int      | 卖4档量          |
| ask_volume5        | int      | 卖5档量          |
| bid_price1         | float    | 买1档价格         |
| bid_price2         | float    | 买2档价格         |
| bid_price3         | float    | 买3档价格         |
| bid_price4         | float    | 买4档价格         |
| bid_price5         | float    | 买5档价格         |
| bid_volume1        | int      | 买1档量          |
| bid_volume2        | int      | 买2档量          |
| bid_volume3        | int      | 买3档量          |
| bid_volume4        | int      | 买4档量          |
| bid_volume5        | int      | 买5档量          |
| iopv               | float    | 净值估产（仅基金品种有效） |
| trading_phase_code | str      | 交易阶段代码        |

---

## 4.2.2 ETF 期权快照 `SnapshotOption`

适用：上/深交所 ETF 期权。

| 字段名                     | 类型       | 说明                                     |
|-------------------------|----------|----------------------------------------|
| code                    | str      | 证券代码+市场                                |
| trade_time              | datetime | 交易所行情数据时间                              |
| trading_phase_code      | str      | 交易阶段代码                                 |
| total_long_position     | int      | 总持仓量                                   |
| volume                  | float    | 成交总量                                   |
| amount                  | float    | 成交总金额                                  |
| pre_close               | float    | 昨收价                                    |
| pre_settle              | float    | 上次结算价                                  |
| auction_price           | float    | 动态参考价（波动性中断参考价，仅上海有效）                  |
| auction_volume          | int      | 虚拟匹配数量（仅上海有效）                          |
| last                    | float    | 最新价                                    |
| open                    | float    | 开盘价                                    |
| high                    | float    | 最高价                                    |
| low                     | float    | 最低价                                    |
| close                   | float    | 收盘价                                    |
| settle                  | float    | 本次结算价                                  |
| high_limited            | float    | 涨停价                                    |
| low_limited             | float    | 跌停价                                    |
| ask_price1              | float    | 卖1档价格                                  |
| ask_price2              | float    | 卖2档价格                                  |
| ask_price3              | float    | 卖3档价格                                  |
| ask_price4              | float    | 卖4档价格                                  |
| ask_price5              | float    | 卖5档价格                                  |
| ask_volume1             | int      | 卖1档量                                   |
| ask_volume2             | int      | 卖2档量                                   |
| ask_volume3             | int      | 卖3档量                                   |
| ask_volume4             | int      | 卖4档量                                   |
| ask_volume5             | int      | 卖5档量                                   |
| bid_price1              | float    | 买1档价格                                  |
| bid_price2              | float    | 买2档价格                                  |
| bid_price3              | float    | 买3档价格                                  |
| bid_price4              | float    | 买4档价格                                  |
| bid_price5              | float    | 买5档价格                                  |
| bid_volume1             | int      | 买1档量                                   |
| bid_volume2             | int      | 买2档量                                   |
| bid_volume3             | int      | 买3档量                                   |
| bid_volume4             | int      | 买4档量                                   |
| bid_volume5             | int      | 买5档量                                   |
| contract_type           | str      | 合约类别                                   |
| expire_date             | int      | 到期日                                    |
| underlying_security_cod | str      | 标的代码（原文字段名为 *underlying_security_cod*） |
| exercise_price          | float    | 行权价                                    |

---

## 4.2.3 期货快照 `SnapshotFuture`

适用：中金所/上期所/大商所/郑商所/上期能源期货。

| 字段名               | 类型       | 说明        |
|-------------------|----------|-----------|
| code              | str      | 证券代码+市场   |
| trade_time        | datetime | 交易所行情数据时间 |
| action_day        | str      | 业务日期      |
| trading_day       | str      | 交易日期      |
| pre_close         | float    | 昨收价       |
| pre_settle        | float    | 上次结算价     |
| pre_open_interest | int      | 昨持仓量      |
| open_interest     | int      | 持仓量       |
| last              | float    | 最新价       |
| open              | float    | 开盘价       |
| high              | float    | 最高价       |
| low               | float    | 最低价       |
| close             | float    | 收盘价       |
| volume            | float    | 成交总量      |
| amount            | float    | 成交总金额     |
| high_limited      | float    | 涨停价       |
| low_limited       | float    | 跌停价       |
| ask_price1        | float    | 卖1档价格     |
| ask_price2        | float    | 卖2档价格     |
| ask_price3        | float    | 卖3档价格     |
| ask_price4        | float    | 卖4档价格     |
| ask_price5        | float    | 卖5档价格     |
| ask_volume1       | int      | 卖1档量      |
| ask_volume2       | int      | 卖2档量      |
| ask_volume3       | int      | 卖3档量      |
| ask_volume4       | int      | 卖4档量      |
| ask_volume5       | int      | 卖5档量      |
| bid_price1        | float    | 买1档价格     |
| bid_price2        | float    | 买2档价格     |
| bid_price3        | float    | 买3档价格     |
| bid_price4        | float    | 买4档价格     |
| bid_price5        | float    | 买5档价格     |
| bid_volume1       | int      | 买1档量      |
| bid_volume2       | int      | 买2档量      |
| bid_volume3       | int      | 买3档量      |
| bid_volume4       | int      | 买4档量      |
| bid_volume5       | int      | 买5档量      |
| average_price     | float    | 当日均价      |
| settle            | float    | 本次结算价     |

---

## 4.2.4 指数快照 `SnapshotIndex`

适用：北交所/上交所/深交所指数。

| 字段名        | 类型       | 说明                |
|------------|----------|-------------------|
| code       | str      | 证券代码+市场           |
| trade_time | datetime | 交易所行情数据时间         |
| last       | float    | 最新价               |
| pre_close  | float    | 前收盘价              |
| open       | float    | 今开盘价              |
| high       | float    | 最高价               |
| low        | float    | 最低价               |
| close      | float    | 收盘价（仅上海有效）        |
| volume     | int      | 成交总量（上交所：手，深交所：张） |
| amount     | float    | 成交总金额             |

---

## 4.2.5 港股通快照 `SnapshotHKT`

适用：港股通标的。

| 字段名                    | 类型       | 说明        |
|------------------------|----------|-----------|
| code                   | str      | 证券代码+市场   |
| trade_time             | datetime | 交易所行情数据时间 |
| pre_close              | float    | 昨收价       |
| last                   | float    | 最新价       |
| high                   | float    | 最高价       |
| low                    | float    | 最低价       |
| volume                 | float    | 成交总量      |
| amount                 | float    | 成交总金额     |
| nominal_price          | float    | 暗盘价       |
| ref_price              | float    | 参考价       |
| bid_price_limit_up     | float    | 买盘上限价     |
| bid_price_limit_down   | float    | 买盘下限价     |
| offer_price_limit_up   | float    | 卖盘上限价     |
| offer_price_limit_down | float    | 卖盘下限价     |
| high_limited           | float    | 冷静期价格上限   |
| low_limited            | float    | 冷静期价格下限   |
| ask_price1             | float    | 卖1档价格     |
| ask_price2             | float    | 卖2档价格     |
| ask_price3             | float    | 卖3档价格     |
| ask_price4             | float    | 卖4档价格     |
| ask_price5             | float    | 卖5档价格     |
| ask_volume1            | int      | 卖1档量      |
| ask_volume2            | int      | 卖2档量      |
| ask_volume3            | int      | 卖3档量      |
| ask_volume4            | int      | 卖4档量      |
| ask_volume5            | int      | 卖5档量      |
| bid_price1             | float    | 买1档价格     |
| bid_price2             | float    | 买2档价格     |
| bid_price3             | float    | 买3档价格     |
| bid_price4             | float    | 买4档价格     |
| bid_price5             | float    | 买5档价格     |
| bid_volume1            | int      | 买1档量      |
| bid_volume2            | int      | 买2档量      |
| bid_volume3            | int      | 买3档量      |
| bid_volume4            | int      | 买4档量      |
| bid_volume5            | int      | 买5档量      |
| trading_phase_code     | str      | 交易阶段代码    |

---

## 4.2.6 K 线 `Kline`

适用：股票、指数、ETF、期货等历史或实时 K 线。

| 字段名        | 类型       | 说明        |
|------------|----------|-----------|
| code       | str      | 证券代码+市场   |
| trade_time | datetime | 交易所行情数据时间 |
| open       | float    | 今开盘价      |
| high       | float    | 最高价       |
| low        | float    | 最低价       |
| close      | float    | 收盘价       |
| volume     | int      | 成交总量      |
| amount     | float    | 成交总金额     |

---

> 参考关联枚举：`trading_phase_code`、`Period` 等详见手册“4.1 字段取值说明”。
