# Provider 契约错配、预加载配置丢失与 Dask 镜像配置泄露边界问题

- **发现日期**: 2026-02-17
- **严重程度**: 高
- **类型**: architecture / config / security
- **状态**: resolved

## 问题描述

本轮评审发现 3 个会在常规部署路径触发的 P1 问题：

1. `apps/api/api/endpoints/amazingdata/amazingdata_api.py` 的 `/login` 将 `AmazingDataExtended` 写入 `DataProviderFactory._instances["amazingdata"]`，与工厂路径中 `check_health()` 契约不兼容。  
2. `packages/core/infrastructure/providers/integration/fastapi.py` 的 `_iter_enabled_provider_configs()` 扁平化了 `provider["config"]`，导致 `AkShareFactory` 在预加载时读不到嵌套配置。  
3. `Dockerfile.dask` 通过 `COPY packages/core/config/ ./core/config/` 把完整配置目录打进镜像层，包含 `settings.prod.yaml`、`data_sources.yaml` 等敏感配置载体。

## 关键证据

- `apps/api/api/endpoints/amazingdata/amazingdata_api.py:225`
- `apps/api/api/endpoints/amazingdata/amazingdata_api.py:171`
- `packages/core/infrastructure/providers/integration/fastapi.py:42`
- `Dockerfile.dask:41`
- `packages/core/infrastructure/providers/factory/akshare_factory.py:39`
- `apps/api/api/providers.py:797`

## 影响

1. AmazingData 登录态无法稳定复用，首次业务请求可能触发健康检查异常并重建 Actor。  
2. FastAPI 启动期预加载 `akshare` 时配置回退默认值，可能绕过代理设置。  
3. Dask 镜像分发和仓库存储路径扩大敏感信息暴露面，存在凭据泄露风险。

## 建议修复

1. 登录会话与 Actor 缓存解耦，禁止把本地登录实例写入 `DataProviderFactory` 的 `amazingdata` 键。  
2. 预加载路径保持 provider 外层结构，`config` 子字段原样保留给工厂层解析。  
3. Dask 镜像仅白名单复制配置代码和脱敏模板，避免复制真实 `settings*.yaml` / `data_sources.yaml`。

## 解决记录

- **解决日期**: 2026-02-17
- **解决方式**:
  - `apps/api/api/endpoints/amazingdata/amazingdata_api.py`
    - 引入 `_manual_login_provider` 路由内会话缓存；
    - `get_amazingdata_provider()` 优先复用本地登录会话，失效后回退工厂路径；
    - `/login` 不再写入 `DataProviderFactory._instances["amazingdata"]`。
  - `packages/core/infrastructure/providers/integration/fastapi.py`
    - `_iter_enabled_provider_configs()` 改为返回保留外层结构的 payload，并显式保留 `config` 子字段。
  - `Dockerfile.dask`
    - 移除整目录复制 `packages/core/config/`；
    - 改为白名单复制 `*.py`、`models/`、`services/` 与 `settings.prod.yaml.example` 等脱敏模板。
  - 测试留痕
    - 更新 `tests/unit/api/test_amazingdata_provider_resolution.py`
    - 更新 `tests/unit/infrastructure/providers/test_fastapi_integration.py`
    - 新增 `tests/unit/infrastructure/test_dockerfile_dask_security.py`
