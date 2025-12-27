# 批次2分析结果：图片11-20

## 概览

图片11-20主要包含BaseData模块的复权因子、交易日历、证券基础信息等接口。

---

## 提取的接口信息

### 3. BaseData 模块接口 (续)

#### 3.1 get_backward_factor - 后复权因子 (3.5.2.4)

```python
ad.BaseData.get_backward_factor(
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

**返回**: DataFrame，index为交易日期，columns为股票代码

#### 3.2 get_adj_factor - 单次复权因子 (3.5.2.5)

```python
ad.BaseData.get_adj_factor(
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

**返回**: DataFrame，index为交易日期，columns为股票代码

#### 3.3 get_hist_code_list - 历史代码列表 (3.5.2.6)

```python
ad.BaseData.get_hist_code_list(
    security_type="EXTRA_STOCK_A_SH_SZ",
    start_date=20130101,
    end_date=20250101,
    local_path="./data"
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| security_type | str | 代码类型 |
| start_date | int | 开始日期 YYYYMMDD |
| end_date | int | 结束日期 YYYYMMDD |
| local_path | str | 本地存储路径 |

**返回**: 代码列表

#### 3.4 get_calendar - 交易日历 (3.5.2.7)

```python
ad.BaseData.get_calendar(
    data_type="str",
    market="SH"
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| data_type | str | 返回类型 "str"/"datetime" |
| market | str | 市场 "SH"/"SZ" |

**返回**: 交易日列表

#### 3.5 get_stock_basic - 证券基础信息 (3.5.2.8)

```python
ad.BaseData.get_stock_basic(code_list=["000001.SZ"])
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| code_list | List[str] | 股票代码列表 |

**返回**: DataFrame，包含公司名称、上市日期、退市日期等

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| get_backward_factor | 3.5.2.4 | 是 | 已实现 |
| get_adj_factor | 3.5.2.5 | 是 | 已实现 |
| get_hist_code_list | 3.5.2.6 | 是 | 已实现 |
| get_calendar | 3.5.2.7 | 是 | 已实现 |
| get_stock_basic | 3.5.2.8 | 是 | 已实现 |
