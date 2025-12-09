# AmazingData 登录异常排查进展记录

> 记录时间：2025-10-24  
> 记录人：自动运维助手（Codex）

## 1. 背景简述

- 现场日志持续出现 `CheckLogonLegal username is empty or over kUsernameLen`、`The internet mode of tgw init failed`
  等报错，提示凭证缺失或会话初始化失败。
- 同一账号被多入口复用（进程隔离、优化版、WebUI）导致登录互踢，触发 SDK Session 失效。
- 当前目标是统一凭证管理、收敛登录入口、强化异常兜底，避免核心行情链路断流。

## 2. 今日推进（2025-10-24）

1. **配置补全与掩码处理**
    - 在 `providers.registry` 增补 `_patch_missing_credentials`，当前端传入的是掩码值（仅 `*`）或留空时，会回退读取
      `settings.<env>.yaml` 中的真实凭证并补写。
    - 新增 `_is_masked_credential` 判定逻辑，确保不会把非字符串/空白误判为有效凭证，同时在缺少 fallback
      配置时输出告警日志，方便追踪配置缺口。
    - 凭证合并后统一执行 `_sanitize_payload` 与 `_validate_connection`，保证结构化字段和模式校验不被绕过。

2. **进程隔离模式登录校验**
    - `ProcessIsolatedAmazingDataProvider._perform_login` 在发起登录前强制校验用户名、密码有效性，防止将空值传入 SDK
      触发模糊错误。
    - 若检测到凭证缺失，立即抛出 `DataProviderError` 并写明模式来源，便于故障定位。

3. **WebUI ProviderFactory 重构**
    - 默认路径改为通过 `DataSourceManager` 获取 AmazingData 实例，遵循 `implementation_mode=process` 的配置约束。
    - 仅当设置 `DEEPSEARCH_AMAZINGDATA_STUB` 环境变量时，才回退到旧的直接 `new AmazingDataProvider` 逻辑，并维持原有
      AkShare 兜底。
    - 补充 `_fallback_status` 和 `_provider_health` 的更新逻辑，保证降级原因、时间戳可观察；同时对 “SDK 强制退出” 单独打点记录。
    - 纠正内部导入导致的 `get_data_source_manager` 作用域冲突，杜绝 WebUI 启动阶段出现 “cannot access local variable” 异常。

4. **登录异常与告警统一**
    - `_trigger_alert` 触发时构造的错误信息现在包含退出码 `exit code`，并确保 `DataProviderFactory` 侧同样捕捉该信息用于告警上报。
    - 统一了告警文案和日志等级，后续便于筛检与 Prometheus 侧指标对齐。

## 3. 测试与验证

- 执行 `uv run --python .\.venv\Scripts\python.exe pytest tests/test_amazingdata_isolation.py`。  
  结果：17 项用例中 13 通过、2 跳过、2 失败；失败用例如下：  
  `TestSDKIsolation::test_safe_login_catches_system_exit`  
  `TestSDKIsolation::test_safe_login_catches_system_exit_with_code_1`  
  具体原因：断言仍期望出现“SDK尝试强制退出程序”，而当前告警文案已改为“SDK尝试强制退出，请查看 exit code: {n}”，需要同步测试或文案。
- 在 PyCharm 中使用 `uv run --project D:\Stock\code\deepsearch --module deepsearch run dev --log-level DEBUG` 预热服务时，生成日志
  `C:\Users\bahb6\AppData\Roaming\JetBrains\PyCharm2025.2\scratches\scratch_3.txt`；系统在关机阶段抛出
  `ConnectionResetError` 与跨事件循环的 `RuntimeError`，最终退出码为 -1，尚未进入测试环节即报错，需另行排查。

## 4. 遗留问题 / 风险

- SDK 强退告警文案的最终版本尚未定稿，应确认对终端用户显示的提示后，再同步调整用例或文案。
- 需进一步验证 `DataSourceManager` 初始化是否始终拉起进程隔离实现，避免误回落到优化版或跳过登录池限流。
- 告警触发后暂未将关键字段对接至 Prometheus 指标/值守看板，需要补齐监控链路。
- 当前仅在 AmazingData 路径补上凭证回补逻辑，后续如其他数据源复用掩码策略，应抽象为通用能力。

## 5. 后续计划

1. 决定 SDK 强退提示语的最终版，同步修改 `tests/test_amazingdata_isolation.py` 断言或回滚文案，确保用例恢复通过。
2. 增加一条 DataSourceManager 初始化的集成测试，验证 `implementation_mode=process` 下的登录链路与隔离池限流。
3. 将 `_trigger_alert` 的输出字段接入指标上报，并补充一份运维手册说明如何在告警出现时执行现场确认。
4. 自测通过后，更新《AmazingData SDK 登录修复方案》文档及 README 相关章节，保持对外信息一致。
