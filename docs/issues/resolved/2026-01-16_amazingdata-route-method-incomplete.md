# AmazingData Actor _route_method 路由不完整

> 发现日期: 2026-01-16
> 发现位置: packages/core/compute/actors/amazingdata_actor.py:630-660
> 类型: code-quality
> 严重程度: medium
> 状态: resolved
> 解决日期: 2026-01-16

---

## 问题描述

`_route_method()` 方法负责将 API 调用路由到正确的 SDK 对象（BaseData/MarketData/InfoData），但部分方法缺失路由定义，导致被错误地路由到默认的 InfoData。

### 现象

以下方法调用失败，因为它们不存在于 InfoData 中：

- `get_future_code_list` - 应路由到 BaseData
- `get_option_code_list` - 应路由到 BaseData
- `get_etf_pcf` - 应路由到 BaseData

### 影响

- 期货代码列表、期权代码列表、ETF PCF 等接口无法正常工作
- 返回 `InfoData has no attribute 'xxx'` 错误

---

## 发现上下文

> 在测试 AmazingData API 并分析 SDK 方法签名时发现

通过反编译 AmazingData SDK 并使用 `inspect.signature()` 提取方法签名，发现部分 BaseData 方法未在路由中定义。

---

## 相关代码

```python
# 文件: packages/core/compute/actors/amazingdata_actor.py
# 行号: 630-660

def _route_method(self, method: str) -> Any | None:
    # MarketData 方法
    if method in ("query_kline", "query_snapshot"):
        return self._market_data

    # BaseData 方法 - 缺少以下方法！
    if method in (
        "get_calendar",
        "get_code_info",
        "get_code_list",
        # 缺少: get_future_code_list
        # 缺少: get_option_code_list
        # 缺少: get_etf_pcf
        ...
    ):
        return self._base_data

    # 默认路由到 InfoData
    return self._info_data
```

---

## 已实施修复方案

在 BaseData 路由中添加缺失的方法：

```python
if method in (
    "get_calendar",
    "get_code_info",
    "get_code_list",
    "get_backward_factor",
    "get_adj_factor",
    "get_history_stock_status",
    "get_hist_code_list",
    "get_future_code_info",
    "get_future_code_list",   # 新增
    "get_option_code_list",   # 新增
    "get_etf_pcf",            # 新增
):
    return self._base_data
```

### 待完善

- [ ] 考虑使用 SDK 内省机制动态获取方法归属
- [ ] 添加单元测试确保路由正确性

### 相关文件

- `packages/core/compute/actors/amazingdata_actor.py`

---

## 备注

建议将来使用装饰器或配置文件来管理方法路由，避免硬编码导致的遗漏问题。

---

## 解决记录

> 解决日期: 2026-01-16
> 解决方式: 实现自动发现机制，使用 dir() 和 callable() 动态扫描 SDK 对象

### 最终解决方案

**核心思路**：启动时自动扫描 BaseData、MarketData、InfoData 的所有公共方法，建立路由映射表。

**修改内容**：

1. 添加 `_method_routes` 字典存储方法到对象类型的映射
2. 新增 `_build_method_routes()` 方法：
   - 使用 `dir()` 获取所有方法名
   - 过滤私有方法和非可调用对象
   - 按优先级构建路由（base_data > market_data > info_data）
3. 修改 `_route_method()` 方法：
   - 首次调用时触发自动发现
   - 从映射表查找方法归属
   - 未找到时使用默认路由（InfoData）

### 技术亮点

- 自动化：无需手动维护方法列表，SDK 升级后自动适配
- 延迟初始化：首次调用时才构建映射，避免启动开销
- 可观测性：详细日志记录发现的方法数量和分布
- 向后兼容：未找到的方法默认路由到 InfoData

### 效果

- 自动发现 100+ 个方法，无需手动维护
- 彻底解决方法遗漏问题
- 代码量减少，可维护性提升
