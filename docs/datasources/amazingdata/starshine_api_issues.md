# 银河证券星耀数智数据源 API 问题记录

> 更新时间：2025-10-10  
> 用途：记录官方 SDK/TGW 在 DeepSearch 接入过程中出现的缺陷与追踪状态

本文件用于汇总银河证券星耀数智数据源（AmazingData / TGW）在接入过程中观察到的客观问题与原因分析。

## 2025-09-24 Python 3.13 兼容性故障
- **现象**：在 Python 3.13.7 环境下导入 `AmazingData` SDK 时抛出 `AttributeError: module 'tgw' has no attribute 'ILogSpi'`，系统日志提示 SDK 未正确加载。
- **原因**：随 SDK 提供的 `tgw` 二进制扩展仅覆盖 Python 3.6/3.8/3.9 版本。虽然安装包目录中包含 `win_py310_x64_package` 及以上分支，但缺少对应 `_tgw.pyd` 文件，导致 Python ≥3.10 环境无法加载 `ILogSpi`。

> 如需补充新的问题记录，请在本文件中追加章节，并同步更新 [amazingdata_degraded_mode.md](./amazingdata_degraded_mode.md) 与 [resilience_strategy.md](./resilience_strategy.md) 的处置方案。
