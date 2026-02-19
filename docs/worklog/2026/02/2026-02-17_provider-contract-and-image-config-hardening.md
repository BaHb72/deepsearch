# Provider 契约与镜像配置边界加固

> 日期: 2026-02-17
> 模块: amazingdata-api, provider-fastapi-integration, docker-dask
> 类型: bugfix / security-hardening

---

## 为什么要改

### 遇到的问题

评审发现三个同源问题：

1. `/api/amazingdata/login` 把本地 `AmazingDataExtended` 写入 `DataProviderFactory` 的 `amazingdata` 缓存键，和 Actor 路径的 `check_health()` 契约冲突。
2. FastAPI 预加载路径将 provider 配置扁平化，导致 `AkShareFactory` 读取不到 `config` 内层配置。
3. Dask 镜像通过整目录复制把 `settings.prod.yaml` 与 `data_sources.yaml` 带入镜像层，扩大了敏感信息暴露面。

### 现有方案的问题

- 方案在“看起来可运行”的同时，破坏了运行时契约一致性与安全边界。
- 问题在部署流程中容易触发，且会表现为启动成功后业务路径异常，排障成本高。

---

## 尝试过的方案

### 方案 A：在工厂路径里兼容 `health_check()` / `check_health()`

**思路**: 保留 `/login` 写工厂缓存的行为，通过增加健康检查兼容逻辑兜底。

**问题**: 仍然把“本地登录会话”与“Actor 缓存键”混在一起，职责边界不清晰。

### 方案 B：登录会话与工厂缓存解耦（最终采用）

**思路**: `/login` 只维护路由内会话缓存，不写入 `DataProviderFactory._instances["amazingdata"]`。

**收益**: 保留登录凭据复用，同时不破坏 Actor 路径契约。

---

## 最终方案

### 选择: 方案 B + 配置结构保真 + 镜像白名单复制

**原因**:

1. 契约清晰：本地会话与 Actor 缓存职责分离。
2. 配置一致：工厂层接收原始结构，避免隐式默认回退。
3. 安全收敛：镜像层不携带真实敏感配置文件。

### 关键改动

- `apps/api/api/endpoints/amazingdata/amazingdata_api.py`
  - 新增 `_manual_login_provider` 本地会话缓存；
  - `get_amazingdata_provider()` 优先复用本地会话并做健康检查；
  - `/login` 不再写入 `DataProviderFactory` 缓存键。
- `packages/core/infrastructure/providers/integration/fastapi.py`
  - `_iter_enabled_provider_configs()` 返回保留外层结构的 provider payload；
  - `config` 子字段保持嵌套，交由工厂解析。
- `Dockerfile.dask`
  - 移除 `COPY packages/core/config/ ./core/config/`；
  - 改为复制配置代码文件、模型目录、服务目录与脱敏模板（`settings.prod.yaml.example`）。
- 测试
  - `tests/unit/api/test_amazingdata_provider_resolution.py`
  - `tests/unit/infrastructure/providers/test_fastapi_integration.py`
  - `tests/unit/infrastructure/test_dockerfile_dask_security.py`

---

## 解决路径（留痕）

1. 依赖状态确认：`uv pip check --python ./.venv/Scripts/python.exe`。
2. 调用链定位：确认 `DataProviderFactory.get_provider_async()` 对 `check_health()` 的硬依赖，以及 `AkShareFactory` 对嵌套 `config` 的读取方式。
3. 代码修复：按“最小变更 + 契约收口”原则分别处理 API、FastAPI 集成与 Docker 打包边界。
4. 回归验证：补齐对应单测并执行目标测试集。
5. 文档归档：更新 `docs/issues`、`docs/worklog/index.json`、`docs/tracker/index.json` 建立关联。

---

## 关键结论

> 对运行路径稳定性最有效的修复，不是增加更多兼容分支，而是恢复“缓存职责、配置结构、安全边界”三条主线的一致性。
