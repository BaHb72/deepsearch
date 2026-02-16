# AmazingData API 完整清单

## 概述

本文档汇总了AmazingData开发手册 (V1.0.24, 2025-12-16) 中所有API接口，并与现有实现进行对比。

---

## 接口汇总

### 1. 基础接口 (System)

| 接口 | 功能 | 状态 |
|------|------|------|
| login | 登录 | 已实现 |
| logout | 登出 | 未确认 |
| update_password | 更新密码 | 未确认 |

### 2. 基础数据 (BaseData)

**文档章节**: 3.5.2

| 接口 | 功能 | 状态 | 说明 |
|------|------|------|------|
| get_code_info | 获取证券基本信息 | 已实现 | |
| get_code_list | 获取最新代码列表 | 已实现 | |
| get_future_code_list | 获取期货代码列表 | 已实现 | |
| get_option_code_list | 获取期权代码列表 | 已实现 | |
| get_backward_factor | 获取后复权因子 | 已实现 | |
| get_adj_factor | 获取复权因子 | 已实现 | |
| get_hist_code_list | 获取历史代码列表 | 已实现 | |
| get_calendar | 获取交易日历 | 已实现 | |
| get_stock_basic | 股票基本信息 | 已实现 | **(修正归属: 原InfoData)** |
| get_history_stock_status | 历史股票状态 | 已实现 | **(修正归属: 原InfoData)** |
| get_bj_code_mapping | 北交所代码映射 | 已实现 | **(修正归属: 原InfoData)** |

### 3. 实时行情 (SubscribeData)

**文档章节**: 3.5.3

| 接口 | 功能 | 状态 | 说明 |
|------|------|------|------|
| onSnapshotIndex | 指数快照回调 | 已实现 | |
| onSnapshot | 股票快照回调 | 已实现 | |
| onSnapshotfuture | 期货快照回调 | 已实现 | |
| onSnapshotetf | ETF快照回调 | 已实现 | |
| onSnapshotkzz | 可转债快照回调 | 已实现 | |
| onSnapshothkt | 港股通快照回调 | 已实现 | 与 `onSnapshotglra` 功能描述重复 |
| onSnapshotglra | 港股通快照回调 (新增) | 新增 (待实现) | 与 `onSnapshothkt` 功能描述重复 |
| onSnapshotoption | ETF期权快照回调 | 已实现 | |
| OnKLine | 实时K线回调 | 已实现 | |

### 4. 历史行情 (MarketData)

**文档章节**: 3.5.4

| 接口 | 功能 | 状态 |
|------|------|------|
| query_snapshot | 行情快照查询 | 已实现 |
| query_kline | K线数据查询 | 已实现 |

### 5. 财务数据 (InfoData)

**文档章节**: 3.5.5

| 接口 | 功能 | 状态 |
|------|------|------|
| get_balance_sheet | 资产负债表 | 已实现 |
| get_cash_flow | 现金流量表 | 已实现 |
| get_income | 利润表 | 已实现 |
| get_profit_express | 业绩快报 | 已实现 |
| get_profit_notice | 业绩预告 | 已实现 |

### 6. 股东股本 (InfoData)

**文档章节**: 3.5.6

| 接口 | 功能 | 状态 |
|------|------|------|
| get_share_holder | 十大股东 | 已实现 |
| get_holder_num | 股东人数 | 已实现 |
| get_equity_structure | 股本结构 | 已实现 |
| get_equity_pledge_freeze | 股权质押冻结 | 已实现 |
| get_equity_restricted | 限售解禁 | 已实现 |

### 7. 股东权益 (InfoData)

**文档章节**: 3.5.7

| 接口 | 功能 | 状态 |
|------|------|------|
| get_dividend | 分红派息 | 已实现 |
| get_right_issue | 配股 | 已实现 |

### 8. 融资融券 (InfoData)

**文档章节**: 3.5.8

| 接口 | 功能 | 状态 |
|------|------|------|
| get_margin_summary | 融资融券汇总 | 已实现 |
| get_margin_detail | 融资融券明细 | 已实现 |

### 9. 交易异动 (InfoData)

**文档章节**: 3.5.9

| 接口 | 功能 | 状态 |
|------|------|------|
| get_long_hu_bang | 龙虎榜 | 已实现 |
| get_block_trading | 大宗交易 | 已实现 |

### 10. 期权数据 (InfoData) [新增]

**文档章节**: 3.5.10

| 接口 | 功能 | 状态 |
|------|------|------|
| get_option_basic_info | 期权基本资料 | 新增 (待实现) |
| get_option_std_ctr_specs | 期权标准合约属性 | 新增 (待实现) |
| get_option_mon_ctr_specs | 期权月合约属性变动 | 新增 (待实现) |

### 11. ETF数据 (InfoData) [新增]

**文档章节**: 3.5.11

| 接口 | 功能 | 状态 |
|------|------|------|
| get_etf_pcf | ETF申赎数据 | 新增 (待实现) |
| get_fund_share | ETF基金份额 | 新增 (待实现) |
| get_fund_iopv | ETF每日IOPV | 新增 (待实现) |

### 12. 指数数据 (InfoData) [新增]

**文档章节**: 3.5.12

| 接口 | 功能 | 状态 |
|------|------|------|
| get_index_constituent | 指数成份股 | 新增 (待实现) |
| get_index_weight | 指数成份股权重 | 新增 (待实现) |

### 13. 行业指数 (InfoData) [新增]

**文档章节**: 3.5.13

| 接口 | 功能 | 状态 |
|------|------|------|
| get_industry_base_info | 行业指数基础信息 | 新增 (待实现) |
| get_industry_constituent | 行业指数成份股 | 新增 (待实现) |
| get_industry_weight | 行业指数权重 | 新增 (待实现) |
| get_industry_daily | 行业指数日行情 | 新增 (待实现) |

### 14. 可转债数据 (InfoData) [新增]

**文档章节**: 3.5.14

| 接口 | 功能 | 状态 |
|------|------|------|
| get_kzz_issuance | 可转债发行 | 新增 (待实现) |
| get_kzz_share | 可转债份额 | 新增 (待实现) |
| get_kzz_conv | 可转债转股 | 新增 (待实现) |
| get_kzz_conv_change | 转股变动 | 新增 (待实现) |
| get_kzz_corr | 修正数据 | 新增 (待实现) |
| get_kzz_call | 赎回数据 | 新增 (待实现) |
| get_kzz_put | 回售数据 | 新增 (待实现) |
| get_kzz_put_call_item | 回售赎回条款 | 新增 (待实现) |
| get_kzz_put_explanation | 回售条款说明 | 新增 (待实现) |
| get_kzz_call_explanation | 赎回条款说明 | 新增 (待实现) |
| get_kzz_suspend | 停复牌信息 | 新增 (待实现) |

### 15. 国债数据 (InfoData) [新增]

**文档章节**: 3.5.15

| 接口 | 功能 | 状态 |
|------|------|------|
| get_treasury_yield | 国债收益率 | 新增 (待实现) |

---

## 枚举值支持

### security_type (代码类型)

请参考开发手册 **附录 4.1.1** 及 **4.1.2**。
包含 A股 (SH_A, SZ_A, BJ_A)、指数 (SH_INDEX...)、ETF、可转债、期货、期权等多种类型。

### market (市场类型)

请参考开发手册 **附录 4.1.4**。
支持 SH, SZ, BJ, SHF, CFE, DCE, CZC, INE 等。

---

## 统计

- **总接口数**: 63个
- **已实现数**: 36个 (基于旧版统计)
- **新增/待实现**: 27个
- **当前覆盖率**: ~57%
