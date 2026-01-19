# DaskAdapter: 日志标识规范化

> 日期: 2026-01-18
> 模块: packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py
> 类型: optimization

---

## 为什么要改

### 遇到的问题

日志输出使用 `[DaskAdapter]` 作为标识前缀，在系统有多个组件时，难以快速区分日志来源：

```
[DaskAdapter] 初始化成功 | worker=tcp://...
```

问题：

1. `DaskAdapter` 是实现层面的术语，不够直观
2. 如果未来有其他 Dask 适配器（如 AkShare/Dask），会产生混淆
3. 无法通过日志前缀快速关联到具体的数据源

### 现有方案的问题

`[DaskAdapter]` 只描述了"如何实现"（通过 Dask），没有说明"为谁实现"（AmazingData 数据源）。

---

## 最终方案

### 选择: 采用 `[Provider/Component]` 命名模式

将日志标识改为 `[AmazingData/Dask]`：

```
[AmazingData/Dask] 初始化成功 | worker=tcp://...
```

**原因**:

1. **数据源优先**：AmazingData 是业务概念，放在前面表明这是哪个数据源的日志
2. **组件次之**：Dask 说明实现方式，帮助定位技术细节
3. **统一风格**：为其他数据源（MiniQMT、AkShare）建立命名规范

### 关键改动

#### 文件: `dask_adapter.py`

```python
# 改之前
logger.info("[DaskAdapter] 初始化成功 | worker={} | actor=available", ...)

# 改之后
logger.info("[AmazingData/Dask] 初始化成功 | worker={} | actor=available", ...)
```

共 20 处替换，涵盖：

- 初始化日志（成功/失败）
- Worker 发现日志
- 任务提交日志
- 调用结果日志（成功/失败/超时）
- 重试日志
- 关闭日志

---

## 注意事项

### 命名规范建议

未来其他数据源的日志标识应遵循同样模式：

| 数据源 | 组件 | 日志标识 |
|-------|------|---------|
| AmazingData | Dask 适配器 | `[AmazingData/Dask]` |
| AmazingData | 本地 SDK | `[AmazingData/Local]` |
| MiniQMT | 交易接口 | `[MiniQMT/Trade]` |
| AkShare | HTTP 客户端 | `[AkShare/HTTP]` |

### 如果要改回去

直接全局替换 `[AmazingData/Dask]` 为 `[DaskAdapter]` 即可，但不建议这样做。

---

## 关键结论

> 日志标识应该回答"谁的日志"而不仅仅是"什么组件的日志"，采用 `[Provider/Component]` 模式提高可观测性。
