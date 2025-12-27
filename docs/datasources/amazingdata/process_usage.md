# AmazingData 进程隔离版使用指南

本文档汇总了进程隔离版 Provider 的推荐用法，并给出可落地的最小示例，便于在业务侧或脚本中快速复用。

## 1. 快速开始（Provider）

- 推荐在生产环境统一使用进程隔离版以规避 SDK 级别的 `SystemExit/TerminateProcess` 风险。
- 入口：`deepsearch.infrastructure.providers.implementations.amazingdata.process`。

示例：

```python
import asyncio
from deepsearch.infrastructure.providers.implementations.amazingdata.process import (
    ProcessIsolatedAmazingDataProvider,
)

CONFIG = {
    "enabled": True,
    "implementation_mode": "process",
    "connection": {
        "username": "your_user",
        "password": "your_pass",
        "host": "101.230.159.234",
        "port": 8600,
        "timeout": 10,
    },
    "worker_env": {"DEEPSEARCH_AMAZINGDATA_STUB": "tests.stubs.amazingdata_stub"},  # 示例
}

async def main():
    provider = ProcessIsolatedAmazingDataProvider(CONFIG)
    try:
        await provider.initialize()
        # K 线 / 实时
        kline = await provider.get_kline_data("000001.SZ", period="1d", limit=5)
        quote = await provider.get_realtime_quote(["000001.SZ", "600000.SH"])
        print(kline, quote)
    finally:
        await provider.close()

asyncio.run(main())
```

## 2. 登录流程复用（login_flow）

- 进程版运行时已内置登录流程（`ProcessIsolatedAmazingDataProvider._perform_login`），如需在自定义 Provider
  或工具脚本中按相同策略执行，可直接复用：

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.process.login_flow import perform_login

# provider: ProcessIsolatedAmazingDataProvider 实例
# adapter: AmazingDataProcessAdapter 实例（provider._ensure_adapter() 获取）
await perform_login(provider, adapter)
```

- 能力：
  - 登录并发节流（全局锁 + 池级序列化）
  - 自动识别 `TGW push init failed`/`SystemExit` 并切换 `api_mode`
  - 成功/失败埋点写入进程池状态

## 3. 告警与日志片段（alert_utils）

如需在登录失败、SDK 异常等场景触发统一告警并附带 TGW 日志片段：

```python
from deepsearch.infrastructure.providers.implementations.amazingdata.process.alert_utils import (
    trigger_alert, collect_tgw_log_snippet,
)

await trigger_alert(provider, "SDK_EXIT", "登录失败：SDK SystemExit")
snippet = collect_tgw_log_snippet(provider, max_lines=20)
print(snippet)
```

- provider.config 可配置 `tgw_log_path` 指向日志文件或目录；目录场景下自动选择最近的 `*.log`

## 4. 订阅恢复（SubscriptionCoordinator）

- 运行时已封装 `ProcessSubscriptionCoordinator` 作为组合成员，断线自动 `drain -> restore`。
- 如需手动管理：

```python
snapshot = await provider.snapshot_subscriptions()
# ... 重连后
await provider.restore_subscriptions(snapshot)
```

## 5. 类型与适配

- 实时行情 TypedDict：`AmazingDataStreamQuote`/`AmazingDataStreamPayload`（见 `amazingdata_types.py`）。
- 市场流适配器 `AmazingDataMarketStreamAdapter` 已采用上述类型，便于 IDE 提示与静态检查。

## 6. 质量与测试

- 本仓库提供 `scripts/run_all_tests.py` 作为一键回归入口：

```powershell
uv run python scripts/run_all_tests.py
```

- 推荐在提交前执行：

```powershell
uv run ruff check deepsearch tests
uv run mypy deepsearch
uv run bandit -r deepsearch
```

## 7. 迁移注意事项

- 代码中出现 `from .amazingdata_process import ...` 的引用，建议统一替换为 `from .process import ...`。
- 外部模块复用登录/告警逻辑时，优先以 `process/login_flow.py`、`process/alert_utils.py` 暴露的函数为主，不再从运行时复制实现。
