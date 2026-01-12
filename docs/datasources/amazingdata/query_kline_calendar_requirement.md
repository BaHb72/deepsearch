# MarketData.query_kline 必须传入 calendar 参数

## 问题描述

调用 `MarketData.query_kline()` 时抛出
`TypeError: 'NoneType' object is not iterable`。
错误位置在 SDK 内部 `market_data.py` 第 140 行。

## 错误现象

```python
import AmazingData as ad

ad.login('username', 'password', 'host', 8600)

# 错误用法：calendar=None
m = ad.MarketData(calendar=None)
kline = m.query_kline(
    code_list=['000001.SZ'],
    begin_date=20241201,
    end_date=20241220,
    period=ad.constant.Period.day.value
)
# TypeError: 'NoneType' object is not iterable
```

## 根因分析

通过反编译 SDK 字节码发现：

```text
# 第140行字节码：
140    L2:     LOAD_FAST     0 (self)
               LOAD_ATTR     4 (calendar)
               GET_ITER      # <-- 遍历 self.calendar
```

SDK 在第 140 行对 `self.calendar` 执行迭代操作，
用于筛选查询日期范围内的交易日。
当 `calendar=None` 时，迭代 `None` 导致报错。

## 正确用法

```python
import AmazingData as ad

ad.login('username', 'password', 'host', 8600)

# Step 1: 获取交易日历
base = ad.BaseData()
calendar = base.get_calendar()
print(f"交易日历长度: {len(calendar)}")

# Step 2: 创建 MarketData 时传入 calendar
m = ad.MarketData(calendar=calendar)

# Step 3: 调用 query_kline
kline = m.query_kline(
    code_list=['000001.SZ'],
    begin_date=20241201,
    end_date=20241220,
    period=ad.constant.Period.day.value
)
# 成功！返回 15 条日K数据
```

## period 参数说明

根据 SDK 文档，`period` 参数类型为 `int`：

| 周期 | 枚举 | 值 |
|------|------|-----|
| 1分钟 | `Period.min1` | 10000 |
| 5分钟 | `Period.min5` | 10002 |
| 日线 | `Period.day` | 10008 |
| 周线 | `Period.week` | 10009 |
| 月线 | `Period.month` | 10010 |

## 代码修改要点

在系统中使用 `MarketData` 时，必须：

1. 先调用 `BaseData().get_calendar()` 获取交易日历
2. 将 calendar 传递给 `MarketData(calendar=calendar)`
3. `period` 参数使用 `.value` 整数值

## 发现日期

2025-12-28
