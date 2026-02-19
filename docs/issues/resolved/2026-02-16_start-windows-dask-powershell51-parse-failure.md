# start_windows_dask.ps1 在 powershell.exe (5.1) 下解析失败

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: config
- **状态**: resolved

## 问题描述

`scripts/start_windows_dask.ps1` 在 `powershell.exe` 执行时报：

- `Missing closing '}' in statement block`

导致 Windows 默认 Shell 无法直接启动 Worker。

## 关键证据

- 命令：`powershell -File scripts/start_windows_dask.ps1 ...`
- 错误定位：`scripts/start_windows_dask.ps1:27`

## 影响

- 本地和 CI 使用 Windows PowerShell 时无法启动 Dask Worker
- 需要绕行 `pwsh`，增加运行门槛

## 建议修复

1. 脚本改为 ASCII-only，避免编码差异触发解析异常
2. 保持 PowerShell 5.1 与 7.x 双兼容

## 处理优先级

P1

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 重写 `scripts/start_windows_dask.ps1`（ASCII-only）
  - 保留原功能：自动检测 HostAddress、连通性检查、启动 Worker
  - 验证：`powershell -File scripts/start_windows_dask.ps1 -SchedulerAddress localhost:1 ...` 可正常执行到连通性失败分支

