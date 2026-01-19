# AmazingData: Dask Adapter 领域层接口补全

> 日期: 2026-01-17
> 模块: providers/implementations/amazingdata/dask_adapter.py
> 类型: design-change

---

## 为什么要改

### 遇到的问题

AmazingDataDaskAdapter 成功注册到 ProviderContainer 后，DataProxy 调用时仍然失败：

```
数据源 amazingdata 不支持股票列表
数据源 amazingdata 不支持交易日历
```

### 接口层次不匹配

| 层次 | `get_stock_list` | `get_calendar` |
|-----|------------------|----------------|
| **领域层** (DataProxy 期望) | `(market, board)` | `(market)` |
| **SDK 原生** (已实现) | `get_code_list(security_type)` | `(begin_date, end_date)` |

DataProxy 使用 `isinstance(adapter, CalendarCapable)` 检查能力，而 `CalendarCapable` 协议要求的签名是 `get_calendar(market: str) -> list[int]`，与现有 SDK 原生 API 不匹配。

---

## 尝试过的方案

### 方案 A: 修改 DataProxy 适配 SDK 接口

**思路**: 让 DataProxy 直接调用 SDK 原生方法

**问题**:

- 破坏了接口统一性
- DataProxy 需要为每个数据源写特殊逻辑
- 违反开闭原则

### 方案 B: 在 Adapter 中添加领域层接口（最终选择）

**思路**:

- 保留 SDK 原生 API，供直接调用
- 新增领域层接口，实现 Protocol 协议
- Adapter 负责参数转换和格式映射

**优势**:

- 符合适配器模式本意
- DataProxy 保持简洁
- 同一 Adapter 服务于不同调用场景

---

## 最终方案

### 设计决策: 双接口并存

一个 Adapter 同时提供：

1. **SDK 原生 API** - 供熟悉 AmazingData 的开发者直接调用
2. **领域层接口** - 供 DataProxy 统一调度

### 关键改动

#### 文件: `dask_adapter.py`

**改动 1: 重命名 SDK 原生 get_calendar**

```python
# 改之前
async def get_calendar(begin_date, end_date) -> list[int] | None:
    """3.5.2.7 交易日历"""

# 改之后
async def get_calendar_range(begin_date, end_date) -> list[int] | None:
    """3.5.2.7 交易日历（SDK 原生 API）"""
```

**为什么重命名**: 避免与领域层接口方法名冲突。

**改动 2: 新增领域层 get_calendar**

```python
async def get_calendar(self, market: str = "SH") -> list[int]:
    """获取交易日历（领域层接口）

    实现 CalendarCapable 协议，供 DataProxy 使用。
    """
    result = await self._call_actor("get_calendar", market=market)
    if result is None:
        return []
    return [int(d) for d in result]
```

**为什么返回空列表而非 None**: 领域层接口应保证返回值可迭代，减少上层空值检查。

**改动 3: 新增领域层 get_stock_list**

```python
async def get_stock_list(
    self,
    market: str | None = None,
    board: str | None = None,
) -> list[dict[str, Any]]:
    """获取股票列表（领域层接口）

    实现 StockListCapable 协议，供 DataProxy 使用。
    将 market/board 参数转换为 security_type 后调用 SDK。
    """
    security_type = "EXTRA_STOCK_A"
    result = await self._call_actor("get_code_list", security_type=security_type)

    if result is None:
        return []

    stocks = []
    for code in result:
        if not isinstance(code, str):
            continue
        # 按市场过滤
        if market:
            if market == "SH" and not code.endswith(".SH"):
                continue
            # ... SZ, BJ 过滤
        stocks.append({"symbol": code, "name": ""})

    return stocks
```

**为什么在 Adapter 做过滤**: SDK 返回全量数据，市场过滤是领域层语义，应在适配层处理。

---

## 注意事项

### 这个方案的局限

1. **name 字段为空**: `get_code_list` 只返回代码，没有名称。如需名称，需额外调用 `get_code_info`
2. **board 过滤未实现**: 当前只做了 market 过滤，板块过滤需要更多数据支持
3. **市场参数在 get_calendar 中被忽略**: A股交易日历统一，市场参数目前不影响结果

### 如果要扩展

- 如需支持 board 过滤，需要先调用 `get_code_info` 获取完整证券信息
- 如需股票名称，考虑缓存 `get_code_info` 结果

### 相关历史

- [2026-01-17 Dask 代理注册](2026-01-17_amazingdata_dask-proxy-registration.md) - 第 154-156 行提到了这个待办
- [2026-01-15 Provider 架构重构](2026-01-15_provider-architecture-refactor.md)

---

## 关键结论

> **接口分层是适配器模式的核心价值**: SDK 原生 API 面向数据源（参数是 security_type、begin_date），领域层接口面向业务（参数是 market、board）。Adapter 的职责就是做这层转换，让上层调用者无需关心底层 SDK 的细节。保留双接口可以同时服务于"直接调用"和"代理调度"两种场景。
