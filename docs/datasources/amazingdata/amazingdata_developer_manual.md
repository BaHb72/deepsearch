# AmazingData 开发手册 (API Reference)

> **版本**: V1.0.20
> **Python SDK 版本**: V1.0.20
> **最新发布日期**: 2025年12月16日
> **平台**: 中国银河证券星耀数智

---

## 目录

1. [功能介绍](#1-功能介绍)
2. [SDK 安装与环境配置](#2-sdk-安装与环境配置)
3. [Python 开发步骤](#3-python-开发步骤)
4. [API 接口详细](#4-api-接口详细)
   - [基础接口](#41-基础接口)
   - [基础数据](#42-基础数据)
   - [实时行情数据](#43-实时行情数据)
   - [历史行情数据](#44-历史行情数据)
   - [财务数据](#45-财务数据)
   - [股东股本数据](#46-股东股本数据)
   - [股东权益数据](#47-股东权益数据)
   - [融资融券数据](#48-融资融券数据)
   - [交易异动数据](#49-交易异动数据)
   - [期权数据](#410-期权数据)
   - [ETF 数据](#411-etf-数据)
   - [指数数据](#412-指数数据)
   - [国债收益率数据](#413-国债收益率数据)
5. [附录](#5-附录)
   - [字段取值说明](#51-字段取值说明)
   - [数据结构说明](#52-数据结构说明)
   - [相关算法说明](#53-相关算法说明)
   - [本地数据缓存方案](#54-本地数据缓存方案)

---

## 1. 功能介绍

### 1.1 金融数据服务概述

金融数据功能是指用户使用 Python 等程序设计语言，获取公司通过对证券交易所等渠道的公开信息加工而成的行情数据、金融资讯数据等金融数据的功能。

### 1.2 数据覆盖范围

#### 行情数据

| 品种 | 数据类型 | 数据起点 | 说明 | 支持实时订阅 |
|------|----------|----------|------|--------------|
| 股票 | Level1 快照、K线 | 2013年至今 | 上交所、深交所、北交所 | ✓ |
| 指数 | Level1 快照、K线 | - | 上交所、深交所、北交所 | ✓ |
| 债券 | Level1 快照、K线 | - | 上交所、深交所 | ✓ |
| 场内基金 | Level1 快照、K线 | - | 上交所、深交所 | ✓ |
| 期权 | Level1 快照、K线 | 2015年至今 | 深交所/上交所 ETF期权 | ✓ |
| 港股通 | 港股通行情快照 | 2023年至今 | 上交所、深交所 | ✓ |
| 期货(中金所) | Level1 快照、K线 | 2010年4月至今 | - | ✓ |
| 期货(大商所) | Level1 快照、K线 | 2013年6月至今 | - | ✓ |
| 期货(郑商所) | Level1 快照、K线 | 2011年1月至今 | - | ✓ |
| 期货(上期所) | Level1 快照、K线 | 2019年8月至今 | - | ✓ |
| 期货(上海国际能源交易中心) | Level1 快照、K线 | 2019年8月至今 | - | ✓ |

#### 其他数据

- **基础数据**: 每日最新证券信息、复权因子、每日最新代码表、历史代码表、交易日历
- **财务数据**: 资产负债表、现金流量表、利润表、业绩快报、业绩预告
- **股东股本数据**: 十大股东数据、股东户数、股本结构、股权冻结/质押、限售股解禁
- **股东权益数据**: 分红数据、配股数据
- **融资融券数据**: 融资融券成交汇总、融资融券交易明细
- **交易异动数据**: 龙虎榜、大宗交易

---

## 2. SDK 安装与环境配置

### 2.1 Wheel 文件版本

| wheel 文件名 | 操作系统 | Python 版本 |
|--------------|----------|-------------|
| tgw-1.*.*-py3-none-any.whl | Linux/Windows | Python 3.8-3.13 |
| AmazingData-1.*.*-cp38-none-any.whl | Linux/Windows | Python 3.8-3.13 |

### 2.2 下载路径

1. **银河网盘**: <https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA>
2. **公众号**: "中国银河证券星耀数智" → "业务介绍" → "安装包下载"

### 2.3 推荐运行环境

#### Linux 推荐配置

| 类型 | 最低配置 | 推荐配置 |
|------|----------|----------|
| 处理器 | 2.10GHz, 4核 | 2.10GHz, 8核 |
| 内存 | DDR4 4GB | DDR4 4GB |
| 硬盘 | 200G | 480G |
| 操作系统 | REDHAT 7.2/7.4/7.6 | REDHAT 7.2/7.4/7.6 |

#### Windows 推荐配置

| 类型 | 最低配置 | 推荐配置 |
|------|----------|----------|
| 处理器 | 2.60GHz, 4核 | 2.60GHz, 8核 |
| 内存 | DDR4 4GB | DDR4 4GB |
| 硬盘 | 200G | 480G |
| 操作系统 | Windows 10 (64位) | Windows 10 (64位) |

### 2.4 SDK 安装

```bash
# 安装 tgw
pip install tgw-1.7.1-py3-none-any.whl

# 安装 AmazingData (选择对应 Python 版本)
pip install AmazingData-1.0.0-cp312-none-any.whl
```

---

## 3. Python 开发步骤

### 3.1 登录 AmazingData

**所有数据接口调用前，必须先登录。**

```python
import AmazingData as ad

ad.login(
    username='username',
    password='password',
    host='***.***.***.***',
    port=****
)
```

> **注**: 账号、密码、ip 和端口号需联系开户营业部申请开通权限后获取。

### 3.2 查询接口调用模式

```python
# 第一步：登录
import AmazingData as ad
ad.login(username='username', password='password', host='***.***.***.***', port=****)

# 第二步：实例化对应的数据查询类
base_data_object = ad.BaseData()

# 第三步：调用查询数据接口
code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')
```

### 3.3 订阅接口调用模式

```python
from typing import Union
import AmazingData as ad

# 第一步：登录
ad.login(username='username', password='password', host='***.***.***.***', port=****)

# 第二步：获取标的代码列表
base_data_object = ad.BaseData()
etf_code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')

# 第三步：实例化数据订阅类
sub_data = ad.SubscribeData()

# 第四步：用装饰器装饰回调函数
@sub_data.register(code_list=etf_code_list, period=ad.constant.Period.snapshot.value)
def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
    print(period, data)

# 第五步：执行订阅
sub_data.run()
```

---

## 4. API 接口详细

### 4.1 基础接口

#### 4.1.1 login - 登录

**功能**: API 登录（调用任何数据接口前必须先调用）

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| username | str | 是 | 账号 |
| password | str | 是 | 密码 |
| host | str | 是 | 服务器 IP |
| port | int | 是 | 服务器端口号 |

```python
import AmazingData as ad
ad.login(username='username', password='password', host='***.***.***.***', port=****)
```

#### 4.1.2 logout - 登出

**功能**: API 退出登录链接（正常使用情况下无需使用此接口）

| 参数 | 类型 | 说明 |
|------|------|------|
| username | str | 用户名 |

#### 4.1.3 update_password - 更新密码

**功能**: 更新密码（必须先登录才能修改密码）

| 参数 | 类型 | 说明 |
|------|------|------|
| username | str | 用户名 |
| old_password | str | 旧密码 |
| new_password | str | 新密码 |

---

### 4.2 基础数据

#### 4.2.1 get_code_info - 每日最新证券信息

**功能**: 获取每日最新证券信息（交易日早上9点前更新）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| security_type | str | 否 | 代码类型，默认 EXTRA_STOCK_A |

**输出参数**:

| 字段 | 说明 |
|------|------|
| symbol | 证券简称 |
| security_status | 产品状态标志 |
| pre_close | 昨收价 |
| high_limited | 涨停价 |
| low_limited | 跌停价 |
| price_tick | 最小价格变动单位 |

```python
base_data_object = ad.BaseData()
code_info = base_data_object.get_code_info(security_type='EXTRA_ETF')
```

#### 4.2.2 get_code_list - 每日最新代码表(沪深北)

**功能**: 获取代码表（每日最新，无法获取历史代码表）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| security_type | str | 否 | 代码类型，默认 EXTRA_STOCK_A |

**输出**: `list` - 证券代码列表

```python
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
```

#### 4.2.3 get_future_code_list - 每日最新代码表(期货交易所)

**功能**: 获取期货代码表（每日最新）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| security_type | str | 是 | 默认 EXTRA_FUTURE |

```python
code_list = base_data_object.get_future_code_list(security_type='EXTRA_FUTURE')
```

#### 4.2.4 get_option_code_list - 每日最新代码表(期权)

**功能**: 获取期权代码表（每日最新）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| security_type | str | 是 | 默认 EXTRA_ETF_OP |

```python
code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')
```

#### 4.2.5 get_backward_factor - 复权因子(后复权因子)

**功能**: 获取后复权因子数据并本地存储

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 代码列表（支持股票、ETF） |
| local_path | str | 是 | 本地存储文件夹绝对路径 |
| is_local | bool | 是 | 是否使用本地数据（默认True） |

**输出**: DataFrame - index为交易日期，column为股票代码

```python
backward_factor = base_data_object.get_backward_factor(
    code_list,
    local_path='D://AmazingData_local_data//',
    is_local=False
)
```

#### 4.2.6 get_adj_factor - 复权因子(单次复权因子)

**功能**: 获取单次复权因子数据

**参数与用法与 get_backward_factor 相同**

#### 4.2.7 get_hist_code_list - 历史代码表

**功能**: 获取历史代码表（先检查本地，再从服务端补充）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| security_type | str | 是 | 默认 EXTRA_STOCK_A_SH_SZ |
| start_date | int | 是 | 开始时间（闭区间），格式 YYYYMMDD |
| end_date | int | 是 | 结束时间（闭区间），格式 YYYYMMDD |
| local_path | str | 是 | 本地存储路径 |

```python
code_list = base_data_object.get_hist_code_list(
    security_type='EXTRA_STOCK_A_SH_SZ',
    start_date=20240101,
    end_date=20240701,
    local_path='D://AmazingData_local_data//'
)
```

#### 4.2.8 get_calendar - 交易日历

**功能**: 获取交易所的交易日历

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| data_type | str | 否 | 默认 str，可选 datetime |
| market | str | 否 | 市场类型，默认 SH |

```python
calendar = base_data_object.get_calendar()
```

#### 4.2.9 get_stock_basic - 证券基础信息

**功能**: 获取上市公司的证券基础数据（含已退市标的）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 沪深北三个交易所的代码列表 |

**输出字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| COMP_NAME | string | 证券中文名称 |
| PINYIN | string | 中文拼音简称 |
| COMP_NAME_ENG | string | 证券英文名称 |
| LISTDATE | int | 上市日期 |
| DELISTDATE | int | 退市日期 |
| LISTPLATE_NAME | string | 上市板块名称 |
| IS_LISTED | int | 上市状态 (1:上市交易, 3:终止上市) |

```python
info_data_object = ad.InfoData()
stock_basic = info_data_object.get_stock_basic(code_list)
```

#### 4.2.10 get_history_stock_status - 历史证券信息

**功能**: 获取上市公司的历史证券数据（日度频率，含涨跌停、ST、除权除息等）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 沪深A的代码列表 |
| local_path | str | 是 | 本地存储路径 |
| is_local | bool | 否 | 默认True |
| begin_date | int | 否 | 交易日 |
| end_date | int | 否 | 交易日 |

**输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 证券代码 |
| TRADE_DATE | 日期 |
| PRECLOSE | 前收价 |
| HIGH_LIMITED | 涨停价 |
| LOW_LIMITED | 跌停价 |
| IS_ST_SEC | 是否ST (1:是, 0:否) |
| IS_SUSP_SEC | 是否停牌 (1:是, 0:否) |
| IS_WD_SEC | 是否除息 (1:是, 0:否) |
| IS_XR_SEC | 是否除权 (1:是, 0:否) |

#### 4.2.11 get_bj_code_mapping - 北交所新旧代码对照表

**功能**: 获取北交所存量上市公司股票新旧代码对照表

**输出字段**:

| 字段 | 说明 |
|------|------|
| OLD_CODE | 旧代码 |
| NEW_CODE | 新代码 |
| SECURITY_NAME | 证券简称 |
| LISTING_DATE | 上市日期 |

---

### 4.3 实时行情数据

实时行情订阅接口使用步骤:

1. 实例化 `ad.SubscribeData()`
2. 用装饰器传入 code_list 和 period 两个参数
3. 在回调函数中获取数据

#### 4.3.1 onSnapshotindex - 指数实时快照

**功能**: 交易所指数快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 北交所、上交所、深交所指数 |
| period | Period | 是 | Period.snapshot.value |

**输出**: SnapshotIndex 对象

```python
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotindex(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
    print(period, data)
```

#### 4.3.2 onSnapshot - 股票实时快照

**功能**: Level1 股票快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 北交所、上交所、深交所股票 |
| period | Period | 是 | Period.snapshot.value |

**输出**: Snapshot 对象

#### 4.3.3 onSnapshotfuture - 期货实时快照

**功能**: Level1 期货快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 中金所/上期所/大商所/郑商所/上海国际能源交易中心所 |
| period | Period | 是 | Period.snapshotfuture.value |

**输出**: SnapshotFuture 对象

#### 4.3.4 onSnapshotetf - ETF 实时快照

**功能**: Level1 ETF 快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 上交所、深交所ETF |
| period | Period | 是 | Period.snapshot.value |

**输出**: Snapshot 对象

#### 4.3.5 onSnapshotkzz - 可转债实时快照

**功能**: Level1 可转债快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 上交所、深交所可转债 |
| period | Period | 是 | Period.snapshot.value |

#### 4.3.6 onSnapshothkt - 港股通实时快照

**功能**: 港股通快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 沪深港股通 |
| period | Period | 是 | Period.snapshotHKT.value |

**输出**: SnapshotHKT 对象

#### 4.3.7 onSnapshotoption - ETF期权实时快照

**功能**: ETF期权快照数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 上交所、深交所ETF期权 |
| period | Period | 是 | Period.snapshotoption.value |

**输出**: SnapshotOption 对象

```python
option_code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')

@sub_data.register(code_list=option_code_list, period=ad.constant.Period.snapshotoption.value)
def onSnapshotoption(data: Union[ad.constant.SnapshotOption], period):
    print('onSnapshotoption: ', data)
```

#### 4.3.8 OnKLine - 实时K线

**功能**: K线数据的实时订阅

**装饰器参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 支持各品种（股票、指数、ETF、可转债、期货等） |
| period | Period | 是 | 见 Period 枚举 |

**输出**: Kline 对象

```python
@sub_data.register(code_list=code_list, period=ad.constant.Period.min1.value)
def OnKLine(data: Union[ad.constant.Kline], period):
    print('OnKLine: ', data)
```

---

### 4.4 历史行情数据

使用步骤:

1. 实例化 `ad.MarketData(calendar)`，入参需交易日历
2. 调用 MarketData 的方法获取数据

#### 4.4.1 query_snapshot - 历史快照

**功能**: 快照数据的历史数据查询

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 支持各品种代码列表 |
| begin_date | int | 是 | 日期，格式 YYYYMMDD |
| end_date | int | 是 | 日期，格式 YYYYMMDD |
| begin_time | int | 否 | 时间戳，格式如 90000000 (9:00) |
| end_time | int | 否 | 时间戳，格式如 172500000 (17:25) |

**输出**: dict - key为代码，value为DataFrame

```python
market_data_object = ad.MarketData(calendar)
snapshot_dict = market_data_object.query_snapshot(
    code_list,
    begin_date=20240530,
    end_date=20240530
)
```

#### 4.4.2 query_kline - 历史K线

**功能**: K线数据的历史数据查询（支持全部周期）

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 支持各品种代码列表 |
| begin_date | int | 是 | 日期，格式 YYYYMMDD |
| end_date | int | 是 | 日期，格式 YYYYMMDD |
| period | Period | 是 | 数据周期 |
| begin_time | int | 否 | 时间戳，格式如 900 (9:00) |
| end_time | int | 否 | 时间戳，格式如 1725 (17:25) |

**输出**: dict - key为代码，value为DataFrame

```python
kline_dict = market_data_object.query_kline(
    code_list,
    begin_date=20240530,
    end_date=20240530,
    period=ad.constant.Period.min1.value
)
```

---

### 4.5 财务数据

#### 4.5.1 get_balance_sheet - 资产负债表

**功能**: 获取上市公司的资产负债表数据

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 沪深A的代码列表 |
| local_path | str | 是 | 本地存储路径 |
| is_local | bool | 否 | 默认True |
| begin_date | int | 否 | 报告期 |
| end_date | int | 否 | 报告期 |

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 证券代码 |
| STATEMENT_TYPE | 报表类型 |
| REPORT_TYPE | 报告期名称 |
| REPORTING_PERIOD | 报告期 |
| TOTAL_ASSETS | 资产总计 |
| TOTAL_LIAB | 负债合计 |
| TOT_SHARE_EQUITY_INCL_MIN_INT | 股东权益合计(含少数股东权益) |
| CURRENCY_CAP | 货币资金 |
| ACC_RECEIVABLE | 应收账款 |
| INV | 存货 |
| FIXED_ASSETS | 固定资产 |
| LT_LOAN | 长期借款 |
| ST_BORROWING | 短期借款 |
| ... | (更多字段见完整文档) |

```python
info_data_object = ad.InfoData()
balance_sheet = info_data_object.get_balance_sheet(all_code_list)
```

#### 4.5.2 get_cash_flow - 现金流量表

**功能**: 获取上市公司的现金流量表数据

**输入参数**: 同 get_balance_sheet

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| NET_CASH_FLOWS_OPERA_ACT | 经营活动产生的现金流量净额 |
| NET_CASH_FLOWS_INV_ACT | 投资活动产生的现金流量净额 |
| NET_CASH_FLOWS_FIN_ACT | 筹资活动产生的现金流量净额 |
| NET_INCR_CASH_AND_CASH_EQU | 现金及现金等价物净增加额 |
| CASH_RECP_SG_AND_RS | 销售商品、提供劳务收到的现金 |
| CASH_PAY_GOODS_SERVICES | 购买商品、接受劳务支付的现金 |
| ... | (更多字段见完整文档) |

#### 4.5.3 get_income - 利润表

**功能**: 获取上市公司的利润表数据

**输入参数**: 同 get_balance_sheet

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| TOT_OPERA_REV | 营业总收入 |
| OPERA_REV | 营业收入 |
| OPERA_PROFIT | 营业利润 |
| TOTAL_PROFIT | 利润总额 |
| NET_PRO_INCL_MIN_INT_INC | 净利润(含少数股东损益) |
| BASIC_EPS | 基本每股收益 |
| DILUTED_EPS | 稀释每股收益 |
| ... | (更多字段见完整文档) |

#### 4.5.4 get_profit_express - 业绩快报

**功能**: 获取上市公司的业绩快报数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| TOTAL_ASSETS | 总资产(元) |
| NET_PRO_EXCL_MIN_INT_INC | 净利润(元) |
| TOT_OPERA_REV | 营业总收入(元) |
| OPERA_PROFIT | 营业利润(元) |
| EPS_BASIC | 每股收益-基本(元) |
| ROE_WEIGHTED | 净资产收益率-加权(%) |
| YOY_GR_NET_PROFIT_PARENT | 同比增长率:归母净利润(%) |
| ... | (更多字段见完整文档) |

#### 4.5.5 get_profit_notice - 业绩预告

**功能**: 获取上市公司的业绩预告数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| P_TYPECODE | 业绩预告类型代码 (1:不确定, 2:略减, 3:略增, 4:扭亏, 5:其他, 6:首亏, 7:续亏, 8:续盈, 9:预减, 10:预增, 11:持平) |
| P_CHANGE_MAX | 预告净利润变动幅度上限(%) |
| P_CHANGE_MIN | 预告净利润变动幅度下限(%) |
| NET_PROFIT_MAX | 预告净利润上限(万元) |
| NET_PROFIT_MIN | 预告净利润下限(万元) |
| P_REASON | 业绩变动原因 |
| ... | (更多字段见完整文档) |

---

### 4.6 股东股本数据

#### 4.6.1 get_share_holder - 十大股东数据

**功能**: 获取上市公司的十大股东数据

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| code_list | list[str] | 是 | 沪深A的代码列表 |
| local_path | str | 是 | 本地存储路径 |
| is_local | bool | 否 | 默认True |
| begin_date | int | 否 | 到期日期 |
| end_date | int | 否 | 到期日期 |

**输出字段**:

| 字段 | 说明 |
|------|------|
| HOLDER_TYPE | 股东类别 (10:十大股东, 20:流通股前十大股东) |
| HOLDER_NAME | 股东名称 |
| HOLDER_QUANTITY | 持股数(股) |
| HOLDER_PCT | 持股比例(%) |
| HOLDER_HOLDER_CATEGORY | 股东性质 (1:个人, 2:公司) |

#### 4.6.2 get_holder_num - 股东户数

**功能**: 获取上市公司的股东户数数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| HOLDER_ENDDATE | 股东户数统计的截止日期 |
| HOLDER_TOTAL_NUM | A股、B股、H股、境外股的总户数 |
| HOLDER_NUM | A股股东户数 |

#### 4.6.3 get_equity_structure - 股本结构

**功能**: 获取上市公司的股本结构数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| CHANGE_DATE | 变动日期 |
| TOT_SHARE | 总股本(万股) |
| FLOAT_SHARE | 流通股(万股) |
| FLOAT_A_SHARE | 流通A股(万股) |
| RESTRICTED_A_SHARE | 限售A股(万股) |
| TOT_RESTRICTED_SHARE | 限售股合计 |

#### 4.6.4 get_equity_pledge_freeze - 股权冻结/质押

**功能**: 获取上市公司的股权冻结/质押数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| HOLDER_NAME | 股东名称 |
| TOTAL_HOLDING_SHR | 持股总数(万股) |
| FRO_SHARES | 本次冻结/质押股数 |
| TOTAL_PLEDGE_SHR | 累计冻结/质押股数 |
| FREEZE_TYPE | 冻结/质押类型 (1:质押, 2:司法, 3:质押式回购) |
| BEGIN_DATE | 冻结/质押起始日 |
| END_DATE | 解冻/解押日期 |

#### 4.6.5 get_equity_restricted - 限售股解禁

**功能**: 获取上市公司的限售股解禁数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| LIST_DATE | 解禁日期 |
| SHARE_RATIO | 解禁股占总股本比(%) |
| SHARE_LST_TYPE_NAME | 解禁股份类型名称 |
| SHARE_LST | 解禁数量(股) |
| SHARE_LST_IS_ANN | 上市数量是否公布值 (0:否，为预测值, 1:是，为实际公布值) |
| SHARE_LST_MARKET_VALUE | 解禁市值(元) |

---

### 4.7 股东权益数据

#### 4.7.1 get_dividend - 分红数据

**功能**: 获取上市公司的分红数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| DIV_PROGRESS | 方案进度 |
| DVD_PER_SHARE_STK | 每股送转 |
| DVD_PER_SHARE_PRE_TAX_CASH | 每股派息(税前)(元) |
| DVD_PER_SHARE_AFTER_TAX_CASH | 每股派息(税后)(元) |
| DATE_EQY_RECORD | 股权登记日 |
| DATE_EX | 除权除息日 |
| DATE_DVD_PAYOUT | 派息日 |
| LISTINGDATE_OF_DVD_SHR | 红股上市日 |
| DIV_BASESHARE | 基准股本(万股) |

#### 4.7.2 get_right_issue - 配股数据

**功能**: 获取上市公司的配股数据

**主要输出字段**:

| 字段 | 说明 |
|------|------|
| PROGRESS | 方案进度 |
| PRICE | 配股价格(元) |
| RATIO | 配股比例 |
| AMT_PLAN | 配股计划数量(万股) |
| AMT_REAL | 配股实际数量(万股) |
| COLLECTION_FUND | 募集资金(元) |
| SHAREB_REG_DATE | 股权登记日 |
| EX_DIVIDEND_DATE | 除权日 |
| LISTED_DATE | 配股上市日 |

---

### 4.8 融资融券数据

#### 4.8.1 get_margin_summary - 融资融券成交汇总

**功能**: 获取指定日期的融资融券成交汇总数据

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| local_path | str | 是 | 本地存储路径 |
| is_local | bool | 否 | 默认True |
| begin_date | int | 否 | 交易日 |
| end_date | int | 否 | 交易日 |

**输出字段**:

| 字段 | 说明 |
|------|------|
| TRADE_DATE | 交易日期 |
| SUM_BORROW_MONEY_BALANCE | 融资余额(元) |
| SUM_PURCH_WITH_BORROW_MONEY | 融资买入额(元) |
| SUM_REPAYMENT_OF_BORROW_MONEY | 融资偿还额(元) |
| SUM_SEC_LENDING_BALANCE | 融券余额(元) |
| SUM_SALES_OF_BORROWED_SEC | 融券卖出量(股,份,手) |
| SUM_MARGIN_TRADE_BALANCE | 融资融券余额(元) |

#### 4.8.2 get_margin_detail - 融资融券交易明细

**功能**: 获取上市公司的融资融券交易明细数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 证券代码 |
| TRADE_DATE | 交易日期 |
| BORROW_MONEY_BALANCE | 融资余额(元) |
| PURCH_WITH_BORROW_MONEY | 融资买入额(元) |
| SEC_LENDING_BALANCE | 融券余额(元) |
| SEC_LENDING_BALANCE_VOL | 融券余量(股,份,手) |
| MARGIN_TRADE_BALANCE | 融资融券余额(元) |

---

### 4.9 交易异动数据

#### 4.9.1 get_long_hu_bang - 龙虎榜

**功能**: 获取上市公司的龙虎榜数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 证券代码 |
| TRADE_DATE | 交易日期 |
| REASON_TYPE_NAME | 上榜原因 |
| CHANGE_RANGE | 涨跌幅(%) |
| TRADER_NAME | 营业部名称 |
| BUY_AMOUNT | 买入金额(元) |
| SELL_AMOUNT | 卖出金额(元) |
| FLOW_MARK | 买卖表示 (1:买入, 2:卖出) |
| TOTAL_AMOUNT | 实际交易金额(元) |
| TOTAL_VOLUME | 实际交易量(万股) |

#### 4.9.2 get_block_trading - 大宗交易

**功能**: 获取上市公司的大宗交易数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 证券代码 |
| TRADE_DATE | 交易日期 |
| B_SHARE_PRICE | 成交价(元) |
| B_SHARE_VOLUME | 成交量(万股) |
| B_FREQUENCY | 笔数 |
| B_SHARE_AMOUNT | 成交金额(万元) |
| B_BUYER_NAME | 买方营业部名称 |
| B_SELLER_NAME | 卖方营业部名称 |

---

### 4.10 期权数据

#### 4.10.1 get_option_basic_info - 期权基本资料

**功能**: 获取指定期权的基本资料（沪深交易所的ETF期权）

**输出字段**:

| 字段 | 说明 |
|------|------|
| CONTRACT_FULL_NAME | 合约全称 |
| CONTRACT_TYPE | 合约类别 (C:认购, P:认沽) |
| DELIVERY_MONTH | 交割月份 |
| EXPIRY_DATE | 到期日 |
| EXERCISE_PRICE | 行权价格 |
| EXERCISE_END_DATE | 最后行权日 |
| START_TRADE_DATE | 开始交易日 |
| LAST_TRADE_DATE | 最后交易日 |
| CONTRACT_UNIT | 合约单位 |
| MARKET_CODE | 合约代码 |

#### 4.10.2 get_option_std_ctr_specs - 期权标准合约属性

**功能**: 获取指定期权标准合约属性

**支持的ETF代码**: 159919.SZ, 159915.SZ, 159922.SZ, 159901.SZ, 510300.SH, 588000.SH, 588080.SH, 510050.SH, 510500.SH

#### 4.10.3 get_option_mon_ctr_specs - 期权月合约属性变动

**功能**: 获取指定期权月合约属性变动

**输出字段**:

| 字段 | 说明 |
|------|------|
| CODE_OLD | 原交易代码 |
| CODE_NEW | 新交易代码 |
| NAME_OLD | 原合约简称 |
| NAME_NEW | 新合约简称 |
| EXERCISE_PRICE_OLD | 原行权价(元) |
| EXERCISE_PRICE_NEW | 新行权价(元) |
| UNIT_OLD | 原合约单位(股) |
| UNIT_NEW | 新合约单位(股) |
| CHANGE_DATE | 调整日期 |
| CHANGE_REASON | 调整原因 |

---

### 4.11 ETF 数据

#### 4.11.1 get_etf_pcf - ETF每日最新申赎数据

**功能**: 获取指定ETF的申赎和成分股数据

**返回值**:

- `etf_pcf_info`: DataFrame - ETF信息
- `etf_pcf_constituent`: dict - 成分股数据

**etf_pcf_info 主要字段**:

| 字段 | 说明 |
|------|------|
| creation_redemption_unit | 每个篮子对应的ETF份数 |
| max_cash_ratio | 最大现金替代比例 |
| publish | 是否发布IOPV (Y/N) |
| creation | 是否允许申购 (Y/N) |
| redemption | 是否允许赎回 (Y/N) |
| estimate_cash_component | 预估现金差额 |
| cash_component | 前一日现金差额 |
| nav_per_cu | 前一日最小申赎单位净值 |
| nav | 前一日基金份额净值 |

**etf_pcf_constituent 主要字段**:

| 字段 | 说明 |
|------|------|
| underlying_symbol | 成份证券简称 |
| component_share | 成份证券数量 |
| substitute_flag | 现金替代标志 |
| creation_cash_substitute | 申购替代金额 |
| redemption_cash_substitute | 赎回替代金额 |

```python
etf_pcf_info, etf_pcf_constituent = base_data_object.get_etf_pcf(code_list)
```

#### 4.11.2 get_fund_share - ETF基金份额

**功能**: 获取指定ETF列表的基金份额数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| FUND_SHARE | 基金份额(万份) |
| TOTAL_SHARE | 基金总份额(万份) |
| FLOAT_SHARE | 流通份额(万份) |
| CHANGE_DATE | 变动日期 |
| CHANGE_REASON | 份额变动原因 |

#### 4.11.3 get_fund_iopv - ETF每日收盘IOPV

**功能**: 获取指定ETF列表的每日收盘IOPV数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| MARKET_CODE | 市场代码 |
| PRICE_DATE | 日期 |
| IOPV_NAV | IOPV收盘净值 |

---

### 4.12 指数数据

#### 4.12.1 get_index_constituent - 交易所指数成分股

**功能**: 获取指定交易所指数列表的成分股数据（仅支持约600多只常用指数）

**输出字段**:

| 字段 | 说明 |
|------|------|
| INDEX_CODE | 指数代码 |
| INDEX_NAME | 指数名称 |
| CON_CODE | 成份股代码 |
| INDATE | 纳入日期 |
| OUTDATE | 剔除日期 (未剔除时为nan) |

```python
index_constituent = info_data_object.get_index_constituent(code_list, is_local=False)
```

#### 4.12.2 get_index_weight - 交易所指数成分股日权重

**功能**: 获取指定交易所指数列表的成分股日权重数据

**支持的指数**: 上证50(000016.SH), 沪深300(000300.SH), 中证500(000905.SH), 中证800(000906.SH), 中证1000(000852.SH)

**输出字段**:

| 字段 | 说明 |
|------|------|
| INDEX_CODE | 指数代码 |
| CON_CODE | 标的代码 |
| TRADE_DATE | 生效日期 |
| TOTAL_SHARE | 总股本(股) |
| FREE_SHARE_RATIO | 自由流通比例(%) |
| CALC_SHARE | 计算用股本(股) |
| WEIGHT_FACTOR | 权重因子 |
| WEIGHT | 权重(%) |
| CLOSE | 收盘价 |

#### 4.12.3 get_industry_base_info - 行业指数基本信息

**功能**: 获取行业指数的基本信息数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| INDEX_CODE | 指数代码 |
| INDUSTRY_CODE | 行业代码 |
| LEVEL_TYPE | 指数类别 (1:一级行业, 2:二级行业, 3:三级行业) |
| LEVEL1_NAME | 一级行业 |
| LEVEL2_NAME | 二级行业 |
| LEVEL3_NAME | 三级行业 |
| IS_PUB | 是否发布 (1:已发布, 2:未发布) |

#### 4.12.4 get_industry_constituent - 行业指数成分股

**功能**: 获取指定行业指数列表的成分股数据

#### 4.12.5 get_industry_weight - 行业指数成分股日权重

**功能**: 获取指定行业指数列表的成分股日权重数据

#### 4.12.6 get_industry_daily - 行业指数日行情

**功能**: 获取指定行业指数列表的日行情数据

**输出字段**:

| 字段 | 说明 |
|------|------|
| INDEX_CODE | 指数代码 |
| TRADE_DATE | 交易日期 |
| OPEN | 开盘价 |
| HIGH | 最高价 |
| LOW | 最低价 |
| CLOSE | 收盘价 |
| PRE_CLOSE | 昨收盘价 |
| VOLUME | 成交量(股) |
| AMOUNT | 成交金额(元) |
| PE | 指数市盈率 |
| PB | 指数市净率 |
| TOTAL_CAP | 总市值(万元) |
| A_FLOAT_CAP | A股流通市值(万元) |

---

### 4.13 国债收益率数据

#### 4.13.1 get_treasury_yield - 国债收益率

**功能**: 获取指定期限的国债收益率数据

**输入参数**:

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| term_list | list[str] | 是 | 期限列表 |
| local_path | str | 是 | 本地存储路径 |
| is_local | bool | 否 | 默认True |
| begin_date | int | 否 | 变动日期 |
| end_date | int | 否 | 变动日期 |

**支持的期限**:

| 枚举值 | 说明 |
|--------|------|
| m3 | 3个月 |
| m6 | 6个月 |
| y1 | 1年 |
| y2 | 2年 |
| y3 | 3年 |
| y5 | 5年 |
| y7 | 7年 |
| y10 | 10年 |
| y30 | 30年 |

**输出**: dict - key为期限，value为DataFrame (column: YIELD, index: 日期)

```python
treasury_yield = info_data_object.get_treasury_yield(
    ['m3', 'm6', 'y1', 'y2', 'y3', 'y5', 'y7', 'y10', 'y30']
)
```

---

## 5. 附录

### 5.1 字段取值说明

#### 5.1.1 代码类型 security_type (沪深北)

| 枚举值 | 说明 |
|--------|------|
| EXTRA_STOCK_A | 上交所A股、深交所A股和北交所的股票列表 |
| SH_A | 上交所A股 |
| SZ_A | 深交所A股 |
| BJ_A | 北交所 |
| EXTRA_STOCK_A_SH_SZ | 上交所A股和深交所A股 |
| EXTRA_INDEX_A | 上交所、深交所和北交所的指数列表 |
| EXTRA_INDEX_A_SH_SZ | 上交所和深交所指数列表 |
| SH_INDEX | 上交所指数 |
| SZ_INDEX | 深交所指数 |
| BJ_INDEX | 北交所指数 |
| SH_ETF | 上交所ETF |
| SZ_ETF | 深交所ETF |
| EXTRA_ETF | 上交所、深交所ETF |
| SH_KZZ | 上交所可转债 |
| SZ_KZZ | 深交所可转债 |
| EXTRA_KZZ | 上交所、深交所可转债 |
| SH_HKT | 沪港通 |
| SZ_HKT | 深港通 |
| EXTRA_HKT | 沪深港通 |

#### 5.1.2 代码类型 security_type (期货交易所)

| 枚举值 | 说明 |
|--------|------|
| EXTRA_FUTURE | 期货(含中金所/上期所/大商所/郑商所/上海国际能源交易中心所) |
| ZJ_FUTURE | 中金所 |
| SQ_FUTURE | 上期所 |
| DS_FUTURE | 大商所 |
| ZS_FUTURE | 郑商所 |
| SN_FUTURE | 上海国际能源交易中心所 |

#### 5.1.3 代码类型 security_type (期权)

| 枚举值 | 说明 |
|--------|------|
| EXTRA_ETF_OP | ETF期权(上交所/深交所) |
| SH_OPTION | 上交所ETF期权 |
| SZ_OPTION | 深交所ETF期权 |

#### 5.1.4 市场类型 market

| 枚举值 | 说明 |
|--------|------|
| SH | 上交所 |
| SZ | 深交所 |
| BJ | 北交所 |
| SHF | 上期所 |
| CFE | 中金所 |
| DCE | 大商所 |
| CZC | 郑商所 |
| INE | 上海国际能源交易中心所 |
| SHN | 沪港通 |
| SZN | 深港通 |
| HK | 港交所 |

#### 5.1.5 交易阶段代码 trading_phase_code

**上海现货快照交易状态** (8位字符):

- 第0位: 'S'启动, 'C'开盘集合竞价, 'T'连续交易, 'E'闭市, 'P'停牌
- 第1位: '0'不可正常交易, '1'可正常交易
- 第2位: '0'未上市, '1'已上市
- 第3位: '0'不接受新订单, '1'可接受新订单

**深圳现货快照交易状态**:

- 第0位: 'S'启动, 'O'开盘集合竞价, 'T'连续竞价, 'B'休市, 'C'收盘集合竞价, 'E'已闭市, 'H'临时停牌, 'A'盘后交易, 'V'波动性中断
- 第1位: '0'正常, '1'全天停牌

**港股股票行情交易状态**: '1'正常交易, '2'停牌, '3'复牌

#### 5.1.6 产品状态标志 security_status

| 状态 | 标志 | 说明 |
|------|------|------|
| 停牌 | 1 | 深交所、北交所 |
| 除权 | 2 | 上交所、深交所、北交所 |
| 除息 | 3 | 上交所、深交所、北交所 |
| 风险警示 | 4 | 上交所、深交所、北交所 |
| 退市整理期 | 5 | 上交所、深交所、北交所 |
| 上市首日 | 6 | 上交所、深交所、北交所 |

#### 5.1.7 数据周期 Period

| 枚举值 | 说明 |
|--------|------|
| Period.min1.value | 1分钟线 |
| Period.min3.value | 3分钟线 |
| Period.min5.value | 5分钟线 |
| Period.min10.value | 10分钟线 |
| Period.min15.value | 15分钟线 |
| Period.min30.value | 30分钟线 |
| Period.min60.value | 60分钟线 |
| Period.min120.value | 120分钟线 |
| Period.day.value | 日线 |
| Period.week.value | 周线 |
| Period.month.value | 月线 |
| Period.season.value | 季度线 |
| Period.year.value | 年线 |

#### 5.1.8 报告期名称 REPORT_TYPE

| 代码 | 报告期月份 |
|------|-----------|
| 1 | 3月 |
| 2 | 6月 |
| 3 | 9月 |
| 4 | 12月 |

#### 5.1.9 报表类型代码表 STATEMENT_TYPE

| 代码 | 报表类型 | 说明 |
|------|----------|------|
| 1 | 合并报表 | 涵盖母公司的财务报表数据，为最新报表 |
| 2 | 合并报表(单季度) | 合并报表(本期)-合并报表(上一季) |
| 3 | 合并报表(单季度调整) | 合并报表(本期调整)-合并报表(上一季调整) |
| 4 | 合并报表(调整) | 本年度公布上年同期的财务报表数据 |
| 5 | 合并报表(更正前) | 出更正公告后的原记录 |
| 6 | 母公司报表 | 该公司母公司的财务报表数据 |
| 7 | 母公司报表(单季度) | 母公司报表(本期)-母公司报表(上一季) |
| 8 | 母公司报表(单季度调整) | 母公司报表(本期调整)-母公司报表(上一季调整) |
| 9 | 母公司报表(调整) | 母公司本年度公布上年同期的财务报表数据 |
| 10 | 母公司报表(更正前) | 更正前的原始财务报表数据 |

#### 5.1.10 股票分红进度代码表 DIV_PROGRESS

| 进度代码 | 描述 |
|----------|------|
| 1 | 董事会预案 |
| 2 | 股东大会通过 |
| 3 | 实施 |
| 4 | 未通过 |
| 12 | 停止实施 |
| 17 | 股东提议 |
| 19 | 董事会预案预披露 |

#### 5.1.11 股票配股进度代码表 PROGRESS

| 进度代码 | 描述 |
|----------|------|
| 1 | 董事会预案 |
| 2 | 股东大会通过 |
| 3 | 实施 |
| 4 | 未通过 |
| 5 | 证监会核准 |
| 11 | 延期实施 |
| 12 | 停止实施 |
| 20 | 发审委通过 |
| 21 | 发审委未通过 |
| 22 | 股东大会未通过 |
| 26 | 提交注册 |

---

### 5.2 数据结构说明

#### 5.2.1 Level1 快照 Snapshot

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| pre_close | float | 昨收价 |
| last | float | 最新价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | float | 成交总量 |
| amount | float | 成交总金额 |
| num_trades | float | 成交笔数 |
| high_limited | float | 涨停价 |
| low_limited | float | 跌停价 |
| ask_price1~5 | float | 卖1~5档价格 |
| ask_volume1~5 | int | 卖1~5档量 |
| bid_price1~5 | float | 买1~5档价格 |
| bid_volume1~5 | int | 买1~5档量 |
| iopv | float | 净值估产（仅基金品种有效） |
| trading_phase_code | str | 交易阶段代码 |

#### 5.2.2 ETF期权快照 SnapshotOption

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| trading_phase_code | str | 交易阶段代码 |
| total_long_position | int | 总持仓量 |
| volume | float | 成交总量 |
| amount | float | 成交总金额 |
| pre_close | float | 昨收价 |
| pre_settle | float | 上次结算价 |
| auction_price | float | 动态参考价（仅上海有效） |
| auction_volume | int | 虚拟匹配数量（仅上海有效） |
| last | float | 最新价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| settle | float | 本次结算价 |
| high_limited | float | 涨停价 |
| low_limited | float | 跌停价 |
| ask_price1~5 | float | 卖1~5档价格 |
| ask_volume1~5 | int | 卖1~5档量 |
| bid_price1~5 | float | 买1~5档价格 |
| bid_volume1~5 | int | 买1~5档量 |
| contract_type | str | 合约类别 |
| expire_date | int | 到期日 |
| underlying_security_code | str | 标的代码 |
| exercise_price | float | 行权价 |

#### 5.2.3 期货快照 SnapshotFuture

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| action_day | str | 业务日期 |
| trading_day | str | 交易日期 |
| pre_close | float | 昨收价 |
| pre_settle | float | 上次结算价 |
| pre_open_interest | int | 昨持仓量 |
| open_interest | int | 持仓量 |
| last | float | 最新价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | float | 成交总量 |
| amount | float | 成交总金额 |
| high_limited | float | 涨停价 |
| low_limited | float | 跌停价 |
| ask_price1~5 | float | 卖1~5档价格 |
| ask_volume1~5 | int | 卖1~5档量 |
| bid_price1~5 | float | 买1~5档价格 |
| bid_volume1~5 | int | 买1~5档量 |
| average_price | float | 当日均价 |
| settle | float | 本次结算价 |

#### 5.2.4 指数快照 SnapshotIndex

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| last | float | 最新价 |
| pre_close | float | 前收盘价 |
| open | float | 今开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价（仅上海有效） |
| volume | int | 成交总量（上交所:手，深交所:张） |
| amount | float | 成交总金额 |

#### 5.2.5 港股通快照 SnapshotHKT

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| pre_close | float | 昨收价 |
| last | float | 最新价 |
| high | float | 最高价 |
| low | float | 最低价 |
| volume | float | 成交总量 |
| amount | float | 成交总金额 |
| nominal_price | float | 暗盘价 |
| ref_price | float | 参考价 |
| bid_price_limit_up | float | 买盘上限价 |
| bid_price_limit_down | float | 买盘下限价 |
| offer_price_limit_up | float | 卖盘上限价 |
| offer_price_limit_down | float | 卖盘下限价 |
| high_limited | float | 冷静期价格上限 |
| low_limited | float | 冷静期价格下限 |
| ask_price1~5 | float | 卖1~5档价格 |
| ask_volume1~5 | int | 卖1~5档量 |
| bid_price1~5 | float | 买1~5档价格 |
| bid_volume1~5 | int | 买1~5档量 |
| trading_phase_code | str | 交易阶段代码 |

#### 5.2.6 K线 Kline

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码+市场 |
| trade_time | datetime | 交易所行情数据时间 |
| open | float | 今开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交总量 |
| amount | float | 成交总金额 |

---

### 5.3 相关算法说明

#### 5.3.1 商品期货查询算法

当查询非中金所（大商所、郑商所、上期所、上期能源）的商品期货快照时，因涉及夜盘快照，需根据查询时间参数做相应区分：

- **夜盘分割时间点**: 20:00
- **归属T1日范围**: 20:00:00.000~23:59:59.999
- **归属T日范围**: 00:00:00.000~19:59:59.999

**查询逻辑示例**:

| 上送日期 | 开始时间 | 结束时间 | 系统响应 |
|----------|----------|----------|----------|
| 20220407 | 093000000 | 150000000 | 返回4月7日9:30~15:00的数据 |
| 20220407 | 200000000 | 235900000 | 返回4月6日20:00~23:59的数据 |
| 20220407 | 200000000 | 010000000 | 返回4月6日20:00~4月7日01:00的数据 |
| 20220407 | 030000000 | 230000000 | 无效查询（开始时间归属T日，结束时间归属T1日） |

#### 5.3.2 K线算法说明

**集合竞价的处理**:

- 开盘集合竞价数据的成交量包含在当日第一根K线
- 收盘集合竞价数据的成交量包含在当日最后一根K线

**前推算法**:

- 9:30的1分钟K线，计算的是9:30:00.000~9:30:59.999期间的K线
- 9:35的5分钟K线，计算的是9:35:00.000~9:39:59.999期间的K线

---

### 5.4 本地数据缓存方案

#### 5.4.1 应用场景

1. **接口取全量历史时间区间的数据**: 使用 `local_path` 和 `is_local` 参数组
2. **接口取指定时间区间的数据**: 使用 `begin_date` 和 `end_date` 参数组

> **注意**: 两个参数组需独立使用，不可同时使用

#### 5.4.2 函数入参说明

**local_path**: 本地存储文件夹的绝对路径，如 `'D://AmazingData_local_data//'`

**is_local**:

- `True`: 优先从本地取数据，本地无数据则从服务端获取并更新本地
- `False`: 强制从服务端获取数据并更新本地

**begin_date/end_date**: 按照日期从服务端取数据，不使用本地缓存

#### 5.4.3 本地存储文件说明

- 文件格式: HDF5 格式
- 建议本地存储空间: **500GB 以上**

---

## 免责声明

1. 本公司不能保证数据的及时性、准确性、真实性和完整性
2. 由于计算机故障以及互联网数据传输等原因，数据传输可能出现中断、停顿、延迟、数据错误等情况
3. 本平台所提供的信息数据等全部内容仅供参考，不构成投资建议
4. 用户使用本平台过程中，凡使用用户本人的用户名和密码的操作均视为用户亲自办理
5. 本平台的相关数据知识产权归中国银河证券所有，用户不得将数据转移、出售和公开给任何第三人

---

*文档生成日期: 2026年1月10日*
*基于 AmazingData 开发手册 V1.0.20*
