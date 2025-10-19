# AmazingData SDK 异常退出情况报告

## 现象概述

- 触发流程：在 WebUI 发起「测试 AmazingData 数据源」，后台成功完成登录，日志出现 “AmazingData 登录成功 / AmazingData 优化版本连接成功”。
- 随后主进程立即被操作系统终止，退出码为 `0xC0000005`（Windows `STATUS_ACCESS_VIOLATION`）。
- 崩溃发生前没有 Python Traceback，FastAPI 没有输出异常响应，只留下原生 SDK 的 TGW 日志和系统退出码。

## 关键日志

```
2025-10-18 19:53:58.435 INFO  AmazingData 登录成功
2025-10-18 19:53:58.435 INFO  AmazingData 优化版本连接成功
[Process Exit] code = -1073741819 (0xC0000005)
```

`0xC0000005` 为访问违规错误，说明崩溃在 C/C++ 层发生，与 Python 解释器本身无关。

## 初步原因分析

1. 当前默认实现（`OptimizedAmazingDataProvider`）直接在主解释器内调用官方 SDK。
2. SDK 在登录完毕后会启动推送线程和心跳逻辑；若其内部模块访问无效内存或调用 `ExitProcess`，Python 无法捕获，整个主进程被系统终止。
3. 该错误只在原生 DLL 层留下退出码，没有 Python 级别的异常栈，因此日志看起来像是“登录成功后突然退出”。

## 影响范围

- 运行在「优化模式」(`implementation_mode = "optimized"`) 的任何环境都会受到影响。
- WebUI、API 服务、后台任务与 SDK 同进程运行时都会被一并结束，造成服务不可用。

## 处置方案

1. **强制切换到进程隔离模式**  
   - 已在配置与代码层面默认使用 `implementation_mode: process`。  
   - 该模式通过 `ProcessIsolatedAmazingDataProvider` 将 SDK 放入子进程，主进程只负责 IPC 通信。
2. **在进程隔离模式下的行为**  
   - 即便 SDK 再次触发访问违规，只会导致子进程退出；主进程会记录日志并按策略重启子进程，不会导致整个 Web 服务崩溃。
3. **必要时收集 SDK Dump**  
   - 若仍需定位 SDK 内部缺陷，可在子进程中开启迷你转储（MiniDump）或联系 SDK 厂商获取补丁。

## 后续建议

- 观察切换到 process 模式后的运行日志，确认不再出现 `0xC0000005` 及“Server.serve() was cancelled”类异常。
- 与 SDK 厂商沟通，提供崩溃时间点与 TGW 日志，确认是否已有修复版本。
- 若需进一步调试，可在隔离子进程外层增加保活与重试策略，同时保留崩溃 dump 以供分析。

---

> 备注：本报告针对 2025-10-18 19:53 左右的线上日志，若后续出现新的异常码或不同堆栈，需要另行采集和分析。*** End Patch*** End Patch
