# AmazingData 枚举类型扩展文档

## 📅 更新日期
2025-12-16

## 📝 概述

根据 AmazingData SDK 官方文档附录，本文档详细说明了所有常用的枚举类型定义，包括证券类型、交易阶段代码、数据周期、报告期类型、报表类型等。

## 🔍 数据来源

本文档基于以下官方文档：
- 中泰数据交易平台数据字典说明文档附录
  - 4.1 字段取值说明
  - 4.1.1 代码类型 security_type (沪深北)
  - 4.1.2 代码类型 security_type (期货交易所)
  - 4.1.3 代码类型 security_type (期权)
  - 4.1.4 市场类型 market
  - 4.1.5 交易阶段代码 trading_phase_code
  - 4.1.6 数据周期 Period
  - 4.1.7 报告期名称 REPORT_TYPE
  - 4.1.8 报表类型代码类型 STATEMENT_TYPE

---

## 📊 枚举类型列表

### 1. AmazingDataSecurityType - 证券类型

#### 1.1 沪深北证券类型

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `STOCK_A` | `EXTRA_STOCK_A` | 上交所 A 股、深交所 A 股投资概念股类表 |
| `STOCK_A_SH_SZ` | `EXTRA_STOCK_A_SH_SZ` | 上交所 A 股深投资概念列表 |
| `SZ_A` | `SZ_A` | 深交所 A 股投资列表 |
| `BJ_A` | `BJ_A` | 北交所新投资列表 |
| `STOCK_A_SH_SZ_BJ` | `EXTRA_STOCK_A_SH_SZ` | 上交所 A 股深交所 A 股投资概念表 |
| `INDEX_A_SH_SZ` | `EXTRA_INDEX_A_SH_SZ` | 上交所、深交所 A 股投资列表 |
| `INDEX_A` | `EXTRA_INDEX_A` | 上交所、深交所北交所新投资列表 |
| `SH_INDEX` | `SH_INDEX` | 上交所指数列表 |
| `SZ_INDEX` | `SZ_INDEX` | 深交所指数列表 |
| `BJ_INDEX` | `BJ_INDEX` | 北交所新投资额列表 |
| `ETF_SH` | `SH_ETF` | 上交所 ETF 列表 |
| `ETF_SZ` | `SZ_ETF` | 深交所 ETF 列表 |
| `ETF` | `EXTRA_ETF` | 上交所、深交所 ETF 列表 |
| `KZZ_SH` | `SH_KZZ` | 上交所可转债备案表 |
| `KZZ_SZ` | `SZ_KZZ` | 深交所可转债备案表 |
| `KZZ` | `EXTRA_KZZ` | 上交所、深交所可转债备案表 |
| `HKT_SH` | `SH_HKT` | 沪港通 |
| `HKT_SZ` | `SZ_HKT` | 深港通 |
| `HKT` | `EXTRA_HKT` | 沪深港通 |

#### 1.2 期货交易所类型

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `FUTURE` | `EXTRA_FUTURE` | 期货，包含中金所/上期所/郑商所/上海国际能源交易中心 |
| `FUTURE_CFFEX` | `ZJ_FUTURE` | 期货，包含中金所 |
| `FUTURE_SHFE` | `SQ_FUTURE` | 期货，包含上期所 |
| `FUTURE_DCE` | `DS_FUTURE` | 期货，包含大商所 |
| `FUTURE_CZCE` | `ZS_FUTURE` | 期货，包含郑商所 |
| `FUTURE_INE` | `SN_FUTURE` | 期货，包含国际能源交易中心 |

#### 1.3 期权类型

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `OPTION_ETF` | `EXTRA_ETF_OP` | ETF 期权，上交所深交所 |
| `OPTION_SH` | `SH_OPTION` | ETF 期权，包含上交所 |
| `OPTION_SZ` | `SZ_OPTION` | ETF 期权，包含深交所 |

---

### 2. AmazingDataMarket - 市场类型

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `SH` | `SH` | 上交所 |
| `SZ` | `SZ` | 深交所 |
| `BJ` | `BJ` | 北交所 |
| `SHF` | `SHF` | 上期所 |
| `CFE` | `CFE` | 中金所 |
| `DCE` | `DCE` | 大商所 |
| `CZC` | `CZC` | 郑商所 |
| `INE` | `INE` | 上海国际能源交易中心 |
| `SHN` | `SHN` | 沪港通 |
| `SZN` | `SZN` | 深港通 |
| `HK` | `HK` | 港交所 |

---

### 3. AmazingDataTradingPhase - 交易阶段代码

#### 3.1 上市现货连续竞价交易状态

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `BEFORE_OPENING` | `S` | 启动（开市前）|
| `OPENING_CALL_AUCTION_UNCLOSED` | `O` | 开盘集合竞价 |
| `OPENING_CALL_AUCTION_CLOSED` | `0` | 开盘集合竞价（已闭市) |
| `CONTINUOUS_TRADING_NOT_TRADABLE` | `T` | 连续竞价（开市未可交易）|
| `CONTINUOUS_TRADING_SUSPENDED` | `1` | 连续竞价成交不可交易（未可交易，停牌）|
| `CONTINUOUS_TRADING` | `2` | 连续竞价 |
| `CLOSING_CALL_AUCTION` | `3` | 收盘集合竞价 |
| `POST_TRADING_TRANSFER` | `E` | 盘后固定价格交易 |
| `CLOSED` | `C` | 闭市 |
| `MARKET_CLOSED` | `P` | 停牌 |
| `VOLATILITY_INTERRUPTION` | `U` | 波动性中断 |

#### 3.2 深交所现货连续竞价交易状态

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `SZ_BEFORE_OPENING` | `S` | 启动（开市前）|
| `SZ_OPENING_CALL_AUCTION` | `O` | 开盘集合竞价 |
| `SZ_CONTINUOUS_MATCHING` | `T` | 连续竞价 |
| `SZ_CLOSING_CALL_AUCTION` | `B` | 盘中收盘集合竞价 |
| `SZ_CLOSING` | `C` | 收盘处理 |
| `SZ_POST_TRADING` | `E` | 盘后固定价格交易 |
| `SZ_CLOSED` | `P` | 停牌 |
| `SZ_VOLATILITY_INTERRUPTION` | `V` | 波动性中断 |
| `SZ_AFTER_HOURS_TRADING` | `U` | 盘后交易 |

#### 3.3 竞价交易阶段状态

| 枚举值 | 代码值 | 说明 |
|--------|--------|------|
| `CALL_BEFORE_OPENING` | `S` | 启动上午交易 |

#### 3.4 数据周期 Period

基于文档 4.1.6，Period 枚举已在 `AmazingDataPeriod` 中定义：

| 枚举值 | API 值 | 说明 |
|--------|--------|------|
| `M1` | `Period.min1.value` | 1 分钟线 |
| `M3` | `Period.min3.value` | 3 分钟线 |
| `M5` | `Period.min5.value` | 5 分钟线 |
| `M10` | `Period.min10.value` | 10 分钟线 |
| `M15` | `Period.min15.value` | 15 分钟线 |
| `M30` | `Period.min30.value` | 30 分钟线 |
| `M60` | `Period.min60.value` | 60 分钟线 |
| `M120` | `Period.min120.value` | 120 分钟线 |
| `DAY` | `Period.day.value` | 日线 |
| `WEEK` | `Period.week.value` | 周线 |
| `MONTH` | `Period.month.value` | 月线 |
| `QUARTER` | `Period.season.value` | 季线 |
| `YEAR` | `Period.year.value` | 年线 |

---

### 4. AmazingDataReportPeriod - 报告期名称

基于文档 4.1.7：

| 枚举值 | 数值 | 说明 |
|--------|------|------|
| `Q1` | `1` | 3 月 |
| `Q2` | `2` | 6 月 |
| `Q3` | `3` | 9 月 |
| `ANNUAL` | `4` | 12 月 |

---

### 5. AmazingDataStatementType - 报表类型代码

基于文档 4.1.8，定义了 36 种主要报表类型：

#### 5.1 合并报表

| 枚举值 | 数值 | 报表类型 | 说明 |
|--------|------|----------|------|
| `CONSOLIDATED_INCOME` | `1` | 合并报表 | 综合收益表披露报表数据总额，为资产股表 |
| `CONSOLIDATED_BALANCE_SHEET` | `2` | 合并报表（母子） | 母公司披露母子公司（本期）与母公司报表（上一母） |
| `PARENT_INCOME` | `3` | 母公司报表（母子） | 母公司报表（母季累）母公司报表（本期累期）与母公司报表（上一母 —）组母 |
| `CONSOLIDATED_REPORT` | `4` | 合并报表（母益） | 本年度公司上市公司利润权益报表类型，设包期专业土地 |
| `PARENT_BALANCE_SHEET_PROFIT` | `5` | 母公司报表（资正 别） | 别期母公司母石，析母非排期表时记录投支母资股非表（以财 资本母母） |

#### 5.2 现金流量表

| 枚举值 | 数值 | 报表类型 | 说明 |
|--------|------|----------|------|
| `CONSOLIDATED_CASH_FLOW` | `6` | 母公司母报表 | 该公司母公司母公司母母财报类型 |
| `PARENT_CASH_FLOW` | `7` | 母公司母报表（资 本母义）| 母公司母报表（母母事）母公司母报表（上期）母公司母报表（上一母义） |

#### 5.3 利润表

| 枚举值 | 数值 | 报表类型 | 说明 |
|--------|------|----------|------|
| `CONSOLIDATED_PROFIT_PARENT` | `8` | 母公司母报表（母 母度母期） | 母公司母报表（母母季期期）母公司母报表（本期母母）母公司母报表（本一期母母）母公司 期母母（上一母母母） |
| `CONSOLIDATED_PROFIT` | `9` | 母公司母报表（票 验） | 母公司母公司母公司母本母券母资资上母期母验母资类表 |

---

## 💻 代码实现

### 基本使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataSecurityType,
    AmazingDataMarket,
    AmazingDataPeriod,
    AmazingDataTradingPhase,
    AmazingDataReportPeriod,
    AmazingDataStatementType
)

# 使用证券类型枚举
security_type = AmazingDataSecurityType.STOCK_A
print(f"证券类型: {security_type.value}")  # 输出: EXTRA_STOCK_A

# 使用市场类型枚举
market = AmazingDataMarket.SH
print(f"市场: {market.value}")  # 输出: SH

# 使用数据周期枚举
period = AmazingDataPeriod.DAY
print(f"周期: {period.value}")  # 输出: 1d

# 使用报告期枚举
report_period = AmazingDataReportPeriod.Q1
print(f"报告期: {report_period.value}")  # 输出: 1
```

### 与 AmazingData API 配合使用

```python
from deepsearch.infrastructure.providers.implementations.amazingdata import AmazingDataExtended
from deepsearch.config.models.amazingdata import AmazingDataConfig
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataSecurityType,
    AmazingDataPeriod
)

# 创建配置
config = AmazingDataConfig(
    username="your_username",
    password="your_password"
)

# 创建提供者实例
provider = AmazingDataExtended(config)
await provider.initialize()

# 使用枚举类型查询数据
# 示例 1: 获取 A 股列表
stock_list = await provider.get_stock_list(
    security_type=AmazingDataSecurityType.STOCK_A.value
)

# 示例 2: 获取日线数据
kline_data = await provider.get_kline(
    code_list=["000001.SZ"],
    period=AmazingDataPeriod.DAY.value,
    begin_date=20241101,
    end_date=20241216
)
```

---

## 📋 枚举值映射表

### SecurityType 完整映射

| 业务含义 | 枚举名称 | SDK 代码值 |
|---------|---------|-----------|
| 沪深A股 | `STOCK_A_SH_SZ` | `EXTRA_STOCK_A_SH_SZ` |
| 沪深北A股 | `STOCK_A` | `EXTRA_STOCK_A` |
| 深圳A股 | `SZ_A` | `SZ_A` |
| 北京A股 | `BJ_A` | `BJ_A` |
| 沪深指数 | `INDEX_A_SH_SZ` | `EXTRA_INDEX_A_SH_SZ` |
| 沪深北指数 | `INDEX_A` | `EXTRA_INDEX_A` |
| 上证指数 | `SH_INDEX` | `SH_INDEX` |
| 深证指数 | `SZ_INDEX` | `SZ_INDEX` |
| 北证指数 | `BJ_INDEX` | `BJ_INDEX` |
| 沪深ETF | `ETF` | `EXTRA_ETF` |
| 上证ETF | `ETF_SH` | `SH_ETF` |
| 深证ETF | `ETF_SZ` | `SZ_ETF` |
| 沪深可转债 | `KZZ` | `EXTRA_KZZ` |
| 沪港通 | `HKT_SH` | `SH_HKT` |
| 深港通 | `HKT_SZ` | `SZ_HKT` |
| 所有期货 | `FUTURE` | `EXTRA_FUTURE` |
| 中金所期货 | `FUTURE_CFFEX` | `ZJ_FUTURE` |
| 上期所期货 | `FUTURE_SHFE` | `SQ_FUTURE` |
| 大商所期货 | `FUTURE_DCE` | `DS_FUTURE` |
| 郑商所期货 | `FUTURE_CZCE` | `ZS_FUTURE` |
| 能源中心期货 | `FUTURE_INE` | `SN_FUTURE` |
| ETF期权 | `OPTION_ETF` | `EXTRA_ETF_OP` |
| 上证期权 | `OPTION_SH` | `SH_OPTION` |
| 深证期权 | `OPTION_SZ` | `SZ_OPTION` |

---

## ⚠️ 注意事项

1. **枚举值使用**：在调用 AmazingData API 时，应该使用枚举的 `.value` 属性获取实际的代码值
2. **大小写敏感**：所有代码值都是大小写敏感的，请严格按照文档使用
3. **市场区分**：不同市场的证券类型需要使用对应的枚举值
4. **兼容性**：这些枚举类型与 AmazingData SDK 官方文档完全一致

---

## 🔗 相关文档

- [AmazingData 接口扩展总结](./amazingdata_interface_extensions.md)
- [AmazingData 扩展总结（第二批）](./amazingdata_extension_summary.md)
- 中泰数据交易平台数据字典说明文档

---

## 📝 更新日志

### 2025-12-16
- 初始版本
- 根据官方文档附录完善所有枚举类型定义
- 添加详细的使用示例和映射表
