# settings.dev.yaml 配置整改说明

## 背景

- 多次在前端保存数据源配置后，`settings.dev.yaml` 出现重复/冲突字段，导致：
    - 表单回显与实际运行状态不一致（如 `default: akshare` 但 AmazingData 已启用）。
    - 进程池与实时行情使用不同凭据，引发二次登录和 “This user does not exist” 错误。
    - Cloudflare、重试等字段重复，增加维护成本。

## 现有问题

1. **默认源与启用状态冲突**  
   `data_sources.default` 保留为 `akshare`，而 `amazingdata` 被启用、`akshare` 关闭。
2. **重复的凭据定义**  
   `config.connection.*` 与同级 `config.username/password/host/port` 同时存在，且值不一致。
3. **占位符未清理**  
   仍残留 `ui_test / secret123 / 9.9.9.9` 等占位账号。
4. **Cloudflare 配置重复**  
   同时存在 `workers` 数组与 `worker_url` 字段。
5. **杂项字段混用**  
   例如 `retryCount` 与 `retry_count` 并存、`rateLimit` 与新的限流字段重叠。

## 整改目标

- 让配置文件内的默认源、凭据、启用状态与运行时保持一致。
- 杜绝重复或过时字段，避免再次回写冗余。
- 确保所有使用 AmazingData 的模块仅依赖单一凭据来源。

## 处理计划

1. **梳理字段**
    - 列出 `settings.dev.yaml` 与 UI 中的所有数据源相关字段，标注冲突项。
    - 确认当前运行依赖的真实凭据，防止清理误删。

2. **清理与合并**
    - 仅保留 `config.connection` 段落中的账号、密码、host、port 等核心字段；删除同级扁平字段及占位符。
    - 将 `data_sources.default` 调整为与启用状态一致（启用 AmazingData 时默认也指向 AmazingData）。
    - 移除 `cloudflare.workers` 等重复配置，仅保留 `worker_url`。
    - 统一字段命名（`retry_count`、`rate_limit` 等）与大小写。

3. **验证回归**
    - 重启后端服务，确认：
        - 进程池与实时行情初始化仅登录一次 AmazingData。
        - 日志不再出现 “This user does not exist”。
        - UI 回显与配置文件互相一致。
    - 按需补充自动化检查（例如启动时校验 default 与 enabled 是否矛盾）。

4. **文档与交付**
    - 更新 README/配置管理说明，约束后续编辑流程。
    - 记录整改前后差异与测试结果，供团队存档。

## 注意事项

- 清理前备份原 `settings.dev.yaml`，必要时可回滚。
- 如果未来改造 `DataProviderFactory`，可考虑直接复用数据源管理器缓存的凭据，避免依赖文件。
- 统一在 UI 保存后审查生成的配置，防止旧版本逻辑再次写入冗余字段。

