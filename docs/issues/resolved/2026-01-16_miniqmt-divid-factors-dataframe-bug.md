# MiniQMT divid-factors 接口 DataFrame 判断错误

> 发现日期: 2026-01-16
> 发现位置: apps/api/api/endpoints/qmt/miniqmt.py:1390
> 类型: code-quality
> 严重程度: medium
> 状态: resolved

---

## 问题描述

`GET /api/miniqmt/xtdata/divid-factors` 接口在返回数据时触发 DataFrame 真值判断错误。

### 现象

```bash
curl -s "http://localhost:8000/api/miniqmt/xtdata/divid-factors?symbol=000001.SZ"
```

返回错误:

```json
{"detail":"The truth value of a DataFrame is ambiguous. Use a.empty, a.bool(), a.item(), a.any() or a.all()."}
```

### 影响

- 无法通过 API 获取股票的复权因子数据
- 需要使用其他方式获取复权信息

---

## 发现上下文

> 在执行 MiniQMT API 全接口测试时发现此问题

---

## 相关代码

```python
# 文件: apps/api/api/endpoints/qmt/miniqmt.py
# 行号: 约 1390

# 错误代码模式:
if df:  # 错误: DataFrame 不能直接用于布尔判断
    return {"success": True, "data": df.to_dict()}

# 正确写法:
if df is not None and not df.empty:
    return {"success": True, "data": df.to_dict()}

# 或者:
if isinstance(df, pd.DataFrame) and not df.empty:
    return {"success": True, "data": df.to_dict()}
```

---

## 建议修复方案

修改 DataFrame 判断逻辑，使用 `df.empty` 或 `len(df)` 替代直接布尔判断。

### 预估工作量

- [x] 小（< 30 分钟）

### 相关文件

- `apps/api/api/endpoints/qmt/miniqmt.py`

---

## 备注

这是一个常见的 Pandas 使用错误，修复很简单。
