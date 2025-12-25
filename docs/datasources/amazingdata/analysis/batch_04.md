# 批次4分析结果：图片31-40

## 概览
图片31-40主要包含InfoData模块的财务报表相关接口。

---

## 提取的接口信息

### 6. InfoData 模块 - 财务报表接口

#### 6.1 get_balance_sheet - 资产负债表 (3.5.5.1)
```python
ad.InfoData.get_balance_sheet(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| code_list | List[str] | 股票代码列表 |
| local_path | str | 本地存储路径 |
| is_local | bool | 是否使用本地存储 |

**返回**: DataFrame，资产负债表数据

#### 6.2 get_cash_flow - 现金流量表 (3.5.5.2)
```python
ad.InfoData.get_cash_flow(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，现金流量表数据

#### 6.3 get_income - 利润表 (3.5.5.3)
```python
ad.InfoData.get_income(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，利润表数据

#### 6.4 get_profit_express - 业绩快报 (3.5.5.4)
```python
ad.InfoData.get_profit_express(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True,
    begin_date=20240101,
    end_date=20241231
)
```
**返回**: DataFrame，业绩快报数据

#### 6.5 get_profit_notice - 业绩预告 (3.5.5.5)
```python
ad.InfoData.get_profit_notice(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True,
    begin_date=20240101,
    end_date=20241231
)
```
**返回**: DataFrame，业绩预告数据

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| get_balance_sheet | 3.5.5.1 | 是 | 已实现 |
| get_cash_flow | 3.5.5.2 | 是 | 已实现 |
| get_income | 3.5.5.3 | 是 | 已实现 |
| get_profit_express | 3.5.5.4 | 是 | 已实现 |
| get_profit_notice | 3.5.5.5 | 是 | 已实现 |
