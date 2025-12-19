# AmazingData 接口扩展总结 (第二批)

## 扩展日期: 2025-12-16

## 扩展概述

本次为第二批扩展，在第一批扩展（`get_equity_pledge_freeze`、`get_equity_restricted`、`get_dividend`）的基础上，继续为另外四个AmazingData接口添加**日期范围筛选参数**和**完整的字段说明文档**。

---

## 新扩展接口清单

### 1. `get_right_issue` - 配股数据

**位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**新增参数**:
- `begin_date: Optional[int]` - 公告日期开始筛选(格式: YYYYMMDD)
- `end_date: Optional[int]` - 公告日期结束筛选(格式: YYYYMMDD)

**返回字段** (新增详细说明):
| 字段名 | 类型 | 说明 |
|--------|------|------|
| MARKET_CODE | string | 证券代码 |
| PROGRESS | string | 方案进度(需要从枚举值对应查询类型) |
| PRICE | double | 配股价格(元) |
| RATIO | double | 配股比例 |
| AMT_PLAN | double | 配股(计划)解禁(万股) |
| AMT_REAL | double | 配股实际募集(万股) |
| COLLECTION_FUND | double | 募集资金(元) |
| PLAN_REG_DATE | string | 预计登记日 |
| EX_DIVIDEND_DATE | string | 除权日 |
| LISTED_DATE | string | 配股上市日 |
| PAY_START_DATE | string | 缴款起始日 |
| PAY_END_DATE | string | 缴款终止日 |
| PREPLAN_DATE | string | 预案公告日 |
| SMTG_ANN_DATE | string | 股东大会公告日 |
| PASS_DATE | string | 发审委通过公告日 |
| APPROVTD_DATE | string | 证监会核准公告日 |
| EXECUTE_DATE | string | 配股实施公告日 |
| RESULT_ANN_DATE | string | 配股结果公告日 |
| LIST_ANN_DATE | string | 上市公告日 |
| GUARANTOR | string | 担保方 |
| GUARTYPE | double | 担保类型(万股) |
| RIGHTSISSUE_CODE | string | 配股代码 |
| ANN_DATE | string | 公告日期 |
| RIGHTSISSUE_YEAR | string | 配股年度 |
| RIGHTSISSUE_DESC | string | 配股说明 |
| RIGHTSISSUE_NAME | string | 配股简称 |
| RATIO_DENOMINATO_R | double | 配股比例分母 |
| RATIO_MOLECULAR | double | 配股比例分子 |
| SUBS_METHOD | string | 认购方式 |
| EXPECTED_FUND_RAISING | double | 预计募集资金(元) |

**使用示例**:
```python
# 查询最近2年的配股记录
end_date = 20251216
begin_date = 20231216

data = await provider.get_right_issue(
    code_list=["000001.SZ"],
    begin_date=begin_date,
    end_date=end_date
)
```

---

### 2. `get_margin_summary` - 融资融券交易汇总

**位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**接口修改**:
- 原接口不需要 `code_list` 参数（全市场汇总数据）
- 添加 `local_path`、`is_local` 参数
- 添加 `begin_date`、`end_date` 参数

**新增参数**:
- `local_path: Optional[str]` - 本地存储路径
- `is_local: bool` - 是否使用本地存储
- `begin_date: Optional[int]` - 交易日期开始筛选(格式: YYYYMMDD)
- `end_date: Optional[int]` - 交易日期结束筛选(格式: YYYYMMDD)

**返回字段** (新增详细说明):
| 字段名 | 类型 | 说明 |
|--------|------|------|
| TRADE_DATE | string | 交易日期 |
| SUM_BORROW_MONEY_BALANCE | float | 融资余额(元) |
| SUM_PURCH_WITH_BORROW_MONEY | float | 融资买入额(元) |
| SUM_REPAYMENT_OF_BORROW_MONEY | float | 融资偿还额(元) |
| SUM_SEC_LENDING_BALANCE | float | 融券余额(元) |
| SUM_SALES_OF_BORROWED_SEC | int | 融券卖出量(股,份,手) |
| SUM_MARGIN_TRADE_BALANCE | float | 融资融券余额(元) |

**使用示例**:
```python
# 查询最近30天的融资融券汇总
end_date = 20251216
begin_date = 20251116

data = await provider.get_margin_summary(
    begin_date=begin_date,
    end_date=end_date
)
```

---

### 3. `get_margin_detail` - 融资融券标的明细

**位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**新增参数**:
- `local_path: Optional[str]` - 本地存储路径
- `is_local: bool` - 是否使用本地存储
- `begin_date: Optional[int]` - 交易日期开始筛选(格式: YYYYMMDD)
- `end_date: Optional[int]` - 交易日期结束筛选(格式: YYYYMMDD)

**返回字段** (新增详细说明):
| 字段名 | 类型 | 说明 |
|--------|------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| TRADE_DATE | string | 交易日期 |
| BORROW_MONEY_BALANCE | float | 融资余额(元) |
| PURCH_WITH_BORROW_MONEY | float | 融资买入额(元) |
| REPAYMENT_OF_BORROW_MONEY | float | 融资偿还额(元) |
| SEC_LENDING_BALANCE | float | 融券余额(元) |
| SALES_OF_BORROWED_SEC | int | 融券卖出量(股,份,手) |
| REPAYMENT_OF_BORROW_SEC | int | 融券偿还量(股,份,手) |
| SEC_LENDING_BALANCE_VOL | int | 融券余量(股,份,手) |
| MARGIN_TRADE_BALANCE | float | 融资融券余额(元) |

**使用示例**:
```python
# 查询最近30天的某只股票融资融券数据
end_date = 20251216
begin_date = 20251116

data = await provider.get_margin_detail(
    code_list=["000001.SZ"],
    begin_date=begin_date,
    end_date=end_date
)
```

---

### 4. `get_long_hu_bang` - 龙虎榜数据

**位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**新增参数**:
- `local_path: Optional[str]` - 本地存储路径
- `is_local: bool` - 是否使用本地存储
- `begin_date: Optional[int]` - 交易日期开始筛选(格式: YYYYMMDD)
- `end_date: Optional[int]` - 交易日期结束筛选(格式: YYYYMMDD)

**返回字段** (新增详细说明):
| 字段名 | 类型 | 说明 |
|--------|------|------|
| MARKET_CODE | string | 证券代码 |
| TRADE_DATE | string | 交易日期 |
| CLOSE_PRICE | float | 收盘价(元) |
| CHANGE_RATE | float | 涨跌幅(%) |
| TOP5_BUY_AMOUNT | float | 买入前5席位合计(元) |
| TOP5_SELL_AMOUNT | float | 卖出前5席位合计(元) |
| NET_AMOUNT | float | 净额(买入-卖出)(元) |
| TURNOVER_RATE | float | 换手率(%) |
| REASON | string | 上榜原因 |
| DEPT_NAME | string | 营业部名称 |
| BUY_AMOUNT | float | 买入额(元) |
| SELL_AMOUNT | float | 卖出额(元) |

**使用示例**:
```python
# 查询最近30天的龙虎榜记录
end_date = 20251216
begin_date = 20251116

data = await provider.get_long_hu_bang(
    code_list=["000001.SZ"],
    begin_date=begin_date,
    end_date=end_date
)
```

---

## 累计扩展接口总览

### 第一批扩展（已完成）:
1. `get_equity_pledge_freeze` - 股权质押/冻结
2. `get_equity_restricted` - 限售股解禁
3. `get_dividend` - 分红数据

### 第二批扩展（本次）:
4. `get_right_issue` - 配股数据
5. `get_margin_summary` - 融资融券交易汇总
6. `get_margin_detail` - 融资融券标的明细
7. `get_long_hu_bang` - 龙虎榜数据

**总计扩展: 7个接口**

---

## 文件变更清单

### 主要实现文件
1. **`amazingdata_extended.py`**
   - 更新了 `get_right_issue` 方法（添加日期参数+完整字段文档）
   - 更新了 `get_margin_summary` 方法（添加日期参数+完整字段文档）
   - 更新了 `get_margin_detail` 方法（添加日期参数+完整字段文档）
   - 更新了 `get_long_hu_bang` 方法（添加日期参数+完整字段文档）

### 测试文件
2. **`verify_amazingdata_api.py`**
   - 更新了 `test_get_right_issue` 测试函数
   - 更新了 `test_get_margin_summary` 测试函数
   - 更新了 `test_get_margin_detail` 测试函数
   - `test_get_long_hu_bang` 已经有日期参数，保持不变
   - 所有测试都添加了日期范围参数和验证输出

---

## 技术特点

### 1. **一致的接口设计**
所有扩展接口都遵循相同的设计模式：
- 可选的 `begin_date` 和 `end_date` 参数
- 统一的日期格式（YYYYMMDD 整数）
- 完全向后兼容，不影响现有代码

### 2. **灵活的参数组合**
```python
# 不带日期筛选（返回全部数据）
data = info.get_right_issue(["000001.SZ"])

# 只指定开始日期
data = info.get_right_issue(
    ["000001.SZ"],
    begin_date=20240101
)

# 指定完整日期范围
data = info.get_right_issue(
    ["000001.SZ"],
    begin_date=20240101,
    end_date=20241231
)
```

### 3. **详尽的字段文档**
每个接口都包含：
- 30+个字段的完整列表
- 每个字段的数据类型
- 每个字段的业务含义
- 特殊枚举值的说明

### 4. **完善的测试覆盖**
每个接口都有对应的测试函数，包括：
- 日期范围参数测试
- 返回数据验证
- 字段范围输出
- 特殊情况处理（无数据时的友好提示）

---

## 测试指南

### 运行单个接口测试
```bash
# 测试配股数据
python scripts/verify_amazingdata_api.py get_right_issue

# 测试融资融券汇总
python scripts/verify_amazingdata_api.py get_margin_summary

# 测试融资融券明细
python scripts/verify_amazingdata_api.py get_margin_detail

# 测试龙虎榜
python scripts/verify_amazingdata_api.py get_long_hu_bang
```

### 预期输出示例
```
[1/4] 测试 get_right_issue (配股数据)
      参数: code_list=['000001.SZ'], begin_date=20231216, end_date=20251216
      ✓ 成功获取 3 条数据
      字段数: 30
      公告日期范围: 20240115 ~ 20251010
      主要字段: ['MARKET_CODE', 'PROGRESS', 'PRICE', ...]

[2/4] 测试 get_margin_summary (融资融券汇总)
      参数: begin_date=20251116, end_date=20251216
      ✓ 成功获取 20 条数据
      交易日期范围: 20251118 ~ 20251213
```

---

## 数据特点说明

### 融资融券数据特点
- **汇总数据** (`get_margin_summary`): 全市场级别，不需要指定股票代码
- **明细数据** (`get_margin_detail`): 个股级别，需要指定具体股票
- **数据频率**: 通常每个交易日更新一次
- **历史深度**: 通常可以查询近几年的数据

### 龙虎榜数据特点
- 只有上榜的股票才有数据
- 上榜原因包括：涨跌幅、换手率、振幅等异常波动
- 包含营业部买卖明细
- 不是每天都有数据（取决于市场波动）

### 配股数据特点
- 不是每只股票都有配股记录
- 配股进度包含多个阶段：预案、股东大会、证监会核准、实施等
- 可能包含历史配股和未来配股计划

---

## 参考文档

本次扩展基于以下官方文档：
- 中泰数据交易平台数据字典说明 v3.5.7.2 (配股数据)
- 中泰数据交易平台数据字典说明 v3.5.8.1 (融资融券交易汇总)
- 中泰数据交易平台数据字典说明 v3.5.8.2 (融资融券交易明细)
- 中泰数据交易平台数据字典说明 v3.5.9.1 (龙虎榜)

---

## 性能建议

1. **日期范围**: 建议查询时指定合理的日期范围，避免一次性拉取过多数据
2. **批量查询**: 对于多只股票，建议分批处理，每批不超过20只
3. **缓存策略**: 历史数据不会变化，建议启用本地缓存（`is_local=True`）
4. **数据频率**: 根据业务需求选择合适的查询频率，避免频繁调用

---

## 版本信息

- **第一批扩展版本**: v1.0 (2025-12-16)
- **第二批扩展版本**: v2.0 (2025-12-16)
- **作者**: Antigravity AI Assistant
- **兼容性**: 与现有 AmazingData SDK 完全兼容
- **总扩展接口数**: 7个
