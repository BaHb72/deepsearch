# AmazingData API 完整清单

## 概述
本文档汇总了AmazingData开发手册中所有API接口，与现有实现进行对比。

---

## 已实现接口汇总

### 1. BaseData 模块 (8个接口)
| 接口 | 功能 | 状态 |
|------|------|------|
| get_code_info | 获取证券基本信息 | 已实现 |
| get_code_list | 获取最新代码列表 | 已实现 |
| get_future_code_list | 获取期货代码列表 | 已实现 |
| get_option_code_list | 获取期权代码列表 | 已实现 |
| get_backward_factor | 获取后复权因子 | 已实现 |
| get_adj_factor | 获取复权因子 | 已实现 |
| get_hist_code_list | 获取历史代码列表 | 已实现 |
| get_calendar | 获取交易日历 | 已实现 |

### 2. InfoData 模块 (19个接口)
| 接口 | 功能 | 状态 |
|------|------|------|
| get_stock_basic | 股票基本信息 | 已实现 |
| get_history_stock_status | 历史股票状态 | 已实现 |
| get_bj_code_mapping | 北交所代码映射 | 已实现 |
| get_balance_sheet | 资产负债表 | 已实现 |
| get_cash_flow | 现金流量表 | 已实现 |
| get_income | 利润表 | 已实现 |
| get_profit_express | 业绩快报 | 已实现 |
| get_profit_notice | 业绩预告 | 已实现 |
| get_share_holder | 十大股东 | 已实现 |
| get_holder_num | 股东人数 | 已实现 |
| get_equity_structure | 股本结构 | 已实现 |
| get_equity_pledge_freeze | 股权质押冻结 | 已实现 |
| get_equity_restricted | 限售解禁 | 已实现 |
| get_dividend | 分红派息 | 已实现 |
| get_right_issue | 配股 | 已实现 |
| get_margin_summary | 融资融券汇总 | 已实现 |
| get_margin_detail | 融资融券明细 | 已实现 |
| get_long_hu_bang | 龙虎榜 | 已实现 |
| get_block_trading | 大宗交易 | 已实现 |

### 3. MarketData 模块 (2个接口)
| 接口 | 功能 | 状态 |
|------|------|------|
| query_snapshot | 行情快照查询 | 已实现 |
| query_kline | K线数据查询 | 已实现 |

### 4. SubscribeDataCallbacks 模块 (7个接口)
| 接口 | 功能 | 状态 |
|------|------|------|
| onSnapshotindex | 指数快照回调 | 已实现 |
| onSnapshot | 股票快照回调 | 已实现 |
| onSnapshotfuture | 期货快照回调 | 已实现 |
| onSnapshotetf | ETF快照回调 | 已实现 |
| onSnapshotkzz | 可转债快照回调 | 已实现 |
| onSnapshothkt | 港股通快照回调 | 已实现 |
| OnKLine | 实时K线回调 | 已实现 |

---

## 枚举值支持

### security_type (28种类型)
包含A股、指数、ETF、可转债、港股通、期货、期权等全部类型。

### market (10种市场)
支持SH/SZ/BJ/SHF/CFE/DCE/CZC/INE/SHN/SZN。

### periods (13种周期)
支持1/3/5/10/15/30/60/120分钟，日/周/月/季/年。

---

## 统计

- **总接口数**: 36个
- **已实现数**: 36个
- **未实现数**: 0个
- **覆盖率**: 100%
