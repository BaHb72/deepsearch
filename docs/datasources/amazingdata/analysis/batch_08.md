# 批次8分析结果：图片71-80

## 概览
图片71-80包含SubscribeData实时K线回调和快照数据字段详细说明。

---

## 提取的接口信息

### 10. SubscribeData 模块 - K线订阅

#### 10.1 OnKLine - 实时K线回调 (3.5.6.7)
```python
def OnKLine(data):
    """实时K线数据回调"""
    pass

ad.SubscribeData.subscribe_kline(
    code_list=["000001.SZ"],
    period="min1",
    callback=OnKLine
)
```
**回调参数**:
| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 股票代码 |
| time | int | K线时间戳 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交量 |
| amount | float | 成交额 |

---

### 11. 快照数据字段详解

| 字段索引 | 字段名 | 说明 |
|----------|--------|------|
| 0 | code | 证券代码 |
| 1 | last | 最新价 |
| 2 | open | 开盘价 |
| 3 | high | 最高价 |
| 4 | low | 最低价 |
| 5 | preclose | 昨收盘 |
| 6 | volume | 成交量 |
| 7 | amount | 成交额 |
| 8-17 | bidN/askN | 五档买卖价 |
| 18-27 | bidvolN/askvolN | 五档买卖量 |
| 28 | timestamp | 时间戳 |

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| OnKLine | 3.5.6.7 | 是 | 已实现 |
