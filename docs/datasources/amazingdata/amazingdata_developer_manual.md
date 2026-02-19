# AmazingData 接口文档（接口相关内容转存）

> 说明：本文件由 `AmazingData开发手册.pdf` 中“接口相关章节”转存而来，仅做 Markdown 排版优化，未对原文含义做扩写。

## 3.4 Python 开发步骤

登录AmazingData 之后，实现数据获取。

### 3.4.1 登录AmazingData

（1）所有数据接口调用前，必须登录
（2）import AmazingData 库，填写账号、密码、ip/port 等信息，调用登录api。

```python
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
```

### 3.4.2 调用数据接口

#### 3.4.2.1 查询接口调用

（1）登录api；
（2）实例化对应的数据查询类；

（3）调用查询数据接口，获取数据；

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
# 第二步 实例化对应的数据查询类
base_data_object = ad.BaseData()
# 第三步，调用查询数据接口，获取数据
code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')

```

#### 3.4.2.2 订阅接口调用

（1）登录api；
（2）实例化对应的数据查询类；
（3）实例化数据订阅类；
（4）用装饰器装饰回调函数，接收订阅数据；
（5）订阅数据执行；

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
# 第二步 输入标的代码列表
base_data_object = ad.BaseData()
etf_code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')
# 第三步 实例化数据订阅类
sub_data = ad.SubscribeData()
# 第四步  用装饰器装饰回调函数，接收订阅数据
@sub_data.register(code_list=etf_code_list, period=ad.constant.Period.snapshot.value)
def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
# 第五步 订阅数据执行
sub_data.run()

```

## 3.5 API 接口详细

### 3.5.1 基础接口

#### 3.5.1.1 登录

调用任何数据接口之前，必须先调用登录接口。

SDK 的账号、密码、ip 和端口号需联系您的开户营业部申请开通权限之后获取。
函数接口：login
功能描述：api 登陆
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| username | str | 是 | 账号 |
| password | str | 是 | 密码 |
| ip | str | 是 | 服务器ip |
| host | int | 是 | 服务器端口号 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
```

#### 3.5.1.2 登出

函数接口：logout
功能描述：api 退出登录链接 ，必须在登录状态下，才可使用；正常使用情况
下，无需使用此接口

| 名称 | 类型 | 说明 |
| --- | --- | --- |
| username | str | 用户名 |

#### 3.5.1.3 更新密码

函数接口：update_password
功能描述：更新密码接口，必须先登录才能修改密码

| 名称 | 类型 | 说明 |
| --- | --- | --- |
| username | str | 用户名 |
| old_password | str | 旧密码 |
| new_password | str | 新密码 |

### 3.5.2 基础数据

#### 3.5.2.1 每日最新证券信息

函数接口：get_code_info
功能描述：获取每日最新证券信息，交易日早上9 点前更新当日最新
输入：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| security_type | str | 否 | 代码类型security_type（见附录），<br><br>默认为EXTRA_STOCK_A（上交<br>所A 股、深交所A 股和北交所的股<br>票列表） |
输出：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| code_info | dataframe | index 为股票代码<br>column 为<br>symbol (证券简称)<br>security_status（产品状态标志）<br>pre_close (昨收价)<br>high_limited  (涨停价)<br>low_limited ( 跌停价)<br>price_tick (最小价格变动单位) |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_info = base_data_object.get_code_info(security_type='EXTRA_ETF')
```

#### 3.5.2.2 每日最新代码表（沪深北）

交易日早上9 点前更新
函数接口：get_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表
输入：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| security_type | str | 否 | 代码类型security_type（见附录），<br>默认为EXTRA_STOCK_A（上交<br>所A 股、深交所A 股和北交所的股<br>票列表） |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| code_list | list | 证券代码 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')

```

#### 3.5.2.3 每日最新代码表（期货交易所）

交易日早上9 点前更新
函数接口：get_future_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表
输入：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| security_type | str | 是 | 代码类型security_type(期货交易<br>所)（见附录），默认为EXTRA_F<br>UTURE（期货, 包含中金所/上期所<br>/大商所/郑商所/上海国际能源交易<br>中心所） |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| code_list | list | 证券代码 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_future_code_list(security_type='EXTRA_FUTURE')
```

#### 3.5.2.4 每日最新代码表（期权）

交易日早上9 点前更新
函数接口：get_option_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表
输入：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| security_type | str | 是 | 代码类型security_type 期权)（见附<br>录），默认为EXTRA_ETF_OP（E<br>TF 期权, 包含上交所和深交所） |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| code_list | list | 证券代码 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')

```

#### 3.5.2.5 复权因子（后复权因子）

函数接口：BaseData.get_backward_factor
功能描述：获取复权因子数据并本地存储，复权因子为根据交易所行情数据计算得出的后复
权因子；
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | lis[str] | 是 | 代码列表，支持股票、ETF |
| local_path | str | 是 | 本地存储复权因子数据的文件夹地址 |
| is_local | Bool | 是 | 是否使用本地存储的数据，默认为True |
注：
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

（2）is_local
True:
本地local_path 有数据的情况下，从本地取数据，但无法从服务端获取最新的数据
本地local_path 无数据的情况下，从互联网取数据，并更新本地local_path 的数据
False:从互联网取数据，并更新本地local_path 的数据
输出：

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| backward_factor | dataframe | index 为交易日期<br>column 为股票代码 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
backward_factor = base_data_object.get_backward_factor(code_list, local_path='D://AmazingData_local_data//',
is_local=False)
```

#### 3.5.2.6 复权因子（单次复权因子）

函数接口：BaseData.get_adj_factor
功能描述：获取复权因子数据并本地存储，复权因子为根据交易所行情数据计算得出的单次
复权因子；
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | lis[str] | 是 | 代码列表，支持股票、ETF |
| local_path | str | 是 | 本地存储复权因子数据的文件夹地址 |
| is_local | Bool | 是 | 是否使用本地存储的数据，默认为True |
注：
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

（2）is_local
True:
本地local_path 有数据的情况下，从本地取数据，但有可能无法获取最新的数据
本地local_path 无数据的情况下，从互联网取数据，并更新本地local_path 的数据
False:从互联网取数据，并更新本地local_path 的数据
输出：

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| adj_factor | dataframe | index 为交易日期<br>column 为股票代码 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
```

adj_factor
=

```python
base_data_object.get_adj_factor(code_list,
local_path='D://AmazingData_local_data//',
is_local=False)
```

#### 3.5.2.7 历史代码表

函数接口：BaseData 的get_hist_code_list
功能描述：获取历史代码表，先检查本地数据，再从服务端补充，最后返回数据输入参数：
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| security_type | str | 是 | 默认为<br>"EXTRA_STOCK_A_SH_SZ"  沪深A 股，支持<br>附录security_type(沪深北)和security_type(期货<br>交易所)， |
| start_date | int | 是 | 开始时间，闭区间 |
| end_date | int | 是 | 结束时间，闭区间 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式类似“<br>'D://AmazingData_local_data//'” |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| code_list | List[str] | 证券代码 |

```python
# 第一步 登录api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
```

code_list
=

```python
base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ',start_date=20240101,
end_date=20240701, local_path=local_path)

```

#### 3.5.2.8 交易日历

函数接口：get_calendar
功能描述：获取交易所的交易日历

输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| data_type | str | 否 | 选择返回数据的类型，默认为str ，可选datetime<br>或 str |
| market | str | 否 | 选择市场market（见附录），默认为SH（上海） |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| calendar | List[int] | 日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
```

#### 3.5.2.9 证券基础信息

函数接口：get_stock_basic
功能描述：获取指定股票列表的上市公司的证券基础数据，包含沪深北三个交易所，所有股
票（包含已退市标的）的中英文名称、上市日期、退市日期、上市板块等信息
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深北三个交易所的代码列表，可见<br>示例 |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| stock_basic | dataframe | column 为stock_basic 的字段<br>index 为序号（无意义）<br>stock_basic 的字段说明：<br><br>参数<br>数据类型<br>必选<br>解释 |
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| COMP_NAME | string | 证券中文名称 |
| PINYIN | string | 中文拼音简称 |
| COMP_NAME_ENG | string | 证券英文名称 |
| LISTDATE | int | 上市日期 |
| DELISTDATE | int | 退市日期 |
| LISTPLATE_NAME | string | 上市板块名称 |
| COMP_SNAME_ENG | string | 英文名称缩写 |
| IS_LISTED | int | 上市状态<br>1：上市交易<br>3：终止上市 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A_SH_SZ')
info_data_object = ad.InfoData()
stock_basic = info_data_object.get_stock_basic (code_list)
```

#### 3.5.2.10 历史证券信息

函数接口：get_history_stock_status
功能描述：获取指定股票列表的上市公司的历史证券数据，以日度为频率，包含历史的涨跌
停、st、除权除息等信息
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式类<br>似“D://AmazingData_local_data//” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日，本地数据缓存方案 |
| end_date | int | 否 | 交易日，本地数据缓存方案 |
输出参数：
| 返回值 | 数据类型 | 解释 |
| --- | --- | --- |
| history_stock_status | dataframe | column 为history_stock_status 的字段<br>index 为序号（无意义）<br>history_stock_status 的字段说明：<br>参数<br>数据类型<br>必选<br>解释 |
| MARKET_CODE | string | 证券代码 |
| TRADE_DATE | string | 日期 |
| PRECLOSE | float | 前收价 |
| HIGH_LIMITED | float | 涨停价 |
| LOW_LIMITED | float | 跌停价 |
| PRICE_HIGH_LMT_RATE | float | 涨停价上限 |
| PRICE_LOW_LMT_RATE | float | 跌停价下限 |
| IS_ST_SEC | string | 是否ST<br>1 表示是，0 表示否 |
| IS_SUSP_SEC | string | 是否停牌<br>1 表示是，0 表示否 |
| IS_WD_SEC | string | 是否除息<br>1 表示是，0 表示否 |
| IS_XR_SEC | string | 是否除权<br>1 表示是，0 表示否 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
end_date=today)
history_stock_status = info_data_object.get_history_stock_status(all_code_list)

```

#### 3.5.2.11 北交所新旧代码对照表

函数接口：get_bj_code_mapping
功能描述：获取北交所的存量上市公司股票新旧代码对照表
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，首选从本地读取，读取失败<br>再从服务器取数据<br>False，以本地数据为基础，增量从服务器<br>取数据 |
 输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| bj_code_map | ping | dataframe<br>column 为bj_code_mapping 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
bj_code_mapping = info_data_object.get_bj_code_mapping()
```

bj_code_mapping 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| OLD_CODE | string | 旧代码 |
| NEW_CODE | string | 新代码 |
| SECURITY_NAME | string | 证券简称 |
| LISTING_DATE | int | 上市日期 |

### 3.5.3 实时行情数据

实时行情订阅接口使用步骤
（1） 实例化AmazingData 的SubscribeData
（2） 回调函数的装饰器传入code_list(代码表)和period(数据周期)两个参数
（3） 回调函数中获取数据

#### 3.5.3.1 指数实时快照

函数接口：onSnapshotindex
功能描述：交易所指数快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持北交所、上交所、深交所<br>的指数 |
| period | Period | 是 | Period.snapshot.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 指数为SnapshotIndex（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)

base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type=' EXTRA_INDEX_A')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotindex(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
    print(period, data)
sub_data.run()

```

#### 3.5.3.2 股票实时快照

函数接口：onSnapshot
功能描述：level-1 快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持北交所、上交所、深交所<br>的股票 |
| period | Period | 是 | Period.snapshot.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 股票为Snapshot（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshot(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
sub_data.run()
```

#### 3.5.3.3 逆回购实时快照

函数接口：onSnapshotglra
功能描述：level-1 快照数据的实时订阅回调函数

输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持上交所、深交所的逆回购<br>代码 |
| period | Period | 是 | Period.snapshot.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 为Snapshot（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_GLRA')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotglra(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
sub_data.run()
```

#### 3.5.3.4 期货实时快照

函数接口：onSnapshotfuture
功能描述：level-1 快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持中金所/上期所/大商所/<br>郑商所/上海国际能源交易中心所 |
| period | Period | 是 | Period.snapshotfuture.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 期货为SnapshotFuture（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)

base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_FUTURE')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshotfuture.value)
def onSnapshotfuture (data: Union[ad.constant.SnapshotFuture], period):
print(period, data)
sub_data.run()
```

#### 3.5.3.5 ETF 实时快照

函数接口：onSnapshotetf
功能描述：level-1 快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持上交所、深交所的ETF |
| period | Period | 是 | Period.snapshot.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | ETF 为Snapshot（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotetf(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
sub_data.run()


```

#### 3.5.3.6 可转债实时快照

函数接口：onSnapshotkzz
功能描述：level-1 快照数据的实时订阅回调函数

输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持上交所、深交所的可转债 |
| period | Period | 是 | Period.snapshot.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 可转债为Snapshot（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_KZZ')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotkzz(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
sub_data.run()
```

#### 3.5.3.7 港股通实时快照

函数接口：onSnapshothkt
功能描述：港股通快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持上交所、深交所的可转债 |
| period | Period | 是 | Period.snapshotHKT.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | 港股通为SnapshotHKT（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_HKT')

# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshothkt(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):
print(period, data)
sub_data.run()
```

#### 3.5.3.8 ETF 期权实时快照

函数接口：onSnapshotoption
功能描述：港股通快照数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持上交所、深交所的ETF<br>期权 |
| period | Period | 是 | Period.snapshotoption.value |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | ETF 期权为SnapshotOption（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
option_code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')
# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=option_code_list, period=ad.constant.Period.snapshotoption.value)
def onSnapshotoption(data: Union[ad.constant.SnapshotOption], period):
    print('onSnapshotoption: ', data)
sub_data.run()
```

#### 3.5.3.9 实时K 线

函数接口：OnKLine
功能描述：K 线数据的实时订阅回调函数
输入参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持北交所、上交所、深交<br><br>所的可转债、股票、指数、ETF 等品种<br>支持期货（中金所/上期所/大商所/郑商所/<br>上海国际能源交易中心所） |
| period | Period | 是 | Period（见附录） |
输出参数：入参需传入装饰器中SubscribeData.register

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| data | Object | Kline（见附录） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A ')
# 实时订阅
sub_data = ad.SubscribeData()
# K 线
@sub_data.register(code_list=code_list, period=ad.constant.Period.min1.value)
def OnKLine(data: Union[ad.constant.Kline], period):
 print('OnKLine: ', data)
sub_data.run()
```

### 3.5.4 历史行情数据

（1） 实例化AmazingData 的MarketData，入参需交易日历
（2） 调用MarketData 的方法获取数据

#### 3.5.4.1 历史快照

函数接口：query_snapshot
功能描述：快照数据的历史数据查询接口
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持北交所、上交所、深交<br>所的可转债、股票、指数、ETF、港股通<br>等、ETF 期权等品种 |
| begin_date | int | 是 | 日期，填写8 位的整型格式的日期，比如 |
| end_date | int | 是 | 日期，填写8 位的整型格式的日期，比如 |
| begin_time | int | 否 | 时分秒毫秒的时间戳，填写8 位或9 位的<br><br>整型格式的日期，时占一位或两位，分占<br>两位，秒占两位，毫秒占三位，例如9 点<br>整<br>为90000000, 17 点25 分为172500000 |
| end_time | int | 否 | 时分秒毫秒的时间戳，填写8 位或9 位的<br>整型格式的日期，时占一位或两位，分占<br>两位，秒占两位，毫秒占三位，例如9 点<br>整<br>为90000000, 17 点25 分为172500000 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| snapshot_dict | dict | 指字典的key：代码<br>字典的value：dataframe，<br>column 为快照数据（指数为SnapshotIndex（见附录），<br>股票、ETF 和可转债为Snapshot（见附录），<br>港股通为SnapshotHKT（见附录）），<br>ETF 期权为SnapshotOption（见附录）），<br><br>index 为日期（datetime） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A ')
calendar = base_data_object.get_calendar()
market_data_object=ad.MarketData(calendar)
snapshot_dict = market_data_object.query_snapshot(code_list, begin_date=20240530, end_date=20240530)
```

#### 3.5.4.2 历史K 线

函数接口：query_kline
功能描述：K 线数据的实时订阅回调函数 ，支持全部周期的K 线数据查询
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list:[str] | 是 | 可传入列表，支持北交所、上交所、深交<br>所的可转债、股票、指数、ETF 等品种，<br>上交所、深交所的ETF 期权；<br>支持期货（中金所/上期所/大商所/郑商所/<br>上海国际能源交易中心所） |
| begin_date | int | 是 | 日期，填写8 位的整型格式的日期，比如 |
| end_date | int | 是 | 日期，填写8 位的整型格式的日期，比如 |
| period | Period | 是 | 数据周期Period（见附录） |
| begin_time | int | 否 | 时分的时间戳，填写3 位或4 位的整型格<br>式的日期，时占一位或两位，分占两位，，<br>例如9 点整<br>为900, 17 点25 分为1725 |
| end_time | int | 否 | 时分的时间戳，填写3 位或4 位的整型格<br>式的日期，时占一位或两位，分占两位，，<br>例如9 点整<br>为900, 17 点25 分为1725 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kline_dict | dict | 字典的key：代码<br>字典的value：dataframe，<br>column 为K 线数据Kline（见附录），<br>index 为日期（datetime） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
calendar = base_data_object.get_calendar()
market_data_object=ad.MarketData(calendar)
kline_dict = market_data_object.query_kline (code_list, begin_date=20240530, end_date=20240530)
```

### 3.5.5 财务数据

#### 3.5.5.1 资产负债表

函数接口：get_balance_sheet
功能描述：获取指定股票列表的上市公司的资产负债表数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 报告期，本地数据缓存方案 |
| end_date | int | 否 | 报告期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| balance_sheet | dict | key：code<br>value:dataframe<br>column 为balance_sheet 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
balance_sheet = info_data_object.get_balance_sheet(all_code_list)
```

balance_sheet 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | str<br>证券代码 |
| SECURITY_NAME | str | 证券简称 |
| STATEMENT_TYPE | str | 报表类型<br>参看报表类型代码表 |
| REPORT_TYPE | str | 报告期名称<br>参看报告期名称 |
| REPORTING_PERIOD | str | 报告期 |
| ANN_DATE | str | 公告日期 |
| ACTUAL_ANN_DATE | str | 实际公告日期 |
| ACC_PAYABLE | float | 应付票据及应付账<br>款 |
| ACC_RECEIVABLE | float | 应收票据及应收账<br>款 |
| ACC_RECEIVABLES | float | 应收款项 |
| ACCRUED_EXP | float | 预提费用 |
| ACCT_PAYABLE | float | 应付账款 |
| ACCT_RECEIVABLE | float | 应收账款 |
| ACT_TRADING_SEC | float | 代理买卖证券款 |
| ACT_UW_SEC | float | 代理承销证券款 |
| ADV_PREM | float | 预收保费 |
| ADV_RECEIPT | float | 预收款项 |
| AGENCY_ASSETS | float | 代理业务资产 |
| AGENCY_BUSINESS_LI | AB | float<br>代理业务负债 |
| ANTICIPATION_LIAB | float | 预计负债<br><br>ASSET_DEP_FUNDS_O |
| TH_FIN_INST | float | 存放同业和其它金<br>融机构款项 |
| BONDS_PAYABLE | float | 应付债券 |
| CAP_RESV | float | 资本公积金 |
| CAP_STOCK | float | 股本<br>金额（元），公布值<br>CASH_CENTRAL_BAN |
| K_DEPOSITS | float | 现金及存放中央银<br>行款项<br><br>CED_INSUR_CONT_RE |
| SERVES_RCV | float | 应收分保合同准备<br>金 |
| CLAIMS_PAYABLE | float | 应付赔付款 |
| CLIENTS_FUND_DEPO | SIT | float<br>客户资金存款 |
| CLIENTS_RESERVES | float | 客户备付金<br><br>CNVD_DIFF_FOREIGN_ |
| CURR_STAT | float | 外币报表折算差额 |
| COMP_TYPE_CODE | int | 公司类型代码<br>1：非金融类2：银行3：<br>保险4：证券 |
| CONST_IN_PROC | float | 在建工程 |
| CONST_IN_PROC_TOT | AL | float<br>在建工程(合计)(元)<br><br><br>CONSUMP_BIO_ASSET |
| S | float | 消耗性生物资产 |
| CONT_ASSETS | float | 合同资产<br>单位（元） |
| CONT_LIABILITIES | float | 合同负债<br>单位（元） |
| CURRENCY_CAP | float | 货币资金 |
| CURRENCY_CODE | float | 货币代码 |
| DEBT_INV | float | 债权投资(元)<br><br>DEFERRED_INC_NONC |
| UR_LIAB | float | 递延收益-非流动负<br>债 |
| DEFERRED_INCOME | float | 递延收益 |
| DEFERRED_TAX_ASSE | TS | float<br>递延所得税资产 |
| DEFERRED_TAX_LIAB | float | 递延所得税负债<br><br>DEP_RECEIVED_IB_DE |
| P | float | 吸收存款及同业存<br>放 |
| DEPOSIT_CAP_RECOG | float | 存出资本保证金 |
| DEPOSIT_TAKING | float | 吸收存款 |
| DEPOSITS_RECEIVED | float | 存入保证金 |
| DER_FIN_ASSETS | float | 衍生金融资产 |
| DERI_FIN_LIAB | float | 衍生金融负债 |
| DEVELOP_EXP | float | 开发支出<br><br>DISPOSAL_FIX_ASSET |
| S | float | 固定资产清理 |
| DIV_PAYABLE | float | 应付股利 |
| DIV_RECEIVABLE | float | 应收股利 |
| EMPL_PAY_PAYABLE | float | 应付职工薪酬 |
| ENGIN_MAT | float | 工程物资<br><br>FIN_ASSETS_AVA_FOR |
| _SALE | float | 可供出售金融资产 |
| FIN_ASSETS_COST_SH | ARING | float<br>以摊余成本计量的<br>金融资产 |
| FIN_ASSETS_FAIR_VAL | UE | float<br>以公允价值计量且<br>其变动计入其他综<br>合收益的金融资产 |
| FIXED_ASSETS | float | 固定资产 |
| FIXED_ASSETS_TOTAL | float | 固定资产(合计)(元)<br><br>FIXED_TERM_DEPOSIT |
| S | float | 定期存款 |
| GOODWILL | float | 商誉 |
| GUA_DEPOSITS_PAID | float | 存出保证金 |
| GUA_PLEDGE_LOANS | float | 保户质押贷款 |
| HOLD_ASSETS_FOR_S | ALE | float<br>持有待售的资产 |
| HOLD_TO_MTY_INV | float | 持有至到期投资 |
| INC_PLEDGE_LOAN | float | 其中:质押借款 |
| INCL_TRADING_SEAT_ | FEES | float<br>其中:交易席位费 |
| IND_ACCT_ASSETS | float | 独立账户资产 |
| IND_ACCT_LIAB | float | 独立账户负债<br><br>INSURED_DEPOSIT_IN |
| V | float | 保户储金及投资款<br><br>INSURED_DIV_PAYABL |
| E | float | 应付保单红利 |
| INT_RECEIVABLE | float | 应收利息 |
| INTANGIBLE_ASSETS | float | 无形资产 |
| INTEREST_PAYABLE | float | 应付利息 |
| INV | float | 存货 |
| INV_REALESTATE | float | 投资性房地产 |
| LEASE_LIABILITY | float | 租赁负债 |
| LEND_FUNDS | float | 融出资金 |
| LENDING_FUNDS | float | 拆出资金 |
| LESS_TREASURY_STK | float | 减:库存股 |
| LIA_HFS | float | 持有待售的负债<br><br>LIAB_DEP_FUNDS_OT |
| H_FIN_INST | float | 同业和其它金融机<br>构存放款项 |
| LIFE_INSUR_RESV | float | 寿险责任准备金<br><br>LOAN_CENTRAL_BAN |
| K | float | 向中央银行借款 |
| LOANS_AND_ADVANC | ES | float<br>发放贷款及垫款 |
| LOANS_FROM_OTH_B | ANKS | float<br>拆入资金 |
| LT_DEFERRED_EXP | float | 长期待摊费用 |
| LT_EMP_COMP_PAY | float | 长期应付职工薪酬 |
| LT_EQUITY_INV | float | 长期股权投资 |
| LT_HEALTH_INSUR_RE | SV | float<br>长期健康险责任准<br>备金 |
| LT_LOAN | float | 长期借款 |
| LT_PAYABLE | float | 长期应付款 |
| LT_PAYABLE_TOTAL | float | 长期应付款(合计)<br>(元) |
| LT_RECEIVABLES | float | 长期应收款 |
| MINORITY_EQUITY | float | 少数股东权益 |
| NOM_RISKS_PREP | float | 一般风险准备<br><br>NONCUR_ASSETS_DUE |
| _WITHIN_1Y | float | 一年内到期的非流<br>动资产<br><br>NONCUR_LIAB_DUE_ |
| WITHIN_1Y | float | 一年内到期的非流<br>动负债 |
| NOTES_PAYABLE | float | 应付票据 |
| NOTES_RECEIVABLE | float | 应收票据<br><br>OIL_AND_GAS_ASSET |
| S | float | 油气资产 |
| OTH_COMP_INCOME | float | 其他综合收益 |
| OTH_EQUITY_TOOLS | float | 其他权益工具<br><br><br>OTH_EQUITY_TOOLS_ |
| PRE_SHR | float | 其他权益工具:优先<br>股 |
| OTH_NONCUR_ASSETS | float | 其他非流动资产 |
| OTHER_ASSETS | float | 其他资产 |
| OTHER_CUR_ASSETS | float | 其他流动资产 |
| OTHER_CUR_LIAB | float | 其他流动负债 |
| OTHER_DEBT_INV | float | 其他债权投资(元) |
| OTHER_EQUITY_INV | float | 其他权益工具投资<br>(元) |
| OTHER_LIAB | float | 其他负债 |
| OTHER_NONCUR_FIN_ | ASSETS | float<br>其他非流动金融资<br>产(元) |
| OTHER_NONCUR_LIAB | float | 其他非流动负债 |
| OTHER_PAYABLE | float | 其他应付款 |
| OTHER_PAYABLE_TOT | AL | float<br>其他应付款(合计)<br>(元) |
| OTHER_RCV_TOTAL | float | 其他应收款(合计)<br>（元） |
| OTHER_RECEIVABLE | float | 其他应收款<br><br>OTHER_SUSTAIN_BON |
| D | float | 其他权益工具:永续<br>债(元) |
| OUT_LOSS_RESV | float | 未决赔款准备金 |
| PAYABLE | float | 应付款项 |
| PAYABLE_FOR_REINSU | RER | float<br>应付分保账款 |
| PRECIOUS_METAL | float | 贵金属 |
| PREPAYMENT | float | 预付款项 |
| PROD_BIO_ASSETS | float | 生产性生物资产<br><br>RCV_CED_CLAIM_RES |
| V | float | 应收分保未决赔款<br>准备金<br><br>RCV_CED_LIFE_INSUR |
| _RESV | float | 应收分保寿险责任<br>准备金<br><br><br>RCV_CED_LT_HEALTH |
| _INSUR_RESV | float | 应收分保长期健康<br>险责任准备金<br><br>RCV_CED_UNEARNED |
| _PREM_RESV | float | 应收分保未到期责<br>任准备金 |
| RCV_FINANCING | float | 应收款项融资 |
| RCV_INV | float | 应收款项类投资 |
| RECEIVABLE_PREM | float | 应收保费 |
| RED_MON_CAP_FOR_S | ALE | float<br>买入返售金融资产 |
| REINSURANCE_ACC_R | CV | float<br>应收分保账款 |
| RSRV_FUND_INSUR_C | ONT | float<br>保险合同准备金 |
| SELL_REPO_FIN_ASSE | TS | float<br>卖出回购金融资产<br>款<br><br>SERVICE_CHARGE_CO |
| MM_PAYABLE | float | 应付手续费及佣金 |
| SETTLE_FUNDS | float | 结算备付金<br><br>SPE_ASSETS_BAL_DIF |
| F | float | 资产差额(特殊报表<br>科目)<br><br>SPE_CUR_ASSETS_DIF |
| F | float | 流动资产差额(特殊<br>报表科目) |
| SPE_CUR_LIAB_DIFF | float | 流动负债差额(特殊<br>报表科目) |
| SPE_LIAB_BAL_DIFF | float | 负债差额(特殊报表<br>科目)<br><br>SPE_LIAB_EQUITY_BA |
| L_DIFF | float | 负债及股东权益差<br>额(特殊报表项目)<br><br>SPE_NONCUR_ASSETS |
| _DIFF | float | 非流动资产差额(特<br>殊报表科目) |
| SPE_NONCUR_LIAB_DI | FF | float<br>非流动负债差额(特<br>殊报表科目)<br><br>SPE_SHARE_EQUITY_B |
| AL_DIFF | float | 股东权益差额(特殊<br>报表科目) |
| SPECIAL_PAYABLE | float | 专项应付款 |
| SPECIAL_RESV | float | 专项储备 |
| ST_BONDS_PAYABLE | float | 应付短期债券 |
| ST_BORROWING | float | 短期借款 |
| ST_FIN_PAYABLE | float | 应付短期融资款 |
| SUBR_RCV | float | 应收代位追偿款 |
| SURPLUS_RESV | float | 盈余公积金 |
| TAX_PAYABLE | float | 应交税费<br><br>TOT_ASSETS_BAL_DIF |
| F | float | 资产差额(合计平衡<br>项目)<br><br>TOT_CUR_ASSETS_DIF |
| F | float | 流动资产差额(合计<br>平衡项目) |
| TOT_CUR_LIAB_DIFF | float | 流动负债差额(合计<br>平衡项目) |
| TOT_LIAB_BAL_DIFF | float | 负债差额(合计平衡<br>项目)<br><br>TOT_LIAB_EQUITY_BA |
| L_DIFF | float | 负债及股东权益差<br>额(合计平衡项目) |
| TOT_NONCUR_ASSETS | float | 非流动资产合计<br><br>TOT_NONCUR_ASSETS |
| _DIFF | float | 非流动资产差额(合<br>计平衡项目) |
| TOT_NONCUR_LIAB_D | IFF | float<br>非流动负债差额(合<br>计平衡项目) |
| TOT_SHARE | float | 期末总股本<br>单位（股）<br>TOT_SHARE_EQUITY_ |
| BAL_DIFF | float | 股东权益差额(合计<br>平衡项目)<br><br>TOT_SHARE_EQUITY_ |
| EXCL_MIN_INT | float | 股东权益合计(不含<br>少数股东权益)<br><br>TOT_SHARE_EQUITY_I |
| NCL_MIN_INT | float | 股东权益合计(含少<br>数股东权益) |
| TOTAL_ASSETS | float | 资产总计 |
| TOTAL_CUR_ASSETS | float | 流动资产合计 |
| TOTAL_CUR_LIAB | float | 流动负债合计 |
| TOTAL_LIAB | float | 负债合计 |
| TOTAL_LIAB_SHARE_E | QUITY | float<br>负债及股东权益总<br>计 |
| TOTAL_NONCUR_LIAB | float | 非流动负债合计 |
| TRADING_FIN_LIAB | float | 交易性金融负债 |
| TRADING_FINASSETS | float | 交易性金融资产 |
| UNAMORTIZED_EXP | float | 待摊费用 |
| UNCONFIRMED_INV_L | OSS | float<br>未确认的投资损失 |
| UNDISTRIBUTED_PRO | float | 未分配利润 |
| UNEARNED_PREM_RE | SV | float<br>未到期责任准备金 |
| USE_RIGHT_ASSETS | float | 使用权资产 |

#### 3.5.5.2 现金流量表

函数接口：get_cash_flow
功能描述：获取指定股票列表的上市公司的现金流量表数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 报告期，本地数据缓存方案 |
| end_date | int | 否 | 报告期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| cash_flow | dict | key：code<br>value:dataframe<br>column 为cash_flow 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
cash_flow = info_data_object.get_cash_flow (all_code_list)
```

cash_flow 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | str<br>证券代码<br><br>SECURITY_NAM |
| E | str | 证券简称<br><br>STATEMENT_TYP |
| E | str | 报表类型<br>参看报表类<br>型代码表 |
| REPORT_TYPE | str | 报告期名称<br>参看报告期<br>名称 |
| REPORTING_PERI | OD | str<br>报告期 |
| ANN_DATE | str | 公告日期 |
| ACTUAL_ANN_D | ATE | str<br>实际公告日期<br><br>ABSORB_CASH_ |
| RECP_INV | double | 吸收投资收到的现金 |
| AMORT_INTAN_ | ASSETS | double<br>无形资产摊销<br><br>AMORT_LT_DEFE |
| RRED_EXP | double | 长期待摊费用摊销<br><br>BEG_BAL_CASH_ |
| CASH_EQU | double | 期初现金及现金等价物余额 |
| CASH_END_BAL | double | 现金的期末余额 |
| CASH_FOR_CHA | RGE | double<br>支付手续费的现金<br><br>CASH_PAID_INSU |
| R_POLICY | double | 支付保单红利的现金 |
| CASH_PAID_INV | double | 投资支付的现金<br><br>CASH_PAID_PUR |
| _CONST_FIOLTA | double | 购建固定资产、无形资产和其他长期<br>资产支付的现金<br><br>CASH_PAY_CLAI |
| MS_OIC | double | 支付原保险合同赔付款项的现金<br><br>CASH_PAY_DIST_ |
| DIV_PRO_INT | double | 分配股利、利润或偿付利息支付的现<br>金 |
| CASH_PAY_EMPL | OYEE | double<br>支付给职工以及为职工支付的现金 |
| CASH_PAY_FOR_ | DEBT | double<br>偿还债务支付的现金<br><br>CASH_PAY_GOO |
| DS_SERVICES | double | 购买商品、接受劳务支付的现金 |
| CASH_RECE_BO | RROW | double<br>取得借款收到的现金<br><br>CASH_RECE_ISS |
| UE_BONDS | double | 发行债券收到的现金<br><br>CASH_RECP_INV |
| _INCOME | double | 取得投资收益收到的现金<br><br>CASH_RECP_PRE |
| M_OIC | double | 收到原保险合同保费取得的现金<br><br>CASH_RECP_REC |
| OV_INV | double | 收回投资收到的现金<br><br>CASH_RECP_SG_ |
| AND_RS | double | 销售商品、提供劳务收到的现金 |
| COMP_TYPE_CO | DE | str<br>公司类型代码<br>1：非金融类<br>2：银行3：<br>保险4：证券<br>CONV_CORP_BO<br>NDS_DUE_WITHI |
| N_1Y | double | 一年内到期的可转换公司债券<br><br>CONV_DEBT_INT |
| O_CAP | double | 债务转为资本 |
| CREDIT_IMPAIR_ | LOSS | double<br>信用减值损失<br><br>CURRENCY_COD |
| E | str | 货币代码<br><br>DECR_DEFE_INC |
| _TAX_ASSETS | double | 递延所得税资产减少<br><br>DECR_DEFERRE |
| D_EXPENSE | double | 待摊费用减少<br><br>DECR_INVENTOR |
| Y | double | 存货的减少 |
| DECR_OPERA_RE | CEIVABLE | double<br>经营性应收项目的减少 |
| DEPRE_FA_OGA_ | PBA | double<br>固定资产折旧、油气资产折耗、生产<br>性生物资产折旧 |
| EFF_FX_FLUC_C | ASH | double<br>汇率变动对现金的影响<br><br>END_BAL_CASH_ |
| CASH_EQU | double | 期末现金及现金等价物余额 |
| FINANCIAL_EXP | double | 财务费用<br><br>FIXED_ASSETS_F |
| IN_LEASE | double | 融资租入固定资产<br><br>FREE_CASH_FLO |
| W | double | 企业自由现金流量<br><br><br>INCL_CASH_REC |
| P_SAIMS | double | 其中:子公司吸收少数股东投资收到<br>的现金<br><br>INCL_DIV_PRO_P |
| AID_SMS | double | 其中:子公司支付给少数股东的股利、<br>利润 |
| INCR_ACCRUED_ | EXP | double<br>预提费用增加<br><br>INCR_DEFE_INC_ |
| TAX_LIAB | double | 递延所得税负债增加 |
| INCR_OPERA_PA | YABLE | double<br>经营性应付项目的增加<br><br>IND_NET_CASH_ |
| FLOWS_OPERA_ | ACT | double<br>间接法-经营活动产生的现金流量净<br>额<br><br>IND_NET_INCR_ |
| CASH_AND_EQU | double | 间接法-现金及现金等价物净增加额 |
| INV_LOSS | double | 投资损失<br><br>IS_CALCULATIO |
| N | int | 是否计算报表<br><br>LESS_OPEN_BAL |
| _CASH | double | 减:现金的期初余额<br><br>LESS_OPEN_BAL |
| _CASH_EQU | double | 减:现金等价物的期初余额 |
| LOSS_DISP_FIOL | TA | double<br>处置固定、无形资产和其他长期资产<br>的损失<br><br>LOSS_FAIRVALU |
| E_CHG | double | 公允价值变动损失 |
| LOSS_FIXED_ASS | ETS | double<br>固定资产报废损失<br><br>NET_CASH_FLO |
| WS_FIN_ACT | double | 筹资活动产生的现金流量净额<br><br><br>NET_CASH_FLO |
| WS_INV_ACT | double | 投资活动产生的现金流量净额<br><br>NET_CASH_FLO |
| WS_OPERA_ACT | double | 经营活动产生的现金流量净额<br><br>NET_CASH_PAID |
| _SOBU | double | 取得子公司及其他营业单位支付的现<br>金净额 |
| NET_CASH_REC_ | SEC | double<br>代理买卖证券收到的现金净额<br><br>NET_CASH_RECP |
| _DISP_FIOLTA | double | 处置固定资产、无形资产和其他长期<br>资产收回的现金净额<br><br>NET_CASH_RECP |
| _DISP_SOBU | double | 处置子公司及其他营业单位收到的现<br>金净额<br><br>NET_CASH_RECP |
| _REINSU_BUS | double | 收到再保业务现金净额<br><br>NET_INCR_BORR |
| _FUND | double | 拆入资金净增加额<br><br>NET_INCR_BORR |
| _OFI | double | 向其他金融机构拆入资金净增加额<br><br>NET_INCR_CASH<br>_AND_CASH_EQ |
| U | double | 现金及现金等价物净增加额<br><br>NET_INCR_CUS_ |
| LOAN_ADV | double | 客户贷款及垫款净增加额<br><br>NET_INCR_DEP_ |
| CB_IB | double | 存放央行和同业款项净增加额<br><br>NET_INCR_DEP_ |
| CUS_AND_IB | double | 客户存款和同业存放款项净增加额<br><br><br>NET_INCR_DISM |
| ANTLE_CAP | double | 拆出资金净增加额 |
| NET_INCR_DISP_ | FAAS | double<br>处置可供出售金融资产净增加额 |
| NET_INCR_DISP_ | TFA | double<br>处置交易性金融资产净增加额<br><br>NET_INCR_INSU |
| RED_SAVE | double | 保户储金净增加额<br><br>NET_INCR_INT_A |
| ND_CHARGE | double | 收取利息和手续费净增加额<br><br>NET_INCR_LOAN |
| S_CENTRAL_BA | NK | double<br>向中央银行借款净增加额<br><br>NET_INCR_PLED |
| GE_LOAN | double | 质押贷款净增加额<br><br>NET_INCR_REPU |
| _BUS_FUND | double | 回购业务资金净增加额 |
| NET_PROFIT | double | 净利润<br><br>OTH_CASH_PAY_ |
| INV_ACT | double | 支付其他与投资活动有关的现金<br><br>OTH_CASH_PAY_ |
| OPERA_ACT | double | 支付其他与经营活动有关的现金<br><br>OTH_CASH_RECP |
| _INV_ACT | double | 收到其他与投资活动有关的现金<br><br>OTHER_ASSETS_ |
| IMPAIR_LOSS | double | 其他资产减值损失<br><br>OTHER_CASH_PA |
| Y_FIN_ACT | double | 支付其他与筹资活动有关的现金<br><br>OTHER_CASH_R |
| ECP_FIN_ACT | double | 收到其他与筹资活动有关的现金<br><br><br>OTHER_CASH_R |
| ECP_OPER_ACT | double | 收到其他与经营活动有关的现金 |
| OTHERS | double | 其他（废弃） |
| PAY_ALL_TAX | double | 支付的各项税费<br><br>PLUS_ASSETS_D |
| EPRE_PREP | double | 加:资产减值准备<br><br>PLUS_END_BAL_ |
| CASH_EQU | double | 加:现金等价物的期末余额 |
| RECP_TAX_REFU | ND | double<br>收到的税费返还<br><br>SPE_BAL_CASH_I |
| NFLOW_FIN_ACT | double | 筹资活动现金流入差额<br><br>SPE_BAL_CASH_I<br>NFLOW_INV_AC |
| T | double | 投资活动现金流入差额<br><br>SPE_BAL_CASH_I |
| NFLOW_OPERA_ | ACT | double<br>经营活动现金流入差额<br><br>SPE_BAL_CASH_ |
| OUTFLOW_FIN | double | 筹资活动现金流出差额<br><br>SPE_BAL_CASH_ |
| OUTFLOW_INV | double | 投资活动现金流出差额<br><br>SPE_BAL_CASH_<br>OUTFLOW_OPER |
| A | double | 经营活动现金流出差额<br><br>SPE_BAL_NETCA<br>SH_INC_DIFF_IN |
| D | double | 间接法-现金净增加额差额<br><br>SPE_BAL_NETCA |
| SH_INCR_DIFF | double | 现金净增加额差额<br><br>SPE_BAL_NETCA |
| SH_OPERA_IND | double | 间接法-经营活动现金流量净额差额<br><br><br>TOT_BAL_CASH_<br>INFLOW_FIN_AC |
| T | double | 筹资活动现金流入差额<br><br>TOT_BAL_CASH_<br>INFLOW_INV_AC |
| T | double | 投资活动现金流入差额<br><br>TOT_BAL_CASH_ |
| INFLOW_OPERA_ | ACT | double<br>经营活动现金流入差额<br><br>TOT_BAL_CASH_ |
| OUTFLOW_FIN | double | 筹资活动现金流出差额<br><br>TOT_BAL_CASH_ |
| OUTFLOW_INV | double | 投资活动现金流出差额<br><br>TOT_BAL_CASH_<br>OUTFLOW_OPER |
| A | double | 经营活动现金流出差额<br><br>TOT_BAL_NETCA |
| SH_FLOW_FIN | double | 筹资活动产生的现金流量净额差额<br><br>TOT_BAL_NETCA |
| SH_FLOW_INV | double | 投资活动产生的现金流量净额差额<br><br>TOT_BAL_NETCA<br>SH_FLOW_OPER |
| A | double | 经营活动产生的现金流量净额差额<br><br>TOT_BAL_NETCA<br>SH_INC_DIFF_IN |
| D | double | 间接法-现金净增加额差额<br><br>TOT_BAL_NETCA |
| SH_INCR_DIFF | double | 现金净增加额差额<br><br>TOT_BAL_NETCA |
| SH_OPERA_IND | double | 间接法-经营活动现金流量净额差额<br><br>TOT_CASH_INFL |
| OW_FIN_ACT | double | 筹资活动现金流入小计<br><br>TOT_CASH_INFL |
| OW_INV_ACT | double | 投资活动现金流入小计<br><br><br>TOT_CASH_INFL |
| OW_OPER_ACT | double | 经营活动现金流入小计<br><br>TOT_CASH_OUTF |
| LOW_FIN_ACT | double | 筹资活动现金流出小计<br><br>TOT_CASH_OUTF |
| LOW_INV_ACT | double | 投资活动现金流出小计<br><br>TOT_CASH_OUTF<br>LOW_OPERA_AC |
| T | double | 经营活动现金流出小计<br><br>UNCONFIRMED_I |
| NV_LOSS | double | 未确认投资损失<br><br>USE_RIGHT_ASS |
| ET_DEP | double | 使用权资产折旧 |

#### 3.5.5.3 利润表

函数接口：get_income
功能描述：获取指定股票列表的上市公司的利润表数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 报告期，本地数据缓存方案 |
| end_date | int | 否 | 报告期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| income | dict | key：code<br>value:dataframe<br>column 为income 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad

ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
income = info_data_object.get_income (all_code_list)
```

income 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | str<br>证券代码 |
| SECURITY_NAME | str | 证券简称<br><br>STATEMENT_TYP |
| E | str | 报表类型<br>参看报表类型代码表 |
| REPORT_TYPE | str | 报告期名称<br>参看报告期名称 |
| REPORTING_PERI | OD | str<br>报告期 |
| ANN_DATE | str | 公告日期 |
| ACTUAL_ANN_DA | TE | str<br>实际公告日期<br><br>AMORT_COST_FI |
| N_ASSETS_EAR | float | 以摊余成本计量的<br>金融资产终止确认<br>收益 |
| ANN_DATE | str | 公告日期 |
| BASIC_EPS | float | 基本每股收益<br><br>BEG_UNDISTRIBU |
| TED_PRO | float | 年初未分配利润<br><br>CAPITALIZED_CO |
| M_STOCK_DIV | float | 转作股本的普通股<br>股利 |
| COMMENTS | str | 备注<br><br>COMMON_STOCK |
| _DIV_PAYABLE | float | 应付普通股股利<br><br>COMP_TYPE_COD |
| E | str | 公司类型代码<br>1：非金融类2：银行3：<br>保险4：证券<br><br>CONTINUED_NET |
| _OPERA_PRO | float | 持续经营净利润 |
| CREDIT_IMPAIR_L | OSS | float<br>信用减值损失 |
| CURRENCY_CODE | str | 货币代码 |
| DILUTED_EPS | float | 稀释每股收益<br><br>DISTRIBUTIVE_PR |
| O | float | 可分配利润<br><br>DISTRIBUTIVE_PR |
| O_SHAREHOLDER | float | 可供股东分配的利<br>润 |
| DIV_EXP_INSUR | float | 保户红利支出 |
| EBIT | float | 息税前利润 |
| 正向法 | EBITDA | float<br>息税折旧摊销前利<br>润 |
| EMPLOYEE_WELF | ARE | float<br>职工奖金福利<br><br>END_NET_OPERA |
| _PRO | float | 终止经营净利润<br><br>EXT_INSUR_CONT |
| _RSRV | float | 提取保险责任准备<br>金<br><br>EXT_UNEARNED_ |
| PREM_RES | float | 提取未到期责任准<br>备金 |
| FIN_EXP_INT_EXP | float | 财务费用:利息费<br>用 |
| FIN_EXP_INT_INC | float | 财务费用:利息收<br>入 |
| GAIN_DISPOSAL_ | ASSETS | float<br>资产处置收益<br><br>HANDLING_CHRG |
| _COMM_FEE | float | 手续费及佣金收入<br><br>INCL_INC_INV_JV |
| _ENTP | float | 其中:对联营企业<br>和合营企业的投资<br>收益 |
| INCL_LESS_LOSS_ | float | 其中:减:非流动资<br><br><br>DISP_NCUR_ASSE<br>T<br>产处置净损失<br>INCL_REINSUR_P |
| REM_INC | float | 其中:分保费收入 |
| INCOME_TAX | float | 所得税 |
| INSUR_EXP | float | 保险业务支出 |
| INSUR_PREM | float | 已赚保费 |
| INTEREST_INC | float | 利息收入 |
| IS_CALCULATION | float | 是否计算报表 |
| LESS_ADMIN_EXP | float | 减:管理费用<br><br>LESS_AMORT_CO |
| MPEN_EXP | float | 减:摊回赔付支出<br><br>LESS_AMORT_INS |
| UR_CONT_RSRV | float | 减:摊回保险责任<br>准备金<br><br>LESS_AMORT_REI |
| NSUR_EXP | float | 减:摊回分保费用<br><br>LESS_ASSETS_IMP |
| AIR_LOSS | float | 减:资产减值损失 |
| LESS_BUS_TAX_S | URCHARGE | float<br>减:营业税金及附<br>加 |
| LESS_FIN_EXP | float | 减:财务费用<br><br>LESS_HANDLING_<br>CHRG_COMM_FE |
| E | float | 减:手续费及佣金<br>支出 |
| LESS_INTEREST_E | XP | float<br>减:利息支出<br><br>LESS_NON_OPER |
| A_EXP | float | 减:营业外支出<br><br>LESS_OPERA_COS |
| T | float | 减:营业成本 |
| LESS_REINSUR_P | REM | float<br>减:分出保费 |
| LESS_SELLING_E | XP | float<br>减:销售费用 |
| MARKET_CODE | str | 证券代码 |
| MIN_INT_INC | float | 少数股东损益<br><br>NET_EXPOSURE_ |
| HEDGING_GAIN | float | 净敞口套期收益<br><br>NET_HANDLING_<br>CHRG_COMM_FE |
| E | float | 手续费及佣金净收<br>入<br><br>NET_INC_EC_ASS |
| ET_MGMT_BUS | float | 受托客户资产管理<br>业务净收入<br><br>NET_INC_SEC_BR |
| OK_BUS | float | 代理买卖证券业务<br>净收入<br><br>NET_INC_SEC_UW |
| _BUS | float | 证券承销业务净收<br>入 |
| NET_INTEREST_I | NC | float<br>利息净收入<br><br>NET_PRO_AFTER_ |
| DED_NR_GL | float | 扣除非经常性损益<br>后净利润（扣除少<br>数股东损益）<br><br>NET_PRO_AFTER_ |
| DED_NR_GL_COR | float | 扣除非经常性损益<br>后的净利润(财务<br>重要指标(更正前))<br><br>NET_PRO_EXCL_ |
| MIN_INT_INC | float | 净利润(不含少数<br>股东损益)<br><br>NET_PRO_INCL_M |
| IN_INT_INC | float | 净利润(含少数股<br>东损益)<br><br>NET_PRO_UNDER |
| _INT_ACC_STA | float | 国际会计准则净利<br>润 |
| OPERA_EXP | float | 营业支出 |
| OPERA_PROFIT | float | 营业利润 |
| OPERA_REV | float | 营业收入<br><br>OTH_ASSETS_IMP |
| AIR_LOSS | float | 其他资产减值损失 |
| OTH_BUS_COST | float | 其他业务成本 |
| OTH_BUS_INC | float | 其他业务收入<br><br><br>OTH_COMPRE_IN |
| C | float | 其他综合收益 |
| OTH_INCOME | float | 其他收益<br><br>OTH_NET_OPERA |
| _INC | float | 其他经营净收益<br><br>PLUS_NET_FX_IN |
| C | float | 加:汇兑净收益<br><br>PLUS_NET_GAIN_ |
| CHG_FV | float | 加:公允价值变动<br>净收益 |
| PLUS_NET_INV_I | NC | float<br>加:投资净收益<br><br>PLUS_NON_OPER |
| A_REV | float | 加:营业外收入<br><br>PLUS_OTH_NET_B |
| US_INC | float | 加:其他业务净收<br>益<br><br>PREFERRED_SHA |
| RE_DIV_PAYABLE | float | 应付优先股股利 |
| PREM_BUS_INC | float | 保费业务收入 |
| RD_EXP | float | 研发费用 |
| REINSURANCE_E | XP | float<br>分保费用 |
| REPORTING_PERI | OD | str<br>报告期 |
| SECURITY_NAME | str | 证券简称<br><br>SPE_BAL_NET_PR |
| O_MARG | float | 净利润差额(特殊<br>报表科目)<br><br>SPE_BAL_OPERA_ |
| PRO_MARG | float | 营业利润差额(特<br>殊报表科目)<br><br>SPE_BAL_TOT_OP |
| ERA_COST_DIF | float | 营业总成本差额<br>(特殊报表科目)<br><br>SPE_BAL_TOT_OP |
| ERA_INC_DIF | float | 营业总收入差额<br>(特殊报表科目)<br><br>SPE_BAL_TOT_PR |
| O_MARG | float | 利润总额差额(特<br>殊报表科目)<br><br><br>SPE_TOT_OPERA_ |
| COST_DIF_STATE | str | 营业总成本差额说<br>明(特殊报表科目)<br><br>SPE_TOT_OPERA_ |
| INC_DIF_STATE | str | 营业总收入差额说<br>明(特殊报表科目) |
| SURR_VALUE | float | 退保金<br><br>TOT_BAL_NET_PR |
| O_MARG | float | 净利润差额(合计<br>平衡项目)<br><br>TOT_BAL_OPERA |
| _PRO_MARG | float | 营业利润差额(合<br>计平衡项目)<br><br>TOT_BAL_TOT_PR |
| O_MARG | float | 利润总额差额(合<br>计平衡项目)<br><br>TOT_COMPEN_EX |
| P | float | 赔付总支出<br><br>TOT_COMPRE_IN |
| C | float | 综合收益总额<br><br>TOT_COMPRE_IN |
| C_MIN_SHARE | float | 综合收益总额(少<br>数股东)<br><br>TOT_COMPRE_IN |
| C_PARENT_COMP | float | 综合收益总额(母<br>公司)<br><br>TOT_OPERA_COS |
| T | float | 营业总成本 |
| TOT_OPERA_COS | T2 | float<br>营业总成本2 |
| TOT_OPERA_REV | float | 营业总收入 |
| TOTAL_PROFIT | float | 利润总额<br><br>TRANSFER_HOUSI |
| NG_REVO_FUNDS | float | 住房周转金转入 |
| TRANSFER_OTHE | RS | float<br>其他转入<br><br>TRANSFER_SURP |
| LUS_RESERVE | float | 盈余公积转入<br><br>UNCONFIRMED_I |
| NV_LOSS | float | 未确认投资损失 |
| WITHDRAW_ANY | float | 提取任意盈余公积<br><br><br>_SURPLUS_RESV<br>金<br>WITHDRAW_ENT_ |
| DEVELOP_FUND | float | 提取企业发展基金<br><br>WITHDRAW_LEG_ |
| PUB_WEL_FUND | float | 提取法定公益金 |
| WITHDRAW_LEG_ | SURPLUS | float<br>提取法定盈余公积<br><br>WITHDRAW_RESV |
| _FUND | float | 提取储备基金 |

#### 3.5.5.4 业绩快报

函数接口：get_profit_express
功能描述：获取指定股票列表的上市公司的业绩快报数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 报告期，本地数据缓存方案 |
| end_date | int | 否 | 报告期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| profit_express | dataframe | column 为profit_express 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,

                                             end_date=today)
profit_express = info_data_object.get_profit_express (all_code_list)
```

profit_express 的字段说明：
参数
 数据类型
字段说明
备注
MARKET_CODE
str
证券代码

REPORTING_PERI
OD
str
报告期
报告内容记录的截止时间点，报
告成果的时期
ANN_DATE
str
公告日期
公告发布当天的日期；有多个阶
段的事件，首次披露该事件的日
期
ACTUAL_ANN_D
ATE
str
实际公告日
期
实际数据来源公告的日期；更正
发生公告的日期
TOTAL_ASSETS
float64
总资产(元)
指经济实体拥有或控制的能带来
经济利益的全部资产
NET_PRO_EXCL_
MIN_INT_INC
float64
净利润(元)
企业合并净利润中归属于母公司
股东所有的那部分利润
TOT_OPERA_REV
float64
营业总收入
(元)
企业从事销售商品、提供劳务和
让渡资产使用权等日常业务过程
形成的经济利益的总流入
TOTAL_PROFIT
float64
利润总额
(元)
企业一定时期内的纯收入扣除应
交纳后的余额
OPERA_PROFIT
float64
营业利润
(元)
企业在其全部销售业务中实现的
利润
EPS_BASIC
float64
每股收益-
基本(元)
企业按照属于普通股股东的当期
净利润，除以发行在外普通股的
加权平均数计算得到的每股收益
TOT_SHARE_EQU
_EXCL_MIN_INT
float64
股东权益合
计( 不含少
数股东权
益)(元)
公司集团的所有者权益中归属于
母公司所有者权益的部分
IS_AUDIT
float64
是否审计
1:是 0：否
ROE_WEIGHTED
float64
净资产收益
率-加权(%)
经营期间净资产赚取利润的结果
的一个动态指标，反应企业净资
产创造利润的能力
LAST_YEAR_REV
ISED_NET_PRO
float64
去年同期修
正后净利润
元

PERFORMANCE_
SUMMARY
str
业绩简要说
明
针对业绩快报的简单说明
NET_ASSET_PS
float64
每股净资产
元
MEMO
str
备注
附加的注解说明
YOY_GR_GROSS_
PRO
float64
同比增长率:
营业利润
%
YOY_GR_GROSS_
REV
float64
同比增长率:
营业总收入
%
YOY_GR_NET_PR
OFIT_PARENT
float64
同比增长率:
归属母公司
股东的净利
润
%
YOY_GR_TOT_PR
O
float64
同比增长率:
利润总额
%
YOY_ID_WAROE
float64
同比增减:加
权平均净资
产收益率
%
YOY_GR_EPS_BA
SIC
float64
同比增长率:
基本每股收
益
%
GROWTH_RATE_
EQUITY
float64
比年初增长
率:归属母公
司的股东权
益
%
GROWTH_RATE_
ASSETS
float64
比年初增长
率:总资产
%
GROWTH_RATE_
NAPS
float64
比年初增长
率:归属于母
公司股东的
每股净资产
%
LAST_YEAR_TOT
_OPERA_REV
float64
去年同期营
业总收入
元
LAST_YEAR_TOT
AL_PROFIT
float64
去年同期利
润总额
元
LAST_YEAR_OPE
RA_PRO
float64
去年同期营
业利润
元

LAST_YEAR_EPS
_DILUTED
float64
去年同期每
股收益
元
LAST_YEAR_NET
_PROFIT
float64
去年同期净
利润
元
INITIAL_NET_AS
SET_PS
float64
期初每股净
资产
元
INITIAL_NET_AS
SETS
float64
期初净资产
元

#### 3.5.5.5 业绩预告

函数接口：get_profit_notice
功能描述：获取指定股票列表的上市公司的业绩预告数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 报告期，本地数据缓存方案 |
| end_date | int | 否 | 报告期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| profit_notice | dataframe | column 为profit_notice 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
profit_notice = info_data_object.get_profit_notice (all_code_list)

```

profit_notice 的字段说明：
参数
 数据类型
字段说明
备注
MARKET_CODE
str
证券代码

SECURITY_NAME
str
证券简称

P_TYPECODE
str
业绩预告类型代
码
1：不确定
2：略减
3：略增
4：扭亏
5：其他
6：首亏
7：续亏
8：续盈
9：预减
10：预增
11：持平
REPORTING_PERI
OD
str
报告期
分为年度、半年度、季度
ANN_DATE
str
公告日期
公告发布当天的日期
P_CHANGE_MAX
float64
预告净利润变动
幅度上限（%）
对于净利润金额同比变动幅
度预计的最高值
P_CHANGE_MIN
float64
预告净利润变动
幅度下限（%）
对于净利润金额同比变动幅
度预计的最低值
NET_PROFIT_MA
X
float64
预告净利润上限
（万元）
对于净利润金额预计的最高
值
NET_PROFIT_MIN
float64
预告净利润下限
（万元）
对于净利润金额预计的最低
值
FIRST_ANN_DAT
E
str
首次公告日
首次披露本报告期业绩预告
内容的公告日期
P_NUMBER
float64
公布次数
同一报告期的业绩预告公告
的披露次数
P_REASON
str
业绩变动原因

P_SUMMARY
str
业绩预告摘要

P_NET_PARENT_F
IRM
float64
上年同期归母净
利润
业绩预告中直接公布的上年
同期归母净利润
REPORT_TYPE
str
报告期名称
参看报告期名称

### 3.5.6 股东股本数据

#### 3.5.6.1 十大股东数据

函数接口：get_share_holder
功能描述：获取指定股票列表的上市公司的十大股东数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 到期日期，本地数据缓存方案 |
| end_date | int | 否 | 到期日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| share_holder | dataframe | column 为share_holder 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
share_holder = info_data_object.get_share_holder (all_code_list)
```

share_holder 的字段说明：
参数
 数据类
型
字段说明
备注
ANN_DATE
str
公告日期,

MARKET_CODE
str
证券代码

HOLDER_ENDDATE
str
到期日期

HOLDER_TYPE
int
股东类别
10:十大股东

20:流通股前十大股东
QTY_NUM
int
持股量序号

HOLDER_NAME
str
股东名称

HOLDER_HOLDER_C
ATEGORY
int
股东性质
1：个人 2：公司
HOLDER_QUANTITY,
float
持股数（股）

HOLDER_PCT
float
持股比例
（%）,

HOLDER_SHARECAT
EGORYNAME
str
股份类型
当HOLDER_TYPE 为20:流通股
前十大股东时，全部为‘A Float
Holder’
FLOAT_QTY
float
流通股数量

#### 3.5.6.2 股东户数

函数接口：get_holder_num
功能描述：获取指定股票列表的上市公司的股东户数数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 股东户数统计的截止日期，本地数据缓存<br>方案 |
| end_date | int | 否 | 股东户数统计的截止日期，本地数据缓存<br>方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| holder_num | dataframe | column 为holder_num 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()

base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
holder_num = info_data_object.get_holder_num (all_code_list)
```

holder_num 的字段说明：
参数
 数据类
型
字段说明
MARKET_CODE
string
证券代码
ANN_DT
string
公告日期
HOLDER_ENDDATE
string
股东户数统计的截止日期
HOLDER_TOTAL_NUM
float
A 股、B 股、H 股、境外股的总户数
HOLDER_NUM
float
A 股股东户数

#### 3.5.6.3 股本结构

函数接口：get_equity_structure
功能描述：获取指定股票列表的上市公司的股本结构数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 变动日期，本地数据缓存方案 |
| end_date | int | 否 | 变动日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| equity_structu | re | dataframe<br>column 为equity_structuree 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()

calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
equity_structure = info_data_object.get_equity_structure (all_code_list)
```

equity_structure 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | string<br>证券代码 |
| ANN_DATE | string | 公告日期 |
| CHANGE_DATE | string | 变动日期 |
注：股票分红送转股时的红
股上市日;股票增发时的新股
上市日
SHARE_CHANGE_REA
SON_STR
string
股本变动原因描述

EX_CHANGE_DATE
string
除权日期
股票分红送转股时的除权日;
股票增发时的登记日
CURRENT_SIGN
int
最新标志
1:是0:否
IS_VALID
int
是否有效
用来区分除权日相同时，是
否为公司公告公布的最新股
份数
1:是0:否
TOT_SHARE
float
总股本(万股)

FLOAT_SHARE
float
流通股(万股)

FLOAT_A_SHARE
float
流通A 股(万股)

FLOAT_B_SHARE
float
流通B 股(万股)

FLOAT_HK_SHARE
float
香港流通股(万股)

FLOAT_OS_SHARE
float
海外流通股(万股)

TOT_TRADABLE_SHA
RE
float
流通股合计

RTD_A_SHARE_INST
float
限售A 股(其他内资
持股:机构配售股)

RTD_A_SHARE_DOME
SNP
float
限售A 股(其他内资
持股:境内自然人持
股)

RTD_SHARE_SENIOR
float
限售股份(高管持
股)(万股)

RTD_A_SHARE_FOREI
GN
float
限售A 股(外资持
股)

RTD_A_SHARE_FORJ
UR
float
限售A 股(境外法人
持股)

RTD_A_SHARE_FORN
P
float
限售A 股(境外自然
人持股)

RESTRICTED_B_SHAR
float
限售B 股(万股)

E
OTHER_RTD_SHARE
float
其他限售股

NON_TRADABLE_SH
ARE
float
非流通股

NTRD_SHARE_STATE_
PCT
float
非流通股(国有股)

NTRD_SHARE_STATE
float
非流通股(国家股)

NTRD_SHARE_STATEJ
UR
float
非流通股(国有法人
股)

NTRD_SHARE_DOME
SJUR
float
非流通股(境内法人
股)

NTRD_SHARE_DOME
S_INITIATOR
float
非流通股(境内法人
股:境内发起人股)

NTRD_SHARE_IPOJUR
IS
float
非流通股(境内法人
股:募集法人股)

NTRD_SHARE_GENJU
RIS
float
非流通股(境内法人
股:一般法人股)

NTRD_SHARE_STRA_I
NVESTOR
float
非流通股(境内法人
股: 战略投资者持
股)

NTRD_SHARE_FUND
float
非流通股(境内法人
股:基金持股)

NTRD_SHARE_NAT
float
非流通股(自然人
股)

TRAN_SHARE
float
转配股(万股)

FLOAT_SHARE_SENIO
R
float
流通股(高管持股)

SHARE_INEMP
float
内部职工股(万股)

PREFERRED_SHARE
float
优先股(万股)

NTRD_SHARE_NLIST_
FRGN
float
非流通股(非上市外
资股)

STAQ_SHARE
float
STAQ 股(万股)

NET_SHARE
float
NET 股(万股)

SHARE_CHANGE_REA
SON
string
股本变动原因

TOT_A_SHARE
float
A 股合计

TOT_B_SHARE
float
B 股合计

OTCA_SHARE
float
三板A 股

OTCB_SHARE
float
三板B 股

TOT_OTC_SHARE
float
三板合计

SHARE_HK
float
香港上市股

PRE_NON_TRADABLE
float
股改前非流通股

_SHARE
RESTRICTED_A_SHAR
E
float
限售A 股(万股)

RTD_A_SHARE_STATE
float
限售A 股(国家持
股)

RTD_A_SHARE_STATE
JUR
float
限售A 股(国有法人
持股)

RTD_A_SHARE_OTHE
R_DOMES
float
限售A 股(其他内资
持股)

RTD_A_SHARE_OTHE
R_DOMESJUR
float
限售A 股(其他内资
持股: 境内法人持
股)

TOT_RESTRICTED_SH
ARE
float
限售股合计

#### 3.5.6.4 股权冻结/质押

函数接口：get_equity_pledge_freeze
功能描述：获取指定股票列表的上市公司的股权冻结/质押数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 公告日期，本地数据缓存方案 |
| end_date | int | 否 | 公告日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| equity_pledge | _freeze | dict<br>key：code<br>value:dataframe<br>column 为equity_pledge_freeze 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()

base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
equity_pledge_freeze = info_data_object.get_equity_pledge_freeze (all_code_list)
```

equity_pledge_freeze 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | string<br>证券代码 |
| ANN_DATE | string | 公告日期 |
| HOLDER_NAME | string | 股东名称 |
| HOLDER_TYPE_C | ODE | int<br>股东类型代码<br>2:公司3:个人<br>TOTAL_HOLDING |
| _SHR" | float | 持股总数（万股）<br><br>TOTAL_HOLDING |
| _SHR_RATIO | float | 持股总数占公司<br>总股本比例 |
| FRO_SHARES | float | 本次冻结/质押股<br>数<br><br>FRO_SHR_TO_TO |
| TAL_HOLDING_R | ATIO | float<br><br>本次冻结/质押占<br>所持股比例<br><br>FRO_SHR_TO_TO |
| TAL_RATIO | float | 本次冻结/质押占<br>总股本比例 |
| TOTAL_PLEDGE_ | SHR | float<br>累计冻结/质押股<br>数<br><br>IS_EQUITY_PLED |
| GE_REPO | int | 是否股权质押回<br>购<br>1:是0:否 |
| BEGIN_DATE | string | 冻结/质押起始日 |
| END_DATE | string | 解冻/解押日期 |
| IS_DISFROZEN | int | 是否质押或解冻<br>1:是0:否 |
| FROZEN_INSTITU | TION | string<br>执行冻结机构/质<br>权方 |
| DISFROZEN_TIME | string | 解压或解冻日期 |
| SHR_CATEGORY_ | int | 股份性质类别代<br>1:法人股2:个人股3:国有<br><br>CODE<br>码<br>股4:国有股,法人股5:流通<br>股6:流通股,限售流通股7:<br>外资股8:限售流通股9:优<br>先<br>股 |
| FREEZE_TYPE | int | 冻结/质押类型<br>1:质押2:司法3:质押式回<br>购 |

#### 3.5.6.5 限售股解禁

函数接口：get_equity_restricted
功能描述：获取指定股票列表的上市公司的限售股解禁数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 解禁日期，本地数据缓存方案 |
| end_date | int | 否 | 解禁日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| equity_restrict | ed | dict<br>key：code<br>value:dataframe<br>column 为equity_restricted 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
equity_restricted = info_data_object.get_equity_restricted (all_code_list)
```

equity_restricted 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | string<br>证券代码 |
| LIST_DATE | string | 解禁日期 |
| SHARE_RATIO | float | 解禁股占总股本比(%) |
| SHARE_LST_TYPE_NAME | string | 解禁股份类型名称 |
| SHARE_LST | int | 解禁数量（股） |
| SHARE_LST_IS_ANN | int | 上市数量是否公布值<br>0：否，为预测<br>值 1: 是, 为实<br>际公布值 |
| CLOSE_PRICE | float | 前日收盘价（元） |
| SHARE_LST_MARKET_VA | LUE | float<br>解禁市值（元）<br>SHARE_LST*<br>CLOSE_PRICE |

### 3.5.7 股东权益数据

#### 3.5.7.1 分红数据

函数接口：get_dividend
功能描述：获取指定股票列表的上市公司的分红数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 公告日期，本地数据缓存方案 |
| end_date | int | 否 | 公告日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| dividend | dataframe | column 为dividend 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
dividend = info_data_object.get_dividend(all_code_list)
```

dividend 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | string<br>证券代码 |
| DIV_PROGRESS | string | 方案进度<br>参看股票分红进度代<br>码表 |
| DVD_PER_SHARE_STK | float | 每股送转<br><br>DVD_PER_SHARE_PRE_T |
| AX_CASH | float | 每股派息(税前)(元)<br><br>DVD_PER_SHARE_AFTE |
| R_TAX_CASH | float | 每股派息(税后)(元) |
| DATE_EQY_RECORD | string | 股权登记日 |
| DATE_EX | string | 除权除息日 |
| DATE_DVD_PAYOUT | string | 派息日 |
| LISTINGDATE_OF_DVD_ | SHR | string<br>红股上市日 |
| DIV_PRELANDATE | string | 预案公告日<br>董事会预案公告日期 |
| DIV_SMTGDATE | string | 股东大会公告日 |
| DATE_DVD_ANN | string | 分红实施公告日 |
| DIV_BASEDATE | string | 基准日期 |
| DIV_BASESHARE | float | 基准股本(万股) |
| CURRENCY_CODE | string | 货币代码 |
| ANN_DATE | string | 公告日期 |
| IS_CHANGED | int | 方案是否变更<br>1：有变更过0：未变<br>更 |
| REPORT_PERIOD | string | 分红年度 |
| DIV_CHANGE | string | 方案变更说明 |
| DIV_BONUSRATE | float | 每股送股比例 |
| DIV_CONVERSEDRATE | float | 每股转增比例 |
| REMARK | string | 备注 |
| DIV_PREANN_DATE | string | 预案预披露公告日<br>股东提议的公告日期 |
| DIV_TARGET | string | 分红对象 |

#### 3.5.7.2 配股数据

函数接口：get_right_issue
功能描述：获取指定股票列表的上市公司的配股数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 公告日期，本地数据缓存方案 |
| end_date | int | 否 | 公告日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| right_issue | dataframe | column 为right_issue 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
right_issue = info_data_object.get_right_issue(all_code_list)
```

right_issue 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | MARKET_CODE | string<br>证券代码 |
| PROGRESS | int | 方案进度<br>参看股票配股进度代 |
| 码表 | PRICE | double<br>配股价格(元) |
| RATIO | double | 配股比例 |
| AMT_PLAN | double | 配股计划数量(万股) |
| AMT_REAL | double | 配股实际数量(万股) |
| COLLECTION_FUND | double | 募集资金(元) |
| SHAREB_REG_DATE | string | 股权登记日 |
| EX_DIVIDEND_DATE | string | 除权日 |
| LISTED_DATE | string | 配股上市日 |
| PAY_START_DATE | string | 缴款起始日 |
| PAY_END_DATE | string | 缴款终止日 |
| PREPLAN_DATE | string | 预案公告日 |
| SMTG_ANN_DATE | string | 股东大会公告日 |
| PASS_DATE | string | 发审委通过公告日 |
| APPROVED_DATE | string | 证监会核准公告日 |
| EXECUTE_DATE | string | 配股实施公告日 |
| RESULT_DATE | string | 配股结果公告日 |
| LIST_ANN_DATE | string | 上市公告日 |
| GUARANTOR | string | 基准年度 |
| GUARTYPE | double | 基准股本(万股) |
| RIGHTSISSUE_CODE | string | 配售代码 |
| ANN_DATE | string | 公告日期 |
| RIGHTSISSUE_YEAR | string | 配股年度 |
| RIGHTSISSUE_DESC | string | 配股说明 |
| RIGHTSISSUE_NAME | string | 配股简称<br><br>RATIO_DENOMINATO |
| R | double | 配股比例分母 |
| RATIO_MOLECULAR | double | 配股比例分子 |
| SUBS_METHOD | string | 认购方式 |
| EXPECTED_FUND_RA | ISING | double<br>预计募集资金(元) |

### 3.5.8 融资融券数据

#### 3.5.8.1 融资融券成交汇总

函数接口：get_margin_summary
功能描述：获取指定日期的上市公司的融资融券成交汇总数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日，本地数据缓存方案 |
| end_date | int | 否 | 交易日，本地数据缓存方案 |
输出参数：

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| margin_summ | ary | dataframe<br>column 为margin_summary 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
margin_summary = info_data_object.get_margin_summary()
```

margin_summary 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| TRADE_DATE | string | 交易日期 |
| SUM_BORROW_MONEY_BALANCE | float | 融资余额(元) |
| SUM_PURCH_WITH_BORROW_MONEY | float | 融资买入额(元)<br>SUM_REPAYMENT_OF_BORROW_MONE |
| Y | float | 融资偿还额(元) |
| SUM_SEC_LENDING_BALANCE | float | 融券余额(元) |
| SUM_SALES_OF_BORROWED_SEC | int | 融券卖出量(股,份,手) |
| SUM_MARGIN_TRADE_BALANCE | float | 融资融券余额(元) |

#### 3.5.8.2 融资融券交易明细

函数接口：get_margin_detail
功能描述：获取指定股票列表的上市公司的融资融券交易明细数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日，本地数据缓存方案 |
| end_date | int | 否 | 交易日，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| margin_detail | dict | key：code<br><br>value:dataframe<br>column 为margin_detail 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
margin_detail = info_data_object.get_margin_detail(all_code_list)
```

margin_detail 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| TRADE_DATE | string | 交易日期 |
| BORROW_MONEY_BALANCE" | float | 融资余额(元) |
| PURCH_WITH_BORROW_MON | EY | float<br>融资买入额(元) |
| REPAYMENT_OF_BORROW_MO | NEY | float<br>融资偿还额(元) |
| SEC_LENDING_BALANCE | float | 融券余额(元) |
| SALES_OF_BORROWED_SEC | int | 融券卖出量(股,份,手)<br>REPAYMENT_OF_BORROW_SE |
| C | int | 融券偿还量(股,份,手) |
| SEC_LENDING_BALANCE_VOL | int | 融券余量(股,份,手) |
| MARGIN_TRADE_BALANCE | float | 融资融券余额(元) |

### 3.5.9 交易异动数据

#### 3.5.9.1 龙虎榜

函数接口：get_long_hu_bang
功能描述：获取指定股票列表的上市公司的龙虎榜数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日，本地数据缓存方案 |
| end_date | int | 否 | 交易日，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| long_hu_bang | dataframe | column 为long_hu_bang 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
long_hu_bang = info_data_object.get_long_hu_bang(all_code_list)
```

long_hu_bang 的字段说明：
参数
 数据类型
字段说明
备注
MARKET_CODE
string
证券代码

TRADE_DATE
string
交易日期

SECURITY_NAME
string
证券名称

REASON_TYPE
string
上榜原因类
型

REASON_TYPE_NAME
string
上榜原因

CHANGE_RANGE
float
涨跌幅（%）

TRADER_NAME
string
营业部名称

BUY_AMOUNT
float
买入金额
（元）

SELL_AMOUNT
float
卖出金额
（元）

FLOW_MARK
int
买卖表示
1 表示买入，2 表示卖出
TOTAL_AMOUNT
float
实际交易金
额（元）

TOTAL_VOLUME
float
实际交易量
（万股）

#### 3.5.9.2 大宗交易

函数接口：get_block_trading
功能描述：获取指定股票列表的大宗交易数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深A 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日，本地数据缓存方案 |
| end_date | int | 否 | 交易日，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| block_trading | dataframe | column 为block_trading 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()

today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,
                                             end_date=today)
block_trading = info_data_object. block_trading (all_code_list)
```

block_trading 的字段说明：
参数
 数据类型
字段说明
MARKET_CODE
string
证券代码
TRADE_DATE
string
交易日期
B_SHARE_PRICE
float
成交价（元）
B_SHARE_VOLUME
float
成交量（万股）
B_FREQUENCY
int
笔数
BLOCK_AVG_VOLUME
float
每笔成交数量（万股份）
B_SHARE_AMOUNT
float
成交金额（万元）
B_BUYER_NAME
string
买方营业部名称
B_SELLER_NAME
string
卖方营业部名称

### 3.5.10 期权数据

#### 3.5.10.1 期权基本资料

函数接口：get_option_basic_info

功能描述：获取指定期权的基本资料（沪深交易所的ETF 期权）
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 期权的的代码列表，可见示<br>例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| option_basic_ | info | dataframe<br>column 为option_basic_info 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')
```

hist_code_list
=

```python
base_data_object.get_hist_code_list(security_type='EXTRA_ETF_OP'', start_date=20130101,
                         end_date=today)
option_basic_info =info_data_object.get_option_basic_info(code_list, is_local=False)
```

option_basic_info 的字段说明：
参数
 数据类型
字段说明
备注
CONTRACT_FULL_NAME
string
合约全称

CONTRACT_TYPE
string
合约类别
C 表示认购
P 表示认沽
DELIVERY_MONTH
string
交割月份

EXPIRY_DATE
string
到期日

EXERCISE_PRICE
float
行权价格

EXERCISE_END_DATE
string
最后行权日

START_TRADE_DATE
string
开始交易日

LISTING_REF_PRICE
float
挂牌基准价

LAST_TRADE_DATE
string
最后交易日

EXCHANGE_CODE
string
合约交易所代码

DELIVERY_DATE
string
最后交割日

CONTRACT_UNIT
Int
合约单位

IS_TRADE
string
是否交易

EXCHANGE_SHORT_NAME
string
合约交易所简称

CONTRACT_ADJUST_FLAG
string
合约调整标志

MARKET_CODE
string
合约代码

#### 3.5.10.2 期权标准合约属性

函数接口：get_option_std_ctr_specs
功能描述：获取指定期权标准合约属性（沪深交易所的ETF 期权）
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 的的代码列表，目前包含 |

## 159919. SZ

## 159915. SZ

## 159922. SZ

## 159901. SZ

## 510300. SH

## 588000. SH

## 588080. SH

## 510050. SH

## 510500. SH

local_path
str
是
本地存储数据的路径，需绝对路径，格式
类似“
'D://AmazingData_local_data//'
”
is_local
bool
否
默认为True，本地数据缓存方案

输出参数：

| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| option_std_ctr | _specs | dataframe<br>column 为option_std_ctr_specs 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
option_std_ctr_specs =info_data_object.get_option_std_ctr_specs(['510050.SH'], is_local=False)
```

option_std_ctr_specs 的字段说明：
参数
 数据类型
字段说明
备注
EXERCISE_DATE
string
期权行权日

CONTRACT_UNIT
int
合约单位

POSITION_DECLARE_MIN
string
头寸申报下限

QUOTE_CURRENCY_UNIT
string
报价货币单位

LAST_TRADING_DATE
string
最后交易日

POSITION_LIMIT
string
头寸限制

DELIST_DATE
string
退市日期

NOTIONAL_VALUE
string
立约价值

EXERCISE_METHOD
string
行权方式

DELIVERY_METHOD
string
交割方式

SETTLEMENT_MONTH
string
合约结算月份

TRADING_FEE
string
交易费用

EXCHANGE_NAME
string
交易所名称

OPTION_EN_NAME
string
期权英文名称

CONTRACT_VALUE
float
合约价值

IS_SIMULATION
int
是否仿真合约
0 否 1 是
CONTRACT_UNIT_DIMENSI
ON
string
合约单位量纲

OPTION_STRIKE_PRICE
string
期权行权价

IS_SIMULATION_TRADE
string
是否仿真交易
0 否 1 是

LISTED_DATE
string
上市日期

OPTION_NAME
string
期权名称

PREMIUM
string
期权金

OPTION_TYPE
string
期权类型
ETF 期权等
TRADING_HOURS_DESC
string
交易时间说明

FINAL_SETTLEMENT_DATE
string
最后结算日

FINAL_SETTLEMENT_PRICE
string
最后结算价

MIN_PRICE_UNIT
string
最小报价单位

MARKET_CODE
string
市场代码

CONTRACT_MULTIPLIER
int
合约乘数

#### 3.5.10.3 期权月合约属性变动

函数接口：get_option_mon_ctr_specs

功能描述：获取指定期权月合约属性变动（沪深交易所的ETF 期权）
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 期权的的代码列表，可见示<br>例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| block_trading | dataframe | column 为block_trading 的字段<br>index 为序号（无意义） |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')
```

hist_code_list
=

```python
base_data_object.get_hist_code_list(security_type='EXTRA_ETF_OP'', start_date=20130101,
                         end_date=today)
option_mon_ctr_specs =info_data_object.get_option_mon_ctr_specs(code_list, is_local=False)
```

option_mon_ctr_specs 的字段说明：
参数
 数据类型
字段说明
CODE_OLD
string
原交易代码
CHANGE_DATE
string
调整日期
MARKET_CODE
string
市场代码
NAME_NEW
string
新合约简称
EXERCISE_PRICE_NEW
float
新行权价(元)
NAME_OLD
string
原合约简称
CODE_NEW
string
新交易代码
EXERCISE_PRICE_OLD
float
原行权价(元)
UNIT_OLD
float
原合约单位(股)

UNIT_NEW
float
新合约单位(股)
CHANGE_REASON
string
调整原因

### 3.5.11 ETF 数据

#### 3.5.11.1 ETF 每日最新申赎数据

函数接口： get_etf_pcf
功能描述：获取指定ETF 的申赎和成分股数据（沪深交易所的ETF）
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 的的代码列表，可见示例 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| etf_pcf_info | dataframe | column 为etf_pcf_info 的字段<br>index 为ETF 代码<br>etf_pcf_consti |
| tuent | dict | 字典的key：ETF 代码<br>字典的value：dataframe，<br>column 为etf_pcf_constituent 的字段，<br>index 为序号 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_hist_code_list(security_type='EXTRA_ETF')
```

etf_pcf_info, etf_pcf_constituent = base_data_object.get_etf_pcf(code_list)
etf_pcf_info 的字段说明：
参数
 数据类型
字段说明
备注
creation_redemption_unit
int
每个篮子对应的
ETF 份数

max_cash_ratio
string
最大现金替代比
例

publish
string
是否发布IOPV

```python
Y=是,N=否
```

creation
string
是否允许申购

```python
Y=是,N=否(仅深圳
```

有效)
redemption
string
是否允许赎回

```python
Y=是,N=否(仅深圳

```

有效)
creation_redemption_switch
string
申购赎回切换
(仅上海有效,0-不
允许申购/赎回,1-
申购和赎回皆允许,
2-仅允许申购,3-仅
允许赎回)
record_num
int
深市成份证券数
目

total_record_num
int
所有成份证券数
量

estimate_cash_component
int
预估现金差额

trading_day
int
当前交易日
(格式:YYYYMMD
D)
pre_trading_day
int
前一交易日
(格式:YYYYMMD
D)
cash_component
int
前一日现金差额

nav_per_cu
int
前一日最小申赎
单位净值

nav
int
前一日基金份额
净值

symbol
string
基金名称
仅深圳有效
fund_management_company
string
基金公司名称
仅深圳有效
underlying_security_id
string
拟合指数代码
仅深圳有效
underlying_security_id_source
string
拟合指数市场
参考Market，仅深
圳有效
dividend_per_cu
int
红利金额

creation_limit
int
累计申购总额限
制
为0 表示没有限制
(仅深圳有效)
redemption_limit
int
累计赎回总额限
制
0 表示没有限制(仅
深圳有效)
creation_limit_per_user
int
单个账户累计申
购总额限制
0 表示没有限制(仅
深圳有效)
redemption_limit_per_user
int
单个账户累计赎
回总额限制
0 表示没有限制(仅
深圳有效)

net_creation_limit
int
净申购总额限制
0 表示没有限制(仅
深圳有效)
net_redemption_limit
int
净赎回总额限制
0 表示没有限制(仅
深圳有效)
net_creation_limit_per_user
int
单个账户净申购
总额限制
0 表示没有限制(仅
深圳有效)
net_redemption_limit_per_user
int
单个账户净赎回
总额限制
0 表示没有限制(仅
深圳有效)

etf_pcf_constituent 的字段说明：
参数
 数据类型
字段说明
备注
underlying_symbol
string
成份证券简称

component_share
int
成份证券数量

substitute_flag
string
现金替代标志
//*_深圳现金替代
标志_        //0=
禁止现金替代(必
须有证券),1=可以
进行现金替代(先
用证券,证券不足时
差额部分用现金替
代),2=必须用现金
替代
//*_上海现金替代
标志_

//ETF 公告文件

## 1.0 版格式

//0 –沪市不可被替
代, 1 – 沪市可以被
替代, 2 – 沪市必须
被替代, 3 – 深市退
补现金替代, 4 – 深
市必须现金替代
//5 – 非沪深市场
成份证券退补现金
替代(不适用于跨
沪深港 ETF 产
品), 6 – 非沪深市
场成份证券必须现

金替代(不适用于
跨沪深港 ETF 产
品)

//ETF 公告文件

## 2.1 版格式

//0 –沪市不可被替
代, 1 – 沪市可以被
替代, 2 – 沪市必须
被替代, 3 – 深市退
补现金替代, 4 – 深
市必须现金替代
//5 – 非沪深市场
成份证券退补现金
替代(不适用于跨
沪深港 ETF 产
品), 6 – 非沪深市
场成份证券必须现
金替代(不适用于
跨沪深港 ETF 产
品)
//7 – 港市退补现
金替代(仅适用于
跨沪深港ETF 产
品),
//8 – 港市必须现
金替代(仅适用于
跨沪深港 ETF 产
品)
premium_ratio
int
溢价比例

discount_ratio
int
折价比例

creation_cash_substitute
int
申购替代金额
仅深圳有效
redemption_cash_substitute
int
赎回替代金额
仅深圳有效
substitution_cash_amount
int
替代总金额
仅上海有效
underlying_security_id
string
成份证券所属市
场ID
仅对跨市场债券
(银行间)ETF 启用

#### 3.5.11.2 ETF 基金份额

函数接口：get_fund_share
功能描述：获取指定ETF 列表的基金份额数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 变动日期，本地数据缓存方案 |
| end_date | int | 否 | 变动日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| fund_share | dict | key：code<br>value:dataframe<br>column 为fund_share 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
etf_code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')
# ETF 份额
fund_share = info_data_object.get_fund_share(etf_code_list, is_local=False)
```

fund_share 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | FUND_SHARE | float<br>基金份额(万份) |
| CHANGE_REASON | string | 份额变动原因 |
| IS_CONSOLIDATED_DATA | int | 是否合并数据<br>0：非合并数据<br>1：合并数据<br>2：合并数据，<br>但该基金代码<br>属于不实际交<br>易基金 |
| MARKET_CODE | string | 市场代码 |
| ANN_DATE | string | 公告日期 |
| TOTAL_SHARE | float | 基金总份额(万份) |
| CHANGE_DATE | string | 变动日期 |
| FLOAT_SHARE | float | 流通份额(万份) |

#### 3.5.11.3 ETF 每日收盘iopv

函数接口：get_fund_iopv
功能描述：获取指定ETF 列表的基金份额数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深ETF 的的代码列表，可见示例 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 变动日期，本地数据缓存方案 |
| end_date | int | 否 | 变动日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| fund_iopv | dict | key：code<br>value:dataframe<br>column 为fund_iopv 的字段<br>index 为序号，无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
etf_code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')
# ETF 份额
fund_iopv = info_data_object.get_fund_iopv(etf_code_list, is_local=False)
```

fund_iopv 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| PRICE_DATE | string | 日期 |
| IOPV_NAV | float | IOPV 收盘净值 |

### 3.5.12 交易所指数数据

#### 3.5.12.1 交易所指数成分股

函数接口：get_index_constituent
功能描述：获取指定交易所指数列表的成分股数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持沪深指数的的代码列表，可见示例，<br>仅支持常用指数，约600 多只，无返回数<br>据则不支持。 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，仅从本地获取，不从服务器<br>获取数据；<br>False ，仅从服务器获取，不从本地获取<br>数据；<br>因为原始数据的剔除日期会根据最新数<br>据修改，所以第一次运行is_local 需要设<br>置成 False 才会从服务器获取数据。 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| index_constit | uent | dict<br>key：code<br>value:dataframe<br>column 为index_constituent 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_INDEX_A')
index_constituent = info_data_object.get_index_constituent(code_list, is_local=False)

```

index_constituent 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | INDEX_CODE | string<br>指数代码 |
| CON_CODE | string | 成份股代码 |
| INDATE | string | 纳入日期 |
| OUTDATE | string | 剔除日期<br>未剔除时为na<br>n |
| INDEX_NAME | string | 指数名称 |

#### 3.5.12.2 交易所指数成分股日权重

函数接口：get_index_weight
功能描述：获取指定交易所指数列表的成分股日权重数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持指数列表；<br>指数代码：支持以下5 个指数<br>上证50： 000016.SH<br>沪深300： 000300.SH<br>中证500：  000905.SH<br>中证800：  000906.SH<br>中证1000： 000852.SH |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 变动日期，本地数据缓存方案 |
| end_date | int | 否 | 变动日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| index_weight | dict | key：code<br>value:dataframe<br>column 为index_weight 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad

ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
```

index_weight
=

```python
info_data_object.get_index_weight(['000016.SH',
```

'000300.SH',
'000905.SH','000906.SH','000852.SH'],

```python
is_local=False)
```

index_weight 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| INDEX_CODE | string | 指数代码 |
| CON_CODE | string | 标的代码 |
| TRADE_DATE | string | 生效日期 |
| TOTAL_SHARE | float | 总股本（股） |
| FREE_SHARE_RATIO | float | 自由流通比例（%）（归<br>档后） |
| CALC_SHARE | float | 计算用股本（股） |
| WEIGHT_FACTOR | float |  |
| 权重因子 | WEIGHT | float |
| 权重（%） | CLOSE | float<br>收盘价 |

### 3.5.13 行业指数数据

#### 3.5.13.1 行业指数基本信息

函数接口：get_industry_base_info
功能描述：获取行业指数的基本信息数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，仅从本地获取，不从服务器<br>获取数据；<br>False ，仅从服务器获取，不从本地获取<br>数据；<br>因为原始数据的剔除日期会根据最新数<br>据修改，所以第一次运行is_local 需要设<br>置成 False 才会从服务器获取数据。 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| industry_base | _info | dict<br>key：code<br>value:dataframe<br>column 为industry_base_info 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
industry_base_info = info_data_object.get_industry_base_info()
```

industry_base_info 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | INDEX_CODE | string<br>指数代码 |
| INDUSTRY_CODE | string | 行业代码 |
| LEVEL_TYPE | int | 指数类别<br>1：一级行业<br>2：二级行业<br>3：三级行业 |
| LEVEL1_NAME | string | 一级行业 |
| LEVEL2_NAME | string | 二级行业 |
| LEVEL3_NAME | string | 三级行业 |
| IS_PUB | int | 是否发布<br>1：已发布；<br>2：未发布 |
| CHANGE_REASON | string | 变动原因 |

#### 3.5.13.2 行业指数成分股

函数接口：get_industry_constituent
功能描述：获取指定行业指数列表的成分股数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持行业指数的的代码列表，可见示例，<br>仅从get_industry_base_info 取到的指数代<br>码。 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，仅从本地获取，不从服务器<br>获取数据；<br>False ，仅从服务器获取，不从本地获取<br>数据；<br>因为原始数据的剔除日期会根据最新数<br>据修改，所以第一次运行is_local 需要设<br>置成 False 才会从服务器获取数据。 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| industry_cons | tituent | dict<br>key：code<br>value:dataframe<br>column 为industry_constituent 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
industry_base_info = info_data_object.get_industry_base_info()
industry_base_list = list(industry_base_info['INDEX_CODE'])
# 行业指数成分股
industry_constituent = info_data_object.get_industry_constituent(industry_base_list, is_local=False)
```

industry_constituent 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| 备注 | INDEX_CODE | string<br>指数代码 |
| CON_CODE | string | 成份股代码 |
| INDATE | string | 纳入日期 |
| OUTDATE | string | 剔除日期<br>未剔除时为na<br>n |
| INDEX_NAME | string | 指数名称 |

#### 3.5.13.3 行业指数成分股日权重

函数接口：get_industry_weight
功能描述：获取指定行业指数列表的成分股日权重数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持行业指数的的代码列表，可见示例，<br>仅从get_industry_base_info 取到的指数代<br>码。 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日期，本地数据缓存方案 |
| end_date | int | 否 | 交易日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| industry_weig | ht | dict<br>key：code<br>value:dataframe<br>column 为industry_weight 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
industry_base_info = info_data_object.get_industry_base_info()
industry_base_list = list(industry_base_info['INDEX_CODE'])
# 行业指数日权重
industry_weight = info_data_object.get_industry_weight(industry_base_list)
```

industry_weight 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| WEIGHT | float | 权重 |
| CON_CODE | string | 成份股代码 |
| TRADE_DATE | string | 交易日期 |
| INDEX_CODE | string | 指数代码 |

#### 3.5.13.4 行业指数日行情

函数接口：get_industry_daily
功能描述：获取指定行业指数列表的日行情数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持行业指数的的代码列表，可见示例，<br>仅从get_industry_base_info 取到的指数代<br>码。 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 交易日期，本地数据缓存方案 |
| end_date | int | 否 | 交易日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| industry_daily | dict | key：code<br>value:dataframe<br>column 为industry_daily 的字段<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
industry_base_info = info_data_object.get_industry_base_info()
industry_base_list = list(industry_base_info['INDEX_CODE'])
# 行业指数日行情
industry_daily = info_data_object.get_industry_daily(industry_base_list, is_local=False)
```

industry_daily 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| OPEN | float |  |
| 开盘价 | HIGH | float |
| 最高价 | CLOSE | float |
| 收盘价 | LOW | float |
| 最低价 | AMOUNT | float<br>成交金额(元) |
| VOLUME | float |  |
| 成交量(股) | PB | float |
| 指数市净率 | PE | float<br>指数市盈率 |
| TOTAL_CAP | float | 总市值(万元) |
| A_FLOAT_CAP | float | A 股流通市值(万元) |
| INDEX_CODE | string | 指数代码 |
| PRE_CLOSE | float | 昨收盘价 |
| TRADE_DATE | string | 交易日期 |

### 3.5.14 可转债数据

#### 3.5.14.1 可转债发行

函数接口：get_kzz_issuance
功能描述：获取指定可转债列表的可转债发行数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_issuance | dict | dataframe<br>column 为kzz_issuance 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_issuance = info_data_object.get_kzz_issuance(code_list, is_local=False)

```

kzz_issuance 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| STOCK_CODE | string | 正股代码 |
| CRNCY_CODE | string | 货币代码 |
| ANN_DT | string | 公告日期 |
| PRE_PLAN_DATE | string | 预案公告日 |
| SMTG_ANN_DATE | string | 股东大会公告日 |
| LISTED_ANN_DATE | string | 上市公告日 |
| LISTED_DATE | string | 上市日期 |
| PLAN_SCHEDULE | string | 方案进度<br>1: 董事会预案<br>2: 股东大会通过<br>3: 实施<br>4: 未通过<br>5: 证监会通过<br>6: 达成转让意向<br>7: 签署转让协议<br>8: 国资委批准<br>9: 商务部批准<br>10: 过户<br>11: 延期实施<br>12: 停止实施<br>13: 分红方案待定 |
| IS_SEPARATION | int |  |
| 是否分离交易可转债 | RECOMMENDER | string<br>上市推荐人<br>CLAUSE_IS_INT_CHA_DE |
| PO_RATE | int | 利率是否随存款利率调<br>整 |
| CLAUSE_IS_COM_INT | int | 是否有利息补偿条款 |
| CLAUSE_COM_INT_RATE | float | 补偿利率（%） |
| CLAUSE_COM_INT_DESC | string | 补偿利率说明<br>CLAUSE_INIT_CONV_PRI |
| CE_ITEM | string | 初始转股价条款<br>CLAUSE_CONV_ADJ_ITE |
| M | string | 转股价格调整条款 |
| CLAUSE_CONV_PERIOD_I | TEM | string<br>转换期条款<br>CLAUSE_INI_CONV_PRIC |
| E | float | 初始转换价格<br>CLAUSE_INI_CONV_PRE |
| MIUM_RATIO | float | 初始转股价溢价比例<br>（%） |
| CLAUSE_PUT_ITEM | string | 回售条款 |
| CLAUSE_CALL_ITEM | string | 赎回条款 |
| CLAUSE_SPEC_DOWN_A | DJ | string<br>特别向下修正条款<br>CLAUSE_ORIG_RATION_A |
| RR_ITEM | string | 向原股东配售安排条款 |
| LIST_PASS_DATE | string | 发审通过公告日 |
| LIST_PERMIT_DATE | string | 证监会核准公告日 |
| LIST_ANN_DATE | string | 发行公告日 |
| LIST_RESULT_ANN_DATE | string | 发行结果公告日 |
| LIST_TYPE | string | 发行方式 |
| LIST_FEE | float | 发行费用 |
| LIST_RATION_DATE | string | 老股东配售日期 |
| LIST_RATION_REG_DATE | string | 老股东配售股权登记日 |
| LIST_RATION_PAYMT_DA | TE | string<br>老股东配售缴款日 |
| LIST_RATION_CODE | string | 老股东配售代码 |
| LIST_RATION_NAME | string | 老股东配售简称 |
| LIST_RATION_PRICE | float | 老股东配售价格 |
| LIST_RATION_RATIO_DE | float | 老股东配售比例分母 |
| LIST_RATION_RATIO_MO | float | 老股东配售比例分子 |
| LIST_RATION_VOL | float | 向老股东配售数量<br>(张)） |
| LIST_HOUSEHOLD | float | 老股东配售户数 |
| LIST_ONL_DATE | string | 上网发行日期 |
| LIST_PCHASE_CODE_ONL | string | 上网发行申购代码 |
| LIST_PCH_NAME_ONL | string | 上网发行申购名称 |
| LIST_PCH_PRICE_ONL | float | 上网发行申购价格 |
| LIST_ISSUE_VOL_ONL | float | 上网发行数量(不含优<br>先配售)(张) |
| LIST_CODE_ONL | float | 上网发行配号总数 |
| LIST_EXCESS_PCH_ONL | float | 上网发行超额认购倍数<br>(不含优先配售) |
| RESULT_EF_SUBSCR_P_O | FF | float<br>网上有效申购户数(不<br>含优先配售) |
| RESULT_SUC_RATE_OFF | float | 网上有效申购手数(不<br>含优先配售) |
| LIST_DATE_INST_OFF | string | 网下向机构投资者发行<br>日期 |
| LIST_VOL_INST_OFF | float | 网下向机构投资者发行<br>数量( 不含优先配售)<br>(张) |
| RESULT_SUC_RATE_ON | float | 网上中签率(不含优先<br>配售)(%) |
| LIST_EFFECT_PC_HVOL_ | OFF | float<br>网下有效申购手数(不<br>含优先配售) |
| LIST_EFF_PC_H_OF | float | 网下有效申购户数(不<br>含优先配售) |
| LIST_SUC_RATE_OFF | float | 网下中签率(不含优先<br>配售)(%) |
| PRE_RATION_VOL | float | 网下优先配售数量(张) |
| LIST_ISSUE_SIZE | float | 发行规模(万元) |
| LIST_ISSUE_QUANTITY | float | 发行数量(万张) |
| MIN_OFF_INST_SUBSCR_ | QTY | float<br>网下最小申购数量(机<br>构) |
| OFF_INST_DEP_RATIO | string | 网下定金比例(机构) |
| MAX_OFF_INST_SUBSCR_ | QTY | float<br>网下最大申购数量(机<br>构) |
| OFF_SUBSCR_UNIT_INC_ | DESC | string<br>网下申购累进单位说明 |
| IS_CONV_BONDS | int | 是否可转债 |
| MIN_UNLINE_PUBLIC | float | 网下最小申购数量(公<br>众)(元) |
| MAX_UNLINE_PUBLIC | float | 网上最大申购数量(公<br>众)(元) |
| TERM_YEAR | float | 借款期限(年) |
| INTEREST_TYPE | string | 利率类型 |
| COUPON_RATE | float | 利率(%) |
| INTEREST_FRE_QUENCY | string | 付息频率 |
| RESULT_SUC_RATE_ON2 | float | 网上中签率(不含优先<br>配售)(%) |
| COUPON_TXT | string | 利率说明 |
| RATIO_ANNCE_DATE | string | 网上中签率公告日 |
| RATIO_DATE | string | 网上中签结果公告日 |

#### 3.5.14.2 可转债份额

 函数接口：get_kzz_share
功能描述：获取指定可转债列表的可转债份额数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_share | dict | dataframe<br>column 为kzz_share 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_share = info_data_object.get_kzz_share(code_list, is_local=False)
```

kzz_share 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| CHANGE_DATE | string | 变动日期 |
| ANN_DATE | string | 公告日期 |
| MARKET_CODE | string | 市场代码 |
| BOND_SHARE | float | 债券份额（万元） |
| CONV_SHARE | float | 已转成股份数 |
| CHANGE_REASON | string | 变动原因代码，目前包含 |
| 的枚举类型: | ZZG |  |
| 转债转股 | SH |  |
| 赎回 | KZZS |  |
| 可转债上市 | HS |  |
| 回售 | DQ |  |
| 到期 | QLXQ |  |
| 权利行权 | TQDF | 本金提前兑 |
| 付 | GH | 购回<br>HSZG  回售转股<br>HGZG  回购转股 |

#### 3.5.14.3 可转债转股数据

 函数接口：get_kzz_conv
功能描述：获取指定可转债列表的可转债转股数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br><br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_conv | dict | dataframe<br>column 为kzz_conv 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_conv = info_data_object.get_kzz_conv(code_list, is_local=False)
```

kzz_conv 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| ANN_DATE | string | 公告日期 |
| CONV_CODE | string | 转股申报代码 |
| CONV_NAME | string | 转股简称 |
| CONV_PRICE | float | 股转价格 |
| CURRENCY_CODE | string | 股转申报代码 |
| CONV_START_DATE | string | 自愿转换期起始日 |
| CONV_END_DATE | string | 自愿转换期截止日 |
| TRADE_DATE_LAST | string | 可转换债停止交易日 |
| FORCED_CONV_DATE | string | 强制转换日 |
| FORCED_CONV_PRICE | float | 强制转换价格 |
| REL_CONV_MONTH | float | 相对转换期(月) |
| IS_FORCED | float | 是否强制转股 |
| FORCED_CONV_REASON | string | 强制转换原因 |

#### 3.5.14.4 可转债转股变动数据

 函数接口：get_kzz_conv_change
功能描述：获取指定可转债列表的可转债转股变动数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_conv_cha | nge |  |
| dict | dataframe | column 为kzz_conv_change 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_conv_change = info_data_object.get_kzz_conv_change(code_list, is_local=False)
```

kzz_conv_change 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| CHANGE_DATE | string | 变动日期 |
| ANN_DATE | string | 公告日期 |
| CONV_PRICE | float | 转股价格 |
| CHANGE_REASON | string | 变动原因，<br>变<br>动<br>原<br>因<br>变动原因名称<br>发行<br>换股吸收合并<br><br>派息<br>配股<br>上市<br>送股<br>送转股<br>送转股,派息<br>修正<br>增发<br>转增,派息<br>送股,派息<br>公司选择不行<br>使赎回权<br>回购注销<br>回购注销,派息<br>增发,回购注销<br>增发,回购注销,<br>派息<br>增发,派息<br>换股<br>派息,转增<br>派息,转增,增发<br>派息,送转股<br>调整<br>转增<br>除息 |

#### 3.5.14.5 可转债修正数据

 函数接口：get_kzz_corr
功能描述：获取指定可转债列表的可转债修正数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br><br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_corr | dict | dataframe<br>column 为kzz_corr 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_corr = info_data_object.get_kzz_corr(code_list, is_local=False)
```

kzz_corr 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| START_DATE | string | 特别修正起始时间 |
| END_DATE | string | 特别修正结束时间 |
| CORR_TRIG_CALC_MAX_ | PERIOD | float<br>修正触发计算最大时间<br>区间（天）<br>CORR_TRIG_CALC_PERIO |
| D | float | 修正触发计算时间区间<br>（天） |
| SPEC_CORR_TRIG_RATIO | float | 特别修正触发比例（%）<br>CORR_CONV_PRICE_FLO |
| OR_DESC | string | 修正后转股价格底线说<br>明<br>REF_PRICE_IS_AVG_PRIC |
| E | int | 参考价格是否为算术平<br>均价 |
| CORR_TIMES_LIMIT | string | 修正次数限制<br>IS_TIMEPOINT_CORR_CL |
| AUSE_FLAG | int | 是否有时点修正条款 |
| TIMEPOINT_COUNT | float | 时点数 |
| TIMEPOINT_CORR_TEXT_ | CLAUSE | string<br>时点修正文字条款 |
| SPEC_CORR_RANGE | float | 特别修正幅度<br>IS_SPEC_DOWN_CORR_C |
| LAUSE_FLAG | int | 是否有特别向下修正条<br>款 |

#### 3.5.14.6 可转债赎回数据

 函数接口：get_kzz_call
功能描述：获取指定可转债列表的可转债赎回数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_call | dict | dataframe<br>column 为kzz_call 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_call = info_data_object.get_kzz_call(code_list, is_local=False)
```

kzz_call 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| CALL_PRICE | float | 赎回价 |
| BEGIN_DATE | string | 起始日期 |
| END_DATE | string | 截止日期 |
| TRI_RATIO | float | 触发比例（%） |

#### 3.5.14.7 可转债回售数据

函数接口：get_kzz_put
功能描述：获取指定可转债列表的可转债回售数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_put | dict | dataframe<br>column 为kzz_put 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_put = info_data_object.get_kzz_put(code_list, is_local=False)
```

kzz_put 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| PUT_PRICE | float | 回售价 |
| BEGIN_DATE | string | 起始日期 |
| END_DATE | string | 截止日期 |
| TRI_RATIO | float | 触发比例（%） |

#### 3.5.14.8 可转债回售赎回条款

 函数接口：get_kzz_put_call_item
功能描述：获取指定可转债列表的可转债回售赎回条款数据

输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_put_call_ | item |  |
| dict | dataframe | column 为kzz_put_call_item 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_put_call_item = info_data_object.get_kzz_put_call_item(code_list, is_local=False)
```

kzz_put_call_item 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| MAND_PUT_PERIOD | string | 无条件回售期 |
| MAND_PUT_PRICE | float | 无条件回售价 |
| MAND_PUT_START_DATE | string | 无条件回售开始日期 |
| MAND_PUT_END_DATE | string | 无条件回售结束日期 |
| MAND_PUT_TEXT | string | 无条件回售文字条款<br>IS_MAND_PUT_CONTAIN |
| _CURRENT | int | 无条件回售是否含当期<br>利息 |
| CON_PUT_START_DATE | string | 有条件回售起始日期 |
| CON_PUT_END_DATE | string | 有条件回售结束日期 |
| MAX_PUT_TRI_PER | float | 回售触发计算最大时间<br>区间 |
| PUT_TRI_PERIOD | float | 回售触发计算时间区间 |
| ADD_PUT_CON | string | 附加回售条件 |
| ADD_PUT_PRICE_INS | string | 股价回售价格说明 |
| PUT_NUM_INS | string | 回售次数说明 |
| PUT_PRO_PERIOD | float | 相对回售期（月） |
| PUT_NO_PERY | float | 每年回售次数 |
| IS_PUT_ITEM | int | 是否有回售条款 |
| IS_TERM_PUT_ITEM | int | 是否有到期回售条款 |
| IS_MAND_PUT_ITEM | int | 是否有无条件回售条款 |
| IS_TIME_PUT_ITEM | int | 是否有时点回售条款 |
| TIME_PUT_NO | float | 时点回售数 |
| TIME_PUT_ITEM | string | 时点回售文字条款 |
| TERM_PUT_PRICE | float | 到期回售价 |
| CON_CALL_START_DATE | string | 有条件赎回起始日期 |
| CON_CALL_END_DATE | string | 有条件赎回结束日期 |
| CALL_TRI_CON_INS | string | 赎回触发条件说明 |
| MAX_CALL_TRI_PER | float | 赎回触发计算最大时间<br>区间 |
| CALL_TRI_PER | float | 赎回触发计算时间区间 |
| CALL_NUM_BER_INS | string | 赎回次数说明 |
| IS_CALL_ITEM | int | 是否有赎回条款 |
| CALL_PRO_PERIOD | float | 相对赎回期（月） |
| CALL_NO_PERY | float | 每年赎回次数 |
| IS_TIME_CALL_ITEM | int | 是否有时点赎回条款 |
| TIME_CALL_NO | float | 时点赎回数 |
| TIME_CALL_TEXT | string | 时点赎回文字条款 |
| EXPIRED_REDEMPTION_P | RICE | float<br>到期赎回价 |
| PUT_TRI_CON_DESC | string | 回售触发条件说明 |

#### 3.5.14.9 可转债回售条款执行说明

 函数接口：get_kzz_put_explanation
功能描述：获取指定可转债列表的可转债回售条款执行说明数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_put_expla | nation |  |
| dict | dataframe | column 为kzz_put_explanation 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_put_explanation = info_data_object.get_kzz_put_explanation(code_list, is_local=False)
```

kzz_put_explanation 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| PUT_FUND_ARRIVAL_DA | TE | string<br>回售资金到账日 |
| PUT_PRICE | float | 每百元面值回收价格<br>（元） |
| PUT_ANNOUNCEMENT_D | ATE | string<br>回售公告日 |
| PUT_EX_DATE | string | 回售履行结果公告日 |
| PUT_AMOUNT | float | 回售总面额（亿元） |
| PUT_OUTSTANDING | float | 继续托管总面额（亿元） |
| REPURCHASE_START_DA | TE | string<br>回售行使开始日 |
| REPURCHASE_END_DATE | string | 回售行使截止日 |
| RESALE_START_DATE | string | 转售开始日 |
| FUND_END_DATE | string | 回售日 |
| REPURCHASE_CODE | string | 回售代码 |
| RESALE_AMOUNT | float | 转售总面额（亿元） |
| RESALE_IMP_AMOUNT | float | 实施转售总面额（亿元） |
| RESALE_END_DATE | string | 转售截止日 |

#### 3.5.14.10 可转债赎回条款执行说明

 函数接口：get_kzz_call_explanation
功能描述：获取指定可转债列表的可转债赎回条款执行说明数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_call_expl | anation |  |
| dict | dataframe | column 为kzz_call_explanation 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_call_explanation = info_data_object.get_kzz_call_explanation(code_list, is_local=False)
```

kzz_call_explanation 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| CALL_DATE | string | 赎回日 |
| CALL_PRICE | float | 每百元面值赎回价格(元) |
| CALL_ANNOUNCEMENT_DATE | string | 赎回公告日 |
| CALL_FUL_RES_ANN_DATE | string | 赎回履行结果公告日 |
| CALL_AMOUNT | float | 赎回总面额(亿元) |
| CALL_OUTSTANDING_AMOUNT | float | 继续托管总面额（亿元） |
| CALL_DATE_PUB | string | 赎回日（公布） |
| CALL_FUND_ARRIVAL_DATE | string | 赎回资金到账日 |
| CALL_RECORD_DAY | string | 赎回登记日 |
| CALL_REASON | string | 赎回原因 |

#### 3.5.14.11 可转债停复牌信息

 函数接口：get_kzz_suspend
功能描述：获取指定可转债列表的可转债停复牌信息数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| code_list | list[str] | 是 | 支持可转债的的代码列表 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| kzz_suspend | dict | dataframe<br>column 为kzz_suspend 的字段<br>index 无意义 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()

base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list('EXTRA_KZZ')
kzz_suspend = info_data_object.get_kzz_suspend(code_list, is_local=False)
```

kzz_suspend 的字段说明：

| 字段名称 | 类型 | 字段说明 |
| --- | --- | --- |
| MARKET_CODE | string | 市场代码 |
| SUSPEND_DATE | string | 停牌日期 |
| SUSPEND_TYPE | int | 停牌类型代码<br>001-上午停牌<br>002-下午停牌<br>003-今起停牌<br>004-盘中停牌<br>007-停牌1 小时<br>016-停牌1 天 |
| RESUMP_DATE | string | 复牌日期 |
| CHANGE_REASON | string | 停牌原因 |
| CHANGE_REASON_CODE | int | 停牌原因代码 |
| RESUMP_TIME | string | 停复牌时间 |

### 3.5.15 国债收益率数据

#### 3.5.15.1 国债收益率

函数接口：get_treasury_yield
功能描述：获取指定期限的国债收益率数据
输入参数：

| 参数 | 数据类型 | 必选 | 解释 |
| --- | --- | --- | --- |
| term_list | list[str] | 是 | 支持不同期限的国债收益率<br>'m3'：3 个月,<br>'m6'：6 个月,<br>'y1'：1 年,<br>'y2'：2 年,<br>'y3'：3 年,<br>'y5'：5 年,<br>'y7'：7 年,<br>'y10'：20 年,<br><br>'y30'：30 年 |
| local_path | str | 是 | 本地存储数据的路径，需绝对路径，格式<br>类似“<br>'D://AmazingData_local_data//'<br>” |
| is_local | bool | 否 | 默认为True，本地数据缓存方案 |
| begin_date | int | 否 | 变动日期，本地数据缓存方案 |
| end_date | int | 否 | 变动日期，本地数据缓存方案 |
输出参数：
| 参数 | 数据类型 | 解释 |
| --- | --- | --- |
| treasury_yield | dict | 字典的key：期限<br>字典的value：dataframe，<br>column 为YIELD，国债收益率数据，<br>index 为日期 |

```python
# 第一步 登录api
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
treasury_yield = info_data_object.get_treasury_yield(['m3', 'm6', 'y1', 'y2', 'y3', 'y5', 'y7', 'y10', 'y30'])

```

## 4. 附录

## 4.1 字段取值说明

### 4.1.1 代码类型security_type(沪深北)

| 数据类型 | 枚举值 | 说明 |
| --- | --- | --- |
| str | EXTRA_STOCK_A | 上交所A 股、深交所A 股和北交所的股票列表 |
| str | SH_A | 上交所A 股的股票列表 |
| str | SZ_A | 深交所A 股的股票列表 |
| str | BJ_A | 北交所的股票列表 |
| str | EXTRA_STOCK_A_SH_SZ | 上交所A 股和深交所A 股的股票列表 |
| str | EXTRA_INDEX_A_SH_SZ | 上交所和深交所指数列表 |
| str | EXTRA_INDEX_A | 上交所、深交所和北交所的指数列表 |
| str | SH_INDEX | 上交所指数列表 |
| str | SZ_INDEX | 深交所指数列表 |
| str | BJ_INDEX | 北交所的指数列表 |
| str | SH_ETF | 上交所的ETF 列表 |
| str | SZ_ETF | 深交所的ETF 列表 |
| str | EXTRA_ETF | 上交所、深交所的ETF 列表 |
| str | SH_KZZ | 上交所的可转债列表 |
| str | SZ_KZZ | 深交所的可转债列表 |
| str | EXTRA_KZZ | 上交所、深交所的可转债列表 |
| str | SH_HKT | 沪港通 |
| str | SZ_HKT | 深港通 |
| str | EXTRA_HKT | 沪深港通 |
| str | SH_GLRA | 上交所逆回购 |
| str | SZ_GLRA | 深交所逆回购 |
| str | EXTRA_ GLRA | 沪深逆回购 |

### 4.1.2 代码类型security_type(期货交易所)

| 数据类型 | 枚举值 | 说明 |
| --- | --- | --- |
| str | EXTRA_FUTURE | 期货, 包含中金所/上期所/大商所/郑商所/上海<br>国际能源交易中心所 |
| str | ZJ_FUTURE | 期货, 包含中金所 |
| str | SQ_FUTURE | 期货, 包含上期所 |
| str | DS_FUTURE | 期货, 包含大商所 |
| str | ZS_FUTURE | 期货, 包含郑商所 |
| str | SN_FUTURE | 期货, 包含海国际能源交易中心所 |

### 4.1.3 代码类型security_type(期权)

| 数据类型 | 枚举值 | 说明 |
| --- | --- | --- |
| str | EXTRA_ETF_OP | ETF 期权, 上交所/深交所 |
| str | SH_OPTION | ETF 期货, 包含上交所 |
| str | SZ_OPTION | ETF 期货, 包含深交所 |

### 4.1.4 市场类型market

| 数据类型 | 枚举值 | 说明 |
| --- | --- | --- |
| str | SH | 上交所 |
| str | SZ | 深交所 |
| str | BJ | 北交所 |
| str | SHF | 上期所 |
| str | CFE | 中金所 |
| str | DCE | 大商所 |
| str | CZC | 郑商所 |
| str | INE | 上海国际能源交易中心所 |
| str | SHN | 沪港通 |
| str | SZN | 深港通 |
| str | HK | 港交所 |

### 4.1.5 交易阶段代码trading_phase_code

（1） 上海现货快照交易状态
该字段为8 位字符数组,左起每位表示特定的含义,无定义则填空格。
第0 位: ‘S’表示启动(开市前)时段,‘C’表示开盘集合竞价时段,‘T’表示连续交易时段,‘E’表示
闭市时段,‘P’表示产品停牌。
第1 位: ‘0’表示此产品不可正常交易,‘1’表示此产品可正常交易。
第2 位: ‘0’表示未上市,‘1’表示已上市。
第3 位: ‘0’表示此产品在当前时段不接受进行新订单申报,‘1’ 表示此产品在当前时段可接受
进行新订单申报。

（2） 深圳现货快照交易状态
第 0 位: ‘S’= 启动(开市前)‘O’= 开盘集合竞价‘T’= 连续竞价‘B’= 休市‘C’= 收盘集合竞价
‘E’= 已闭市‘H’= 临时停牌‘A’= 盘后交易‘V’=波动性中断。
第 1 位: ‘0’= 正常状态 ‘1’= 全天停牌。交易阶段代码

（3） 港股股票行情交易状态
‘1’表示正常交易，‘2’表示停牌，‘3’表示复牌
（4） 上海期权快照交易状态
第 1 位： ‘S’表示启动（开市前）时段， ‘C’表示集合竞价时段，‘T’表示连续交易时段，
‘B’表示休市时段， ‘E’表示闭市时段， ‘V’表示波动性中断， ‘P’表示临时停牌、 ‘U’表示
收盘集合竞价。 ‘M’表示可恢复交易的熔断（盘中集合竞价） ,‘N’表示不可恢复交易的熔
断（暂停交易至闭市）；
第 2 位： ‘0’表示未连续停牌，‘1’表示连续停牌。（预留，暂填空格）；
第 3 位： ‘0’表示不限制开仓，‘1’表示限制备兑开仓， ‘2’表示卖出开仓， ‘3’表示限制
卖出开仓、备兑开仓， ‘4’表示限制买入开仓， ‘5’表示限制买入开仓、备兑开仓， ‘6’表示
限制买入开仓、卖出开仓， ‘7’表示限制买入开仓、卖出开仓、备兑开仓；
第 4 位： ‘0’表示此产品在当前时段不接受进行新订单申报，‘1’ 表示此产品在当前时段
可接受进行新订单申报。

### 4.1.6 产品状态标志security_status

状态
标志
说明
停牌
深交所、北交所
除权
上交所、深交所、北交所
除息
上交所、深交所、北交所
风险警示
上交所、深交所、北交所
退市整理期
上交所、深交所、北交所
上市首日
上交所、深交所、北交所

公司再融资
深交所
恢复上市首日
深交所、北交所
网络投票
深交所
增发股份上市
深交所
合约调整
深交所
暂停上市后协议转让
深交所
实施双转单调整
深交所
特定债券转让
深交所、北交所
上市初期
深圳有效
退市整理期首日
深交所、北交所
新增股份
北交所
是否可作为融资融券可充抵
保证金证券
北交所
是否为融资标的
北交所
是否为融券标的
北交所
是否可质押入库
北交所
是否跨市场
北交所
是否处于转股回售期
北交所

### 4.1.7 数据周期Period

| 数据类型 | 枚举值 | 说明 |
| --- | --- | --- |
| int | Period.min1.value | 1 分钟线 |
| int | Period.min3.value | 3 分钟线 |
| int | Period.min5.value | 5 分钟线 |
| int | Period.min10.value | 10 分钟线 |
| int | Period.min15.value | 15 分钟线 |
| int | Period.min30.value | 30 分钟线 |
| int | Period.min60.value | 60 分钟线 |
| int | Period.min120.value | 120 分钟线 |
| int | Period.day.value | 日线 |
| int | Period.week.value | 周线 |
| int | Period.month.value | 月线 |
| int | Period.season.value | 季度线 |
| int | Period.year.value | 年线 |

### 4.1.8 报告期名称REPORT_TYPE

报告期类型代码
报告期月份
3 月

6 月
9 月
12 月

### 4.1.9 报表类型代码表STATEMENT_TYPE

报表类型代码
报表类型
备注
合并报表
涵盖母公司的财务报表数据，为最新报表
合并报表(单季
度)
合并报表(单季度)=合并报表(本期)-合并报表(上一季)
合并报表(单季
度调整)
合并报表(单季度调整)=合并报表(本期调整)-合并报表
(上一季调整)
合并报表(调整)
本年度公布上年同期的财务报表数据，报告期为上年度
合并报表(更正
前)
即出更正公告后，把合并报表的记录修改为合并报表(更
正前)；复制原来的记录，更正后报表类型改为合并报表
母公司报表
该公司母公司的财务报表数据
母公司报表(单
季度)
母公司报表(单季度)=母公司报表(本期)-母公司报表(上
一季)
母公司报表(单
季度调整)
母公司报表(单季度调整)=母公司报表(本期调整)-母公
司报表(上一季调整)
母公司报表(调
整)
该公司母公司的本年度公布上年同期的财务报表数据
母公司报表(更
正前)
之前上市公司已披露财务报表数据，但是由于某些特定
原因导致出错，未调整之前的原始财务报表数据。
合并报表(未公
开)
未在公开信息源披露的财报且加工为合并报表口径
合并报表(调整
未公开)
未在公开信息源披露的财报且加工为合并报表调整口径
合并报表(单季
度未公开)
未在公开信息源披露的财报且加工为合并报表单季度口
径
合并报表(单季
度调整未公开)
未在公开信息源披露的财报且加工为母公司报表口径
母公司报表(未
公开)
未在公开信息源披露的财报且加工为母公司报表口径
母公司报表(调
整未公开)
未在公开信息源披露的财报且加工为母公司报表调整口
径
母公司报表(单
季度未公开)
未在公开信息源披露的财报且加工或计算为母公司报表
单季度口径
母公司报表(单
季度调整未公
开)
未在公开信息源披露的财报且加工或计算为母公司报表
单季度调整口径
合并报表(调整
借壳前的合并报表(调整)

借壳前)
合并调整
对合并前各公司的财务报表进行调整，以确保合并财务
报表的准确性和可比性
合并报表(单季
度借壳前)
借壳前的合并报表(单季度)
合并报表(单季
度调整借壳前)
借壳前的合并报表(单季度调整)
母公司报表(借
壳前)
借壳前的母公司报表
母公司报表(调
整借壳前)
借壳前的母公司报表(调整)
母公司报表(单
季度借壳前)
借壳前的母公司报表(单季度)
母公司报表(单
季度调整借壳
前)
借壳前的母公司报表(单季度调整)
合并报表(第一
次更正)
有多次更正时，合并报表的第一次更正
合并报表(第二
次更正)
有多次更正时，合并报表的第二次更正
合并调整(第一
次更正)
有多次更正时，合并调整的第一次更正
合并报表(单月
度)
根据披露的券商月报公告加工为合并报表口径
合并调整(第二
次更正)
有多次更正时，合并调整的第二次更正
母公司调整(第
二次更正)
有多次更正时，母公司调整的第二次更正
母公司调整(第
一次更正)
有多次更正时，母公司调整的第一次更正
母公司报表(第
二次更正)
有多次更正时，母公司报表的第二次更正
母公司报表(第
一次更正)
有多次更正时，母公司报表的第一次更正
合并报表(第三
次更正)
有多次更正时，合并报表的第三次更正
合并调整(第三
次更正)
有多次更正时，合并调整的第三次更正
母公司报表(第
三次更正)
有多次更正时，母公司报表的第三次更正
母公司调整(第
三次更正)
有多次更正时，母公司调整的第三次更正
母公司报表(单
月度)
根据披露的券商月报公告加工为母公司报表口径的数据

合并报表(业绩
快报)
加工业绩快报中的财务数据（海外数据专用）
合并调整(第一
次)
第一次合并调整数据
合并调整(第二
次)
第二次合并调整数据
合并调整(第三
次)
第三次合并调整数据
合并报表(第四
次更正)
有多次更正时，合并报表的第四次更正
合并调整(第四
次更正)
有多次更正时，合并调整的第四次更正
母公司报表(第
四次更正)
有多次更正时，母公司报表的第四次更正
母公司调整(第
四次更正)
有多次更正时，母公司调整的第四次更正
合并调整(更正
前)
即出更正公告后，把合并报表（调整）的记录修改为合
并调整(更正前)；复制原来的记录，更正后报表类型改
为合并报表(调整)
合并报表(下半
年报)
合并下半年度的报表
母公司调整(更
正前)
该公司母公司的本年度公布上年同期的财务报表数据，
但是由于某些特定原因导致出错，未调整之前的原始财
务报表数据。
合并报表(借壳
前)
公司主体在借壳上市前披露或者计算的为合并报表口径
的报表类型
合并报表(预测)
REITS 基金的定期报告中披露的预测的合并报表数据
合并报表(公司
预测)

项目资产报表
由项目资产管理人编制的一种财务报表，用于反映项目
资产的财务状况和经营情况
合并报表(日历
年)

### 4.1.10 股票分红进度代码表DIV_PROGRESS

分红进度描述
进度代码
董事会预案
股东大会通过
实施
未通过
停止实施

股东提议
董事会预案预披露
 分红实施进程：股东提议--董事会预案--股东大会--实施

### 4.1.11 股票配股进度代码表PROGRESS

配股进度描述
进度代码
董事会预案
股东大会通过
实施
未通过
证监会核准
达成转让意向
签署转让协议
国资委批准
商务部批准
过户
延期实施
停止实施
分红方案待定
传闻
证监会受理
传闻被否认
股东提议
保监会批复
董事会预案预披露
发审委通过
发审委未通过
股东大会未通过
银监会批准
证监会恢复审核
预发行
提交注册

## 4.2 数据结构说明

### 4.2.1 Level-1 快照Snapshot

数据类型
字段名称
说明
str
code
证券代码+市场

datetime
trade_time
交易所行情数据时间
float
pre_close
昨收价
float
last
最新价
float
open
开盘价
float
high
最高价
float
low
最低价
float
close
收盘价
float
volume
成交总量
float
amount
成交总金额
float
num_trades
成交笔数
float
high_limited
涨停价
float
low_limited
跌停价
float
ask_price1
卖1 档价格
float
ask_price2
卖2 档价格
float
ask_price3
卖3 档价格
float
ask_price4
卖4 档价格
float
ask_price5
卖5 档价格
int
ask _volume1
卖1 档量
int
ask_volume2
卖2 档量
int
ask _volume3
卖3 档量
int
ask_volume4
卖4 档量
int
ask _volume5
卖5 档量
float
bid_price1
买1 档价格
float
bid_price2
买2 档价格
float
bid_price3
买3 档价格
float
bid_price4
买4 档价格
float
bid_price5
买5 档价格
int
bid _volume1
买1 档量
int
bid_volume2
买2 档量
int
bid _volume3
买3 档量
int
bid_volume4
买4 档量
int
bid _volume5
买5 档量
float
iopv
净值估产（仅基金品种有效）
str
trading_phase_code
交易阶段代码

### 4.2.2 ETF 期权快照SnapshotOption

数据类型
字段名称
说明
str
code
证券代码+市场
datetime
trade_time
交易所行情数据时间
str
trading_phase_code
交易阶段代码
int
total_long_position
总持仓量

float
volume
成交总量
float
amount
成交总金额
float
pre_close
昨收价
float
pre_settle:
上次结算价
float
auction_price
动态参考价（波动性中断参考价，仅上海有效），
int
auction_volume
虚拟匹配数量（仅上海有效）
float
last
最新价
float
open
开盘价
float
high
最高价
float
low
最低价
float
close
收盘价
float
settle
本次结算价
float
high_limited
涨停价
float
low_limited
跌停价
float
ask_price1
卖1 档价格
float
ask_price2
卖2 档价格
float
ask_price3
卖3 档价格
float
ask_price4
卖4 档价格
float
ask_price5
卖5 档价格
int
ask_volume1
卖1 档量
int
ask _volume2
卖2 档量
int
ask_volume3
卖3 档量
int
ask _volume4
卖4 档量
int
ask_volume5
卖5 档量
float
bid_price1
买1 档价格
float
bid_price2
买2 档价格
float
bid_price3
买3 档价格
float
bid_price4
买4 档价格
float
bid_price5
买5 档价格
int
bid_volume1
买1 档量
int
bid _volume2
买2 档量
int
bid_volume3
买3 档量
int
bid _volume4
买4 档量
int
bid_volume5
买5 档量
str
contract_type
合约类别
int
expire_date
到期日
str
underlying_security_cod
标的代码
float
exercise_price
行权价

### 4.2.3 期货快照SnapshotFuture

数据类型
字段名称
说明
str
code
证券代码+市场
datetime
trade_time
交易所行情数据时间
str
action_day
业务日期
str
trading_day
交易日期
float
pre_close
昨收价
float
pre_settle:
上次结算价
int
pre_open_interest
昨持仓量
int
open_interest
持仓量
float
last
最新价
float
open
开盘价
float
high
最高价
float
low
最低价
float
close
收盘价
float
volume
成交总量
float
amount
成交总金额
float
high_limited
涨停价
float
low_limited
跌停价
float
ask_price1
卖1 档价格
float
ask_price2
卖2 档价格
float
ask_price3
卖3 档价格
float
ask_price4
卖4 档价格
float
ask_price5
卖5 档价格
int
ask_volume1
卖1 档量
int
ask _volume2
卖2 档量
int
ask_volume3
卖3 档量
int
ask _volume4
卖4 档量
int
ask_volume5
卖5 档量
float
bid_price1
买1 档价格
float
bid_price2
买2 档价格
float
bid_price3
买3 档价格
float
bid_price4
买4 档价格
float
bid_price5
买5 档价格
int
bid_volume1
买1 档量
int
bid _volume2
买2 档量
int
bid_volume3
买3 档量
int
bid _volume4
买4 档量
int
bid_volume5
买5 档量
float
average_price
当日均价
float
settle
本次结算价

### 4.2.4 指数快照SnapshotIndex

数据类型
字段名称
说明
str
code
证券代码+市场
datetime
trade_time
交易所行情数据时间
float
last
最新价
float
pre_close
前收盘价
float
open
今开盘价
float
high
最高价
float
low
最低价
float
close
收盘价（仅上海有效）
int
volume
成交总量（上交所:手，深交所:张）
float
amount
成交总金额

### 4.2.5 港股通快照 SnapshotHKT

数据类型
字段名称
说明
str
code
证券代码+市场
datetime
trade_time
交易所行情数据时间
float
pre_close
昨收价
float
last
最新价
float
high
最高价
float
low
最低价
float
volume
成交总量
float
amount
成交总金额
float
nominal_price
暗盘价
float
ref_price
参考价
float
bid_price_limit_up
买盘上限价
float
bid_price_limit_down
买盘下限价
float
offer_price_limit_up
卖盘上限价
float
offer_price_limit_down
卖盘下限价
float
high_limited
冷静期价格上限
float
low_limited
冷静期价格下限
float
ask_price1
卖1 档价格
float
ask_price2
卖2 档价格
float
ask_price3
卖3 档价格
float
ask_price4
卖4 档价格
float
ask_price5
卖5 档价格
int
ask_volume1
卖1 档量

int
ask _volume2
卖2 档量
int
ask_volume3
卖3 档量
int
ask _volume4
卖4 档量
int
ask_volume5
卖5 档量
float
bid_price1
买1 档价格
float
bid_price2
买2 档价格
float
bid_price3
买3 档价格
float
bid_price4
买4 档价格
float
bid_price5
买5 档价格
int
bid_volume1
买1 档量
int
bid _volume2
买2 档量
int
bid_volume3
买3 档量
int
bid _volume4
买4 档量
int
bid_volume5
买5 档量
str
trading_phase_code
交易阶段代码

### 4.2.6 K 线Kline

数据类型
字段名称
说明
str
code
证券代码+市场
datetime
trade_time
交易所行情数据时间
float
open
今开盘价
float
high
最高价
float
low
最低价
float
close
收盘价
int
volume
成交总量
float
amount
成交总金额

## 4.3 相关算法说明

### 4.3.1 商品期货查询算法

当查询非中金所（大商所、郑商所、上期所、上期能源）的商品期货快照时，因涉及夜
盘快照，需根据查询时间参数做相应区分，查询上以 20:00 作为夜盘的分割时间点，处理
逻辑见下表。
归属T-1 日范围20:00:00.000~23:59:59.999
归属T 日范围：00:00:00.000~19:59:59.999
TGW 上送日
期
开始时间
结束时间
系统响应逻辑
开始、结束时间均归属T 日，且开始时间

<结束时间，为有效查询，返回[4 月7 日
9:30, 4 月7 日15:00]的数据
开始、结束时间均归属T-1 日，且开始时
间<结束时间，为有效查询，返回[4 月6
日20:00, 4 月6 日23:59]的数据
开始时间归属T-1 日，结束时间归属T 日，
为有效查询，返回[4 月6 日20:00,4 月7
日01:00]的数据
正常周一（未
跨法定假节
日）
开始时间归属T-1 日，结束时间归属T 日，
为有效查询，返回[周五23:59:59.999,周一
03:00]的数据，需包括周末的数据（部分
品种周六0 点~02:30 会有行情）
特殊日（跨法
定假节日）
开始时间归属T-1 日，结束时间归属T 日，
为有效查询，返回[T-1 日20:00,T 日01:00]
的数据
开始、结束时间均归属T-1 日，但开始时
间>结束时间，为无效查询，无数据返回，
并需弹出相应告警
开始、结束时间均归属T 日，但开始时间>
结束时间，为无效查询，无数据返回，并
需弹出相应告警
开始时间归属T 日，结束时间归属T-1 日，
为无效查询，无数据返回，并需弹出相应
告警

### 4.3.2 K 线算法说明

（1） 集合竞价的处理
对于分钟K 线，开盘集合竞价数据的成交量包含在当日第一根K 线，收盘集合竞
价数据的成交量包含在当日最后一根K 线。
（2） 前推算法
9:30 的1 分钟K 线，计算的是9:30:00.000~9:30:59.999 期间的K 线。
9:35 的5 分钟K 线，计算的是9:35:00.000~9:39:59.999 期间的K 线。

## 4.4 本地数据缓存方案说明

应用场景：
（1） 接口取全量历史时间区间的数据
查询接口包含local_path 和is_local 两个参数的接口，这两个参数必须同时配对使用，支持
此本地缓存方案，本地保存全量历史数据，且每次调用接口默认增量更新本地数据，从而加
速接口读取速度；
（2） 接口取指定时间区间的数据
查询接口包含begin_date 和end_date 两个参数的接口，这两个参数必须同时配对使用，仅从

服务器获取数据，不本地缓存数据，速度较慢，且无增量更新机制。

### 4.4.1 函数入参说明

local_path 和is_local 为参数组1，begin_date 和end_date 为参数组2；
一个参数组内的参数必须同时使用；
两个参数组需独立使用，即使用参数组1 时，参数组2 无效；使用参数组2 时，参数组1
无效。
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

（2）is_local
True:
本地local_path 有数据的情况下，从本地取数据，但无法从服务端获取最新的数据
本地local_path 无数据的情况下，从互联网取数据，并更新本地local_path 的数据
False:从互联网取数据，并更新本地local_path 的数据

（3） begin_date, end_date
开始日期、结束日期，在不同的接口中代表交易日、公告期等不同含义，具体见接口说明；
即按照日期从服务端取数据，不从本地取数据（即local_path 和is_local 两个参数无效）。

### 4.4.2 本地存储文件说明

文件格式为hdf5 格式

### 4.4.3 本地存储空间说明

本地存储空间，不同的数据类型和标的范围，所需空间不同。
建议本地存储空间在500GB 以上。
