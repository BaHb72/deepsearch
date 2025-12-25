# 批次6分析结果：图片51-60

## 概览
图片51-60包含InfoData模块的分红配股、融资融券、龙虎榜、大宗交易等接口。

---

## 提取的接口信息

### 8. InfoData 模块 - 市场交易数据

#### 8.1 get_dividend - 分红派息 (3.5.5.11)
```python
ad.InfoData.get_dividend(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，分红派息历史

#### 8.2 get_right_issue - 配股 (3.5.5.12)
```python
ad.InfoData.get_right_issue(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，配股历史

#### 8.3 get_margin_summary - 融资融券汇总 (3.5.5.13)
```python
ad.InfoData.get_margin_summary(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，融资融券每日汇总数据

#### 8.4 get_margin_detail - 融资融券明细 (3.5.5.14)
```python
ad.InfoData.get_margin_detail(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，融资融券交易明细

#### 8.5 get_long_hu_bang - 龙虎榜 (3.5.5.15)
```python
ad.InfoData.get_long_hu_bang(
    begin_date=20240101,
    end_date=20241231,
    local_path="./data",
    is_local=True
)
```
**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| begin_date | int | 开始日期 |
| end_date | int | 结束日期 |

**返回**: DataFrame，龙虎榜上榜数据

#### 8.6 get_block_trading - 大宗交易 (3.5.5.16)
```python
ad.InfoData.get_block_trading(
    code_list=["000001.SZ"],
    begin_date=20240101,
    end_date=20241231,
    local_path="./data",
    is_local=True
)
```
**返回**: DataFrame，大宗交易记录

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| get_dividend | 3.5.5.11 | 是 | 已实现 |
| get_right_issue | 3.5.5.12 | 是 | 已实现 |
| get_margin_summary | 3.5.5.13 | 是 | 已实现 |
| get_margin_detail | 3.5.5.14 | 是 | 已实现 |
| get_long_hu_bang | 3.5.5.15 | 是 | 已实现 |
| get_block_trading | 3.5.5.16 | 是 | 已实现 |
