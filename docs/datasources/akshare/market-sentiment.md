---
title: 赚钱效应分析
description: AKShare 股票数据 - 赚钱效应分析 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 赚钱效应分析

接口: stock_market_activity_legu

目标地址: <https://www.legulegu.com/stockdata/market-activity>

描述: 乐咕乐股网-赚钱效应分析数据

限量: 单次返回当前赚钱效应分析数据

说明：

1. 涨跌比：即沪深两市上涨个股所占比例，体现的是市场整体涨跌，占比越大则代表大部分个股表现活跃。
2. 涨停板数与跌停板数的意义：涨停家数在一定程度上反映了市场的投机氛围。当涨停家数越多，则市场的多头氛围越强。真实涨停是非一字无量涨停。真实跌停是非一字无量跌停。

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称    | 类型     | 描述  |
|-------|--------|-----|
| item  | object | -   |
| value | object | -   |

接口示例

```python
import akshare as ak

stock_market_activity_legu_df = ak.stock_market_activity_legu()
print(stock_market_activity_legu_df)
```

数据示例

```
        item                value
0         上涨               4770.0
1         涨停                119.0
2       真实涨停                101.0
3   st st*涨停                 10.0
4         下跌                281.0
5         跌停                  6.0
6       真实跌停                  4.0
7   st st*跌停                  4.0
8         平盘                 39.0
9         停牌                 10.0
10       活跃度               93.53%
11      统计日期  2024-10-14 15:00:00
```
