# 配置模块概览

## 模块定位

`deepsearch/config` 提供全局配置生命周期管理：从多环境 YAML 加载、字段校验、迁移、加解密到运行时热更新。模块以 `pydantic`
数据模型约束配置结构，结合 `ConfigManager` 和 `Settings` 类实现“YAML -> 类型化对象 -> 运行态”完整链路。

## 核心组件

- `settings.py`：基于 `pydantic_settings.BaseSettings` 定义 `Settings` 聚合体，列出所有子配置模型（App、Runtime、Database、MarketData
  等），并覆写 `settings_customise_sources` 以 `load_yaml_config` 作为唯一数据源；同时提供 `zeromq` 属性、
  `get_timeseries_config` 等派生访问方法。
- `loader.py`：负责按 `APP__ENV`（默认为 `prod`）定位 `settings.<env>.yaml`。若文件缺失会复制 `.example` 模板或尝试包内备份，成功加载后执行
  `migrate_data_source_config`，必要时自动备份 `.bak` 并写回迁移结果。
- `manager.py`：`ConfigManager` 以单例方式管理原始配置字典，实现查找、深度合并、环境切换、观察者回调、保存与重载。对 CLI
  `config` 命令等运行时修改提供支持。
- `validator.py`：封装结构校验逻辑（依赖 `pydantic` 模型和自定义规则），在 `ConfigManager.load`/`update` 后保证数据满足架构约束。
- `crypto.py`：提供配置项加密/解密工具，配合敏感字段（如数据库密码）使用。
- `data_source_config.py` 与 `migrations/`：维护数据源配置版本迁移脚本，确保旧版配置自动升级到新的 schema。
- `models/`：按照领域划分的 Pydantic 模型集合，如 `MarketRealtimeConfig`、`AmazingDataConfig`、`MessageBusConfig`
  等，对外暴露强类型接口。
- `services/database_connections.py`：对数据库连接信息进行聚合、去重与校验，供基础设施层读取。

## 加载流程

1. 应用启动时（CLI `run` 或测试上下文）通过 `deepsearch.config.get_config()` 或 `get_settings()` 触发 `Settings` 构造。
2. `Settings.settings_customise_sources` 调用 `load_yaml_config`，后者根据 `APP__ENV` 找到对应的 `settings.<env>.yaml`
   ，必要时根据 `.example` 自动生成。
3. `load_yaml_config` 解析 YAML 为字典，执行数据源配置迁移，并返回给 `Settings` 进行 Pydantic 校验。
4. 若外部调用 `config_manager.load`，则在原始字典层面读入文件、合并环境配置、调用 `validator` 校验，并允许注册 watcher 回调。
5. 运行时需要修改配置时可调用 `config_manager.set` 或 CLI `config set`，修改后可通过 `save` 持久化至 YAML。

## 运行时特性

- 所有 YAML 读取使用仓库定义的 `YAML_ENCODING`（通常为 UTF-8）避免编码问题。
- `ConfigManager` 的 `_deep_merge` 支持嵌套字典递归合并，适配环境覆盖策略。
- `Settings` 中的可选配置（如 `amazingdata`、`cloudflare_workers`）默认返回 `None`，外部模块需显式检测。
- `settings` 模块的 `zeromq`、`log_dir` 属性便于其他模块快速获取派生配置，无需重复解析。

## 与其他模块的协作

- `core`, `webui`, `infrastructure` 等在初始化时读取 `Settings`，获取消息总线、数据库、监控等配置。
- `CLI` 的 `config` 子命令通过 `config_manager` 修改 YAML；`application` 层（如市场数据 runner）读取
  `MarketRealtimeConfig`。
- `observability` 通过 `log` 配置控制日志根目录、回滚策略；`memory`、`debug` 模块读取调试/性能开关。

## 扩展建议

- 新增配置类别时，在 `models/` 中定义 Pydantic 模型，并在 `Settings` 中增加字段；同步更新示例 YAML 与
  `settings.template.yaml`。
- 涉及兼容旧版字段时，应在 `migrations/` 中添加脚本，并在 `loader` 中串联执行以保持自动迁移能力。
