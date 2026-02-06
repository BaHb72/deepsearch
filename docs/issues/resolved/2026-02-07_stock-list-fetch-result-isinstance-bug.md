# StockListFetchResult isinstance 检查失败导致股票列表端点 500

- **发现日期**: 2026-02-07
- **严重程度**: 严重
- **影响范围**: `/api/data/stock/list`, `/api/data/stocks`

## 问题描述

`_normalize_stock_records()` 函数中的 `isinstance(payload, StockListFetchResult)` 返回 `False`，尽管 `payload` 的类型名确实是 `StockListFetchResult`。导致代码跳过正确的处理分支，进入 `for entry in payload` 迭代，而 `StockListFetchResult` 不可迭代，抛出 `TypeError`。

## 错误堆栈

```
File "data_unified.py", line 51, in _normalize_stock_records
    for entry in payload:
                 ^^^^^^^
TypeError: 'StockListFetchResult' object is not iterable
```

## 根本原因

可能是模块路径不一致导致的类身份不匹配（Python 的 `isinstance` 需要类对象完全一致）。

`data_unified.py` 的导入：

```python
from core.infrastructure.providers.managers.data_source_manager import StockListFetchResult
```

而 `data_module.get_data_service().get_stock_list()` 返回的对象可能来自不同的导入路径，导致两个 `StockListFetchResult` 类不是同一个对象。

## 影响

- `/api/data/stock/list` 在 `UnifiedDataFeed` 未初始化时的回退路径完全不可用
- `/api/data/stocks`（旧版兼容端点）完全不可用

## 建议修复

1. 检查 `StockListFetchResult` 的实际导入路径是否一致
2. 或者使用 duck typing 替代 isinstance 检查（检查 `hasattr(payload, 'records')` 和 `hasattr(payload, 'as_legacy')`）

## 相关问题

- `2026-01-19_stock-list-datasource-priority.md` -- 股票列表数据源优先级配置
- `2026-02-07_unified-data-feed-not-initialized.md` -- UnifiedDataFeed 未初始化导致触发此回退路径

**关键文件**：

- `apps/api/api/endpoints/data/data_unified.py:34-72` (_normalize_stock_records)
- `core/infrastructure/providers/managers/data_source_manager.py` (StockListFetchResult 定义)
