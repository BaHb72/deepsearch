# API 与 SDK 代码格式不一致

> 发现日期: 2026-01-16
> 发现位置: apps/api/api/endpoints/amazingdata/*.py
> 类型: architecture
> 严重程度: medium
> 状态: resolved
> 解决日期: 2026-01-16

---

## 问题描述

API 层使用的股票代码格式与 AmazingData SDK 期望的格式不一致，导致部分接口无法正确查询数据。

### 现象

- API 使用格式：`SH.600000`（市场前缀）
- SDK 期望格式：`600000.SH`（市场后缀）

### 影响

- 传递给 SDK 的代码格式不正确，可能导致查询失败或返回空数据
- 用户需要知道正确的格式才能调用接口

---

## 发现上下文

> 在分析 AmazingData SDK 方法签名和测试 API 接口时发现

通过查看 SDK 源码和 API 端点定义，发现代码格式约定不统一。

---

## 相关代码

```python
# API 端点示例 (apps/api/api/endpoints/amazingdata/basic_data.py)
# 用户传入: SH.600000
async def get_stock_basic(request: StockBasicRequest):
    result = await provider.get_stock_basic(code_list=request.code_list)
    # SDK 期望: 600000.SH

# SDK 方法签名
def get_stock_basic(self, code_list):
    # code_list 元素格式应为 "600000.SH"
    pass
```

---

## 建议修复方案

### 方案 1: 在 API 层做格式转换

```python
def normalize_code(code: str) -> str:
    """统一代码格式: SH.600000 -> 600000.SH"""
    if '.' in code:
        parts = code.split('.')
        if len(parts) == 2:
            if parts[0] in ('SH', 'SZ', 'BJ'):
                return f"{parts[1]}.{parts[0]}"
    return code
```

### 方案 2: 在 ActorWrapper 层统一转换

在 `method_proxy` 中检测并转换代码格式参数。

### 方案 3: 在 Actor 层转换

在 `_route_method` 调用前转换参数格式。

### 预估工作量

- [x] 小（< 30 分钟）

### 相关文件

- `apps/api/api/providers.py`
- `apps/api/api/endpoints/amazingdata/*.py`
- `packages/core/compute/actors/amazingdata_actor.py`

---

## 备注

建议选择方案 2（ActorWrapper 层转换），这样可以在一个地方统一处理，不需要修改每个 API 端点。

---

## 解决记录

> 解决日期: 2026-01-16
> 解决方式: 在 ActorWrapper 层统一转换代码格式

### 最终解决方案

**核心思路**：在 ActorWrapper 的 method_proxy 中自动检测并转换股票代码格式，对上层 API 透明。

**修改内容**：

1. 新增 `normalize_stock_code()` 函数（`apps/api/api/providers.py`）
   - 自动识别格式：如果是 `SH.600000`，转换为 `600000.SH`
   - 已是正确格式则直接返回
   - 支持 SH、SZ、BJ 市场

2. 新增 `normalize_code_list()` 函数
   - 批量转换代码列表
   - 支持字符串、列表、None 类型

3. 在 `method_proxy` 中应用转换
   - 自动转换 `code` 参数
   - 自动转换 `code_list` 参数
   - 转换发生在参数传递给 Actor 之前

### 技术亮点

- 单一职责：在 ActorWrapper 层统一处理，避免在每个 API 端点重复代码
- 透明性：对 API 调用者完全透明，可以使用任何格式
- 容错性：转换函数能处理各种格式，包括已经是正确格式的代码
- 易测试：独立的转换函数，易于单元测试

### 效果

- 彻底解决格式不一致问题
- API 调用者无需关心代码格式
- 代码量少（约30行）
