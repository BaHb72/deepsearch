# 问题追踪

本目录用于追踪在开发过程中发现的问题，确保技术债务不被遗忘。

## 使用方式

### 记录新问题

```bash
/issue
```

### 查看待处理问题

```bash
/issue list
```

### 标记问题已解决

```bash
/issue resolve <issue-file>
```

---

## 统计

| 状态 | 数量 |
|------|------|
| 待处理 | 13 |
| 已解决 | 9 |

---

## 按严重程度分类

### Critical (0)

（无）

### High (6)

- [Dask Worker 内存超限导致 OOM](backlog/2026-01-19_dask-worker-memory-exceeded.md) - Worker 内存超限，进程被 SIGKILL (137) 终止
- [Dask Worker 模块导入失败](backlog/2026-01-19_dask-worker-module-import-failure.md) - Worker 进程无法导入 core.infrastructure.providers.implementations 模块
- [数据源访问失败与系统健康降级](backlog/2026-01-18_datasource-access-failures.md) - DaskAdapter 超时、AkShare fallback 失败、Redis 响应慢
- [AkShare Provider 生命周期问题](backlog/2026-01-16_akshare-provider-lifecycle.md) - Provider 初始化和清理流程
- [AmazingData SDK 超时配置未被使用](backlog/2026-01-18_amazingdata-timeout-config-unused.md) - server.py 创建 DaskAdapter 时未传递 timeout 参数
- [SDK 架构导致首次调用超时](backlog/2026-01-18_amazingdata-first-call-timeout.md) - 首次调用触发完整登录流程（30-60s）超过 45s 阈值

### Medium (3)

- [AmazingData SDK Prewarm 登录不稳定](backlog/2026-01-19_amazingdata-sdk-prewarm-login-instability.md) - Worker-0 首次登录超时，需重试才成功
- [前后端超时配置不同步](backlog/2026-01-18_frontend-backend-timeout-mismatch.md) - 前端 30s、后端 45s，前端可能先超时
- [SDK 无 HTTP 连接复用](backlog/2026-01-18_amazingdata-no-http-connection-reuse.md) - 每次调用新建连接，是 15-30s 延迟的主因

### Low (0)

（无）

---

## 已解决问题

### 2026-01-16 解决

- [AmazingData ActorWrapper 方法代理设计缺陷](resolved/2026-01-16_amazingdata-actor-wrapper-design.md) - 使用 inspect.signature() 自动转换参数，消除硬编码映射表
- [AmazingData Actor _route_method 路由不完整](resolved/2026-01-16_amazingdata-route-method-incomplete.md) - 实现自动发现机制，动态扫描 SDK 方法
- [API 与 SDK 代码格式不一致](resolved/2026-01-16_code-format-inconsistency.md) - 在 ActorWrapper 层统一转换代码格式
- [Dask Worker 启动机制脆弱](resolved/2026-01-16_dask-worker-startup-fragile.md) - 添加健康检查和启动重试机制
- [MiniQMT reconnect 接口导致服务崩溃](resolved/2026-01-16_miniqmt-reconnect-crash.md) - 使用 Actor 模式重新实现
- [MiniQMTActor 缺少核心方法实现](resolved/2026-01-16_miniqmt-actor-missing-methods.md) - API 端点改用 Actor.call() 方法
- [MiniQMT divid-factors 接口 DataFrame 判断错误](resolved/2026-01-16_miniqmt-divid-factors-dataframe-bug.md) - 改用 is_empty 检查
- [MiniQMT 财务数据接口超时问题](resolved/2026-01-16_miniqmt-financial-timeout.md) - 添加 asyncio.wait_for 超时保护
- [Web 应用中存在未使用的变量声明](resolved/2026-01-16_unused-variables-web-app.md) - 清理未使用变量

---

## 目录结构

```text
docs/issues/
  README.md           # 本文件 - 问题索引和统计
  backlog/            # 待处理的问题
  resolved/           # 已解决的问题
```

## 问题文件命名规范

`YYYY-MM-DD_<简短描述>.md`

示例：

- `2026-01-16_unused-imports-in-providers.md`
- `2026-01-16_missing-error-handling-akshare.md`
