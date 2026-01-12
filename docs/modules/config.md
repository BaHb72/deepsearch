# config 模块实现说明

## 模块定位

`deepsearch.config` 负责管理全局配置、密钥与迁移逻辑，提供统一的加载、校验与热更新能力。模块确保不同环境（dev/test/prod）配置结构一致，可通过示例文件快速落地。

## 目录结构

- `settings.py`：核心 `Settings` 数据模型，继承 `BaseSettings` 提供类型安全的配置对象。
- `manager.py`：封装配置加载、合并覆盖与动态刷新流程。
- `loader.py`：解析 `settings.<env>.yaml`，支持分层覆盖与模板变量。
- `validator.py`：对配置进行结构与业务约束校验。
- `crypto.py`：敏感字段加解密工具，结合 Windows 凭据存储。
- `models/`：细化配置领域模型（数据源、缓存、监控等）。
- `migrations/`：配置迁移脚本，适配版本升级场景。

## 核心数据结构

- `DeepSearchSettings`：聚合全局配置，字段包含 `engine`、`webui`、`infrastructure` 等子模型。
- `DataSourceConfig`：描述数据源优先级、故障切换、认证信息。
- `ConfigSnapshot`：记录加载时间、文件来源、Hash，用于热更新比较。

## 关键流程

1. 系统启动时调用 `manager.load_settings(env)`，读取 YAML 并转换为 `DeepSearchSettings`。
2. 校验阶段执行 `validator.validate()`，发现问题会抛出 `ConfigurationError`。
3. 若启用热更新，`manager.watch()` 会监听文件变化并触发回调。
4. 配置对象通过依赖注入提供给各模块，避免重复读取磁盘。

## 扩展与集成

- 新增配置字段时需同步更新 `settings.*.yaml.example` 与 `models/` 定义。
- 涉及敏感信息的字段必须使用占位符，并通过 `crypto` 工具生成密文。
- 配置变更后建议运行 `python tools/validate_settings.py` 进行回归校验。
- 若引入外部配置中心，可在 `loader` 中新增适配器，但需保持 YAML 模板可用。
