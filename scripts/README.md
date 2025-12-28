# scripts/ 目录说明

本目录包含 **SDK测试脚本** 和 **数据验证脚本**。

## 目录结构

| 类别 | 文件模式 | 用途 |
|------|----------|------|
| SDK测试 | `test_amazingdata_*.py`, `test_sdk_*.py` | 测试数据源SDK功能 |
| 数据验证 | `verify_*.py` | 验证数据源返回数据完整性 |
| 探索脚本 | `explore_*.py` | 探索SDK方法和接口 |
| 诊断脚本 | `diagnose_*.py`, `debug_*.py` | 调试连接和配置问题 |
| 运维脚本 | `git-workflow.py`, `run_*.py` | Git工作流和运行脚本 |

## 子目录

- `archive/` - 归档的旧版本脚本
- `probes/` - 接口探测脚本
- `tests/` - 测试相关脚本

## 运行方式

```bash
# 运行单个测试脚本
uv run python scripts/test_amazingdata_simple.py

# 运行所有测试
uv run python scripts/run_all_tests.py
```

## 相关目录

- `tools/` - 开发工具和架构迁移脚本
- `tests/` - pytest单元测试和集成测试
