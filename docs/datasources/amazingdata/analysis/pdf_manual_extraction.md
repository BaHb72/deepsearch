# AmazingData 开发手册 (PDF) 接口提取

**文档版本**: V1.0.24 (2025年12月16日)
**提取日期**: 2026年2月7日

---

## 接口列表

### 3.5.1 基础接口 (System)

1. **login**: 登录
2. **logout**: 登出
3. **update_password**: 更新密码

### 3.5.2 基础数据 (BaseData)

1. **get_code_info**: 每日最新证券信息
2. **get_code_list**: 每日最新代码表 (沪深北)
3. **get_future_code_list**: 每日最新代码表 (期货)
4. **get_option_code_list**: 每日最新代码表 (期权)
5. **get_backward_factor**: 复权因子 (后复权)
6. **get_adj_factor**: 复权因子 (单次)
7. **get_hist_code_list**: 历史代码表
8. **get_calendar**: 交易日历
9. **get_stock_basic**: 证券基础信息
10. **get_history_stock_status**: 历史证券信息
11. **get_bj_code_mapping**: 北交所新旧代码对照表

### 3.5.3 实时行情数据 (SubscribeData)

1. **onSnapshotIndex**: 指数实时快照
2. **onSnapshot**: 股票实时快照
3. **onSnapshotglra**: 港股通实时快照 (Note: 3.5.3.3)
4. **onSnapshotfuture**: 期货实时快照
5. **onSnapshotetf**: ETF实时快照
6. **onSnapshotkzz**: 可转债实时快照
7. **onSnapshothkt**: 港股通实时快照 (Note: 3.5.3.7, Possible duplicate/alias)
8. **onSnapshotoption**: ETF期权实时快照
9. **OnKLine**: 实时K线

### 3.5.4 历史行情数据 (MarketData)

1. **query_snapshot**: 历史快照
2. **query_kline**: 历史K线

### 3.5.5 财务数据 (InfoData - Financial)

1. **get_balance_sheet**: 资产负债表
2. **get_cash_flow**: 现金流量表
3. **get_income**: 利润表
4. **get_profit_express**: 业绩快报
5. **get_profit_notice**: 业绩预告

### 3.5.6 股东股本数据 (InfoData - Shareholder)

1. **get_share_holder**: 十大股东数据
2. **get_holder_num**: 股东户数
3. **get_equity_structure**: 股本结构
4. **get_equity_pledge_freeze**: 股权冻结/质押
5. **get_equity_restricted**: 限售股解禁

### 3.5.7 股东权益数据 (InfoData - Rights)

1. **get_dividend**: 分红数据
2. **get_right_issue**: 配股数据

### 3.5.8 融资融券数据 (InfoData - Margin)

1. **get_margin_summary**: 融资融券成交汇总
2. **get_margin_detail**: 融资融券交易明细

### 3.5.9 交易异动数据 (InfoData - Transaction)

1. **get_long_hu_bang**: 龙虎榜
2. **get_block_trading**: 大宗交易

### 3.5.10 期权数据 (InfoData - Option) **[NEW]**

1. **get_option_basic_info**: 期权基本资料
2. **get_option_std_ctr_specs**: 期权标准合约属性
3. **get_option_mon_ctr_specs**: 期权月合约属性变动

### 3.5.11 ETF数据 (InfoData - ETF) **[NEW]**

1. **get_etf_pcf**: ETF每日最新申赎数据
2. **get_fund_share**: ETF基金份额
3. **get_fund_iopv**: ETF每日收益iopv

### 3.5.12 交易所指数数据 (InfoData - Index) **[NEW]**

1. **get_index_constituent**: 交易所指数成份股
2. **get_index_weight**: 交易所指数成份股日权重

### 3.5.13 行业指数数据 (InfoData - Industry) **[NEW]**

1. **get_industry_base_info**: 行业指数基本信息
2. **get_industry_constituent**: 行业指数成份股
3. **get_industry_weight**: 行业指数成份股日权重
4. **get_industry_daily**: 行业指数日行情

### 3.5.14 可转债数据 (InfoData - KZZ) **[NEW]**

1. **get_kzz_issuance**: 可转债发行
2. **get_kzz_share**: 可转债份额
3. **get_kzz_conv**: 可转债转股数据
4. **get_kzz_conv_change**: 可转债转股变动数据
5. **get_kzz_corr**: 可转债修正数据
6. **get_kzz_call**: 可转债赎回数据
7. **get_kzz_put**: 可转债回售数据
8. **get_kzz_put_call_item**: 可转债回售赎回条款
9. **get_kzz_put_explanation**: 可转债回售条款执行说明
10. **get_kzz_call_explanation**: 可转债赎回条款执行说明
11. **get_kzz_suspend**: 可转债停复牌信息

### 3.5.15 国债收益率数据 (InfoData - Treasury) **[NEW]**

1. **get_treasury_yield**: 国债收益率

---

## 统计

- **总接口数**: 63
- **新增模块**: 期权、ETF、交易所指数、行业指数、可转债、国债
