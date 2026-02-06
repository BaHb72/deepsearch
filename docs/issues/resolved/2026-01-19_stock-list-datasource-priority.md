# stock_list 接口使用 AkShare 而非 AmazingData 作为主数据源

> 发现日期: 2026-01-19
> 发现位置: packages/core/config/module_sources.yaml:60-62
> 类型: config
> 严重程度: medium
> 状态: open

---

## 问题描述

`stock_list` 接口在 `module_sources.yaml` 配置文件中被设置为使用 AkShare 作为主数据源，而大部分其他接口（如 `market_strength`、`board_overview`、`realtime_quotes`）使用 AmazingData 作为主数据源。

### 现象

用户日志显示：

```
使用AkShare直连模式，备用代理模式
数据访问失败: akshare -> stock_list [None] None
```

查看配置文件 `module_sources.yaml:60-62`：

```yaml
access_types:
  stock_list:
    primary: akshare
    fallback: [ amazingdata ]
```

以及 `stock_list_sync` 模块配置（44-46行）：

```yaml
modules:
  stock_list_sync:
    primary: akshare
    fallback: [ amazingdata ]
```

### 影响

- AkShare 获取股票列表需要下载 557 条数据，每条约 1.2s，总耗时较长
- 当 AkShare 服务不稳定时，股票列表获取失败，影响其他功能
- 不同接口使用不同数据源可能导致数据质量/格式不一致

---

## 发现上下文

> 调查板块数据预热超时问题时，发现 stock_list 是唯一一个默认使用 AkShare 的基础接口

分析日志 "数据访问失败: akshare -> stock_list" 时发现此配置差异。

---

## 相关代码

### 配置文件 (module_sources.yaml)

```yaml
# 按访问类型的默认配置（当模块未显式配置时使用）
access_types:
  stock_list:
    primary: akshare
    fallback: [ amazingdata ]

# 模块配置
modules:
  stock_list_sync:
    primary: akshare
    fallback: [ amazingdata ]
```

### 调用方 (data_unified.py)

`apps/api/api/endpoints/data/data_unified.py:262-321` 中的 `_get_stock_list` 函数会根据配置选择数据源。

---

## 建议修复方案

### 方案 A: 统一数据源优先级

将 `stock_list` 也配置为 AmazingData 优先：

```yaml
access_types:
  stock_list:
    primary: amazingdata
    fallback: [ akshare ]
```

### 方案 B: 保持现状（需文档说明）

如果 AkShare 的股票列表数据更准确/完整，保持现状但添加文档说明原因。

### 预估工作量

- [x] 小（< 30 分钟）- 方案 A
- [ ] 中（30分钟 - 2小时）- 需要对比两个数据源的数据质量

---

## 备注

此问题与超时机制问题（Issue #3）相关。当 stock_list 使用 AkShare 时，批量下载的长耗时可能触发超时。
