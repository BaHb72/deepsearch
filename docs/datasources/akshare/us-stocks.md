---
title: 美股
description: AKShare 股票数据 - 美股 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 美股

#### 实时行情数据-东财

接口: stock_us_spot_em

目标地址: <https://quote.eastmoney.com/center/gridlist.html#us_stocks>

描述: 东方财富网-美股-实时行情

限量: 单次返回美股所有上市公司的实时行情数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称  | 类型      | 描述              |
|-----|---------|-----------------|
| 序号  | int64   | -               |
| 名称  | object  | -               |
| 最新价 | float64 | 注意单位: 美元        |
| 涨跌额 | float64 | 注意单位: 美元        |
| 涨跌幅 | float64 | 注意单位: %         |
| 开盘价 | float64 | 注意单位: 美元        |
| 最高价 | float64 | 注意单位: 美元        |
| 最低价 | float64 | 注意单位: 美元        |
| 昨收价 | float64 | 注意单位: 美元        |
| 总市值 | float64 | 注意单位: 美元        |
| 市盈率 | float64 | -               |
| 成交量 | float64 | -               |
| 成交额 | float64 | 注意单位: 美元        |
| 振幅  | float64 | 注意单位: %         |
| 换手率 | float64 | 注意单位: %         |
| 代码  | object  | 注意: 用来获取历史数据的代码 |

接口示例

```python
import akshare as ak

stock_us_spot_em_df = ak.stock_us_spot_em()
print(stock_us_spot_em_df)
```

数据示例

```
          序号                         名称  ...      换手率         代码
0          1        Nexalin Technology Inc Wt  ...      NaN  105.NXLIW
1          2           Bionexus Gene Lab Corp  ...   427.44   105.BGLC
2          3  PepperLime Health Acquisition C  ...      NaN  105.PEPLW
3          4  Alliance Entertainment Holding   ...      NaN  105.AENTW
4          5         Digital Brands Group Inc  ...  6569.86   105.DBGI
      ...                              ...  ...      ...        ...
11616  11617                      BIOLASE Inc  ...   582.75   105.BIOL
11617  11618           Sunshine Biopharma Inc  ...   144.85   105.SBFM
11618  11619                      Sientra Inc  ...    42.00   105.SIEN
11619  11620        Sunshine Biopharma Inc Wt  ...      NaN  105.SBFMW
11620  11621  Social Leverage Acquisition Cor  ...      NaN  105.SLACW
[11621 rows x 16 columns]
```

#### 实时行情数据-新浪

接口: stock_us_spot

目标地址: <https://finance.sina.com.cn/stock/usstock/sector.shtml>

描述: 新浪财经-美股; 获取的数据有 15 分钟延迟; 建议使用 ak.stock_us_spot_em() 来获取数据

限量: 单次返回美股所有上市公司的实时行情数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称  | 类型  | 描述   |
|-----|-----|------|
| -   | -   | 新浪默认 |

接口示例

```python
import akshare as ak

us_stock_current_df = ak.stock_us_spot()
print(us_stock_current_df)
```

数据示例(美股股票代码可通过 ak.get_us_stock_name() 函数返回值)

```
                                                 name  \
0                                         Apple, Inc.
1                                     Microsoft Corp.
2                                    Amazon.com, Inc.
3                                      Alphabet, Inc.
4                                      Alphabet, Inc.
..                                                ...
75                               salesforce.com, inc.
76                     Thermo Fisher Scientific, Inc.
77                                       AbbVie, Inc.
78  iPath Series B Bloomberg Energy Subindex Total...
79              International Business Machines Corp.
                                                cname category symbol  \
0                                                苹果公司      计算机   AAPL
1                                                微软公司       软件   MSFT
2                                               亚马逊公司      互联网   AMZN
3                                                  谷歌      互联网   GOOG
4                                               谷歌A类股     媒体内容  GOOGL
..                                                ...      ...    ...
75                                              赛富时公司       软件    CRM
76                                          赛默飞世尔科技公司             TMO
77                                              艾伯维公司  生物技术和制药   ABBV
78  iPath Series B Bloomberg Energy Subindex Total...     None   JJEB
79                                    IBM(国际商业机器有限公司)             IBM
      price   diff   chg preclose     open     high      low amplitude  \
0    255.82   7.06  2.84   248.76   249.54   255.93   249.16     2.72%
1    143.72   0.35  0.24   143.37   144.26   144.42   142.97     1.01%
2   1791.44  14.78  0.83  1776.66  1788.01  1797.44  1785.21     0.69%
3   1273.74  13.63  1.08  1260.11  1265.00  1274.62  1260.50     1.12%
4   1272.25  13.45  1.07  1258.80  1265.80  1273.00  1259.71     1.06%
..      ...    ...   ...      ...      ...      ...      ...       ...
75   159.74   3.25  2.08   156.49   157.91   160.09   156.75     2.13%
76   303.60   1.62  0.54   301.98   305.00   305.28   303.12     0.72%
77    81.75   2.20  2.77    79.55    80.03    82.18    79.13     3.83%
78    51.74   0.00  0.00    51.74     0.00     0.00     0.00     3.54%
79   135.53   1.80  1.35   133.73   134.50   135.56   134.09     1.10%
      volume         mktcap            pe  market category_id
0   37781334  1156096660699   21.62468377  NASDAQ           5
1   33128366  1097361048289   26.81343240  NASDAQ          14
2    2790354   881483397489   77.65236086  NASDAQ          41
3    1670072   874498927695   27.11238831  NASDAQ          41
4    1440607   873475960000   27.08067289  NASDAQ         702
..       ...            ...           ...     ...         ...
75   4771053   122239344864  129.86992115    NYSE          14
76    990471   122222192032   33.88392911    NYSE         738
77  13356251   121302156830   29.94505474    NYSE         700
78         0   121175090554          None    AMEX        None
79   3089789   120621698914   15.65011561    NYSE         750
```

#### 历史行情数据-东财

接口: stock_us_hist

目标地址: <https://quote.eastmoney.com/us/ENTX.html#fullScreenChart>

描述: 东方财富网-行情-美股-每日行情

限量: 单次返回指定上市公司的指定 adjust 后的所有历史行情数据；注意其中复权参数是否生效！

输入参数

| 名称         | 类型  | 描述                                                                          |
|------------|-----|-----------------------------------------------------------------------------|
| symbol     | str | 美股代码, 可以通过 **ak.stock_us_spot_em()** 函数返回所有的 pandas.DataFrame 里面的 `代码` 字段获取 |
| period     | str | period='daily'; choice of {'daily', 'weekly', 'monthly'}                    |
| start_date | str | start_date="20210101"                                                       |
| end_date   | str | end_date="20210601"                                                         |
| adjust     | str | 默认 adjust="", 则返回未复权的数据; adjust="qfq" 则返回前复权的数据, adjust="hfq" 则返回后复权的数据     |

输出参数

| 名称  | 类型      | 描述       |
|-----|---------|----------|
| 日期  | object  | -        |
| 开盘  | float64 | 注意单位: 美元 |
| 收盘  | float64 | 注意单位: 美元 |
| 最高  | float64 | 注意单位: 美元 |
| 最低  | float64 | 注意单位: 美元 |
| 成交量 | int32   | 注意单位: 股  |
| 成交额 | float64 | 注意单位: 美元 |
| 振幅  | float64 | 注意单位: %  |
| 涨跌幅 | float64 | 注意单位: %  |
| 涨跌额 | float64 | 注意单位: 美元 |
| 换手率 | float64 | 注意单位: %  |

接口示例

```python
import akshare as ak

stock_us_hist_df = ak.stock_us_hist(symbol='106.TTE', period="daily", start_date="20200101", end_date="20240214", adjust="qfq")
print(stock_us_hist_df)
```

数据示例

```
     日期         开盘   收盘   最高  ...    振幅   涨跌幅  涨跌额 换手率
0    2021-06-11  41.75  41.24  41.75  ...  0.00  0.00  0.00  0.03
1    2021-06-14  41.56  41.61  42.17  ...  1.94  0.90  0.37  0.04
2    2021-06-15  41.40  42.19  42.19  ...  2.04  1.39  0.58  0.09
3    2021-06-16  42.04  41.71  42.16  ...  1.59 -1.14 -0.48  0.06
4    2021-06-17  41.61  40.69  41.80  ...  3.72 -2.45 -1.02  0.05
..          ...    ...    ...    ...  ...   ...   ...   ...   ...
668  2024-02-07  62.90  63.05  63.26  ...  0.94 -3.07 -2.00  0.27
669  2024-02-08  63.39  64.19  64.33  ...  1.67  1.81  1.14  0.14
670  2024-02-09  64.41  64.31  64.53  ...  0.69  0.19  0.12  0.15
671  2024-02-12  64.40  64.63  64.82  ...  0.98  0.50  0.32  0.14
672  2024-02-13  65.21  64.43  65.28  ...  1.81 -0.31 -0.20  0.14
[673 rows x 11 columns]
```

#### 个股信息查询-雪球

接口: stock_individual_basic_info_us_xq

目标地址: <https://xueqiu.com/snowman/S/NVDA/detail#/GSJJ>

描述: 雪球-个股-公司概况-公司简介

限量: 单次返回指定 symbol 的个股信息

输入参数

| 名称      | 类型    | 描述                      |
|---------|-------|-------------------------|
| symbol  | str   | symbol="NVDA"; 股票代码     |
| token   | str   | token=None;             |
| timeout | float | timeout=None; 默认不设置超时参数 |

输出参数

| 名称    | 类型     | 描述  |
|-------|--------|-----|
| item  | object | -   |
| value | object | -   |

接口示例

```python
import akshare as ak

stock_individual_basic_info_us_xq_df = ak.stock_individual_basic_info_us_xq(symbol="SH601127")
print(stock_individual_basic_info_us_xq_df)
```

数据示例

```
                             item                                              value
0                          org_id                                         T000040433
1                     org_name_cn                                              英伟达公司
2               org_short_name_cn                                                英伟达
3                     org_name_en                                 Nvidia Corporation
4               org_short_name_en                                             Nvidia
5         main_operation_business                                           图形和通信处理器
6                 operating_scope  公司的图形和通信处理器已被多种多样的计算平台采用，包括个人数字媒体PC、商用PC、专业工作站...
7                 district_encode                                             001008
8             org_cn_introduction  英伟达公司于1993年4月在加利福尼亚州注册成立，并于1998年4月在特拉华州重新注册成立。...
9            legal_representative                                               None
10                general_manager                                               None
11                      secretary                                               None
12               established_date                                               None
13                      reg_asset                                               None
14                      staff_num                                              36000
15                      telephone                                      1-408-4862000
16                       postcode                                              95051
17                            fax                                               None
18                          email                                               None
19                    org_website                                     www.nvidia.com
20                 reg_address_cn                                               特拉华州
21                 reg_address_en                                               特拉华州
22              office_address_cn                                               None
23              office_address_en  2788 San Tomas Expressway\r\nSanta Clara\r\nCa...
24                currency_encode                                               None
25                       currency
26                    listed_date                                       916981200000
27                         td_mkt                                      美国NASDAQ证券交易所
28                       chairman                                               None
29                executives_nums                                                  6
30  actual_issue_total_shares_num                                               None
31             actual_issue_price                                               None
32            total_raise_capital                                               None
33                     mainholder                                       领航集团 (8.30%)
```

#### 分时数据-东财

接口: stock_us_hist_min_em

目标地址: <https://quote.eastmoney.com/us/ATER.html>

描述: 东方财富网-行情首页-美股-每日分时行情

限量: 单次返回指定上市公司最近 5 个交易日分钟数据, 注意美股数据更新有延时

输入参数

| 名称         | 类型  | 描述                                                                                           |
|------------|-----|----------------------------------------------------------------------------------------------|
| symbol     | str | symbol="105.ATER"; 美股代码可以通过 **ak.stock_us_spot_em()** 函数返回所有的 pandas.DataFrame 里面的 `代码` 字段获取 |
| start_date | str | start_date="1979-09-01 09:32:00"; 日期时间; 默认返回所有数据                                             |
| end_date   | str | end_date="2222-01-01 09:32:00"; 日期时间; 默认返回所有数据                                               |

输出参数

| 名称  | 类型      | 描述       |
|-----|---------|----------|
| 时间  | object  | -        |
| 开盘  | float64 | 注意单位: 美元 |
| 收盘  | float64 | 注意单位: 美元 |
| 最高  | float64 | 注意单位: 美元 |
| 最低  | float64 | 注意单位: 美元 |
| 成交量 | float64 | 注意单位: 股  |
| 成交额 | float64 | 注意单位: 美元 |
| 最新价 | float64 | 注意单位: 美元 |

接口示例

```python
import akshare as ak

stock_us_hist_min_em_df = ak.stock_us_hist_min_em(symbol="105.ATER")
print(stock_us_hist_min_em_df)
```

数据示例

```
          时间    开盘    收盘    最高    最低       成交量          成交额    最新价
0     2021-08-30 21:30:00  0.00  8.86  8.92  8.86  12147424  108372137.0  8.898
1     2021-08-30 21:31:00  0.00  8.72  8.90  8.57    998571    8927364.0  8.813
2     2021-08-30 21:32:00  0.00  8.73  8.73  8.44    725257    6193335.0  8.735
3     2021-08-30 21:33:00  0.00  8.90  8.98  8.67    546888    4965712.0  8.747
4     2021-08-30 21:34:00  0.00  8.60  9.00  8.34   1040362    9456790.0  8.739
                   ...   ...   ...   ...   ...       ...          ...    ...
1950  2021-09-04 03:56:00  6.67  6.65  6.70  6.65     26769     180608.0  6.478
1951  2021-09-04 03:57:00  6.65  6.68  6.68  6.65     13643      90551.0  6.478
1952  2021-09-04 03:58:00  6.68  6.70  6.70  6.67     46469     314155.0  6.480
1953  2021-09-04 03:59:00  6.70  6.69  6.70  6.69     31059     209314.0  6.481
1954  2021-09-04 04:00:00  6.70  6.70  6.70  6.67    243168    1549848.0  6.478
```

#### 历史行情数据-新浪

接口: stock_us_daily

目标地址: <http://finance.sina.com.cn/stock/usstock/sector.shtml>

描述: 美股历史行情数据，设定 adjust="qfq" 则返回前复权后的数据，默认 adjust="", 则返回未复权的数据，历史数据按日频率更新

限量: 单次返回指定上市公司的指定 adjust 后的所有历史行情数据

输入参数

| 名称     | 类型  | 描述                                                                  |
|--------|-----|---------------------------------------------------------------------|
| symbol | str | 美股代码, 可以通过 **ak.get_us_stock_name()** 函数返回所有美股代码, 由于美股数据量大, 建议按需要获取 |
| adjust | str | adjust="qfq" 则返回前复权后的数据，默认 adjust="", 则返回未复权的数据                     |

**ak.get_us_stock_name()**: will return a pandas.DataFrame, which contains name, cname and symbol, you should use
symbol!

输出参数-历史数据

| 名称     | 类型         | 描述  |
|--------|------------|-----|
| date   | datetime64 | -   |
| open   | float64    | 开盘价 |
| high   | float64    | 最高价 |
| low    | float64    | 最低价 |
| close  | float64    | 收盘价 |
| volume | float64    | 成交量 |

输出参数-前复权因子

| 名称         | 类型         | 描述                  |
|------------|------------|---------------------|
| date       | datetime64 | 日期                  |
| qfq_factor | float      | 前复权因子               |
| adjust     | float      | 由于前复权会出现负值, 该值为调整因子 |

P.S. 复权计算公式: 未复权数据 * qfq_factor + adjust

P.S. "CIEN" 股票的新浪美股数据由于复权因子错误，暂不返回前复权数据

接口示例-未复权数据

```python
import akshare as ak

stock_us_daily_df = ak.stock_us_daily(symbol="AAPL", adjust="")
print(stock_us_daily_df)
```

数据示例-未复权数据

```
 date         open      high      low    close       volume
1980-12-12   28.735   28.8750   28.735   28.735    2093900.0
1980-12-15   27.265   27.3700   27.265   27.265     785200.0
1980-12-16   25.235   25.3750   25.235   25.235     472000.0
1980-12-17   25.865   26.0050   25.865   25.865     385900.0
1980-12-18   26.635   26.7400   26.635   26.635     327900.0
             ...       ...      ...      ...          ...
2021-01-04  133.520  133.6116  126.760  129.410  134308607.0
2021-01-05  128.890  131.7400  128.430  131.010   90749416.0
2021-01-06  127.720  131.0499  126.382  126.600  139351145.0
2021-01-07  128.360  131.6300  127.860  130.920  101546989.0
2021-01-08  132.430  132.6300  130.230  132.050   98373014.0
```

接口示例-前复权调整后的数据

```python
import akshare as ak

stock_us_daily_df = ak.stock_us_daily(symbol="AAPL", adjust="qfq")
print(stock_us_daily_df)
```

数据示例-前复权调整后的数据

```
 date          open      high       low     close       volume
1980-12-12   -4.8164   -4.8158   -4.8164   -4.8164    2093900.0
1980-12-15   -4.8230   -4.8225   -4.8230   -4.8230     785200.0
1980-12-16   -4.8321   -4.8314   -4.8321   -4.8321     472000.0
1980-12-17   -4.8293   -4.8286   -4.8293   -4.8293     385900.0
1980-12-18   -4.8258   -4.8253   -4.8258   -4.8258     327900.0
              ...       ...       ...       ...          ...
2021-01-04  133.5200  133.6116  126.7600  129.4100  134308607.0
2021-01-05  128.8900  131.7400  128.4300  131.0100   90749416.0
2021-01-06  127.7200  131.0499  126.3820  126.6000  139351145.0
2021-01-07  128.3600  131.6300  127.8600  130.9200  101546989.0
2021-01-08  132.4300  132.6300  130.2300  132.0500   98373014.0
```

接口示例-前复权因子

```python
import akshare as ak

qfq_df = ak.stock_us_daily(symbol="AAPL", adjust="qfq-factor")
print(qfq_df)
```

数据示例-前复权因子

```
 date               qfq_factor            adjust
2020-08-07                  1                 0
2020-05-08                  1      -0.819999993
2020-02-07                  1      -1.639999986
2019-11-07                  1      -2.409999967
2019-08-09                  1      -3.179999948
                       ...               ...
1987-11-17  0.035714285714285     -18.958676644
1987-08-10  0.035714285714285  -18.958778786857
1987-06-16  0.035714285714285  -18.958855215429
1987-05-11  0.017857142857142  -18.958855215429
1900-01-01  0.017857142857142  -18.958893429714
```

#### 粉单市场

接口: stock_us_pink_spot_em

目标地址: <http://quote.eastmoney.com/center/gridlist.html#us_pinksheet>

描述: 美股粉单市场的实时行情数据

限量: 单次返回指定所有粉单市场的行情数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称  | 类型      | 描述              |
|-----|---------|-----------------|
| 序号  | int64   | -               |
| 名称  | object  | -               |
| 最新价 | float64 | 注意单位: 美元        |
| 涨跌额 | float64 | 注意单位: 美元        |
| 涨跌幅 | float64 | 注意单位: %         |
| 开盘价 | float64 | 注意单位: 美元        |
| 最高价 | float64 | 注意单位: 美元        |
| 最低价 | float64 | 注意单位: 美元        |
| 昨收价 | float64 | 注意单位: 美元        |
| 总市值 | float64 | 注意单位: 美元        |
| 市盈率 | float64 | -               |
| 代码  | object  | 注意: 用来获取历史数据的代码 |

接口示例

```python
import akshare as ak

stock_us_pink_spot_em_df = ak.stock_us_pink_spot_em()
print(stock_us_pink_spot_em_df)
```

数据示例

```
      序号           名称                    最新价  ...  总市值  市盈率  代码
0      1           LiNiu Technology Group  0.0189  ...  NaN  NaN  153.LINUF
1      2              NOBILIS HEALTH CORP  0.0016  ...  NaN  NaN  153.NRTSF
2      3                  Yuma Energy Inc  0.0999  ...  NaN  NaN  153.YUMAQ
3      4                      HHGregg Inc  0.0120  ...  NaN  NaN  153.HGGGQ
4      5  Helios and Matheson Analytics I  0.0010  ...  NaN  NaN   153.HMNY
..   ...                              ...     ...  ...  ...  ...        ...
215  216              root9B Holdings Inc  0.0100  ...  NaN  NaN   153.RTNB
216  217       Immune Pharmaceuticals Inc  0.0012  ...  NaN  NaN  153.IMNPQ
217  218                       JRjr33 Inc  0.0005  ...  NaN  NaN  153.JRJRQ
218  219         Mad Catz Interactive Inc  0.0001  ...  NaN  NaN  153.MCZAF
219  220         Taronis Technologies Inc  0.0010  ...  NaN  NaN   153.TRNX
```

#### 知名美股

接口: stock_us_famous_spot_em

目标地址: <http://quote.eastmoney.com/center/gridlist.html#us_wellknown>

描述: 美股-知名美股的实时行情数据

限量: 单次返回指定 symbol 的行情数据

输入参数

| 名称     | 类型  | 描述                                                                       |
|--------|-----|--------------------------------------------------------------------------|
| symbol | str | symbol="科技类"; choice of {'科技类', '金融类', '医药食品类', '媒体类', '汽车能源类', '制造零售类'} |

输出参数

| 名称  | 类型      | 描述              |
|-----|---------|-----------------|
| 序号  | int64   | -               |
| 名称  | object  | -               |
| 最新价 | float64 | 注意单位: 美元        |
| 涨跌额 | float64 | 注意单位: 美元        |
| 涨跌幅 | float64 | 注意单位: %         |
| 开盘价 | float64 | 注意单位: 美元        |
| 最高价 | float64 | 注意单位: 美元        |
| 最低价 | float64 | 注意单位: 美元        |
| 昨收价 | float64 | 注意单位: 美元        |
| 总市值 | float64 | 注意单位: 美元        |
| 市盈率 | float64 | -               |
| 代码  | object  | 注意: 用来获取历史数据的代码 |

接口示例

```python
import akshare as ak

stock_us_famous_spot_em_df = ak.stock_us_famous_spot_em(symbol='科技类')
print(stock_us_famous_spot_em_df)
```

数据示例

```
    序号              名称           最新价  ...         总市值     市盈率        代码
0    1  Silvergate Capital Corp-A   116.34  ...     3085409047   61.93    106.SI
1    2  Opendoor Technologies Inc    18.94  ...    11451903533  -19.65  105.OPEN
2    3                     阿勒格尼技术    17.55  ...     2233160842   -1.82   106.ATI
3    4                Yandex NV-A    78.71  ...    28129406798  131.13  105.YNDX
4    5                        爱立信    11.83  ...    39443015025   16.44  105.ERIC
5    6                        诺基亚     5.91  ...    33269348763  -14.11   106.NOK
6    7              Groupon Inc-A    22.16  ...      654264338   73.65  105.GRPN
7    8                         推特    62.46  ...    49840992399  129.65  106.TWTR
8    9             Facebook Inc-A   378.00  ...  1065750021378   27.36    105.FB
9   10                         惠普    28.21  ...    32512553599    7.98   106.HPQ
10  11                       谷歌-C  2898.27  ...  1932435735616   16.84  105.GOOG
11  12                      阿卡迈技术   113.38  ...    18461647373   31.60  105.AKAM
12  13                      超威半导体   106.15  ...   128756264684   37.47   105.AMD
13  14                         思科    58.60  ...   247159324736   23.34  105.CSCO
14  15                       中华电信    40.05  ...    31068573413   24.84   106.CHT
15  16                       德州仪器   188.47  ...   173997383234   25.87   105.TXN
16  17                        奥多比   661.68  ...   315224352000   56.47  105.ADBE
17  18                        高知特    76.48  ...    40197673856   23.91  105.CTSH
18  19                        英特尔    53.40  ...   216643800000   11.68  105.INTC
19  20                     美国电话电报    27.42  ...   195778800000 -100.55     106.T
20  21                         高通   141.58  ...   159702240000   17.35  105.QCOM
21  22                         苹果   154.07  ...  2546802675620   29.34  105.AAPL
22  23              IBM国际商业机器(US)   137.74  ...   123459126717   23.15   106.IBM
23  24                         陶氏    60.28  ...    44955123381   10.96   106.DOW
24  25                        思爱普   145.68  ...   171841118251   23.58   106.SAP
25  26                        英伟达   221.77  ...   554425000000   78.33  105.NVDA
26  27                      威瑞森通讯    54.44  ...   225387915421   11.28    106.VZ
27  28                         微软   297.25  ...  2233801423468   36.46  105.MSFT
28  29                   摩托罗拉解决方案   244.00  ...    41315202400   35.80   106.MSI
29  30                        亚马逊  3484.16  ...  1764519802163   59.94  105.AMZN
30  31                         易趣    73.00  ...    47454073765    3.68  105.EBAY
31  32                    沃达丰(US)    16.61  ...    46152628937  351.55   105.VOD
32  33                Zynga Inc-A     8.28  ...     9040854574  -53.06  105.ZNGA
33  34          SentinelOne Inc-A    66.04  ...    16930759265  -85.17     106.S
```
