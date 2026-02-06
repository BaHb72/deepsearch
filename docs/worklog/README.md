# 决策日志 (Worklog)

**核心目的：防止同一处代码被反复重构**

记录每次关键调整的**为什么要改**、**尝试过什么方案**、**为什么选择最终方案**。下次遇到类似情况时，先查日志，避免重复踩坑。

## 什么时候记录

**必须记录**:

- 架构/设计层面的调整
- 同步/异步方案的切换
- 重要模块的重构
- 解决了困扰很久的问题
- 尝试了多个方案后选定的最终方案

**不需要记录**:

- lint 错误修复、typo、格式化
- 简单的 bug 修复（原因明显的）

## 如何使用

```bash
# 记录当前改动
/worklog

# 搜索相关历史日志（推荐）
/worklog ref dask worker       # 按关键词搜索
/worklog ref --module provider # 按模块过滤

# 传统搜索方式
grep -r "EventEngine" docs/worklog/
```

## 目录结构

```
docs/worklog/
  YYYY/
    MM/
      YYYY-MM-DD_<module>_<action>.md
```

---

## 模块索引

### Provider

| 日期 | 改动 | 关键结论 |
|------|------|----------|
| [2026-01-15](2026/01/2026-01-15_provider-architecture-refactor.md) | 架构重构 | 使用容器+协议模式替代全局工厂 |

### EventEngine

(暂无记录)

### Dask

| 日期 | 改动 | 关键结论 |
|------|------|----------|
| [2026-01-17](2026/01/2026-01-17_pyproject_package-discovery.md) | 启用自动包发现 | 使用 setuptools.packages.find 替代手动列出包列表，解决 Worker 模块导入失败 |
| [2026-01-17](2026/01/2026-01-17_amazingdata_dask-proxy-registration.md) | Worker 地址修复 | `host.docker.internal` 仅在 Docker 容器内有效，宿主机应使用 `localhost` |

### AmazingData

| 日期 | 改动 | 关键结论 |
|------|------|----------|
| [2026-01-17](2026/01/2026-01-17_amazingdata_redis-result-passing.md) | **Redis 结果传递 (终极修复)** | tornado/asyncio 无法共处，使用 Redis 彻底绕过 Dask Future 返回机制 |
| [2026-01-17](2026/01/2026-01-17_amazingdata_dask-adapter-bugfix.md) | DaskAdapter 运行时错误修复 | Dask远程调用三陷阱：get_worker()、run_in_executor、参数过滤 |
| [2026-01-17](2026/01/2026-01-17_amazingdata_interface-completion.md) | 领域层接口补全 | 接口分层是适配器模式的核心：SDK原生API面向数据源，领域层接口面向业务 |
| [2026-01-17](2026/01/2026-01-17_amazingdata_dask-proxy-registration.md) | Dask 代理注册到 ProviderContainer | 代理模式桥接跨进程抽象，通过 register_external() 实现无缝集成 |

### AI

| 日期 | 改动 | 关键结论 |
|------|------|----------|
| [2026-01-31](2026/01/2026-01-31_ai_analysis-service-phase1.md) | Phase 1 RAG 模式接入 | 独立模块 + Ollama 本地模型 + SSE 流式，完全不影响现有系统 |

### AkShare

(暂无记录)

### MiniQMT

(暂无记录)

### Health Manager / Checker

| 日期 | 改动 | 关键结论 |
|------|------|----------|
| [2026-01-18](2026/01/2026-01-18_health-checker_redis-attribute-fix.md) | Redis 健康检查器属性名修复 | 健康检查器访问组件属性时必须确认实际命名，长期应通过 Protocol 定义接口契约 |
| [2026-01-18](2026/01/2026-01-18_health-manager_enhanced-logging.md) | 增强 unhealthy 日志输出 | 日志应同时给出诊断信息，避免额外步骤确定问题根因 |

---

## 最近记录

- [2026-01-31 AI 分析服务接入 Phase 1](2026/01/2026-01-31_ai_analysis-service-phase1.md)
- [2026-01-18 Health Checker Redis 属性名修复](2026/01/2026-01-18_health-checker_redis-attribute-fix.md)
- [2026-01-18 Health Manager 增强 unhealthy 日志输出](2026/01/2026-01-18_health-manager_enhanced-logging.md)
- [2026-01-17 AmazingData Redis 结果传递 (终极修复)](2026/01/2026-01-17_amazingdata_redis-result-passing.md)
- [2026-01-17 AmazingData DaskAdapter 运行时修复](2026/01/2026-01-17_amazingdata_dask-adapter-bugfix.md)
- [2026-01-17 AmazingData 领域层接口补全](2026/01/2026-01-17_amazingdata_interface-completion.md)
- [2026-01-17 AmazingData Dask 代理注册](2026/01/2026-01-17_amazingdata_dask-proxy-registration.md)
- [2026-01-17 pyproject.toml 启用自动包发现](2026/01/2026-01-17_pyproject_package-discovery.md)
- [2026-01-15 Provider 架构重构](2026/01/2026-01-15_provider-architecture-refactor.md)

---

## 快速搜索

```bash
# 按模块搜索
grep -r "provider" docs/worklog/ -i

# 按问题搜索
grep -r "timeout\|超时\|async\|异步" docs/worklog/

# 按日期范围
ls docs/worklog/2026/01/
```
