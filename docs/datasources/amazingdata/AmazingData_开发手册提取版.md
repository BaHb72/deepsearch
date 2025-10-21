# 中国银河证券星耀数智 AmazingData 开发手册

中国银河证券星耀数智
AmazingData
开发手册

目录
目录
.................................................................................................................................................................1

1.

版本说明
..............................................................................................................................................2
1.1
文档管理信息表
..............................................................................................................2

2.

功能介绍
..............................................................................................................................................2
2.1
金融数据服务
...................................................................................................................2
2.2
数据详情
............................................................................................................................2

3.

python 开发指南
................................................................................................................................4
3.1
SDK 版本与下载
.............................................................................................................4
3.1.1
wheel 文件版本 ......................................................................................................4
3.1.2
wheel 文件下载路径 .............................................................................................4
3.2
SDK 运行环境
.................................................................................................................4
3.2.1
Linux 推荐运行环境配置 ....................................................................................4
3.2.2
Windows 推荐运行环境配置..............................................................................5
3.3
SDK 安装
...........................................................................................................................5
3.3.1
tgw 安装
....................................................................................................................5
3.3.2
AmazingData 安装 .................................................................................................5
3.4
Python 开发步骤
..............................................................................................................5
3.4.1
登录 AmazingData .................................................................................................5
3.4.2
调用数据接口 .........................................................................................................5
3.4.2.1
查询接口调用 .......................................................................................5
3.4.2.2
订阅接口调用 .......................................................................................6
3.5
API 接口详细
...................................................................................................................6
3.5.1
基础接口
...................................................................................................................6
3.5.1.1
登录 .........................................................................................................6
3.5.1.2
登出 .........................................................................................................7
3.5.1.3
更新密码 ................................................................................................7
3.5.2
基础数据
...................................................................................................................7
3.5.2.1
每日最新证券信息 ..............................................................................7
3.5.2.2
每日最新代码表（沪深北） ...........................................................8
3.5.2.3
每日最新代码表（期货交易所） ..................................................8
3.5.2.4
每日最新代码表（期权） ................................................................9
3.5.2.5
复权因子（后复权因子） ................................................................9
3.5.2.6
复权因子（单次复权因子） ........................................................ 10
3.5.2.7
历史代码表......................................................................................... 11
3.5.2.8
交易日历 ............................................................................................. 12
3.5.2.9
证券基础信息 .................................................................................... 12
3.5.2.10
历史证券信息 .................................................................................... 13
3.5.2.11
北交所新旧代码对照表.................................................................. 14
3.5.3
实时行情数据 ...................................................................................................... 15
3.5.3.1
指数实时快照 .................................................................................... 15
3.5.3.2
股票实时快照 .................................................................................... 16

3.5.3.3
期货实时快照 .................................................................................... 16
3.5.3.4
ETF 实时快照 ............................................................................................. 17
3.5.3.5
可转债实时快照 ............................................................................... 18
3.5.3.6
港股通实时快照 ............................................................................... 18
3.5.3.7
实时 K 线 ............................................................................................ 19
3.5.4
历史行情数据 ...................................................................................................... 20
3.5.4.1
历史快照 ............................................................................................. 20
3.5.4.2
历史 K 线 ............................................................................................ 21
3.5.5
财务数据 ................................................................................................................
22
3.5.5.1
资产负债表......................................................................................... 22
3.5.5.2
现金流量表......................................................................................... 30
3.5.5.3
利润表 .................................................................................................. 39
3.5.5.4
业绩快报 ............................................................................................. 46
3.5.5.5
业绩预告 ............................................................................................. 49
3.5.6
股东股本数据 ...................................................................................................... 51
3.5.6.1
十大股东数据 .................................................................................... 51
3.5.6.2
股东户数 ............................................................................................. 52
3.5.6.3
股本结构 ............................................................................................. 53
3.5.6.4
股权冻结/质押 ................................................................................... 56
3.5.6.5
限售股解禁......................................................................................... 58
3.5.7
股东权益数据 ...................................................................................................... 59
3.5.7.1
分红数据 ............................................................................................. 59
3.5.7.2
配股数据 ............................................................................................. 61
3.5.8
融资融券数据 ...................................................................................................... 63
3.5.8.1
融资融券成交汇总 ........................................................................... 63
3.5.8.2
融资融券交易明细 ........................................................................... 64
3.5.9
交易异动数据 ...................................................................................................... 65
3.5.9.1
龙虎榜 .................................................................................................. 65
3.5.9.2
大宗交易 ............................................................................................. 66

4.

附录 ....................................................................................................................................................
67
4.1
字段取值说明 ................................................................................................................
67
4.1.1
代码类型 security_type(沪深北) ..................................................................... 67
4.1.2
代码类型 security_type(期货交易所)............................................................ 68
4.1.3
代码类型 security_type(期权) ......................................................................... 68
4.1.4
市场类型 market .................................................................................................. 68
4.1.5
交易阶段代码 trading_phase_code ................................................................ 69
4.1.6
数据周期 Period .................................................................................................. 70
4.1.7
报告期名称 REPORT_TYPE ........................................................................... 70
4.1.8
报表类型代码表 STATEMENT_TYPE ........................................................ 70
4.1.9
股票分红进度代码表 DIV_PROGRESS ...................................................... 73
4.1.10
股票配股进度代码表 PROGRESS ................................................................ 73
4.2
数据结构说明 ................................................................................................................
74
4.2.1
Level-1 快照 Snapshot ....................................................................................... 74
4.2.2
ETF 期权快照 SnapshotOption ....................................................................... 75

4.2.3
期货快照 SnapshotFuture.................................................................................. 76
4.2.4
指数快照 SnapshotIndex ................................................................................... 77
4.2.5
港股通快照 SnapshotHKT .............................................................................. 77
4.2.6
K 线 Kline..............................................................................................................
79
4.3
相关算法说明 ................................................................................................................
79
4.3.1
商品期货查询算法 ............................................................................................. 79
4.3.2
K 线算法说明 ...................................................................................................... 80
4.4
本地数据缓存方案说明 ............................................................................................. 80
4.4.1
函数入参说明 ...................................................................................................... 80
4.4.2
本地存储文件说明 ............................................................................................. 81
4.4.3
本地存储空间说明 ............................................................................................. 81

5.

免责声明 ...........................................................................................................................................
81

2

1. 版本说明
   1.1 文档管理信息表
   主题
   中国银河证券星耀数智 AmazingData 开发手册
   文档版本
   V1.0.14
   Python SDK 版本
   V1.0.14
   创建时间
   2025 年 7 月 10 日
   创建人
   中国银河证券财富管理总部
   最新发布日期
   2025 年 9 月 11 日
2. 功能介绍
   本文档是 tgw 的 SDK 开发指南，包含了对 API 接口的说明以及示例，用于指引开发人
   员通过 tgw 金融数据功能接口进行数据接收和查询的开发，如需参考或使用本项目，需要提
   前联系官方获取权限。
   2.1 金融数据服务
   金融数据功能，是指用户使用 C++、Python 以及其他本功能可支持的程序设计语言或
   用户端页面，获取公司通过对证券交易所等渠道的公开信息加工而成的行情数据、金融资讯
   数据等金融数据的功能。

2.2 数据详情

1)

行情数据
品种
数据类型
数据起点
说明
是 否 支 持
实时订阅
股票
Level-1 快照 、K 线数据
2013 年至今

上交所、 深交
所、北交所
是
指数
Level-1 快照 、K 线数据
上交所、 深交
所、北交所
是
债券
Level-1 快照 、K 线数据
上交所、深交所 是
场内基金
Level-1 快照 、K 线数据
上交所、深交所 是
期权
Level-1 快照 、K 线数据
2015 年至今
深交所 ETF 期
权、上交所 ETF
期权
是
港股通
港股通行情快照
2023 年至今
上交所、深交所 是
期货
Level-1 快照 、K 线数据
2010 年 4 月至
中金所
是

3
今
2013 年 6 月至
今
大商所
是
2011 年 1 月至
今
郑商所
是
2019 年 8 月至
今
上期所
是
2019 年 8 月至
今
上海国际能源
交易中心所
是

2)

基础数据
每日最新证券信息，交易日早上 9 点前更新
复权因子
每日最新代码表，交易日早上 9 点前更新
历史代码表
交易日历

3)

财务数据
资产负债表
现金流量表
利润表
业绩快报
业绩预告

4)

股东股本数据
十大股东数据
股东户数
股本结构
股权冻结/质押
限售股解禁

5)

股东权益数据
分红数据
配股数据

6)

融资融券数据
融资融券成交汇总
融资融券交易明细

7)

交易异动数据
龙虎榜
大宗交易

中国银河证券星耀数智服务平台金融资讯数据说明
4

3. python 开发指南
   3.1 SDK 版本与下载
   3.1.1 wheel 文件版本
   wheel 文件名
   操作系统
   Python 版本
   tgw-1.*.*-py3-none-any.whl
   Linux/ Windows
   Python 3.8  
   Python 3.9  
   Python 3.10
   Python 3.11
   Python 3.12
   Python 3.13
   AmazingData-1.*.*-cp38-none-any.whl
   Linux/ Windows
   Python 3.8  
   Python 3.9  
   Python 3.10
   Python 3.11
   Python 3.12
   Python 3.13
   3.1.2 wheel 文件下载路径
1. 银河网盘
   https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA
2. 公众号“中国银河证券星耀数智”
   路径：“业务介绍”——“安装包下载”
   3.2 SDK 运行环境
   3.2.1 Linux 推荐运行环境配置
   类型
   最低配置
   推荐配置
   处理器
   2.10GHz,4 核  
   2.10GHz,8 核  
   内存
   DDR4 4GB
   DDR4 4GB
   硬盘
   200G 机械硬盘/SSD  
   480G 机械硬盘/SSD  
   网卡
   普通网卡
   普通万兆网卡
   操作系统
   REDHAT 7.2/7.4/7.6
   REDHAT 7.2/7.4/7.6

中国银河证券星耀数智服务平台金融资讯数据说明
5
3.2.2 Windows 推荐运行环境配置
类型
最低配置
推荐配置
处理器
2.60GHz，4 核  
2.60GHz，8 核  
内存
DDR4 4GB
DDR4 4GB
硬盘
200G 机械硬盘/SSD
480G 机械硬盘/SSD
网卡
普通网卡
普通万兆网卡
操作系统
Windows 10(64 位)
Windows 10(64 位)
3.3 SDK 安装
3.3.1 tgw 安装
pip install tgw-1.7.1-py3-none-any.whl
3.3.2 AmazingData 安装
选择对应的 python 版本
pip install AmazingData-1.0.0-cp312-none-any.whl
3.4 Python 开发步骤
登录 AmazingData 之后，实现数据获取。
3.4.1 登录 AmazingData
（1）所有数据接口调用前，必须登录
（2）import AmazingData 库，填写账号、密码、ip/port 等信息，调用登录 api。
import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
3.4.2 调用数据接口
3.4.2.1 查询接口调用
（1）登录 api；
（2）实例化对应的数据查询类；

中国银河证券星耀数智服务平台金融资讯数据说明
6
（3）调用查询数据接口，获取数据；

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)

# 第二步 实例化对应的数据查询类

base_data_object = ad.BaseData()

# 第三步，调用查询数据接口，获取数据

code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')

3.4.2.2 订阅接口调用
（1）登录 api；
（2）实例化对应的数据查询类；
（3）实例化数据订阅类；
（4）用装饰器装饰回调函数，接收订阅数据；
（5）订阅数据执行；

# 第一步 登录 api

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

3.5 API 接口详细
3.5.1 基础接口
3.5.1.1 登录
调用任何数据接口之前，必须先调用登录接口。

中国银河证券星耀数智服务平台金融资讯数据说明
7
SDK 的账号、密码、ip 和端口号需联系您的开户营业部申请开通权限之后获取。
函数接口：login
功能描述：api 登陆  
输入参数：   
参数
数据类型
必选
解释
username
str  
是
账号  
password
str  
是
密码  
ip
str  
是
服务器 ip
host
int
是
服务器端口号

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
3.5.1.2 登出
函数接口：logout
功能描述：api 退出登录链接  
3.5.1.3 更新密码
函数接口：update_password
功能描述：更新密码接口，必须先登录才能修改密码
名称
类型
说明
username
str
用户名
old_password
str
旧密码
new_password
str
新密码
3.5.2 基础数据
3.5.2.1 每日最新证券信息
函数接口：get_code_info
功能描述：获取每日最新证券信息，交易日早上 9 点前更新当日最新
输入：
参数
数据类型
必选
解释
security_type
str  
否
代码类型 security_type（见附录），
默认为 EXTRA_STOCK_A（上交
所 A 股、深交所 A 股和北交所的股
票列表）
输出：

中国银河证券星耀数智服务平台金融资讯数据说明
8
参数
数据类型
解释
code_info
dataframe
index 为股票代码
column 为
symbol (证券简称)
pre_close (昨收价)
high_limited  (涨停价)
low_limited ( 跌停价)
price_tick (最小价格变动单位)

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_info = base_data_object.get_code_info(security_type='EXTRA_ETF')
3.5.2.2 每日最新代码表（沪深北）
交易日早上 9 点前更新
函数接口：get_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表
输入：
参数
数据类型
必选
解释
security_type
str  
否
代码类型 security_type（见附录），
默认为 EXTRA_STOCK_A（上交
所 A 股、深交所 A 股和北交所的股
票列表）
输出参数：   
返回值
数据类型
解释
code_list
list
证券代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
3.5.2.3 每日最新代码表（期货交易所）
交易日早上 9 点前更新
函数接口：get_future_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表

中国银河证券星耀数智服务平台金融资讯数据说明
9
输入：
参数
数据类型
必选
解释
security_type
str  
是
代码类型 security_type(期货交易
所)（见附录），默认为 EXTRA_FU
TURE（期货, 包含中金所/上期所/
大商所/郑商所/上海国际能源交易
中心所）
输出参数：   
返回值
数据类型
解释
code_list
list
证券代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_future_code_list(security_type='EXTRA_FUTURE')
3.5.2.4 每日最新代码表（期权）
交易日早上 9 点前更新
函数接口：get_option_code_list
功能描述：获取代码表（每日最新），此接口无法获取历史代码表
输入：
参数
数据类型
必选
解释
security_type
str  
是
代码类型 security_type 期权)（见附
录），默认为 EXTRA_ETF_OP（E
TF 期权, 包含上交所和深交所）
输出参数：   
返回值
数据类型
解释
code_list
list
证券代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_option_code_list(security_type='EXTRA_ETF_OP')
3.5.2.5 复权因子（后复权因子）
函数接口：BaseData.get_backward_factor
功能描述：获取复权因子数据并本地存储，复权因子为根据交易所行情数据计算得出的后复
权因子；

中国银河证券星耀数智服务平台金融资讯数据说明
10
输入参数：   
参数
数据类型
必选
解释
code_list
lis[str]
是
代码列表，支持股票、ETF
local_path
str  
是
本地存储复权因子数据的文件夹地址
is_local
Bool
是
是否使用本地存储的数据，默认为 True

注：
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

（2）is_local
True:  
本地 local_path 有数据的情况下，从本地取数据，但无法从服务端获取最新的数据
本地 local_path 无数据的情况下，从互联网取数据，并更新本地 local_path 的数据
False:从互联网取数据，并更新本地 local_path 的数据
输出：
参数
数据类型
解释
backward_factor
dataframe
index 为交易日期
column 为股票代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
backward_factor = base_data_object.get_backward_factor(code_list, local_path='D://AmazingData_local_data//',
is_local=False)
3.5.2.6 复权因子（单次复权因子）
函数接口：BaseData.get_adj_factor
功能描述：获取复权因子数据并本地存储，复权因子为根据交易所行情数据计算得出的后复
权因子；
输入参数：   
参数
数据类型
必选
解释
code_list
lis[str]
是
代码列表，支持股票、ETF
local_path
str  
是
本地存储复权因子数据的文件夹地址
is_local
Bool
是
是否使用本地存储的数据，默认为 True

注：
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

中国银河证券星耀数智服务平台金融资讯数据说明
11
（2）is_local
True:  
本地 local_path 有数据的情况下，从本地取数据，但有可能无法获取最新的数据
本地 local_path 无数据的情况下，从互联网取数据，并更新本地 local_path 的数据
False:从互联网取数据，并更新本地 local_path 的数据
输出：
参数
数据类型
解释
adj_factor
dataframe
index 为交易日期
column 为股票代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A')
adj_factor
=
base_data_object.get_adj_factor(code_list,
local_path='D://AmazingData_local_data//',
is_local=False)
3.5.2.7 历史代码表
函数接口：BaseData 的 get_hist_code_list
功能描述：获取历史代码表，先检查本地数据，再从服务端补充，最后返回数据输入参数：

输入参数：   
参数
数据类型
必选
解释
security_type
str  
是
默认为
"EXTRA_STOCK_A_SH_SZ"  沪深 A 股，支持
附录 security_type(沪深北)和 security_type(期货
交易所)，
start_date
int  
是
开始时间，闭区间
end_date
int  
是
结束时间，闭区间
local_path
str
是
本地存储数据的路径，需绝对路径，格式类似“
'D://AmazingData_local_data//'”
输出参数：   
返回值
数据类型
解释
code_list
List[str]
证券代码

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list
=
base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ',start_date=20240101,
end_date=20240701, local_path=local_path)

中国银河证券星耀数智服务平台金融资讯数据说明
12

3.5.2.8 交易日历
函数接口：get_calendar
功能描述：获取交易所的交易日历

输入参数：   
参数
数据类型
必选
解释
data_type
str  
否
选择返回数据的类型，默认为 str ，可选 datetime
或 str
market
str  
否
选择市场 market（见附录），默认为 SH（上海）

输出参数：   
返回值
数据类型
解释
calendar
List[int]
日期

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()                         
3.5.2.9 证券基础信息
函数接口：get_stock_basic
功能描述：获取指定股票列表的上市公司的证券基础数据，包含沪深北三个交易所，所有股
票（包含已退市标的）的中英文名称、上市日期、退市日期、上市板块等信息
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深北三个交易所的代码列表，可见
示例
输出参数：   
返回值
数据类型
解释
stock_basic
dataframe
column 为 stock_basic 的字段
index 为序号（无意义）
stock_basic 的字段说明：
参数
数据类型
必选
解释
MARKET_CODE
string
证券代码

SECURITY_NAME
string
证券简称

COMP_NAME
string
证券中文名称

PINYIN
string
中文拼音简称

中国银河证券星耀数智服务平台金融资讯数据说明
13
COMP_NAME_ENG
string
证券英文名称

LISTDATE
int
上市日期

DELISTDATE
int
退市日期

LISTPLATE_NAME
string
上市板块名称

COMP_SNAME_ENG
string
英文名称缩写

IS_LISTED
int
上市状态
1：上市交易
3：终止上市

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A_SH_SZ')   
stock_basic = info_data_object.get_stock_basic (code_list)                   
3.5.2.10
历史证券信息
函数接口：get_history_stock_status
功能描述：获取指定股票列表的上市公司的历史证券数据，以日度为频率，包含历史的涨跌
停、st、除权除息等信息
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
local_path
str  
是
本地存储数据的路径，需绝对路径，格式类
似“D://AmazingData_local_data//”
is_local
bool
否
默认为 True，本地数据缓存方案
begin_date
int
否
交易日，本地数据缓存方案
end_date
int
否
交易日，本地数据缓存方案

输出参数：   
返回值
数据类型
解释
history_stock_status
dataframe
column 为 history_stock_status 的字段
index 为序号（无意义）
history_stock_status 的字段说明：
参数
数据类型
必选
解释
MARKET_CODE
string
证券代码

TRADE_DATE
string
日期

PRECLOSE
float
前收价

HIGH_LIMITED
float
涨停价

LOW_LIMITED
float
跌停价

PRICE_HIGH_LMT_RATE
float
涨停价上限

PRICE_LOW_LMT_RATE
float
跌停价下限

中国银河证券星耀数智服务平台金融资讯数据说明
14
IS_ST_SEC
string
是否 ST
1 表示是，0 表示否
IS_SUSP_SEC
string
是否停牌
1 表示是，0 表示否
IS_WD_SEC
string
是否除息
1 表示是，0 表示否
IS_XR_SEC
string
是否除权
1 表示是，0 表示否

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ',
start_date=20130101,                              
end_date=today)
history_stock_status = info_data_object.get_history_stock_status(all_code_list)

3.5.2.11
北交所新旧代码对照表
函数接口：get_bj_code_mapping
功能描述：获取北交所的存量上市公司股票新旧代码对照表
输入参数：   
参数
数据类型
必选
解释
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

默认为 True，首选从本地读取，读取失败
再从服务器取数据
False，以本地数据为基础，增量从服务器
取数据
输出参数：
参数
数据类型
解释
bj_code_map
ping
dataframe
column 为 bj_code_mapping 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
bj_code_mapping = info_data_object.get_bj_code_mapping()       
bj_code_mapping 的字段说明：

中国银河证券星耀数智服务平台金融资讯数据说明
15
字段名称
类型
字段说明
OLD_CODE
string
旧代码
NEW_CODE
string
新代码
SECURITY_NAME
string
证券简称
LISTING_DATE
int
上市日期

3.5.3 实时行情数据
实时行情订阅接口使用步骤
（1） 实例化 AmazingData 的 SubscribeData
（2） 回调函数的装饰器传入 code_list(代码表)和 period(数据周期)两个参数
（3） 回调函数中获取数据
3.5.3.1 指数实时快照
函数接口：onSnapshotindex
功能描述：交易所指数快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持北交所、上交所、深交所
的指数  
period
Period
是
Period.snapshot.value

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
指数为 SnapshotIndex（见附录）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type=' EXTRA_INDEX_A')

# 实时订阅

sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotindex(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):

中国银河证券星耀数智服务平台金融资讯数据说明
16
print(period, data)
sub_data.run()

3.5.3.2 股票实时快照
函数接口：onSnapshot
功能描述：level-1 快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持北交所、上交所、深交所
的股票
period
Period
是
Period.snapshot.value

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
股票为 Snapshot（见附录）

# 第一步 登录 api

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
3.5.3.3 期货实时快照
函数接口：onSnapshotfuture
功能描述：level-1 快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持中金所/上期所/大商所/
郑商所/上海国际能源交易中心所
period
Period
是
Period.snapshotfuture.value

中国银河证券星耀数智服务平台金融资讯数据说明
17

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
期货为 SnapshotFuture（见附录）

# 第一步 登录 api

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
3.5.3.4 ETF 实时快照
函数接口：onSnapshotetf
功能描述：level-1 快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持上交所、深交所的 ETF
period
Period
是
Period.snapshot.value

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
ETF 为 Snapshot（见附录）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_ETF')

# 实时订阅

sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def onSnapshotetf(data: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):     
print(period, data)

中国银河证券星耀数智服务平台金融资讯数据说明
18
sub_data.run()

3.5.3.5 可转债实时快照
函数接口：onSnapshotkzz
功能描述：level-1 快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持上交所、深交所的可转债
period
Period
是
Period.snapshot.value

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
可转债为 Snapshot（见附录）

# 第一步 登录 api

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
3.5.3.6 港股通实时快照
函数接口：onSnapshothkt
功能描述：港股通快照数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持上交所、深交所的可转债
period
Period
是
Period.snapshotHKT.value

输出参数：入参需传入装饰器中 SubscribeData.register

中国银河证券星耀数智服务平台金融资讯数据说明
19

参数
数据类型
解释
data
Object
港股通为 SnapshotHKT（见附录）

# 第一步 登录 api

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
3.5.3.7 实时 K 线
函数接口：OnKLine
功能描述：K 线数据的实时订阅回调函数  
输入参数：入参需传入装饰器中 SubscribeData.register   
参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持北交所、上交所、深交
所的可转债、股票、指数、ETF 等品种
支持期货（中金所/上期所/大商所/郑商所/
上海国际能源交易中心所）
period
Period
是
Period（见附录）

输出参数：入参需传入装饰器中 SubscribeData.register

参数
数据类型
解释
data
Object
Kline（见附录）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A ')

# 实时订阅

sub_data = ad.SubscribeData()

# K 线

@sub_data.register(code_list=code_list, period=ad.constant.Period.min1.value)
def OnKLine(data: Union[ad.constant.Kline], period):

中国银河证券星耀数智服务平台金融资讯数据说明
20
print('OnKLine: ', data)
sub_data.run()                      
3.5.4 历史行情数据
（1） 实例化 AmazingData 的 MarketData，入参需交易日历
（2） 调用 MarketData 的方法获取数据

3.5.4.1 历史快照
函数接口：query_snapshot
功能描述：快照数据的历史数据查询接口
输入参数：
参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持北交所、上交所、深交
所的可转债、股票、指数、ETF、港股通
等、ETF 期权等品种
begin_date
int
是
日期，填写 8 位的整型格式的日期，比如
20240101
end_date
int
是
日期，填写 8 位的整型格式的日期，比如
20240201
begin_time
int
否
时分秒毫秒的时间戳，填写 8 位或 9 位的
整型格式的日期，时占一位或两位，分占
两位，秒占两位，毫秒占三位，例如 9 点
整
为 90000000, 17 点 25 分为 172500000
end_time
int
否
时分秒毫秒的时间戳，

输出参数：
参数
数据类型
解释
snapshot_dict
dict
指字典的 key：代码
字典的 value：dataframe，
column 为快照数据（指数为 SnapshotIndex（见附录），
股票、ETF 和可转债为 Snapshot（见附录），
港股通为 SnapshotHKT（见附录）），
ETF 期权为 SnapshotOption（见附录）），

index 为日期（datetime）

# 第一步 登录 api

import AmazingData as ad

中国银河证券星耀数智服务平台金融资讯数据说明
21
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A ')
calendar = base_data_object.get_calendar()
market_data_object=ad.MarketData(calendar)
snapshot_dict = market_data_object.query_snapshot(code_list, begin_date=20240530, end_date=20240530)                   
3.5.4.2 历史 K 线
函数接口：query_kline
功能描述：K 线数据的实时订阅回调函数 ，支持全部周期的 K 线数据查询
输入参数：
参数
数据类型
必选
解释
code_list
list:[str]
是
可传入列表，支持北交所、上交所、深交
所的可转债、股票、指数、ETF 等品种
支持期货（中金所/上期所/大商所/郑商所/
上海国际能源交易中心所）
begin_date
int
是
日期，填写 8 位的整型格式的日期，比如
20240101
end_date
int
是
日期，填写 8 位的整型格式的日期，比如
20240201
period
Period
是
数据周期 Period（见附录）
begin_time
int
否
时分的时间戳，填写 3 位或 4 位的整型格
式的日期，时占一位或两位，分占两位，，
例如 9 点整
为 900, 17 点 25 分为 1725
end_time
int
否
时分秒毫秒的时间戳，

输出参数：
参数
数据类型
解释
kline_dict
dict
字典的 key：代码
字典的 value：dataframe，
column 为 K 线数据 Kline（见附录），
index 为日期（datetime）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
base_data_object = ad.BaseData()
code_list = base_data_object.get_code_list(security_type='EXTRA_STOCK_A ')  
calendar = base_data_object.get_calendar()
market_data_object=ad.MarketData(calendar)

中国银河证券星耀数智服务平台金融资讯数据说明
22
kline_dict = market_data_object.query_kline (code_list, begin_date=20240530, end_date=20240530)                   
3.5.5 财务数据
3.5.5.1 资产负债表
函数接口：get_balance_sheet
功能描述：获取指定股票列表的上市公司的资产负债表数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
报告期，本地数据缓存方案
end_date
int
否
报告期，本地数据缓存方案

输出参数：
参数
数据类型
解释
balance_sheet
dict
key：code
value:dataframe
column 为 balance_sheet 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
balance_sheet = info_data_object.get_balance_sheet(all_code_list)           
balance_sheet 的字段说明：
字段名称
类型
字段说明
备注
MARKET_CODE
str
证券代码

SECURITY_NAME
str
证券简称

中国银河证券星耀数智服务平台金融资讯数据说明
23
STATEMENT_TYPE
str
报表类型
参看报表类型代码表
REPORT_TYPE
str
报告期名称
参看报告期名称
REPORTING_PERIOD
str
报告期

ANN_DATE
str
公告日期

ACTUAL_ANN_DATE
str
实际公告日期

ACC_PAYABLE
float
应付票据及应付账
款

ACC_RECEIVABLE
float
应收票据及应收账
款

ACC_RECEIVABLES
float
应收款项

ACCRUED_EXP
float
预提费用

ACCT_PAYABLE
float
应付账款

ACCT_RECEIVABLE
float
应收账款

ACT_TRADING_SEC
float
代理买卖证券款

ACT_UW_SEC
float
代理承销证券款

ADV_PREM
float
预收保费

ADV_RECEIPT
float
预收款项

AGENCY_ASSETS
float
代理业务资产

AGENCY_BUSINESS_LI
AB
float
代理业务负债

ANTICIPATION_LIAB
float
预计负债

ASSET_DEP_FUNDS_O
TH_FIN_INST
float
存放同业和其它金
融机构款项

BONDS_PAYABLE
float
应付债券

CAP_RESV
float
资本公积金

CAP_STOCK
float
股本
金额（元），公布值
CASH_CENTRAL_BAN
K_DEPOSITS
float
现金及存放中央银
行款项

CED_INSUR_CONT_RE
SERVES_RCV
float
应收分保合同准备
金

中国银河证券星耀数智服务平台金融资讯数据说明
24
CLAIMS_PAYABLE
float
应付赔付款

CLIENTS_FUND_DEPO
SIT
float
客户资金存款

CLIENTS_RESERVES
float
客户备付金

CNVD_DIFF_FOREIGN_
CURR_STAT
float
外币报表折算差额

COMP_TYPE_CODE
int
公司类型代码
1：非金融类 2：银行 3：
保险 4：证券
CONST_IN_PROC
float
在建工程

CONST_IN_PROC_TOT
AL
float
在建工程(合计)(元)

CONSUMP_BIO_ASSET
S
float
消耗性生物资产

CONT_ASSETS
float
合同资产
单位（元）
CONT_LIABILITIES
float
合同负债
单位（元）
CURRENCY_CAP
float
货币资金

CURRENCY_CODE
float
货币代码

DEBT_INV
float
债权投资(元)

DEFERRED_INC_NONC
UR_LIAB
float
递延收益-非流动负
债

DEFERRED_INCOME
float
递延收益

DEFERRED_TAX_ASSE
TS
float
递延所得税资产

DEFERRED_TAX_LIAB
float
递延所得税负债

DEP_RECEIVED_IB_DE
P
float
吸收存款及同业存
放

DEPOSIT_CAP_RECOG
float
存出资本保证金

DEPOSIT_TAKING
float
吸收存款

DEPOSITS_RECEIVED
float
存入保证金

DER_FIN_ASSETS
float
衍生金融资产

DERI_FIN_LIAB
float
衍生金融负债

中国银河证券星耀数智服务平台金融资讯数据说明
25
DEVELOP_EXP
float
开发支出

DISPOSAL_FIX_ASSET
S
float
固定资产清理

DIV_PAYABLE
float
应付股利

DIV_RECEIVABLE
float
应收股利

EMPL_PAY_PAYABLE
float
应付职工薪酬

ENGIN_MAT
float
工程物资

FIN_ASSETS_AVA_FOR
_SALE
float
可供出售金融资产

FIN_ASSETS_COST_SH
ARING
float
以摊余成本计量的
金融资产

FIN_ASSETS_FAIR_VAL
UE
float
以公允价值计量且
其变动计入其他综
合收益的金融资产

FIXED_ASSETS
float
固定资产

FIXED_ASSETS_TOTAL
float
固定资产(合计)(元)

FIXED_TERM_DEPOSIT
S
float
定期存款

GOODWILL
float
商誉

GUA_DEPOSITS_PAID
float
存出保证金

GUA_PLEDGE_LOANS
float
保户质押贷款

HOLD_ASSETS_FOR_S
ALE
float
持有待售的资产

HOLD_TO_MTY_INV
float
持有至到期投资

INC_PLEDGE_LOAN
float
其中:质押借款

INCL_TRADING_SEAT_
FEES
float
其中:交易席位费

IND_ACCT_ASSETS
float
独立账户资产

IND_ACCT_LIAB
float
独立账户负债

INSURED_DEPOSIT_IN
V
float
保户储金及投资款

INSURED_DIV_PAYABL
float
应付保单红利

中国银河证券星耀数智服务平台金融资讯数据说明
26
E
INT_RECEIVABLE
float
应收利息

INTANGIBLE_ASSETS
float
无形资产

INTEREST_PAYABLE
float
应付利息

INV
float
存货

INV_REALESTATE
float
投资性房地产

LEASE_LIABILITY
float
租赁负债

LEND_FUNDS
float
融出资金

LENDING_FUNDS
float
拆出资金

LESS_TREASURY_STK
float
减:库存股

LIA_HFS
float
持有待售的负债

LIAB_DEP_FUNDS_OT
H_FIN_INST
float
同业和其它金融机
构存放款项

LIFE_INSUR_RESV
float
寿险责任准备金

LOAN_CENTRAL_BAN
K
float
向中央银行借款

LOANS_AND_ADVANC
ES
float
发放贷款及垫款

LOANS_FROM_OTH_B
ANKS
float
拆入资金

LT_DEFERRED_EXP
float
长期待摊费用

LT_EMP_COMP_PAY
float
长期应付职工薪酬

LT_EQUITY_INV
float
长期股权投资

LT_HEALTH_INSUR_RE
SV
float
长期健康险责任准
备金

LT_LOAN
float
长期借款

LT_PAYABLE
float
长期应付款

LT_PAYABLE_TOTAL
float
长期应付款(合计)
(元)

LT_RECEIVABLES
float
长期应收款

MINORITY_EQUITY
float
少数股东权益

中国银河证券星耀数智服务平台金融资讯数据说明
27
NOM_RISKS_PREP
float
一般风险准备

NONCUR_ASSETS_DUE
_WITHIN_1Y
float
一年内到期的非流
动资产

NONCUR_LIAB_DUE_
WITHIN_1Y
float
一年内到期的非流
动负债

NOTES_PAYABLE
float
应付票据

NOTES_RECEIVABLE
float
应收票据

OIL_AND_GAS_ASSET
S
float
油气资产

OTH_COMP_INCOME
float
其他综合收益

OTH_EQUITY_TOOLS
float
其他权益工具

OTH_EQUITY_TOOLS_
PRE_SHR
float
其他权益工具:优先
股

OTH_NONCUR_ASSETS
float
其他非流动资产

OTHER_ASSETS
float
其他资产

OTHER_CUR_ASSETS
float
其他流动资产

OTHER_CUR_LIAB
float
其他流动负债

OTHER_DEBT_INV
float
其他债权投资(元)

OTHER_EQUITY_INV
float
其他权益工具投资
(元)

OTHER_LIAB
float
其他负债

OTHER_NONCUR_FIN_
ASSETS
float
其他非流动金融资
产(元)

OTHER_NONCUR_LIAB
float
其他非流动负债

OTHER_PAYABLE
float
其他应付款

OTHER_PAYABLE_TOT
AL
float
其他应付款(合计)
(元)

OTHER_RCV_TOTAL
float
其他应收款(合计)
（元）

OTHER_RECEIVABLE
float
其他应收款

OTHER_SUSTAIN_BON
D
float
其他权益工具:永续
债(元)

中国银河证券星耀数智服务平台金融资讯数据说明
28
OUT_LOSS_RESV
float
未决赔款准备金

PAYABLE
float
应付款项

PAYABLE_FOR_REINSU
RER
float
应付分保账款

PRECIOUS_METAL
float
贵金属

PREPAYMENT
float
预付款项

PROD_BIO_ASSETS
float
生产性生物资产

RCV_CED_CLAIM_RES
V
float
应收分保未决赔款
准备金

RCV_CED_LIFE_INSUR
_RESV
float
应收分保寿险责任
准备金

RCV_CED_LT_HEALTH
_INSUR_RESV
float
应收分保长期健康
险责任准备金

RCV_CED_UNEARNED
_PREM_RESV
float
应收分保未到期责
任准备金

RCV_FINANCING
float
应收款项融资

RCV_INV
float
应收款项类投资

RECEIVABLE_PREM
float
应收保费

RED_MON_CAP_FOR_S
ALE
float
买入返售金融资产

REINSURANCE_ACC_R
CV
float
应收分保账款

RSRV_FUND_INSUR_C
ONT
float
保险合同准备金

SELL_REPO_FIN_ASSE
TS
float
卖出回购金融资产
款

SERVICE_CHARGE_CO
MM_PAYABLE
float
应付手续费及佣金

SETTLE_FUNDS
float
结算备付金

SPE_ASSETS_BAL_DIF
F
float
资产差额(特殊报表
科目)

SPE_CUR_ASSETS_DIF
F
float
流动资产差额(特殊
报表科目)

中国银河证券星耀数智服务平台金融资讯数据说明
29
SPE_CUR_LIAB_DIFF
float
流动负债差额(特殊
报表科目)

SPE_LIAB_BAL_DIFF
float
负债差额(特殊报表
科目)

SPE_LIAB_EQUITY_BA
L_DIFF
float
负债及股东权益差
额(特殊报表项目)

SPE_NONCUR_ASSETS
_DIFF
float
非流动资产差额(特
殊报表科目)

SPE_NONCUR_LIAB_DI
FF
float
非流动负债差额(特
殊报表科目)

SPE_SHARE_EQUITY_B
AL_DIFF
float
股东权益差额(特殊
报表科目)

SPECIAL_PAYABLE
float
专项应付款

SPECIAL_RESV
float
专项储备

ST_BONDS_PAYABLE
float
应付短期债券

ST_BORROWING
float
短期借款

ST_FIN_PAYABLE
float
应付短期融资款

SUBR_RCV
float
应收代位追偿款

SURPLUS_RESV
float
盈余公积金

TAX_PAYABLE
float
应交税费

TOT_ASSETS_BAL_DIF
F
float
资产差额(合计平衡
项目)

TOT_CUR_ASSETS_DIF
F
float
流动资产差额(合计
平衡项目)

TOT_CUR_LIAB_DIFF
float
流动负债差额(合计
平衡项目)

TOT_LIAB_BAL_DIFF
float
负债差额(合计平衡
项目)

TOT_LIAB_EQUITY_BA
L_DIFF
float
负债及股东权益差
额(合计平衡项目)

TOT_NONCUR_ASSETS
float
非流动资产合计

TOT_NONCUR_ASSETS
_DIFF
float
非流动资产差额(合
计平衡项目)

中国银河证券星耀数智服务平台金融资讯数据说明
30
TOT_NONCUR_LIAB_D
IFF
float
非流动负债差额(合
计平衡项目)

TOT_SHARE
float
期末总股本
单位（股）
TOT_SHARE_EQUITY_
BAL_DIFF
float
股东权益差额(合计
平衡项目)

TOT_SHARE_EQUITY_
EXCL_MIN_INT
float
股东权益合计(不含
少数股东权益)

TOT_SHARE_EQUITY_I
NCL_MIN_INT
float
股东权益合计(含少
数股东权益)

TOTAL_ASSETS
float
资产总计

TOTAL_CUR_ASSETS
float
流动资产合计

TOTAL_CUR_LIAB
float
流动负债合计

TOTAL_LIAB
float
负债合计

TOTAL_LIAB_SHARE_E
QUITY
float
负债及股东权益总
计

TOTAL_NONCUR_LIAB
float
非流动负债合计

TRADING_FIN_LIAB
float
交易性金融负债

TRADING_FINASSETS
float
交易性金融资产

UNAMORTIZED_EXP
float
待摊费用

UNCONFIRMED_INV_L
OSS
float
未确认的投资损失

UNDISTRIBUTED_PRO
float
未分配利润

UNEARNED_PREM_RE
SV
float
未到期责任准备金

USE_RIGHT_ASSETS
float
使用权资产

3.5.5.2 现金流量表
函数接口：get_cash_flow
功能描述：获取指定股票列表的上市公司的现金流量表数据
输入参数：   
参数
数据类型
必选
解释

中国银河证券星耀数智服务平台金融资讯数据说明
31
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
报告期，本地数据缓存方案
end_date
int
否
报告期，本地数据缓存方案

输出参数：
参数
数据类型
解释
cash_flow
dict
key：code
value:dataframe
column 为 cash_flow 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
cash_flow = info_data_object.get_cash_flow (all_code_list)           
cash_flow 的字段说明：
字段名称
类型
字段说明
备注
MARKET_CODE
str
证券代码

SECURITY_NAM
E
str
证券简称

STATEMENT_TYP
E
str
报表类型
参看报表类
型代码表
REPORT_TYPE
str
报告期名称
参看报告期
名称
REPORTING_PERI
OD
str
报告期

ANN_DATE
str
公告日期

中国银河证券星耀数智服务平台金融资讯数据说明
32
ACTUAL_ANN_D
ATE
str
实际公告日期

ABSORB_CASH_
RECP_INV
double
吸收投资收到的现金

AMORT_INTAN_
ASSETS
double
无形资产摊销

AMORT_LT_DEFE
RRED_EXP
double
长期待摊费用摊销

BEG_BAL_CASH_
CASH_EQU
double
期初现金及现金等价物余额

CASH_END_BAL
double
现金的期末余额

CASH_FOR_CHA
RGE
double
支付手续费的现金

CASH_PAID_INSU
R_POLICY
double
支付保单红利的现金

CASH_PAID_INV
double
投资支付的现金

CASH_PAID_PUR
_CONST_FIOLTA
double
购建固定资产、无形资产和其他长期
资产支付的现金

CASH_PAY_CLAI
MS_OIC
double
支付原保险合同赔付款项的现金

CASH_PAY_DIST_
DIV_PRO_INT
double
分配股利、利润或偿付利息支付的现
金

CASH_PAY_EMPL
OYEE
double
支付给职工以及为职工支付的现金

CASH_PAY_FOR_
DEBT
double
偿还债务支付的现金

CASH_PAY_GOO
DS_SERVICES
double
购买商品、接受劳务支付的现金

CASH_RECE_BO
RROW
double
取得借款收到的现金

中国银河证券星耀数智服务平台金融资讯数据说明
33
CASH_RECE_ISS
UE_BONDS
double
发行债券收到的现金

CASH_RECP_INV
_INCOME
double
取得投资收益收到的现金

CASH_RECP_PRE
M_OIC
double
收到原保险合同保费取得的现金

CASH_RECP_REC
OV_INV
double
收回投资收到的现金

CASH_RECP_SG_
AND_RS
double
销售商品、提供劳务收到的现金

COMP_TYPE_CO
DE
str
公司类型代码
1：非金融类
2：银行 3：
保险 4：证券
CONV_CORP_BO
NDS_DUE_WITHI
N_1Y
double
一年内到期的可转换公司债券

CONV_DEBT_INT
O_CAP
double
债务转为资本

CREDIT_IMPAIR_
LOSS
double
信用减值损失

CURRENCY_COD
E
str
货币代码

DECR_DEFE_INC
_TAX_ASSETS
double
递延所得税资产减少

DECR_DEFERRE
D_EXPENSE
double
待摊费用减少

DECR_INVENTOR
Y
double
存货的减少

DECR_OPERA_RE
CEIVABLE
double
经营性应收项目的减少

DEPRE_FA_OGA_
PBA
double
固定资产折旧、油气资产折耗、生产
性生物资产折旧

中国银河证券星耀数智服务平台金融资讯数据说明
34
EFF_FX_FLUC_C
ASH
double
汇率变动对现金的影响

END_BAL_CASH_
CASH_EQU
double
期末现金及现金等价物余额

FINANCIAL_EXP
double
财务费用

FIXED_ASSETS_F
IN_LEASE
double
融资租入固定资产

FREE_CASH_FLO
W
double
企业自由现金流量

INCL_CASH_REC
P_SAIMS
double
其中:子公司吸收少数股东投资收到
的现金

INCL_DIV_PRO_P
AID_SMS
double
其中:子公司支付给少数股东的股利、
利润

INCR_ACCRUED_
EXP
double
预提费用增加

INCR_DEFE_INC_
TAX_LIAB
double
递延所得税负债增加

INCR_OPERA_PA
YABLE
double
经营性应付项目的增加

IND_NET_CASH_
FLOWS_OPERA_
ACT
double
间接法-经营活动产生的现金流量净
额

IND_NET_INCR_
CASH_AND_EQU
double
间接法-现金及现金等价物净增加额

INV_LOSS
double
投资损失

IS_CALCULATIO
N
int
是否计算报表

LESS_OPEN_BAL
_CASH
double
减:现金的期初余额

LESS_OPEN_BAL
_CASH_EQU
double
减:现金等价物的期初余额

中国银河证券星耀数智服务平台金融资讯数据说明
35
LOSS_DISP_FIOL
TA
double
处置固定、无形资产和其他长期资产
的损失

LOSS_FAIRVALU
E_CHG
double
公允价值变动损失

LOSS_FIXED_ASS
ETS
double
固定资产报废损失

NET_CASH_FLO
WS_FIN_ACT
double
筹资活动产生的现金流量净额

NET_CASH_FLO
WS_INV_ACT
double
投资活动产生的现金流量净额

NET_CASH_FLO
WS_OPERA_ACT
double
经营活动产生的现金流量净额

NET_CASH_PAID
_SOBU
double
取得子公司及其他营业单位支付的现
金净额

NET_CASH_REC_
SEC
double
代理买卖证券收到的现金净额

NET_CASH_RECP
_DISP_FIOLTA
double
处置固定资产、无形资产和其他长期
资产收回的现金净额

NET_CASH_RECP
_DISP_SOBU
double
处置子公司及其他营业单位收到的现
金净额

NET_CASH_RECP
_REINSU_BUS
double
收到再保业务现金净额

NET_INCR_BORR
_FUND
double
拆入资金净增加额

NET_INCR_BORR
_OFI
double
向其他金融机构拆入资金净增加额

中国银河证券星耀数智服务平台金融资讯数据说明
36
NET_INCR_CASH
_AND_CASH_EQ
U
double
现金及现金等价物净增加额

NET_INCR_CUS_
LOAN_ADV
double
客户贷款及垫款净增加额

NET_INCR_DEP_
CB_IB
double
存放央行和同业款项净增加额

NET_INCR_DEP_
CUS_AND_IB
double
客户存款和同业存放款项净增加额

NET_INCR_DISM
ANTLE_CAP
double
拆出资金净增加额

NET_INCR_DISP_
FAAS
double
处置可供出售金融资产净增加额

NET_INCR_DISP_
TFA
double
处置交易性金融资产净增加额

NET_INCR_INSU
RED_SAVE
double
保户储金净增加额

NET_INCR_INT_A
ND_CHARGE
double
收取利息和手续费净增加额

NET_INCR_LOAN
S_CENTRAL_BA
NK
double
向中央银行借款净增加额

NET_INCR_PLED
GE_LOAN
double
质押贷款净增加额

NET_INCR_REPU
_BUS_FUND
double
回购业务资金净增加额

NET_PROFIT
double
净利润

OTH_CASH_PAY_
INV_ACT
double
支付其他与投资活动有关的现金

OTH_CASH_PAY_
OPERA_ACT
double
支付其他与经营活动有关的现金

中国银河证券星耀数智服务平台金融资讯数据说明
37
OTH_CASH_RECP
_INV_ACT
double
收到其他与投资活动有关的现金

OTHER_ASSETS_
IMPAIR_LOSS
double
其他资产减值损失

OTHER_CASH_PA
Y_FIN_ACT
double
支付其他与筹资活动有关的现金

OTHER_CASH_R
ECP_FIN_ACT
double
收到其他与筹资活动有关的现金

OTHER_CASH_R
ECP_OPER_ACT
double
收到其他与经营活动有关的现金

OTHERS
double
其他（废弃）

PAY_ALL_TAX
double
支付的各项税费

PLUS_ASSETS_D
EPRE_PREP
double
加:资产减值准备

PLUS_END_BAL_
CASH_EQU
double
加:现金等价物的期末余额

RECP_TAX_REFU
ND
double
收到的税费返还

SPE_BAL_CASH_I
NFLOW_FIN_ACT
double
筹资活动现金流入差额

SPE_BAL_CASH_I
NFLOW_INV_AC
T
double
投资活动现金流入差额

SPE_BAL_CASH_I
NFLOW_OPERA_
ACT
double
经营活动现金流入差额

SPE_BAL_CASH_
OUTFLOW_FIN
double
筹资活动现金流出差额

SPE_BAL_CASH_
OUTFLOW_INV
double
投资活动现金流出差额

SPE_BAL_CASH_
OUTFLOW_OPER
double
经营活动现金流出差额

中国银河证券星耀数智服务平台金融资讯数据说明
38
A
SPE_BAL_NETCA
SH_INC_DIFF_IN
D
double
间接法-现金净增加额差额

SPE_BAL_NETCA
SH_INCR_DIFF
double
现金净增加额差额

SPE_BAL_NETCA
SH_OPERA_IND
double
间接法-经营活动现金流量净额差额

TOT_BAL_CASH_
INFLOW_FIN_AC
T
double
筹资活动现金流入差额

TOT_BAL_CASH_
INFLOW_INV_AC
T
double
投资活动现金流入差额

TOT_BAL_CASH_
INFLOW_OPERA_
ACT
double
经营活动现金流入差额

TOT_BAL_CASH_
OUTFLOW_FIN
double
筹资活动现金流出差额

TOT_BAL_CASH_
OUTFLOW_INV
double
投资活动现金流出差额

TOT_BAL_CASH_
OUTFLOW_OPER
A
double
经营活动现金流出差额

TOT_BAL_NETCA
SH_FLOW_FIN
double
筹资活动产生的现金流量净额差额

TOT_BAL_NETCA
SH_FLOW_INV
double
投资活动产生的现金流量净额差额

TOT_BAL_NETCA
SH_FLOW_OPER
A
double
经营活动产生的现金流量净额差额

中国银河证券星耀数智服务平台金融资讯数据说明
39
TOT_BAL_NETCA
SH_INC_DIFF_IN
D
double
间接法-现金净增加额差额

TOT_BAL_NETCA
SH_INCR_DIFF
double
现金净增加额差额

TOT_BAL_NETCA
SH_OPERA_IND
double
间接法-经营活动现金流量净额差额

TOT_CASH_INFL
OW_FIN_ACT
double
筹资活动现金流入小计

TOT_CASH_INFL
OW_INV_ACT
double
投资活动现金流入小计

TOT_CASH_INFL
OW_OPER_ACT
double
经营活动现金流入小计

TOT_CASH_OUTF
LOW_FIN_ACT
double
筹资活动现金流出小计

TOT_CASH_OUTF
LOW_INV_ACT
double
投资活动现金流出小计

TOT_CASH_OUTF
LOW_OPERA_AC
T
double
经营活动现金流出小计

UNCONFIRMED_I
NV_LOSS
double
未确认投资损失

USE_RIGHT_ASS
ET_DEP
double
使用权资产折旧

3.5.5.3 利润表
函数接口：get_income
功能描述：获取指定股票列表的上市公司的利润表数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
local_path
str  
是
本地存储数据的路径，需绝对路径，格式
类似“
'D://AmazingData_local_data//'

中国银河证券星耀数智服务平台金融资讯数据说明
40
”
is_local
bool
否
默认为 True，本地数据缓存方案
begin_date
int
否
报告期，本地数据缓存方案
end_date
int
否
报告期，本地数据缓存方案

输出参数：
参数
数据类型
解释
income
dict
key：code
value:dataframe
column 为 income 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
income = info_data_object.get_income (all_code_list)           
income 的字段说明：
字段名称
类型
字段说明
备注
MARKET_CODE
str
证券代码

SECURITY_NAME
str
证券简称

STATEMENT_TYP
E
str
报表类型
参看报表类型代码表
REPORT_TYPE
str
报告期名称
参看报告期名称
REPORTING_PERI
OD
str
报告期

ANN_DATE
str
公告日期

ACTUAL_ANN_DA
TE
str
实际公告日期

AMORT_COST_FI
N_ASSETS_EAR
float
以摊余成本计量的
金融资产终止确认
收益

ANN_DATE
str
公告日期

中国银河证券星耀数智服务平台金融资讯数据说明
41
BASIC_EPS
float
基本每股收益

BEG_UNDISTRIBU
TED_PRO
float
年初未分配利润

CAPITALIZED_CO
M_STOCK_DIV
float
转作股本的普通股
股利

COMMENTS
str
备注

COMMON_STOCK
_DIV_PAYABLE
float
应付普通股股利

COMP_TYPE_COD
E
str
公司类型代码
1：非金融类 2：银行 3：
保险 4：证券
CONTINUED_NET
_OPERA_PRO
float
持续经营净利润

CREDIT_IMPAIR_L
OSS
float
信用减值损失

CURRENCY_CODE
str
货币代码

DILUTED_EPS
float
稀释每股收益

DISTRIBUTIVE_PR
O
float
可分配利润

DISTRIBUTIVE_PR
O_SHAREHOLDER
float
可供股东分配的利
润

DIV_EXP_INSUR
float
保户红利支出

EBIT
float
息税前利润
正向法
EBITDA
float
息税折旧摊销前利
润

EMPLOYEE_WELF
ARE
float
职工奖金福利

END_NET_OPERA
_PRO
float
终止经营净利润

EXT_INSUR_CONT
_RSRV
float
提取保险责任准备
金

EXT_UNEARNED_
PREM_RES
float
提取未到期责任准
备金

FIN_EXP_INT_EXP
float
财务费用:利息费

中国银河证券星耀数智服务平台金融资讯数据说明
42
用
FIN_EXP_INT_INC
float
财务费用:利息收
入

GAIN_DISPOSAL_
ASSETS
float
资产处置收益

HANDLING_CHRG
_COMM_FEE
float
手续费及佣金收入

INCL_INC_INV_JV
_ENTP
float
其中:对联营企业
和合营企业的投资
收益

INCL_LESS_LOSS_
DISP_NCUR_ASSE
T
float
其中:减:非流动资
产处置净损失

INCL_REINSUR_P
REM_INC
float
其中:分保费收入

INCOME_TAX
float
所得税

INSUR_EXP
float
保险业务支出

INSUR_PREM
float
已赚保费

INTEREST_INC
float
利息收入

IS_CALCULATION
float
是否计算报表

LESS_ADMIN_EXP
float
减:管理费用

LESS_AMORT_CO
MPEN_EXP
float
减:摊回赔付支出

LESS_AMORT_INS
UR_CONT_RSRV
float
减:摊回保险责任
准备金

LESS_AMORT_REI
NSUR_EXP
float
减:摊回分保费用

LESS_ASSETS_IMP
AIR_LOSS
float
减:资产减值损失

LESS_BUS_TAX_S
URCHARGE
float
减:营业税金及附
加

LESS_FIN_EXP
float
减:财务费用

LESS_HANDLING_
CHRG_COMM_FE
float
减:手续费及佣金
支出

中国银河证券星耀数智服务平台金融资讯数据说明
43
E
LESS_INTEREST_E
XP
float
减:利息支出

LESS_NON_OPER
A_EXP
float
减:营业外支出

LESS_OPERA_COS
T
float
减:营业成本

LESS_REINSUR_P
REM
float
减:分出保费

LESS_SELLING_E
XP
float
减:销售费用

MARKET_CODE
str
证券代码

MIN_INT_INC
float
少数股东损益

NET_EXPOSURE_
HEDGING_GAIN
float
净敞口套期收益

NET_HANDLING_
CHRG_COMM_FE
E
float
手续费及佣金净收
入

NET_INC_EC_ASS
ET_MGMT_BUS
float
受托客户资产管理
业务净收入

NET_INC_SEC_BR
OK_BUS
float
代理买卖证券业务
净收入

NET_INC_SEC_UW
_BUS
float
证券承销业务净收
入

NET_INTEREST_I
NC
float
利息净收入

NET_PRO_AFTER_
DED_NR_GL
float
扣除非经常性损益
后净利润（扣除少
数股东损益）

NET_PRO_AFTER_
DED_NR_GL_COR
float
扣除非经常性损益
后的净利润(财务
重要指标(更正前))

NET_PRO_EXCL_
MIN_INT_INC
float
净利润(不含少数
股东损益)

中国银河证券星耀数智服务平台金融资讯数据说明
44
NET_PRO_INCL_M
IN_INT_INC
float
净利润(含少数股
东损益)

NET_PRO_UNDER
_INT_ACC_STA
float
国际会计准则净利
润

OPERA_EXP
float
营业支出

OPERA_PROFIT
float
营业利润

OPERA_REV
float
营业收入

OTH_ASSETS_IMP
AIR_LOSS
float
其他资产减值损失

OTH_BUS_COST
float
其他业务成本

OTH_BUS_INC
float
其他业务收入

OTH_COMPRE_IN
C
float
其他综合收益

OTH_INCOME
float
其他收益

OTH_NET_OPERA
_INC
float
其他经营净收益

PLUS_NET_FX_IN
C
float
加:汇兑净收益

PLUS_NET_GAIN_
CHG_FV
float
加:公允价值变动
净收益

PLUS_NET_INV_I
NC
float
加:投资净收益

PLUS_NON_OPER
A_REV
float
加:营业外收入

PLUS_OTH_NET_B
US_INC
float
加:其他业务净收
益

PREFERRED_SHA
RE_DIV_PAYABLE
float
应付优先股股利

PREM_BUS_INC
float
保费业务收入

RD_EXP
float
研发费用

REINSURANCE_E
XP
float
分保费用

REPORT_TYPE
str
报告期名称
参看报告期名称

中国银河证券星耀数智服务平台金融资讯数据说明
45
REPORTING_PERI
OD
str
报告期

SECURITY_NAME
str
证券简称

SPE_BAL_NET_PR
O_MARG
float
净利润差额(特殊
报表科目)

SPE_BAL_OPERA_
PRO_MARG
float
营业利润差额(特
殊报表科目)

SPE_BAL_TOT_OP
ERA_COST_DIF
float
营 业 总 成 本 差 额
(特殊报表科目)

SPE_BAL_TOT_OP
ERA_INC_DIF
float
营 业 总 收 入 差 额
(特殊报表科目)

SPE_BAL_TOT_PR
O_MARG
float
利润总额差额(特
殊报表科目)

SPE_TOT_OPERA_
COST_DIF_STATE
str
营业总成本差额说
明(特殊报表科目)

SPE_TOT_OPERA_
INC_DIF_STATE
str
营业总收入差额说
明(特殊报表科目)

SURR_VALUE
float
退保金

TOT_BAL_NET_PR
O_MARG
float
净利润差额(合计
平衡项目)

TOT_BAL_OPERA
_PRO_MARG
float
营业利润差额(合
计平衡项目)

TOT_BAL_TOT_PR
O_MARG
float
利润总额差额(合
计平衡项目)

TOT_COMPEN_EX
P
float
赔付总支出

TOT_COMPRE_IN
C
float
综合收益总额

TOT_COMPRE_IN
C_MIN_SHARE
float
综合收益总额(少
数股东)

TOT_COMPRE_IN
C_PARENT_COMP
float
综合收益总额(母
公司)

TOT_OPERA_COS
T
float
营业总成本

中国银河证券星耀数智服务平台金融资讯数据说明
46
TOT_OPERA_COS
T2
float
营业总成本 2

TOT_OPERA_REV
float
营业总收入

TOTAL_PROFIT
float
利润总额

TRANSFER_HOUSI
NG_REVO_FUNDS
float
住房周转金转入

TRANSFER_OTHE
RS
float
其他转入

TRANSFER_SURP
LUS_RESERVE
float
盈余公积转入

UNCONFIRMED_I
NV_LOSS
float
未确认投资损失

WITHDRAW_ANY
_SURPLUS_RESV
float
提取任意盈余公积
金

WITHDRAW_ENT_
DEVELOP_FUND
float
提取企业发展基金

WITHDRAW_LEG_
PUB_WEL_FUND
float
提取法定公益金

WITHDRAW_LEG_
SURPLUS
float
提取法定盈余公积

WITHDRAW_RESV
_FUND
float
提取储备基金

3.5.5.4 业绩快报
函数接口：get_profit_express
功能描述：获取指定股票列表的上市公司的业绩快报数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案

中国银河证券星耀数智服务平台金融资讯数据说明
47
begin_date
int
否
报告期，本地数据缓存方案
end_date
int
否
报告期，本地数据缓存方案

输出参数：
参数
数据类型
解释
profit_express
dataframe
column 为 profit_express 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
profit_express = info_data_object.get_profit_express (all_code_list)           
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
利 润 总 额
(元)
企业一定时期内的纯收入扣除应
交纳后的余额
OPERA_PROFIT
float64
营 业 利 润
(元)
企业在其全部销售业务中实现的
利润

中国银河证券星耀数智服务平台金融资讯数据说明
48
EPS_BASIC
float64
每 股 收 益 -
基本(元)
企业按照属于普通股股东的当期
净利润，除以发行在外普通股的
加权平均数计算得到的每股收益
TOT_SHARE_EQU
_EXCL_MIN_INT
float64
股东权益合
计 ( 不 含 少
数 股 东 权
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
%

中国银河证券星耀数智服务平台金融资讯数据说明
49
益
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

3.5.5.5 业绩预告
函数接口：get_profit_notice
功能描述：获取指定股票列表的上市公司的业绩预告数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
报告期，本地数据缓存方案
end_date
int
否
报告期，本地数据缓存方案

中国银河证券星耀数智服务平台金融资讯数据说明
50

输出参数：
参数
数据类型
解释
profit_notice
dataframe
column 为 profit_notice 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
profit_notice = info_data_object.get_profit_notice (all_code_list)           
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
float64
预告净利润上限
对于净利润金额预计的最高

中国银河证券星耀数智服务平台金融资讯数据说明
51
X
（万元）
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

3.5.6 股东股本数据
3.5.6.1 十大股东数据
函数接口：get_share_holder
功能描述：获取指定股票列表的上市公司的十大股东数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
到期日期，本地数据缓存方案
end_date
int
否
到期日期，本地数据缓存方案

输出参数：
参数
数据类型
解释
share_holder
dataframe
column 为 share_holder 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad

中国银河证券星耀数智服务平台金融资讯数据说明
52
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
share_holder = info_data_object.get_share_holder (all_code_list)           
share_holder 的字段说明：
参数
数 据 类
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
持 股 比 例
（%）,

HOLDER_SHARECAT
EGORYNAME
str
股份类型
当 HOLDER_TYPE 为 20:流通股
前十大股东时，全部为‘A Float
Holder’
FLOAT_QTY
float
流通股数量

3.5.6.2 股东户数
函数接口：get_holder_num
功能描述：获取指定股票列表的上市公司的股东户数数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
local_path
str  
是
本地存储数据的路径，需绝对路径，格式
类似“

中国银河证券星耀数智服务平台金融资讯数据说明
53
'D://AmazingData_local_data//'
”
is_local
bool
否
默认为 True，本地数据缓存方案
begin_date
int
否
股东户数统计的截止日期，本地数据缓存
方案
end_date
int
否
股东户数统计的截止日期，本地数据缓存
方案

输出参数：
参数
数据类型
解释
holder_num
dataframe
column 为 holder_num 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
holder_num = info_data_object.get_holder_num (all_code_list)           
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
3.5.6.3 股本结构
函数接口：get_equity_structure
功能描述：获取指定股票列表的上市公司的股本结构数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
local_path
str  
是
本地存储数据的路径，需绝对路径，格式

中国银河证券星耀数智服务平台金融资讯数据说明
54
类似“
'D://AmazingData_local_data//'
”
is_local
bool
否
默认为 True，本地数据缓存方案
begin_date
int
否
变动日期，本地数据缓存方案
end_date
int
否
变动日期，本地数据缓存方案

输出参数：
参数
数据类型
解释
equity_structu
re
dataframe
column 为 equity_structuree 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
equity_structure = info_data_object.get_equity_structure (all_code_list)           
equity_structure 的字段说明：  
字段名称
类型
字段说明
备注
MARKET_CODE
string
证券代码

ANN_DATE
string
公告日期

CHANGE_DATE
string
变动日期
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
1:是 0:否
IS_VALID
int
是否有效
用来区分除权日相同时，是
否为公司公告公布的最新股
份数
1:是 0:否
TOT_SHARE
float
总股本(万股)

FLOAT_SHARE
float
流通股(万股)

FLOAT_A_SHARE
float
流通 A 股(万股)

FLOAT_B_SHARE
float
流通 B 股(万股)

FLOAT_HK_SHARE
float
香港流通股(万股)

中国银河证券星耀数智服务平台金融资讯数据说明
55
FLOAT_OS_SHARE
float
海外流通股(万股)

TOT_TRADABLE_SHA
RE
float
流通股合计

RTD_A_SHARE_INST
float
限售 A 股(其他内资
持股:机构配售股)

RTD_A_SHARE_DOME
SNP
float
限售 A 股(其他内资
持股:境内自然人持
股)

RTD_SHARE_SENIOR
float
限售股 份 (高 管持
股)(万股)

RTD_A_SHARE_FOREI
GN
float
限售 A 股(外资持
股)

RTD_A_SHARE_FORJ
UR
float
限售 A 股(境外法人
持股)

RTD_A_SHARE_FORN
P
float
限售 A 股(境外自然
人持股)

RESTRICTED_B_SHAR
E
float
限售 B 股(万股)

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
股 : 战 略 投 资 者 持
股)

NTRD_SHARE_FUND
float
非流通股(境内法人
股:基金持股)

NTRD_SHARE_NAT
float
非流通 股 (自 然人
股)

TRAN_SHARE
float
转配股(万股)

FLOAT_SHARE_SENIO
float
流通股(高管持股)

中国银河证券星耀数智服务平台金融资讯数据说明
56
R
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
三板 A 股

OTCB_SHARE
float
三板 B 股

TOT_OTC_SHARE
float
三板合计

SHARE_HK
float
香港上市股

PRE_NON_TRADABLE
_SHARE
float
股改前非流通股

RESTRICTED_A_SHAR
E
float
限售 A 股(万股)

RTD_A_SHARE_STATE
float
限售 A 股(国家持
股)

RTD_A_SHARE_STATE
JUR
float
限售 A 股(国有法人
持股)

RTD_A_SHARE_OTHE
R_DOMES
float
限售 A 股(其他内资
持股)

RTD_A_SHARE_OTHE
R_DOMESJUR
float
限售 A 股(其他内资
持 股 : 境 内 法 人 持
股)

TOT_RESTRICTED_SH
ARE
float
限售股合计

3.5.6.4 股权冻结/质押
函数接口：get_equity_pledge_freeze
功能描述：获取指定股票列表的上市公司的股权冻结/质押数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
local_path
str  
是
本地存储数据的路径，需绝对路径，格式
类似“

中国银河证券星耀数智服务平台金融资讯数据说明
57
'D://AmazingData_local_data//'
”
is_local
bool
否
默认为 True，本地数据缓存方案
begin_date
int
否
公告日期，本地数据缓存方案
end_date
int
否
公告日期，本地数据缓存方案

输出参数：
参数
数据类型
解释
equity_pledge
_freeze
dict
key：code
value:dataframe
column 为 equity_pledge_freeze 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
equity_pledge_freeze = info_data_object.get_equity_pledge_freeze (all_code_list)           
equity_pledge_freeze 的字段说明：  
字段名称
类型
字段说明
备注
MARKET_CODE
string
证券代码

ANN_DATE
string
公告日期

HOLDER_NAME
string
股东名称

HOLDER_TYPE_C
ODE
int
股东类型代码
2:公司 3:个人
TOTAL_HOLDING
_SHR"
float
持股总数（万股）

TOTAL_HOLDING
_SHR_RATIO
float
持股总数占公司
总股本比例

FRO_SHARES
float
本次冻结/质押股
数

FRO_SHR_TO_TO
TAL_HOLDING_R
ATIO
float

本次冻结/质押占
所持股比例

中国银河证券星耀数智服务平台金融资讯数据说明
58
FRO_SHR_TO_TO
TAL_RATIO
float

本次冻结/质押占
总股本比例

TOTAL_PLEDGE_
SHR
float
累计冻结/质押股
数

IS_EQUITY_PLED
GE_REPO
int
是否股权质押回
购
1:是 0:否
BEGIN_DATE
string
冻结/质押起始日

END_DATE
string
解冻/解押日期

IS_DISFROZEN
int
是否质押或解冻
1:是 0:否
FROZEN_INSTITU
TION
string
执行冻结机构/质
权方

DISFROZEN_TIME
string
解压或解冻日期

SHR_CATEGORY_
CODE
int
股份性质类别代
码
1:法人股 2:个人股 3:国有
股 4:国有股,法人股 5:流通
股 6:流通股,限售流通股 7:
外资股 8:限售流通股 9:优
先
股                      
FREEZE_TYPE
int
冻结/质押类型
1:质押 2:司法 3:质押式回
购
3.5.6.5 限售股解禁
函数接口：get_equity_restricted
功能描述：获取指定股票列表的上市公司的限售股解禁数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
解禁日期，本地数据缓存方案
end_date
int
否
解禁日期，本地数据缓存方案

输出参数：
参数
数据类型
解释

中国银河证券星耀数智服务平台金融资讯数据说明
59
equity_restrict
ed
dict
key：code
value:dataframe
column 为 equity_restricted 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
equity_restricted = info_data_object.get_equity_restricted (all_code_list)           
equity_restricted 的字段说明：  
字段名称
类型
字段说明
备注
MARKET_CODE
string
证券代码

LIST_DATE
string
解禁日期

SHARE_RATIO
float
解禁股占总股本比
(%)

SHARE_LST_TYPE_NAM
E
string
解禁股份类型名称

SHARE_LST
int
解禁数量（股）

SHARE_LST_IS_ANN
int
上市数量是否公布
值
0 ： 否 ， 为 预 测
值 1: 是, 为实际
公布值
CLOSE_PRICE
float
前日收盘价（元）

SHARE_LST_MARKET_V
ALUE
float
解禁市值（元）
SHARE_LST* CL
OSE_PRICE

3.5.7 股东权益数据
3.5.7.1 分红数据
函数接口：get_dividend
功能描述：获取指定股票列表的上市公司的分红数据

中国银河证券星耀数智服务平台金融资讯数据说明
60
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
公告日期，本地数据缓存方案
end_date
int
否
公告日期，本地数据缓存方案

输出参数：
参数
数据类型
解释
dividend
dataframe
column 为 dividend 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
dividend = info_data_object.get_dividend(all_code_list)           
dividend 的字段说明：
字段名称
类型
字段说明
备注
MARKET_CODE
string
证券代码

DIV_PROGRESS
string
方案进度
参看股票分红进度代
码表
DVD_PER_SHARE_STK
float
每股送转

DVD_PER_SHARE_PRE_T
AX_CASH
float
每股派息(税前)(元)

DVD_PER_SHARE_AFTE
R_TAX_CASH
float
每股派息(税后)(元)

DATE_EQY_RECORD
string
股权登记日

DATE_EX
string
除权除息日

DATE_DVD_PAYOUT
string
派息日

LISTINGDATE_OF_DVD_
SHR
string
红股上市日

DIV_PRELANDATE
string
预案公告日
董事会预案公告日期
DIV_SMTGDATE
string
股东大会公告日

中国银河证券星耀数智服务平台金融资讯数据说明
61
DATE_DVD_ANN
string
分红实施公告日

DIV_BASEDATE
string
基准日期

DIV_BASESHARE
float
基准股本(万股)

CURRENCY_CODE
string
货币代码

ANN_DATE
string
公告日期

IS_CHANGED
int
方案是否变更
1：有变更过 0：未变
更
REPORT_PERIOD
string
分红年度

DIV_CHANGE
string
方案变更说明

DIV_BONUSRATE
float
每股送股比例

DIV_CONVERSEDRATE
float
每股转增比例

REMARK
string
备注

DIV_PREANN_DATE
string
预案预披露公告日
股东提议的公告日期
DIV_TARGET
string
分红对象

3.5.7.2 配股数据
函数接口：get_right_issue
功能描述：获取指定股票列表的上市公司的配股数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
公告日期，本地数据缓存方案
end_date
int
否
公告日期，本地数据缓存方案

输出参数：
参数
数据类型
解释
right_issue
dataframe
column 为 right_issue 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]

中国银河证券星耀数智服务平台金融资讯数据说明
62
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
right_issue = info_data_object.get_right_issue(all_code_list)           
right_issue 的字段说明：  
字段名称
类型
字段说明
备注
MARKET_CODE
string
证券代码

PROGRESS
int
方案进度
参看股票配股进度代
码表
PRICE
double
配股价格(元)

RATIO
double
配股比例

AMT_PLAN
double
配股计划数量(万股)

AMT_REAL
double
配股实际数量(万股)

COLLECTION_FUND
double
募集资金(元)

SHAREB_REG_DATE
string
股权登记日

EX_DIVIDEND_DATE
string
除权日

LISTED_DATE
string
配股上市日

PAY_START_DATE
string
缴款起始日

PAY_END_DATE
string
缴款终止日

PREPLAN_DATE
string
预案公告日

SMTG_ANN_DATE
string
股东大会公告日

PASS_DATE
string
发审委通过公告日

APPROVED_DATE
string
证监会核准公告日

EXECUTE_DATE
string
配股实施公告日

RESULT_DATE
string
配股结果公告日

LIST_ANN_DATE
string
上市公告日

GUARANTOR
string
基准年度

GUARTYPE
double
基准股本(万股)

RIGHTSISSUE_CODE
string
配售代码

ANN_DATE
string
公告日期

RIGHTSISSUE_YEAR
string
配股年度

RIGHTSISSUE_DESC
string
配股说明

RIGHTSISSUE_NAME
string
配股简称

RATIO_DENOMINATO
R
double
配股比例分母

RATIO_MOLECULAR
double
配股比例分子

SUBS_METHOD
string
认购方式

EXPECTED_FUND_RA
ISING
double
预计募集资金(元)

中国银河证券星耀数智服务平台金融资讯数据说明
63
3.5.8 融资融券数据
3.5.8.1 融资融券成交汇总
函数接口：get_margin_summary
功能描述：获取指定股票列表的上市公司的融资融券成交数据
输入参数：   
参数
数据类型
必选
解释
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
默认为 True，本地数据缓存方案
begin_date
int
否
交易日，本地数据缓存方案
end_date
int
否
交易日，本地数据缓存方案

输出参数：
参数
数据类型
解释
margin_summ
ary
dataframe
column 为 margin_summary 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
margin_summary = info_data_object.get_margin_summary()           
margin_summary 的字段说明：
字段名称
类型
字段说明
TRADE_DATE
string
交易日期
SUM_BORROW_MONEY_BALANCE
float
融资余额(元)
SUM_PURCH_WITH_BORROW_MONEY
float
融资买入额(元)
SUM_REPAYMENT_OF_BORROW_MONE
Y
float
融资偿还额(元)
SUM_SEC_LENDING_BALANCE
float
融券余额(元)
SUM_SALES_OF_BORROWED_SEC
int
融券卖出量(股,份,手)
SUM_MARGIN_TRADE_BALANCE
float
融资融券余额(元)

中国银河证券星耀数智服务平台金融资讯数据说明
64
3.5.8.2 融资融券交易明细
函数接口：get_margin_detail
功能描述：获取指定股票列表的上市公司的融资融券交易明细数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
交易日，本地数据缓存方案
end_date
int
否
交易日，本地数据缓存方案

输出参数：
参数
数据类型
解释
margin_detail
dict
key：code
value:dataframe
column 为 margin_detail 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
margin_detail = info_data_object.get_margin_detail(all_code_list)           
margin_detail 的字段说明：
字段名称
类型
字段说明
MARKET_CODE
string
证券代码
SECURITY_NAME
string
证券简称
TRADE_DATE
string
交易日期
BORROW_MONEY_BALANCE"
float
融资余额(元)
PURCH_WITH_BORROW_MON
EY
float
融资买入额(元)

中国银河证券星耀数智服务平台金融资讯数据说明
65
REPAYMENT_OF_BORROW_MO
NEY
float
融资偿还额(元)
SEC_LENDING_BALANCE
float
融券余额(元)
SALES_OF_BORROWED_SEC
int
融券卖出量(股,份,手)
REPAYMENT_OF_BORROW_SE
C
int
融券偿还量(股,份,手)
SEC_LENDING_BALANCE_VOL
int
融券余量(股,份,手)
MARGIN_TRADE_BALANCE
float
融资融券余额(元)

3.5.9 交易异动数据
3.5.9.1 龙虎榜
函数接口：get_long_hu_bang
功能描述：获取指定股票列表的上市公司的龙虎榜数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
交易日，本地数据缓存方案
end_date
int
否
交易日，本地数据缓存方案

输出参数：
参数
数据类型
解释
long_hu_bang
dataframe
column 为 long_hu_bang 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]

中国银河证券星耀数智服务平台金融资讯数据说明
66
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
long_hu_bang = info_data_object.get_long_hu_bang(all_code_list)           
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
上 榜 原 因 类
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
买 入 金 额
（元）

SELL_AMOUNT
float
卖 出 金 额
（元）

FLOW_MARK
int
买卖表示
1 表示买入，2 表示卖出
TOTAL_AMOUNT
float
实 际 交 易 金
额（元）

TOTAL_VOLUME
float
实 际 交 易 量
（万股）

3.5.9.2 大宗交易   
函数接口：get_block_trading
功能描述：获取指定股票列表的大宗交易数据
输入参数：   
参数
数据类型
必选
解释
code_list
list[str]  
是
支持沪深 A 的的代码列表，可见示例
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
默认为 True，本地数据缓存方案
begin_date
int
否
交易日，本地数据缓存方案

中国银河证券星耀数智服务平台金融资讯数据说明
67
end_date
int
否
交易日，本地数据缓存方案

输出参数：
参数
数据类型
解释
block_trading
dataframe
column 为 block_trading 的字段
index 为序号（无意义）

# 第一步 登录 api

import AmazingData as ad
ad.login(username='username', password='password',host='***.***.***.***',port=****)
info_data_object = ad.InfoData()
base_data_object = ad.BaseData()
calendar = base_data_object.get_calendar()
today = calendar[-1]
all_code_list = base_data_object.get_hist_code_list(security_type='EXTRA_STOCK_A_SH_SZ', start_date=20130101,           
end_date=today)
block_trading = info_data_object. block_trading (all_code_list)           
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

4. 附录
   4.1 字段取值说明
   4.1.1 代码类型 security_type(沪深北)
   数据类型
   枚举值
   说明

中国银河证券星耀数智服务平台金融资讯数据说明
68
str
EXTRA_STOCK_A
上交所 A 股、深交所 A 股和北交所的股票列表
str
SH_A
上交所 A 股的股票列表
str
SZ_A
深交所 A 股的股票列表
str
BJ_A
北交所的股票列表
str
EXTRA_STOCK_A_SH_SZ
上交所 A 股和深交所 A 股的股票列表
str
EXTRA_INDEX_A_SH_SZ
上交所和深交所指数列表
str
EXTRA_INDEX_A
上交所、深交所和北交所的指数列表
str
SH_INDEX
上交所指数列表
str
SZ_INDEX
深交所指数列表
str
BJ_INDEX
北交所的指数列表
str
SH_ETF
上交所的 ETF 列表
str
SZ_ETF
深交所的 ETF 列表
str
EXTRA_ETF
上交所、深交所的 ETF 列表
str
SH_KZZ
上交所的可转债列表
str
SZ_KZZ
深交所的可转债列表
str
EXTRA_KZZ
上交所、深交所的可转债列表
str
SH_HKT
沪港通
str
SZ_HKT
深港通
str
EXTRA_ HKT
沪深港通
4.1.2 代码类型 security_type(期货交易所)
数据类型
枚举值
说明
str
EXTRA_FUTURE
期货, 包含中金所/上期所/大商所/郑商所/上海
国际能源交易中心所
str
ZJ_FUTURE
期货, 包含中金所
str
SQ_FUTURE
期货, 包含上期所
str
DS_FUTURE
期货, 包含大商所
str
ZS_FUTURE
期货, 包含郑商所
str
SN_FUTURE
期货, 包含海国际能源交易中心所
4.1.3 代码类型 security_type(期权)
数据类型
枚举值
说明
str
EXTRA_ETF_OP
ETF 期权, 上交所/深交所
str
SH_OPTION
ETF 期货, 包含上交所
str
SZ_OPTION
ETF 期货, 包含深交所
4.1.4 市场类型 market

中国银河证券星耀数智服务平台金融资讯数据说明
69
数据类型
枚举值
说明
str
SH
上交所
str
SZ
深交所
str
BJ
北交所
str
SHF
上期所
str
CFE
中金所
str
DCE
大商所
str
CZC
郑商所
str
INE
上海国际能源交易中心所
str
SHN
深港通
str
SZN
深港通
4.1.5 交易阶段代码 trading_phase_code
（1） 上海现货快照交易状态
该字段为 8 位字符数组,左起每位表示特定的含义,无定义则填空格。
第 0 位: ‘S’表示启动(开市前)时段,‘C’表示开盘集合竞价时段,‘T’表示连续交易时段,‘E’表示
闭市时段,‘P’表示产品停牌。
第 1 位: ‘0’表示此产品不可正常交易,‘1’表示此产品可正常交易。
第 2 位: ‘0’表示未上市,‘1’表示已上市。
第 3 位: ‘0’表示此产品在当前时段不接受进行新订单申报,‘1’ 表示此产品在当前时段可接受
进行新订单申报。

（2） 深圳现货快照交易状态
第 0 位: ‘S’= 启动(开市前)‘O’= 开盘集合竞价‘T’= 连续竞价‘B’= 休市‘C’= 收盘集合竞价
‘E’= 已闭市‘H’= 临时停牌‘A’= 盘后交易‘V’=波动性中断。
第 1 位: ‘0’= 正常状态 ‘1’= 全天停牌。交易阶段代码

（3） 港股股票行情交易状态
‘1’表示正常交易，‘2’表示停牌，‘3’表示复牌
（4） 上海期权快照交易状态
第 1 位： ‘S’表示启动（开市前）时段， ‘C’表示集合竞价时段，
‘T’表示连续交易时段， ‘B’
表示休市时段， ‘E’表示闭市时段， ‘V’表示波动性中断， ‘P’表示临时停牌、 ‘U’表示收
盘集合竞价。 ‘M’表示可恢复交易的熔断（盘中集合竞价） ,‘N’表示不可恢复交易的熔断
（暂停交易至闭市）；
第 2 位： ‘0’表示未连续停牌，‘1’表示连续停牌。（预留，暂填空格）；
第 3 位： ‘0’表示不限制开仓，‘1’表示限制备兑开仓， ‘2’表示卖出开仓， ‘3’表示限制卖
出开仓、备兑开仓， ‘4’表示限制买入开仓， ‘5’表示限制买入开仓、备兑开仓， ‘6’表示限
制买入开仓、卖出开仓， ‘7’表示限制买入开仓、卖出开仓、备兑开仓；
第 4 位： ‘0’表示此产品在当前时段不接受进行新订单申报，‘1’ 表示此产品在当前时段可
接受进行新订单申报。

中国银河证券星耀数智服务平台金融资讯数据说明
70
4.1.6 数据周期 Period
数据类型
枚举值
说明
int
Period.min1.value
1 分钟线
int
Period.min3.value
3 分钟线
int
Period.min5.value
5 分钟线
int
Period.min10.value
10 分钟线
int
Period.min15.value
15 分钟线
int
Period.min30.value
30 分钟线
int
Period.min60.value
60 分钟线
int
Period.min120.value
120 分钟线
int
Period.day.value
日线
int
Period.week.value
周线
int
Period.month.value
月线
int
Period.season.value
季度线
int
Period.year.value
年线
4.1.7 报告期名称 REPORT_TYPE
报告期类型代码
报告期月份
1
3 月
2
6 月
3
9 月
4
12 月

4.1.8 报表类型代码表 STATEMENT_TYPE
报表类型代码
报表类型
备注
1
合并报表
涵盖母公司的财务报表数据，为最新报表
2
合并报表(单季
度)
合并报表(单季度)=合并报表(本期)-合并报表(上一季)
3
合并报表(单季
度调整)
合并报表(单季度调整)=合并报表(本期调整)-合并报表
(上一季调整)
4
合并报表(调整)
本年度公布上年同期的财务报表数据，报告期为上年度
5
合并报表(更正
前)
即出更正公告后，把合并报表的记录修改为合并报表(更
正前)；复制原来的记录，更正后报表类型改为合并报表
6
母公司报表
该公司母公司的财务报表数据
7
母公司报表(单
季度)
母公司报表(单季度)=母公司报表(本期)-母公司报表(上
一季)
8
母公司报表(单
母公司报表(单季度调整)=母公司报表(本期调整)-母公

中国银河证券星耀数智服务平台金融资讯数据说明
71
季度调整)
司报表(上一季调整)
9
母公司报表(调
整)
该公司母公司的本年度公布上年同期的财务报表数据
10
母公司报表(更
正前)
之前上市公司已披露财务报表数据，但是由于某些特定
原因导致出错，未调整之前的原始财务报表数据。
11
合并报表(未公
开)
未在公开信息源披露的财报且加工为合并报表口径
12
合并报表(调整
未公开)
未在公开信息源披露的财报且加工为合并报表调整口径
13
合并报表(单季
度未公开)
未在公开信息源披露的财报且加工为合并报表单季度口
径
14
合并报表(单季
度调整未公开)
未在公开信息源披露的财报且加工为母公司报表口径
15
母公司报表(未
公开)
未在公开信息源披露的财报且加工为母公司报表口径
16
母公司报表(调
整未公开)
未在公开信息源披露的财报且加工为母公司报表调整口
径
17
母公司报表(单
季度未公开)
未在公开信息源披露的财报且加工或计算为母公司报表
单季度口径
18
母公司报表(单
季 度 调 整 未 公
开)
未在公开信息源披露的财报且加工或计算为母公司报表
单季度调整口径
19
合并报表(调整
借壳前)
借壳前的合并报表(调整)
20
合并调整
对合并前各公司的财务报表进行调整，以确保合并财务
报表的准确性和可比性
21
合并报表(单季
度借壳前)
借壳前的合并报表(单季度)
22
合并报表(单季
度调整借壳前)
借壳前的合并报表(单季度调整)
23
母公司报表(借
壳前)
借壳前的母公司报表
24
母公司报表(调
整借壳前)
借壳前的母公司报表(调整)
25
母公司报表(单
季度借壳前)
借壳前的母公司报表(单季度)
26
母公司报表(单
季 度 调 整 借 壳
前)
借壳前的母公司报表(单季度调整)
27
合并报表(第一
次更正)
有多次更正时，合并报表的第一次更正
28
合并报表(第二
次更正)
有多次更正时，合并报表的第二次更正
29
合并调整(第一
有多次更正时，合并调整的第一次更正

中国银河证券星耀数智服务平台金融资讯数据说明
72
次更正)
30
合并报表(单月
度)
根据披露的券商月报公告加工为合并报表口径
31
合并调整(第二
次更正)
有多次更正时，合并调整的第二次更正
32
母公司调整(第
二次更正)
有多次更正时，母公司调整的第二次更正
33
母公司调整(第
一次更正)
有多次更正时，母公司调整的第一次更正
34
母公司报表(第
二次更正)
有多次更正时，母公司报表的第二次更正
35
母公司报表(第
一次更正)
有多次更正时，母公司报表的第一次更正
36
合并报表(第三
次更正)
有多次更正时，合并报表的第三次更正
37
合并调整(第三
次更正)
有多次更正时，合并调整的第三次更正
38
母公司报表(第
三次更正)
有多次更正时，母公司报表的第三次更正
39
母公司调整(第
三次更正)
有多次更正时，母公司调整的第三次更正
40
母公司报表(单
月度)
根据披露的券商月报公告加工为母公司报表口径的数据
41
合并报表(业绩
快报)
加工业绩快报中的财务数据（海外数据专用）
42
合并调整(第一
次)
第一次合并调整数据
43
合并调整(第二
次)
第二次合并调整数据
44
合并调整(第三
次)
第三次合并调整数据
45
合并报表(第四
次更正)
有多次更正时，合并报表的第四次更正
46
合并调整(第四
次更正)
有多次更正时，合并调整的第四次更正
47
母公司报表(第
四次更正)
有多次更正时，母公司报表的第四次更正
48
母公司调整(第
四次更正)
有多次更正时，母公司调整的第四次更正
50
合并调整(更正
前)
即出更正公告后，把合并报表（调整）的记录修改为合
并调整(更正前)；复制原来的记录，更正后报表类型改
为合并报表(调整)
51
合并报表(下半
年报)
合并下半年度的报表

中国银河证券星耀数智服务平台金融资讯数据说明
73
60
母公司调整(更
正前)
该公司母公司的本年度公布上年同期的财务报表数据，
但是由于某些特定原因导致出错，未调整之前的原始财
务报表数据。
70
合并报表(借壳
前)
公司主体在借壳上市前披露或者计算的为合并报表口径
的报表类型
80
合并报表(预测)
REITS 基金的定期报告中披露的预测的合并报表数据
81
合并报表(公司
预测)

90
项目资产报表
由项目资产管理人编制的一种财务报表，用于反映项目
资产的财务状况和经营情况
91
合并报表(日历
年)

4.1.9 股票分红进度代码表 DIV_PROGRESS
分红进度描述
进度代码
董事会预案
1
股东大会通过
2
实施
3
未通过
4
停止实施
12
股东提议
17
董事会预案预披露
19
分红实施进程：股东提议--董事会预案--股东大会--实施
4.1.10 股票配股进度代码表 PROGRESS
配股进度描述
进度代码
董事会预案
1
股东大会通过
2
实施
3
未通过
4
证监会核准
5
达成转让意向
6
签署转让协议
7
国资委批准
8
商务部批准
9
过户
10
延期实施
11
停止实施
12
分红方案待定
13

中国银河证券星耀数智服务平台金融资讯数据说明
74
传闻
14
证监会受理
15
传闻被否认
16
股东提议
17
保监会批复
18
董事会预案预披露
19
发审委通过
20
发审委未通过
21
股东大会未通过
22
银监会批准
23
证监会恢复审核
24
预发行
25
提交注册
26

4.2 数据结构说明
4.2.1 Level-1 快照 Snapshot
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
卖 1 档价格
float
ask_price2
卖 2 档价格
float
ask_price3
卖 3 档价格
float
ask_price4
卖 4 档价格
float
ask_price5
卖 5 档价格
int
ask _volume1
卖 1 档量

中国银河证券星耀数智服务平台金融资讯数据说明
75
int
ask _volume2
卖 2 档量
int
ask _volume3
卖 3 档量
int
ask _volume4
卖 4 档量
int
ask _volume5
卖 5 档量
float
bid_price1
买 1 档价格
float
bid_price2
买 2 档价格
float
bid_price3
买 3 档价格
float
bid_price4
买 4 档价格
float
bid_price5
买 5 档价格
int
bid _volume1
买 1 档量
int
bid _volume2
买 2 档量
int
bid _volume3
买 3 档量
int
bid _volume4
买 4 档量
int
bid _volume5
买 5 档量
float
iopv
净值估产（仅基金品种有效）
str
trading_phase_code
交易阶段代码
4.2.2 ETF 期权快照 SnapshotOption      
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
卖 1 档价格
float
ask_price2
卖 2 档价格
float
ask_price3
卖 3 档价格
float
ask_price4
卖 4 档价格

中国银河证券星耀数智服务平台金融资讯数据说明
76
float
ask_price5
卖 5 档价格
int
ask _volume1
卖 1 档量
int
ask _volume2
卖 2 档量
int
ask _volume3
卖 3 档量
int
ask _volume4
卖 4 档量
int
ask _volume5
卖 5 档量
float
bid_price1
买 1 档价格
float
bid_price2
买 2 档价格
float
bid_price3
买 3 档价格
float
bid_price4
买 4 档价格
float
bid_price5
买 5 档价格
int
bid _volume1
买 1 档量
int
bid _volume2
买 2 档量
int
bid _volume3
买 3 档量
int
bid _volume4
买 4 档量
int
bid _volume5
买 5 档量
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

4.2.3 期货快照 SnapshotFuture      
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

中国银河证券星耀数智服务平台金融资讯数据说明
77
float
ask_price1
卖 1 档价格
float
ask_price2
卖 2 档价格
float
ask_price3
卖 3 档价格
float
ask_price4
卖 4 档价格
float
ask_price5
卖 5 档价格
int
ask _volume1
卖 1 档量
int
ask _volume2
卖 2 档量
int
ask _volume3
卖 3 档量
int
ask _volume4
卖 4 档量
int
ask _volume5
卖 5 档量
float
bid_price1
买 1 档价格
float
bid_price2
买 2 档价格
float
bid_price3
买 3 档价格
float
bid_price4
买 4 档价格
float
bid_price5
买 5 档价格
int
bid _volume1
买 1 档量
int
bid _volume2
买 2 档量
int
bid _volume3
买 3 档量
int
bid _volume4
买 4 档量
int
bid _volume5
买 5 档量
float
average_price
当日均价
float
settle
本次结算价

4.2.4 指数快照 SnapshotIndex
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
4.2.5 港股通快照 SnapshotHKT
数据类型
字段名称
说明

中国银河证券星耀数智服务平台金融资讯数据说明
78
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
卖 1 档价格
float
ask_price2
卖 2 档价格
float
ask_price3
卖 3 档价格
float
ask_price4
卖 4 档价格
float
ask_price5
卖 5 档价格
int
ask _volume1
卖 1 档量
int
ask _volume2
卖 2 档量
int
ask _volume3
卖 3 档量
int
ask _volume4
卖 4 档量
int
ask _volume5
卖 5 档量
float
bid_price1
买 1 档价格
float
bid_price2
买 2 档价格
float
bid_price3
买 3 档价格
float
bid_price4
买 4 档价格
float
bid_price5
买 5 档价格
int
bid _volume1
买 1 档量
int
bid _volume2
买 2 档量
int
bid _volume3
买 3 档量
int
bid _volume4
买 4 档量
int
bid _volume5
买 5 档量
str
trading_phase_code
交易阶段代码

中国银河证券星耀数智服务平台金融资讯数据说明
79
4.2.6 K 线 Kline  
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
4.3 相关算法说明
4.3.1 商品期货查询算法
当查询非中金所（大商所、郑商所、上期所、上期能源）的商品期货快照时，因涉及夜
盘快照，需根据查询时间参数做相应区分，查询上以 20:00 作为夜盘的分割时间点，处理
逻辑见下表。
归属 T-1 日范围 20:00:00.000~23:59:59.999
归属 T 日范围：00:00:00.000~19:59:59.999
TGW 上 送 日
期
开始时间
结束时间
系统响应逻辑
20220407
093000000
150000000
开始、结束时间均归属 T 日，且开始时间
<结束时间，为有效查询，返回[4 月 7 日
9:30, 4 月 7 日 15:00]的数据
20220407
200000000
235900000
开始、结束时间均归属 T-1 日，且开始时
间<结束时间，为有效查询，返回[4 月 6
日 20:00, 4 月 6 日 23:59]的数据
20220407
200000000
010000000
开始时间归属 T-1 日，结束时间归属 T 日，
为有效查询，返回[4 月 6 日 20:00,4 月 7
日 01:00]的数据
正常周一（未
跨 法 定 假 节
日）
235959999
030000000
开始时间归属 T-1 日，结束时间归属 T 日，
为有效查询，返回[周五 23:59:59.999,周一
03:00]的数据，需包括周末的数据（部分
品种周六 0 点~02:30 会有行情）
特殊日（跨法
定假节日）
200000000
010000000
开始时间归属 T-1 日，结束时间归属 T 日，
为有效查询，返回[T-1 日 20:00,T 日 01:00]
的数据
20220407
230000000
200000000
开始、结束时间均归属 T-1 日，但开始时
间>结束时间，为无效查询，无数据返回，
并需弹出相应告警

中国银河证券星耀数智服务平台金融资讯数据说明
80
20220407
030000000
010000000
开始、结束时间均归属 T 日，但开始时间>
结束时间，为无效查询，无数据返回，并
需弹出相应告警
20220407
030000000
230000000
开始时间归属 T 日，结束时间归属 T-1 日，
为无效查询，无数据返回，并需弹出相应
告警
4.3.2 K 线算法说明
（1） 集合竞价的处理
对于分钟 K 线，开盘集合竞价数据的成交量包含在当日第一根 K 线，收盘集合竞
价数据的成交量包含在当日最后一根 K 线。
（2） 前推算法
9:30 的 1 分钟 K 线，计算的是 9:30:00.000~9:30:59.999 期间的 K 线。
9:35 的 5 分钟 K 线，计算的是 9:35:00.000~9:39:59.999 期间的 K 线。
4.4 本地数据缓存方案说明
应用场景：
（1） 接口取全量历史时间区间的数据
查询接口包含 local_path 和 is_local 两个参数的接口，这两个参数必须同时配对使用，支持
此本地缓存方案，本地保存全量历史数据，且每次调用接口默认增量更新本地数据，从而加
速接口读取速度；
（2） 接口取指定时间区间的数据
查询接口包含 begin_date 和 end_date 两个参数的接口，这两个参数必须同时配对使用，仅从
服务器获取数据，不本地缓存数据，速度较慢，且无增量更新机制。

4.4.1 函数入参说明
local_path 和 is_local 为参数组 1，begin_date 和 end_date 为参数组 2；
一个参数组内的参数必须同时使用；
两个参数组需独立使用，即使用参数组 1 时，参数组 2 无效；使用参数组 2 时，参数组 1
无效。
（1）local_path
类似'D://AmazingData_local_data//'，只写文件夹的绝对路径即可

（2）is_local
True:  
本地 local_path 有数据的情况下，从本地取数据，但无法从服务端获取最新的数据
本地 local_path 无数据的情况下，从互联网取数据，并更新本地 local_path 的数据
False:从互联网取数据，并更新本地 local_path 的数据

中国银河证券星耀数智服务平台金融资讯数据说明
81
（3） begin_date, end_date
开始日期、结束日期，在不同的接口中代表交易日、公告期等不同含义，具体见接口说明；
即按照日期从服务端取数据，不从本地取数据（即 local_path 和 is_local 两个参数无效）。
4.4.2 本地存储文件说明
文件格式为 hdf5 格式
4.4.3 本地存储空间说明
本地存储空间，不同的数据类型和标的范围，所需空间不同。
建议本地存储空间在 500GB 以上。