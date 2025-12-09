# **中国银河证券星耀数智 AmazingData Python SDK 接口开发文档**

## **1\. 概述**

AmazingData 平台通过整合交易所直连行情与深度加工的金融资讯数据，为量化交易开发者提供标准化的数据获取解决方案。本 SDK 支持 **请求-响应（Query）** 与 **发布-订阅（Subscription）** 两种模式，覆盖股票、期货、期权、基金、债券等全资产类别。

## ---

**2\. 运行环境与安装**

### **2.1 推荐运行环境**

* **Linux**:  
  * 处理器: 推荐 2.10GHz 8核  
  * 内存: 推荐 DDR4 4GB+  
  * 硬盘: 推荐 480G SSD  
  * 网卡: 推荐万兆网卡  
  * 系统: RedHat 7.2/7.4/7.6  
* **Windows**:  
  * 处理器: 推荐 2.60GHz 8核  
  * 内存: 推荐 DDR4 4GB  
  * 系统: Windows 10 (64位)

### **2.2 安装指南**

SDK 支持 Python 3.8 至 3.13 版本。需安装两个 .whl 文件（文件名中的 \* 代表具体版本号）：

1. **底层传输库**: pip install tgw-1.\*.\*-py3-none-any.whl  
2. **业务SDK**: pip install AmazingData-1.\*.\*-cp38-none-any.whl (根据 Python 版本选择对应的 cp 包)

## ---

**3\. 基础开发流程**

### **3.1 登录 (Login)**

所有接口调用前必须先建立连接。

* **函数**: ad.login(username, password, ip, port)  
* **参数**:  
  * username (str): 账号  
  * password (str): 密码  
  * ip (str): 服务器IP  
  * port (int): 端口号

### **3.2 登出 (Logout)**

* **函数**: ad.logout(username)

## ---

**4\. API 接口详述**

### **4.1 基础数据接口**

实例化类：base\_data\_object \= ad.BaseData()

#### **4.1.1 每日最新证券信息**

* **函数**: get\_code\_info(security\_type)  
* **功能**: 获取当日最新证券基础属性（涨跌停价、最小变动价位等）。  
* **参数**: security\_type (str, 默认 'EXTRA\_STOCK\_A')  
* **返回**: DataFrame (Index: 代码, Columns: symbol, pre\_close, high\_limited, low\_limited, price\_tick)

#### **4.1.2 证券代码表查询**

* **股票/基金/债券**: get\_code\_list(security\_type)  
  * security\_type 示例: 'EXTRA\_STOCK\_A', 'EXTRA\_ETF'  
* **期货**: get\_future\_code\_list(security\_type='EXTRA\_FUTURE')  
* **期权**: get\_option\_code\_list(security\_type='EXTRA\_ETF\_OP')  
* **历史代码表**: get\_hist\_code\_list(security\_type, start\_date, end\_date, local\_path)  
  * 用于获取包含已退市标的的历史代码列表。

#### **4.1.3 交易日历**

* **函数**: get\_calendar(market='SH', data\_type='str')  
* **返回**: 交易日期列表 List。

#### **4.1.4 复权因子**

* **后复权因子**: get\_backward\_factor(code\_list, local\_path, is\_local)  
* **单次复权因子**: get\_adj\_factor(code\_list, local\_path, is\_local)  
* **说明**: is\_local=True 优先读本地缓存，False 强制更新本地数据。

#### **4.1.5 证券基础信息**

* **函数**: ad.InfoData().get\_stock\_basic(code\_list)  
* **返回字段**: MARKET\_CODE, SECURITY\_NAME, LISTDATE (上市日), DELISTDATE (退市日), IS\_LISTED (1上市/3退市)。

#### **4.1.6 历史证券状态**

* **函数**: ad.InfoData().get\_history\_stock\_status(code\_list)  
* **功能**: 查询历史某日的 ST、停牌、除权除息状态。  
* **返回字段**: IS\_ST\_SEC, IS\_SUSP\_SEC (停牌), IS\_XR\_SEC (除权), IS\_WD\_SEC (除息)。

### ---

**4.2 实时行情接口 (订阅模式)**

使用 ad.SubscribeData() 类，通过 @register 装饰器绑定回调函数。

#### **4.2.1 股票/ETF/可转债 快照**

* **回调**: onSnapshot(data, period)  
* **Period**: ad.constant.Period.snapshot.value  
* **数据结构 (Snapshot)**:  
  * 基础: time, open, high, low, last, volume, amount  
  * 五档盘口: ask\_price1\~5, ask\_volume1\~5, bid\_price1\~5, bid\_volume1\~5  
  * 状态: trading\_phase\_code (交易阶段)

#### **4.2.2 指数快照**

* **回调**: onSnapshotIndex(data, period)  
* **数据结构**: 仅包含价格与成交量，无盘口。

#### **4.2.3 期货快照**

* **回调**: onSnapshotFuture(data, period)  
* **特有字段**: open\_interest (持仓量), settle (结算价), pre\_open\_interest, pre\_settle。

#### **4.2.4 期权快照**

* **回调**: onSnapshotOption(data, period)  
* **特有字段**: total\_long\_position, auction\_price (波动性中断参考价)。

#### **4.2.5 港股通快照**

* **回调**: onSnapshotHKT(data, period)  
* **特有字段**: nominal\_price (按盘价), bid/offer\_price\_limit (冷静期上下限)。

#### **4.2.6 实时 K 线**

* **回调**: OnKLine(data, period)  
* **Period**: 支持 min1, min5, day 等。  
* **数据结构**: 标准 OHLCV 数据。

### ---

**4.3 历史行情接口 (查询模式)**

实例化类：ad.MarketData(calendar)

#### **4.3.1 历史快照查询**

* **函数**: query\_snapshot(code\_list, begin\_date, end\_date, begin\_time, end\_time)  
* **返回**: Dict {code: DataFrame}。  
* **注意**: 期货夜盘（21:00-02:30）归属次日交易日，查询时需注意时间跨度设置。

#### **4.3.2 历史 K 线查询**

* **函数**: query\_kline(code\_list, begin\_date, end\_date, period)  
* **返回**: Dict {code: DataFrame}。

### ---

**4.4 财务数据接口**

实例化类：ad.InfoData()。支持 Point-in-Time 查询，通常包含 ANN\_DATE (公告日) 和 REPORT\_PERIOD (报告期)。

#### **4.4.1 资产负债表**

* **函数**: get\_balance\_sheet(code\_list, local\_path, is\_local,...)  
* **关键字段**: TOTAL\_ASSETS (总资产), TOTAL\_LIAB (总负债), CAP\_STOCK (股本), MONETARY\_CAP (货币资金), INVENTORY (存货), GOODWILL (商誉)。

#### **4.4.2 现金流量表**

* **函数**: get\_cash\_flow(code\_list,...)  
* **关键字段**: NET\_CASH\_FLOWS\_OPERA\_ACT (经营性现金流净额), NET\_CASH\_FLOWS\_INV\_ACT (投资性现金流), NET\_CASH\_FLOWS\_FIN\_ACT (筹资性现金流)。

#### **4.4.3 利润表**

* **函数**: get\_income(code\_list,...)  
* **关键字段**: OPERA\_REV (营业收入), NET\_PROFIT (净利润), NET\_PROFIT\_EXCL\_MIN\_INT (归母净利润), BASIC\_EPS (基本每股收益), RD\_EXP (研发费用)。

#### **4.4.4 业绩预告与快报**

* **业绩快报**: get\_profit\_express (含 YOY\_GR\_NET\_PROFIT 同比增长率)。  
* **业绩预告**: get\_profit\_notice (含 P\_TYPECODE 预告类型: 预增/预减/首亏/扭亏等)。

### ---

**4.5 公司行为与市场数据接口**

#### **4.5.1 股东数据**

* **十大股东**: get\_share\_holder (含持股数量、比例、股东性质)。  
* **股东户数**: get\_holder\_num (反映筹码集中度)。  
* **股本结构**: get\_equity\_structure (流通股、限售股变动)。  
* **限售解禁**: get\_equity\_restricted (解禁日期、数量)。  
* **股权质押**: get\_equity\_pledge\_freeze (质押/冻结数量及比例)。

#### **4.5.2 分红配股**

* **分红**: get\_dividend (除权除息日 DATE\_EX, 派息金额 DVD\_PER\_SHARE\_PRE\_TAX\_CASH).  
* **配股**: get\_right\_issue (配股价 PRICE, 配股比例 RATIO).

#### **4.5.3 融资融券**

* **成交汇总**: get\_margin\_summary (融资余额、融券余额)。  
* **交易明细**: get\_margin\_detail (个股的融资买入、偿还详情)。

#### **4.5.4 交易异动**

* **龙虎榜**: get\_long\_hu\_bang (营业部名称、买入/卖出金额、上榜原因)。  
* **大宗交易**: get\_block\_trading (成交价、成交量、买卖方席位)。

### ---

**4.6 衍生品与指数数据接口**

#### **4.6.1 ETF 数据**

* **ETF申赎清单**: get\_etf\_pcf (含现金替代标志 substitute\_flag, 预估现金差额 estimate\_cash\_component)。  
* **ETF份额**: get\_fund\_share。  
* **IOPV**: get\_fund\_iopv。

#### **4.6.2 期权数据**

* **基本资料**: get\_option\_basic\_info (行权价, 到期日, 认购/认沽类型)。  
* **合约属性**: get\_option\_std\_ctr\_specs (合约单位, 涨跌幅限制)。

#### **4.6.3 指数数据**

* **成分股**: get\_index\_constituent (纳入/剔除日期)。  
* **成分股权重**: get\_index\_weight (支持上证50, 沪深300, 中证500/800/1000)。  
* **行业指数**: get\_industry\_daily (行业指数 OHLC), get\_industry\_constituent.

#### **4.6.4 国债收益率**

* **函数**: get\_treasury\_yield (支持不同期限如 'm3', 'y10')。

## ---

**5\. 附录：数据字典**

### **5.1 代码类型枚举 (security\_type)**

| 枚举值 | 说明 |
| :---- | :---- |
| EXTRA\_STOCK\_A | 全市场 A 股 (沪深北) |
| EXTRA\_FUTURE | 全期货 (中金/上期/大商/郑商/能源) |
| EXTRA\_ETF\_OP | ETF 期权 |
| EXTRA\_ETF | ETF 基金 |
| EXTRA\_INDEX\_A | 沪深指数 |

### **5.2 数据周期 (Period)**

* min1 (1分钟), min5, min15, min30, min60  
* day (日线), week (周线), month (月线)

### **5.3 报表类型 (STATEMENT\_TYPE)**

* 401001: 合并报表 (最常用)  
* 401006: 母公司报表  
* 401002: 合并报表(单季度)