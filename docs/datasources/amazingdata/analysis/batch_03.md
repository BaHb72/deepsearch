# 批次3分析结果：图片21-30

## 概览

图片21-30包含BaseData模块剩余接口和InfoData模块介绍。

---

## 提取的接口信息

### 4. BaseData 模块接口 (续)

#### 4.1 get_history_stock_status - 历史证券状态 (3.5.2.9)

```python
ad.BaseData.get_history_stock_status(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| code_list | List[str] | 代码列表 |
| local_path | str | 本地存储路径 |
| is_local | bool | 是否使用本地存储 |

**返回**: DataFrame，包含停牌、ST、除权除息等信息

#### 4.2 get_bj_code_mapping - 北交所代码映射 (3.5.2.10)

```python
ad.BaseData.get_bj_code_mapping(
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，北交所代码新旧映射表

---

### 5. MarketData 模块接口

#### 5.1 query_snapshot - 历史快照 (3.5.4.1)

```python
ad.MarketData.query_snapshot(
    code_list=["000001.SZ"],
    begin_date=20240101,
    end_date=20240201,
    market="SH"
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| code_list | List[str] | 股票列表 |
| begin_date | int | 开始日期 YYYYMMDD |
| end_date | int | 结束日期 YYYYMMDD |
| market | str | 市场 SH/SZ |

**返回**: 快照数据字典

#### 5.2 query_kline - 历史K线 (3.5.4.2)

```python
ad.MarketData.query_kline(
    code_list=["000001.SZ"],
    begin_date=20240101,
    end_date=20240201,
    period="day"
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| code_list | List[str] | 代码列表 |
| begin_date | int | 开始日期 |
| end_date | int | 结束日期 |
| period | str | 周期: min1/min3/min5/min10/min15/min30/min60/min120/day/week/month/season/year |

**返回**: 字典，key为代码，value为DataFrame

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| get_history_stock_status | 3.5.2.9 | 是 | 已实现 |
| get_bj_code_mapping | 3.5.2.10 | 是 | 已实现 |
| query_snapshot | 3.5.4.1 | 是 | 已实现 |
| query_kline | 3.5.4.2 | 是 | 已实现 |
