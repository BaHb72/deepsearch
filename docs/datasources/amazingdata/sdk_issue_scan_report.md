# AmazingData SDK 问题扫描报告

**扫描时间**: 2025-12-28
**修复状态**: ✅ 全部已修复

## 发现的问题

### 问题1: MarketData 创建时 calendar=None

SDK要求创建 `MarketData` 时必须传入交易日历，
否则 `query_kline` 会在内部第140行报错。

#### 已修复的文件

| 文件 | 状态 |
|------|------|
| `test_amazingdata_comprehensive.py` | ✅ |
| `test_amazingdata_working.py` | ✅ |
| `test_amazingdata_sdk.py` | ✅ |
| `verify_amazingdata_full.py` | ✅ |

### 问题2: period 参数使用字符串

SDK要求 `period` 参数传递 `Period.xxx.value` (int)。

#### 修复的脚本

| 文件 | 修复 |
|------|------|
| `test_amazingdata_sdk.py` | `period=10008` |
| `verify_amazingdata_full.py` | `period=10008` |

---

## 修复方案

```python
# 错误用法
market = ad.MarketData(calendar=None)
kline = market.query_kline([...], period="day")

# 正确用法
calendar = ad.BaseData().get_calendar()
market = ad.MarketData(calendar)
kline = market.query_kline([...], period=10008)
```

### Period 值对照表

| 周期 | 枚举 | 值 |
|------|------|-----|
| 1分钟 | `Period.min1` | 10000 |
| 5分钟 | `Period.min5` | 10002 |
| 日线 | `Period.day` | 10008 |
| 周线 | `Period.week` | 10009 |
| 月线 | `Period.month` | 10010 |

---

## 已修复的核心代码

| 文件 | 修复内容 |
|------|----------|
| `helpers.py` | 直接获取calendar创建MarketData |
| `amazingdata_process_proxy.py` | 优先用calendar创建 |
| `runtime.py` | 返回 `.value` 整数 |

---

## 详细文档

- [query_kline_calendar_requirement.md](./query_kline_calendar_requirement.md)
