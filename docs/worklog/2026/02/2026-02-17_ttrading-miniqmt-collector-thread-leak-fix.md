# T-Trading MiniQMT Collector 线程泄漏修复

> 日期: 2026-02-17
> 模块: strategy-center / ttrading / miniqmt
> 类型: bugfix / memory

---

## 问题现象

系统运行一段时间后，线程数和内存持续增长。
定位到 T-Trading 实时/历史数据链路中，存在“每请求新建 MiniQMTCollector”路径。

---

## 复现证据

最小复现（本地执行）：

```python
xs=[MiniQMTCollector() for _ in range(80)]
```

观测结果（示例）：

- `base_threads=1`
- `after_create=81`
- `after_gc=81`

说明：collector 实例携带后台 `Timer` 线程，实例被频繁创建会导致线程与内存占用累积。

---

## 根因

`ttrading` 两条业务路径直接 `MiniQMTCollector()`：

1. `packages/core/strategies/ttrading/providers.py::get_intraday_bars`
2. `apps/api/api/endpoints/strategy_center/ttrading.py::get_kline_data`

同时每次请求还临时创建 `ThreadPoolExecutor`，放大了资源波动。

---

## 复用性检索（按约束留痕）

检索目标: 避免重复创建 collector，复用已有能力。

命中候选:

1. 项目内 `core.adapters.market_data.miniqmt_polling_adapter._get_or_create_collector` 已有全局 collector 复用逻辑。
2. Python 标准库 `asyncio.to_thread` 可替代每次构造临时 `ThreadPoolExecutor`。

取舍:

- 采用候选 1：新增公开函数 `get_shared_miniqmt_collector()` 并统一接入。
- 采用候选 2：改为 `asyncio.to_thread`，减少线程池对象抖动。
- 不新增自研连接池或额外调度器，避免重复造轮子。

---

## 修复内容

1. `packages/core/adapters/market_data/miniqmt_polling_adapter.py`
   - 新增公开函数 `get_shared_miniqmt_collector()`。
2. `packages/core/strategies/ttrading/providers.py`
   - `get_intraday_bars` 改为复用共享 collector；
   - 用 `asyncio.to_thread` 替代临时 `ThreadPoolExecutor`。
3. `apps/api/api/endpoints/strategy_center/ttrading.py`
   - `get_kline_data` 改为复用共享 collector；
   - 用 `asyncio.to_thread` 替代临时 `ThreadPoolExecutor`。

---

## 测试留痕

新增测试：

1. `tests/unit/strategies/test_ttrading_providers.py`
2. `tests/api/test_strategy_center_ttrading_kline_collector_reuse.py`

验证点：

- 走共享 collector 路径；
- 业务不再直接实例化 `MiniQMTCollector`；
- collector 未连接时按预期返回空数据。

---

## 解决路径

1. 依赖检查：`uv pip check --python ./.venv/Scripts/python.exe`。
2. 最小复现线程增长并确认对象回收后线程不下降。
3. 复用现有全局 collector 能力并替换调用链。
4. 补测试覆盖“共享复用/断连回退”场景。
5. 执行定向测试并记录结果。
