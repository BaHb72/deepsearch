# check-amazingdata 总状态掩盖 TGW 配置失败

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: test
- **状态**: resolved

## 问题描述

`check-amazingdata` 在 `TGW 日志配置` 为 `failed` 时，命令总状态仍返回 `ok`。这会让自动化巡检误判为全绿。

## 关键证据

- `packages/core/cli/main.py:502`
- 复现场景：`uv run --python ./.venv/Scripts/python.exe python -m core.cli.main check-amazingdata prod --timeout 1`
- 复现结果：`checks` 中存在 `TGW 日志配置=failed`，但顶层 `status=ok`

## 影响

- CI/运维脚本无法准确识别局部失败
- 需要人工解析详情字段，自动化价值下降

## 建议修复

1. 增加状态聚合规则（`failed > warning > ok`）
2. 对“非致命失败”单独标注等级，避免误报
3. 增加 CLI 单元测试覆盖聚合逻辑

## 处理优先级

P1

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 在 `packages/core/cli/main.py` 新增检查结果聚合逻辑（`failed > warning > ok`）
  - 修正最终退出码：顶层状态为 `failed` 时返回非零退出码
  - 新增测试 `tests/unit/cli/test_check_amazingdata_command.py::test_check_amazingdata_marks_overall_failed_when_tgw_path_missing`
  - 实测 `uv run deepsearch check-amazingdata prod --timeout 1`，当 TGW 路径不存在时顶层状态正确为 `failed`
