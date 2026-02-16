# AmazingData Dask Adapter shutdown 引发 NameError

> 发现日期: 2026-02-16
> 发现位置: packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py:1544
> 类型: bug
> 严重程度: high
> 状态: resolved

---

## 问题描述

`AmazingDataDaskAdapter.shutdown()` 在 Redis 队列模式下调用时触发运行时异常：

```text
NameError: name '_DASK_PROCESS_POOL' is not defined
```

### 影响

- 适配器关闭流程中断
- 生命周期清理链路不完整，可能影响服务优雅关闭
- 错误为确定性触发，不依赖外部网络环境

---

## 根本原因

`dask_adapter.py` 已迁移为 Redis 任务队列架构，不再维护 Dask 进程池；
但 `shutdown()` 仍保留旧版本的全局变量清理逻辑，引用了未定义的 `_DASK_PROCESS_POOL`。

---

## 修复方案

- 删除 `shutdown()` 中对 `_DASK_PROCESS_POOL` 的全局引用与关闭代码
- 保留适配器状态位清理与日志记录

---

## 解决记录

> 解决日期: 2026-02-16
> 解决方式: 移除过时进程池清理逻辑，保持 Redis 模式一致性
> 验证方式: 执行最小复现脚本，`await AmazingDataDaskAdapter().shutdown()` 返回 `shutdown_ok`

---

## 关联改动

- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
- `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py`
