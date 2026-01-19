# AkShare "直连模式"和"代理模式"日志同时出现造成混淆

> 发现日期: 2026-01-19
> 发现位置: packages/core/infrastructure/providers/implementations/akshare/akshare_adapter.py:91, packages/core/utils/network/akshare_proxy.py:36
> 类型: docs
> 严重程度: low
> 状态: open

---

## 问题描述

系统启动时，日志同时显示"直连模式"和"代理模式"的信息，造成用户困惑：

```
使用AkShare直连模式，备用代理模式
配置 akshare 使用 Worker 代理
```

### 根因分析

两条日志来自初始化的不同阶段，实际含义不同：

| 日志 | 来源文件:行号 | 实际含义 |
|------|---------------|----------|
| "使用AkShare直连模式，备用代理模式" | `akshare_adapter.py:91` | 适配器层选择直连作为主模式，代理作为备用 |
| "配置 akshare 使用 Worker 代理" | `akshare_proxy.py:36` | 实际应用了 monkey patch，所有请求将通过 Worker 代理 |

### 实际行为

虽然适配器选择"直连模式"，但 `patch_akshare()` 函数会拦截所有 `requests.get/post/request` 调用并转发到 Worker 代理。所以实际上**所有请求都走代理**。

### 影响

- 用户困惑：不确定实际使用的是直连还是代理
- 调试困难：当代理出问题时，日志显示"直连模式"误导调查方向

---

## 发现上下文

> 分析日志 "数据访问失败: akshare -> stock_list" 时，尝试理解请求流程，发现日志措辞矛盾。

---

## 相关代码

### akshare_adapter.py:80-92

```python
async def initialize(self):
    """初始化提供者"""
    if self.use_proxy:
        # 主用代理，备用直连
        self.provider = AkShareProxyProvider()
        self.fallback_provider = AKShareDirectProvider()
        logger.info("使用AkShare代理模式，备用直连模式")
    else:
        # 主用直连，备用代理
        self.provider = AKShareDirectProvider()
        self.fallback_provider = AkShareProxyProvider()
        logger.info("使用AkShare直连模式，备用代理模式")  # <-- 这条日志
```

### akshare_proxy.py:32-36

```python
def patch_akshare():
    # ...
    if not client.use_proxy:
        logger.info("未配置 Worker 代理，akshare 将使用直连模式")
        return

    logger.info(f"配置 akshare 使用 Worker 代理: {client.worker_url}")  # <-- 这条日志
```

---

## 建议修复方案

### 方案 A: 修改日志措辞

```python
# akshare_adapter.py
logger.info("AkShare适配器初始化: 主=AKShareDirectProvider, 备用=AkShareProxyProvider")

# akshare_proxy.py
logger.info(f"AkShare请求拦截已启用: 通过 Worker 代理 {client.worker_url}")
```

### 方案 B: 统一日志输出点

将两个初始化步骤的日志合并为一条：

```python
# 在最终初始化完成后输出一条清晰的日志
logger.info("AkShare数据源就绪: 请求将通过 Worker 代理转发 (URL: {url})")
```

### 预估工作量

- [x] 小（< 30 分钟）

---

## 备注

此问题优先级低，但对于生产环境的问题排查有帮助。建议在修复超时机制问题时顺便处理。
