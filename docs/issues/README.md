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
| 待处理 | 0 |
| 已解决 | 9 |

---

## 按严重程度分类

### Critical (0)

（无）

### High (0)

（无）

### Medium (0)

（无）

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
