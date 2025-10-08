# 数据接口层概览

> 更新时间：2025-10-04  
> 适用范围：`deepsearch.infrastructure.providers`

数据接口层负责连接外部行情与基础数据服务，并为上层组件提供统一的数据获取 API。当前默认启用 **AmazingData** 并优先通过其提供数据；当 AmazingData 不可用或缺少特定数据时，可以启用 AkShare 作为备选，其余实现（如 QMT）保留在仓库中用于兼容研究且默认不加载。

## 1. 目录结构
```
deepsearch/infrastructure/providers/
├── base/                    # Provider 抽象基类与通用异常
├── interfaces/              # 能力枚举、数据模型、协议定义
├── implementations/
│   ├── amazingdata/         # 默认启用的生产数据源
│   ├── akshare/             # 备选数据源（默认关闭，按需启用）
│   └── qmt/                 # QMT 专用脚本，默认禁用
├── managers/                # Provider 调度与健康管理
├── config/                  # Provider 相关设置模型
├── datafeed/                # 数据拉取/合并辅助组件
├── factory.py               # Provider 构造与依赖注入入口
├── registry.py              # Provider 注册信息与能力标记
└── batch_processor.py       # 批量请求与节流工具
```

## 2. 核心抽象
- `interfaces.base.DataProvider`：所有数据提供方的基类，定义初始化、登录、获取行情等通用接口。
- `interfaces.capabilities.DataCapability`：标记 provider 支持的能力（实时行情、历史数据等）。
- `managers.provider_manager.DataProviderManager`：统一调度入口，负责选择可用 provider、记录度量指标。
- `factory.create_data_provider()`：根据 `DeepSearchSettings` 构造并注入指定 provider。

## 3. AmazingData 实现要点
- **封装文件**：`implementations/amazingdata/amazingdata.py`、`*_optimized.py`、`*_safe_wrapper.py` 等。
- **进程隔离**：`amazingdata_process_pool.py` 仅在兼容老 SDK 或进行回归测试时启用，默认使用单进程优化实现。
- **SDK 加载**：`_sdk_loader.py` 在运行时探测 SDK 版本，并根据系统环境选择合适的 DLL/EXE。
- **异常策略**：`amazingdata_safe_wrapper.py` 提供登录重试、熔断、降级开关，并将告警写入 `observability`。

## 4. 配置与启用
配置项位于 `settings.<env>.yaml`：
```yaml
data_sources:
  providers:
    amazingdata:
      enabled: true
      priority: 1
      config:
        connection:
          username: your_username
          password: your_password
          host: 101.230.159.234
          port: 8600
        retry:
          max_attempts: 3
          backoff: 5s
        cache:
          enabled: true
          ttl: 300
```

其他 provider（如 AkShare、QMT）在配置模板中均保持 `enabled: false`，若需调试请于本地单独开启，并告知运维避免误入生产。

## 5. 使用示例
```python
from deepsearch.infrastructure.providers.factory import create_data_provider
from deepsearch.config.manager import settings_manager

settings = settings_manager.get_settings()
provider = create_data_provider(settings.data_sources.providers["amazingdata"])
provider.initialize()

quotes = provider.get_realtime_quotes(["000001", "600000"])
```

如需在异步环境使用，请配合 `datafeed.async_adapter` 提供的包装器，避免直接在协程中调用阻塞 API。

## 6. 监控与诊断
- `managers.metrics_provider` 会将登录成功率、重试次数、请求耗时写入 `observability` 指标。
- CLI：`uv run python -m deepsearch.cli debug datasource status` 可查看当前 provider 连接状态。
- 日志：`logs/datasource/` 下按日期切分的结构化日志，便于排查异常。

## 7. 扩展指引（仅限获批场景）
1. 在 `implementations/<name>/` 目录实现新的 provider，继承 `DataProvider`。
2. 在 `registry.py` 中登记能力标签，并在 `factory.py` 注册构造器。
3. 补充 `settings.*.yaml.example` 中的占位配置及说明。
4. 编写单元与集成测试，确保与现有 AmazingData 流程兼容。
5. 在 `docs/datasources/` 下新增技术说明，并向架构组提交审批。

---
历史实现与淘汰方案请参考 `docs/archive/datasources/`。
