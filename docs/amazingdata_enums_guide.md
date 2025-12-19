# AmazingData 枚举类型使用指南

## 📚 概述

本文档提供了 AmazingData 数据源中所有枚举类型的完整说明和使用方法。这些枚举类型基于官方文档定义，用于解释 API 返回数据中的状态码和类型码。

## 🏷️ 枚举类型总览

| 枚举类 | 数量 | 用途 | 官方文档章节 |
|--------|------|------|-------------|
| **AmazingDataTradingPhase** | 13 | 交易阶段代码 | 4.1.5 |
| **AmazingDataReportPeriod** | 4 | 报告期名称 | 4.1.7 |
| **AmazingDataStatementType** | 65 | 报表类型代码 (1-91) | 4.1.8 |
| **AmazingDataDivProgress** | 7 | 股票分红进度代码 | 4.1.9 |
| **AmazingDataProgress** | 26 | 股票配股进度代码 | 4.1.10 |
| **总计** | **115** | - | - |

---

## 📖 枚举详细定义

### 1. AmazingDataTradingPhase（交易阶段代码）

**用途**: 解释快照数据中的 `trading_phase_code` 字段

#### 枚举值列表

| 代码 | 枚举名称 | 说明 |
|------|---------|------|
| S | BEFORE_OPENING | 启动（开市前） |
| O | OPENING_CALL_AUCTION_UNCLOSED | 开盘集合竞价 |
| 0 | OPENING_CALL_AUCTION_CLOSED | 开盘集合竞价（已闭市） |
| T | CONTINUOUS_TRADING_NOT_TRADABLE | 连续竞价（开市未可交易） |
| 1 | CONTINUOUS_TRADING_SUSPENDED | 连续竞价成交不可交易（停牌） |
| 2 | CONTINUOUS_TRADING | 连续竞价 |
| 3 | CLOSING_CALL_AUCTION | 收盘集合竞价 |
| E | POST_TRADING_TRANSFER | 盘后固定价格交易 |
| C | CLOSED | 闭市/收盘处理 |
| P | MARKET_CLOSED | 停牌 |
| U | VOLATILITY_INTERRUPTION | 波动性中断/盘后交易 |
| B | SZ_CLOSING | 盘中收盘集合竞价（深交所） |
| V | SZ_VOLATILITY_INTERRUPTION | 波动性中断（深交所） |

#### 使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataTradingPhase,
    get_trading_phase_name
)

# 判断交易状态
snapshot_data = await provider.get_snapshot(["000001.SZ"])
phase_code = snapshot_data.iloc[0]['trading_phase_code']

if phase_code == AmazingDataTradingPhase.CONTINUOUS_TRADING.value:
    print("正在连续竞价交易")

# 获取状态说明
status_desc = get_trading_phase_name(phase_code)
print(f"交易状态: {status_desc}")
```

---

### 2. AmazingDataReportPeriod（报告期名称）

**用途**: 解释财务数据中的 `REPORT_PERIOD` 字段

#### 枚举值列表

| 数值 | 枚举名称 | 说明 |
|------|---------|------|
| 1 | Q1 | 第一季度（3月） |
| 2 | Q2 | 第二季度（6月） |
| 3 | Q3 | 第三季度（9月） |
| 4 | ANNUAL | 年报（12月） |

#### 使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataReportPeriod,
    get_report_period_name
)

# 筛选年报数据
financial_data = await provider.get_financial_data(["000001.SZ"])
annual_reports = financial_data[
    financial_data['REPORT_PERIOD'] == AmazingDataReportPeriod.ANNUAL.value
]

# 获取报告期说明
period_desc = get_report_period_name(2)  # 第二季度
print(f"报告期: {period_desc}")
```

---

### 3. AmazingDataStatementType（报表类型代码）

**用途**: 解释财务报表数据中的 `STATEMENT_TYPE` 字段

#### 主要枚举值

| 数值 | 枚举名称 | 说明 |
|------|---------|------|
| 1 | CONSOLIDATED_INCOME | 合并报表 |
| 2 | CONSOLIDATED_BALANCE_SHEET | 合并报表（母子公司） |
| 3 | PARENT_INCOME | 母公司报表（母子） |
| 6 | CONSOLIDATED_CASH_FLOW | 母公司母报表（现金流） |
| 7 | PARENT_CASH_FLOW | 母公司母报表（资本母义） |
| 37-51 | STATEMENT_37~51 | 更多报表类型 |
| 60 | STATEMENT_60 | 特殊报表类型 |
| 70 | STATEMENT_70 | 特殊报表类型 |
| 80-81 | STATEMENT_80~81 | 特殊报表类型 |
| 90-91 | STATEMENT_90~91 | 特殊报表类型 |

**注意**: 报表类型编号不连续，部分编号未使用。

#### 使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataStatementType,
    get_statement_type_name
)

# 筛选合并报表
statements = await provider.get_financial_statements(["000001.SZ"])
consolidated = statements[
    statements['STATEMENT_TYPE'] == AmazingDataStatementType.CONSOLIDATED_INCOME.value
]

# 获取报表类型说明
stmt_desc = get_statement_type_name(1)
print(f"报表类型: {stmt_desc}")
```

---

### 4. AmazingDataDivProgress（股票分红进度代码）

**用途**: 解释分红数据中的 `DIV_PROGRESS` 字段

#### 枚举值列表

| 数值 | 枚举名称 | 说明 |
|------|---------|------|
| 1 | DECLARED | 董事会预案 |
| 2 | SHAREHOLDER_APPROVED | 股东大会通过 |
| 3 | IMPLEMENTATION | 实施 |
| 4 | COMPLETED | 实施完成 |
| 12 | STOP_IMPLEMENTATION | 停止实施 |
| 17 | SHAREHOLDER_REJECTED | 股东大会否决 |
| 19 | DECLARED_NOT_IMPLEMENTATION | 董事会预案不实施 |

#### 使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataDivProgress,
    get_div_progress_name
)

# 筛选已完成的分红
dividends = await provider.get_dividend_data(["000001.SZ", "600000.SH"])
completed_divs = dividends[
    dividends['DIV_PROGRESS'] == AmazingDataDivProgress.COMPLETED.value
]

# 筛选进行中的分红
in_progress = dividends[
    dividends['DIV_PROGRESS'].isin([
        AmazingDataDivProgress.DECLARED.value,
        AmazingDataDivProgress.SHAREHOLDER_APPROVED.value,
        AmazingDataDivProgress.IMPLEMENTATION.value
    ])
]

# 获取进度说明
progress_desc = get_div_progress_name(4)
print(f"分红进度: {progress_desc}")
```

---

### 5. AmazingDataProgress（股票配股进度代码）

**用途**: 解释配股数据中的 `PROGRESS` 字段（如 `get_right_issue` 接口）

####  枚举值列表

| 数值 | 枚举名称 | 说明 |
|------|---------|------|
| 1 | DECLARED | 董事会预案 |
| 2 | SHAREHOLDER_APPROVED | 股东大会通过 |
| 3 | IMPLEMENTATION | 实施 |
| 4 | COMPLETED | 实施完成 |
| 5 | REGULATORY_APPROVED | 证监会核准 |
| 6 | ISSUANCE_APPROVED | 发审委批准 |
| 7 | EXCHANGE_APPROVED | 交易所批准 |
| 8 | NDRC_APPROVED | 国家发改批准 |
| 9 | CSRC_APPROVED | 证券会批准 |
| 10 | FILING | 备案 |
| 11 | SUSPENSION_REVIEW | 暂缓审批 |
| 12 | TERMINATE | 停止实施 |
| 13 | REGULATORY_REJECTED | 证监会否决 |
| 14 | TERMINATED | 终止 |
| 15 | EXCHANGE_REJECTED | 交易所否决 |
| 16 | SHAREHOLDER_REJECTED | 股东大会否决 |
| 17 | SHAREHOLDER_POSTPONED | 股东大会延期 |
| 18 | EXCHANGE_TERMINATED | 交易所终止 |
| 19 | DECLARED_NOT_IMPLEMENTATION | 董事会预案不实施 |
| 20 | SUSPENSION_REORGANIZATION | 被暂停审批调整 |
| 21 | CSRC_REJECTED | 发审委否决 |
| 22 | SHAREHOLDER_POSTPONED_2 | 股东大会公告延迟 |
| 23 | REGULATORY_FILING | 证监会批准 |
| 24 | EXCHANGE_FILING | 交易所公告备案 |
| 25 | CSRC_FILING | 预发布 |
| 26 | RECEIVED_NOTICE | 接受注册 |

#### 使用示例

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataProgress,
    get_progress_name
)

# 获取配股数据
right_issues = await provider.get_right_issue(
    code_list=["000001.SZ"],
    begin_date=20240101,
    end_date=20241231
)

# 筛选已完成的配股
completed = right_issues[
    right_issues['PROGRESS'] == AmazingDataProgress.COMPLETED.value
]

# 筛选已获监管审批的配股
approved_stages = {5, 6, 7, 8, 9}
approved = right_issues[
    right_issues['PROGRESS'].isin(approved_stages)
]

# 添加进度说明列
right_issues['PROGRESS_NAME'] = right_issues['PROGRESS'].apply(get_progress_name)

# 查看特定配股的进度
for idx, row in right_issues.iterrows():
    progress = row['PROGRESS']
    desc = get_progress_name(progress)
    print(f"{row['MARKET_CODE']}: {desc}")
```

---

## 💻 完整使用示例

### 示例1: 综合使用多个枚举

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataTradingPhase,
    AmazingDataProgress,
    AmazingDataDivProgress,
    get_trading_phase_name,
    get_progress_name,
    get_div_progress_name,
)

async def analyze_stock_status(provider, stock_code):
    """综合分析股票状态"""
    
    # 1. 检查交易状态
    snapshot = await provider.get_snapshot([stock_code])
    if not snapshot.empty:
        phase = snapshot.iloc[0]['trading_phase_code']
        print(f"交易状态: {get_trading_phase_name(phase)}")
        
        if phase == AmazingDataTradingPhase.CONTINUOUS_TRADING.value:
            print("可以交易")
        elif phase == AmazingDataTradingPhase.MARKET_CLOSED.value:
            print("停牌中")
    
    # 2. 检查配股进度
    right_issues = await provider.get_right_issue([stock_code])
    if not right_issues.empty:
        for _, row in right_issues.iterrows():
            progress = row['PROGRESS']
            print(f"配股进度: {get_progress_name(progress)}")
            
            if progress in {5, 6, 7, 8, 9}:
                print("已获得监管审批")
            elif progress == AmazingDataProgress.COMPLETED.value:
                print("配股已完成")
    
    # 3. 检查分红进度（假设有该接口）
    # dividends = await provider.get_dividend([stock_code])
    # if not dividends.empty:
    #     for _, row in dividends.iterrows():
    #         div_progress = row['DIV_PROGRESS']
    #         print(f"分红进度: {get_div_progress_name(div_progress)}")
```

### 示例2: 数据统计分析

```python
def analyze_right_issue_statistics(right_issues_df):
    """统计配股数据的进度分布"""
    
    from collections import Counter
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
        get_progress_name
    )
    
    # 统计各进度的数量
    progress_counts = Counter(right_issues_df['PROGRESS'])
    
    print("配股进度分布:")
    for progress, count in sorted(progress_counts.items()):
        progress_name = get_progress_name(progress)
        print(f"  {progress_name}: {count}条")
    
    # 计算完成率
    total = len(right_issues_df)
    completed = len(right_issues_df[right_issues_df['PROGRESS'] == 4])
    completion_rate = (completed / total * 100) if total > 0 else 0
    print(f"\n配股完成率: {completion_rate:.2f}%")
```

---

## 🔗 与接口的对应关系

| 接口方法 | 涉及字段 | 使用枚举 | 辅助函数 |
|---------|---------|---------|---------|
| `get_right_issue` | PROGRESS | AmazingDataProgress | get_progress_name() |
| `get_snapshot` | trading_phase_code | AmazingDataTradingPhase | get_trading_phase_name() |
| （待补充分红接口） | DIV_PROGRESS | AmazingDataDivProgress | get_div_progress_name() |
| （待补充财务接口） | REPORT_PERIOD | AmazingDataReportPeriod | get_report_period_name() |
| （待补充财务接口） | STATEMENT_TYPE | AmazingDataStatementType | get_statement_type_name() |

---

## 📌 使用建议

### 1. 导入方式

```python
# 方式1: 导入需要的枚举类
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataProgress,
    AmazingDataDivProgress,
)

# 方式2: 只导入辅助函数
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    get_progress_name,
    get_div_progress_name,
)

# 方式3: 全部导入（不推荐，除非确实需要所有枚举）
from deepsearch.infrastructure.providers.implementations.amazingdata import amazingdata_enums_extended as enums
```

### 2. 数据筛选

使用枚举值进行数据筛选时，推荐使用 `.value` 获取实际值：

```python
# 推荐
filtered = df[df['PROGRESS'] == AmazingDataProgress.COMPLETED.value]

# 也可以直接使用数值（但可读性较差）
filtered = df[df['PROGRESS'] == 4]
```

### 3. 数据展示

在展示数据时，使用辅助函数将代码转换为可读文本：

```python
# 添加说明列
df['PROGRESS_NAME'] = df['PROGRESS'].apply(get_progress_name)

# 或在循环中使用
for idx, row in df.iterrows():
    print(f"{row['MARKET_CODE']}: {get_progress_name(row['PROGRESS'])}")
```

---

## ⚠️ 注意事项

1. **枚举值类型**: 
   - `AmazingDataTradingPhase`: 字符串类型 (str)
   - 其他枚举: 整数类型 (int)

2. **数值不连续**: `AmazingDataStatementType` 的数值范围是1-91，但不是所有数值都有定义

3. **向后兼容**: 所有枚举都是可选使用的，不使用枚举不影响API调用

4. **文档更新**: 随着API的更新，枚举值可能会增加，请关注官方文档

---

## 📚 参考文档

- [AmazingData 官方SDK文档](待补充)
- [枚举定义源代码](file:///d:/Stock/code/deepsearch/deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_enums_extended.py)
- [字段映射文档](file:///d:/Stock/code/deepsearch/docs/AMAZINGDATA_FIELD_MAPS_REPORT.md)

---

**最后更新时间**: 2025-12-16 01:45  
**版本**: v1.0  
**状态**: ✅ 完成
