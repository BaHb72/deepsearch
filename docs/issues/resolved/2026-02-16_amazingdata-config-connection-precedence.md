# AmazingData 配置解析优先级错误，真实 connection 被顶层 demo 字段覆盖

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: config
- **状态**: resolved

## 问题描述

`ensure_amazingdata_provider_config()` 在同时存在以下结构时：

1. 顶层 `username/password/host/port`（历史 demo 字段）
2. `connection` 内真实连接配置

会把顶层字段覆盖到 `connection`，导致实际登录走错账号和地址。

## 关键证据

- 生效配置中同时存在：
  - `username=demo_user`
  - `connection.username=212200038719`
- 修复前解析结果使用 `demo_user@1.2.3.4`
- 代码位置：`packages/core/infrastructure/providers/implementations/amazingdata/config.py`

## 影响

- AmazingData 登录失败或连接到错误主机
- 分布式链路排障复杂，症状与根因不直观

## 建议修复

1. 当 `connection` 存在时，优先使用其非空字段
2. 顶层字段仅作为缺省回退
3. 增加单测覆盖“connection 与顶层冲突”场景

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 修改 `ensure_amazingdata_provider_config()` 合并逻辑：
    - 改为“顶层先合并，再用 `connection` 非空字段覆盖”
  - 新增测试 `tests/unit/infrastructure/providers/test_amazingdata_config_resolution.py`
    - `test_ensure_config_prefers_connection_over_legacy_top_level_fields`
    - `test_ensure_config_uses_top_level_when_connection_missing`
