---
title: 财经内容精选
description: AKShare 股票数据 - 财经内容精选 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 财经内容精选

接口: stock_news_main_cx

目标地址: <https://cxdata.caixin.com/pc/>

描述: 财新网-财新数据通-内容精选

限量: 返回所有历史新闻数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称            | 类型     | 描述 |
|---------------|--------|----|
| tag           | object | -  |
| summary       | object | -  |
| interval_time | object | -  |
| pub_time      | object | -  |
| url           | object | -  |

接口示例

```python
import akshare as ak

stock_news_main_cx_df = ak.stock_news_main_cx()
print(stock_news_main_cx_df)
```

数据示例

```
                     tag  ...                                                url
0                 8月5日收盘  ...  https://stock.caixin.com/m/market?cxapp_link=true
1      高盛上调美国衰退预期但认为风险有限  ...  https://database.caixin.com/2024-08-05/1022233...
2       分析人士：股市逢低买入还为时过早  ...  https://database.caixin.com/2024-08-05/1022233...
3        巴菲特加速减持苹果是重大信号吗  ...  https://www.caixin.com/2024-08-04/102223237.ht...
4                 今日股市热点  ...  https://database.caixin.com/2024-08-05/1022233...
...                  ...  ...                                                ...
12729     （接上条）广电的5G牌怎么打  ...  https://cxdata.caixin.com/twotopic/20200925153...
12730           5G建设最新数据  ...  https://www.caixin.com/2020-11-26/101632865.htm...
12731       银行股尾盘爆发有何道理？  ...  https://database.caixin.com/2020-11-22/10163123...
12732  鸿海或将部分苹果产品生产线迁出中国  ...  https://database.caixin.com/2020-11-27/10163291...
12733          “小酒”股今日普跌  ...  https://database.caixin.com/2020-11-26/10163250...
[12734 rows x 5 columns]
```
