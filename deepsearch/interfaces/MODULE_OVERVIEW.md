# 接口聚合模块概览

## 模块定位

`deepsearch/interfaces` 用于集中导出跨模块会复用的协议类型，充当“公共接口层”。当前仓库中主要聚焦数据服务相关的类型别名与缓存配置，避免上层代码直接依赖具体的
provider 实现。

## 主要内容

- `data/__init__.py`：
    - 从 `infrastructure.providers.implementations.amazingdata` 导出 `AmazingDataConfig`, `AmazingDataProvider` 以及枚举类型
      `AmazingDataAdjust`, `AmazingDataPeriod`, `AmazingDataSecurityType`。
    - 定义 `DataCache` 数据类，描述缓存策略（TTL、内存容量、Redis 配置、元数据），提供 `to_dict()` 便于序列化。
    - 重新导出常见异常类型：`AuthenticationError`, `RateLimitError`, `DataProviderError`，使上层代码只需依赖
      `deepsearch.interfaces.data` 即可捕获数据源相关异常。

## 使用说明

- 应用层或策略层如需访问 AmazingData provider，可通过 `from deepsearch.interfaces.data import AmazingDataProvider`
  以保持与基础设施实现解耦。
- 缓存策略可通过构造 `DataCache` 并传入 provider manager，实现统一缓存配置。
- 异常处理建议捕获接口层导出的异常类型，而非直接引用实现模块中的具体异常。

## 扩展建议

- 如后续接入新的数据提供商，可在此模块增加新的类型别名或统一异常，将其作为公共合同层供其他模块调用。
