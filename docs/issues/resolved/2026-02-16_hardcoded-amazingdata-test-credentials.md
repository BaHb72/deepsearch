# AmazingData 集成测试脚本存在明文凭证

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: security
- **状态**: resolved

## 问题描述

`tests/integration/amazingdata/test_amazingdata_working.py` 内嵌了真实账号与密码，存在敏感信息泄露风险。

## 关键证据

- `tests/integration/amazingdata/test_amazingdata_working.py:27`
- `tests/integration/amazingdata/test_amazingdata_working.py:28`

## 影响

- 仓库泄漏时凭证暴露风险高
- 凭证轮换不受控，容易形成“脚本可跑但不可审计”的隐患

## 建议修复

1. 以环境变量注入凭证，不在仓库存储明文
2. 无凭证时明确 skip/提示，避免误报失败
3. 保持脚本为真实链路测试，不引入 mock

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - `tests/integration/amazingdata/test_amazingdata_working.py` 改为读取：
    - `AMAZINGDATA_USERNAME`
    - `AMAZINGDATA_PASSWORD`
    - `AMAZINGDATA_HOST`（默认 `101.230.159.234`）
    - `AMAZINGDATA_PORT`（默认 `8600`）
  - 缺少用户名/密码时输出 skip 信息并退出测试流程
  - 清理不规范输出字符，统一为纯文本日志
