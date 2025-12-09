# 测试模块概览

## 模块定位

`deepsearch/tests` 当前聚焦于领域实体的单元测试，为后续扩展提供骨架。目录结构按测试级别（unit/integration/e2e）预留，现阶段主要覆盖领域模型的校验逻辑。

## 现有用例

- `unit/domain/test_entities.py`：
    - 验证 `Stock` 实体的停/复牌、价格更新、等值判断。
    - 测试 `Price` 值对象的输入校验与涨跌幅计算。
    - 覆盖 `Trade`、`Order` 的成交价值、手续费、部分成交、取消等行为。
    - 使用 `pytest` 断言异常消息、类型和数值，确保领域层约束可靠。

## 结构设计

- `tests/unit/` 预留单元测试目录；未来可在其中细分 `application/`, `infrastructure/` 等子目录。
- 可根据需要新增 `tests/integration/`, `tests/e2e/`, `tests/benchmark/` 等，保持与仓库整体架构一致。

## 扩展建议

- 引入策略或应用层逻辑后，应在 `tests/unit` 增补对应测试，并结合 `pytest` fixture 与 `asyncio` 支持。
- 对外部 IO 依赖可使用 `pytest-mock` 或自定义 stub，遵循 ports + adapters 原则进行隔离。
