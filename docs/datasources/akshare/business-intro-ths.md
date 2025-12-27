---
title: 主营介绍-同花顺
description: AKShare 股票数据 - 主营介绍-同花顺 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 主营介绍-同花顺

接口: stock_zyjs_ths

目标地址: <https://basic.10jqka.com.cn/new/000066/operate.html>

描述: 同花顺-主营介绍

限量: 单次返回所有数据

输入参数

| 名称     | 类型  | 描述              |
|--------|-----|-----------------|
| symbol | str | symbol="000066" |

输出参数

| 名称   | 类型      | 描述      |
|------|---------|---------|
| 股票代码 | object  | -       |
| 主营业务 | object  | -       |
| 产品类型 | object  | -       |
| 产品名称 | object  | -       |
| 经营范围 | object  | -       |

接口示例

```python
import akshare as ak

stock_zyjs_ths_df = ak.stock_zyjs_ths(symbol="000066")
print(stock_zyjs_ths_df)
```

数据示例

```
     股票代码  ...                                               经营范围
0  000066  ...  计算机软件、硬件、终端及其外部设备、网络系统及系统集成、电子产品及零部件、金融机具、税控机具...
[1 rows x 5 columns]
```
