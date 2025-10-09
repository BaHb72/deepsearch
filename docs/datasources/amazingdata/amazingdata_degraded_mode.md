# AmazingData 降级模式说明

> 更新时间：2025-10-10  
> 适用范围：AmazingData SDK 暂时不可用、版本不兼容或网络中断时的应急策略  
> 参考资料：`AmazingData_API.md`（2025-09-11，V1.0.8）、[resilience_strategy.md](./resilience_strategy.md)

## 1. 背景
- 2025-09 起，AmazingData 官方针对 Python 3.13 的 SDK 发布节奏与主干不完全同步，历史上曾出现登录模块缺失或签名接口变动。
- 为保障交易与回测流程不中断，系统保留了“降级模式”，在检测到严重故障时以缓存或只读模式继续提供数据服务。
- TGW 及其它第三方桥接组件已明确禁止接入；本文仅描述 AmazingData 自身的降级逻辑。

## 2. 触发条件
- `_sdk_loader.py` 加载 DLL/EXE 失败或检测到关键符号缺失；
- `AmazingDataSafeWrapper` 连续登录失败超过阈值（默认 3 次）；
- `ProcessPool` 子进程崩溃且在回退重试后仍无法恢复；
- 运维通过 CLI/配置显式开启 `degraded_mode`（用于演练）。

## 3. 执行路径
- `amazingdata.py` / `amazingdata_optimized.py`
  - 捕获初始化异常后设置 `_degraded_mode = True`，所有实时/历史接口返回缓存或占位数据，并记录 WARN 日志。
- `amazingdata_safe_wrapper.py`
  - 在降级状态下拒绝新的登录尝试，仅允许读取缓存，避免触发封禁。
- `logs/datasource/`
  - 输出结构化日志（`event=amazingdata.degraded`) 供监控系统捕捉。

## 4. 恢复流程
1. 运维确认 AmazingData 官方已发布兼容版本或网络恢复；
2. 更新本地 SDK（参考 `docs/datasources/amazingdata/setup.md`），确保 `_sdk_loader.py` 成功检测；
3. 重启 DeepSearch 服务或使用 CLI `uv run python -m deepsearch.cli debug datasource restart`；
4. 观察指标与日志，确认登录成功率恢复正常后关闭降级状态。

## 5. 注意事项
- 降级期间默认不允许写入或触发高频接口，避免得到过期数据；
- 如需为回测保留读取能力，可在配置中启用只读缓存，但务必在文档与 PR 中说明；
- 所有降级/恢复操作需在运维记录中登记，方便后续审计。

---
历史故障分析与旧版说明保存在 `docs/archive/datasources/` 中，仅供参考。
