# 数据源管理概览

> 更新时间：2025-10-04  
> 覆盖范围：WebUI / FastAPI 后端 / 配置文件

DeepSearch 的数据源管理功能用于维护 AmazingData 连接信息、健康状态与优先级。当前默认启用 AmazingData，AkShare 作为必要时启用的备选数据源；其它 provider 默认关闭，如需本地实验请谨慎调整配置并避免提交到主干。

## 1. 体系结构
```
┌─────────────────────────────────────────┐
│ WebUI                                   │
│  src/pages/SystemConfig/DataSourceConfig │
│  - 表单：账号、主备地址、缓存策略        │
│  - 健康卡片：延迟、失败次数、最近同步     │
├─────────────────────────────────────────┤
│ FastAPI 后端                            │
│  webui/api/endpoints/datasource/         │
│  - datasource_management_api.py          │
│  - datasource_manager.py                 │
│  webui/api/endpoints/amazingdata/        │
├─────────────────────────────────────────┤
│ 基础设施层                              │
│  infrastructure/providers/               │
│  - factory.py / registry.py              │
│  - implementations/amazingdata/*         │
│  - managers/provider_manager.py          │
└─────────────────────────────────────────┘
```

## 2. 配置来源
- 模板：`deepsearch/config/settings.template.yaml`
- 示例：`deepsearch/config/settings.dev.yaml.example`
- 生产：`deepsearch/config/settings.prod.yaml`

关键段落示例：
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
          backup_hosts:
            - 140.206.44.234:8600
        retry:
          max_attempts: 3
          backoff: 5s
        cache:
          enabled: true
          ttl: 300
```
> ⚠️ 注意：示例文件仅包含占位符。实际凭据请放置在本地 `_env` 或加密存储中，禁止提交到仓库。

## 3. 前端体验
- 页面路径：`/system/config/data-source`
- 主要能力：
  - 查看当前启用的数据源及优先级
  - 编辑登录信息与网络参数，保存后同步到配置文件
  - 发起“连接测试”，实时验证 AmazingData 登录与基础拉数
  - 查看最近一次故障、重试次数与熔断状态
- React 组件集中在 `frontend/src/pages/SystemConfig/DataSourceConfig.tsx`，与 `frontend/src/api/datasource.ts` 协同调用后端。

## 4. 后端 API
| 方法 | 路径 | 描述 |
| ---- | ---- | ---- |
| `GET` | `/api/datasource/list` | 读取配置与运行时状态，返回单一 provider 列表 |
| `POST` | `/api/datasource/save` | 保存配置并触发重新加载（自动脱敏密码） |
| `POST` | `/api/datasource/test` | 使用临时配置进行登录与基础查询测试 |
| `GET` | `/api/datasource/stats` | 返回 AmazingData 运行指标（失败率、耗时等） |

所有接口均通过 `datasource_management_api.py` 注册，核心业务逻辑位于 `datasource_manager.py`。

## 5. 运行时策略
- **优先级**：目前仅有 AmazingData，优先级恒为 1；预留字段用于未来扩展。
- **熔断**：`AmazingDataSafeWrapper` 在连续失败达到阈值时会暂时阻断请求，并在 `observability` 写入事件。
- **进程隔离**：默认走单进程优化实现；如需启用 `AmazingDataProcessPool`，须在配置中显式声明并在文档记录原因。
- **监控**：指标通过 `observability.metrics` 输出，日志写入 `logs/datasource/`。

## 6. 回归与诊断
- CLI：`uv run python -m deepsearch.cli debug datasource status`
- 快速脚本：`python tools/quick_datasource_test.py`
- 自动化测试：
  - `tests/integration/amazingdata/test_amazingdata_servers.py`
  - `tests/unit/infrastructure/providers/implementations/test_amazingdata_provider_login.py`

执行发布前建议运行：
```bash
python scripts/run_all_tests.py --quick
uv run pytest tests/integration/amazingdata -n auto
```

## 7. 管理流程提示
1. **更新配置**：先在示例文件中确认结构，再修改对应环境的 `settings.<env>.yaml`。
2. **提交前校验**：确保未提交真实密码，必要时运行 `git grep -i "password\|secret"` 进行自查。
3. **文档同步**：任何接口或流程调整需更新本文件及 `docs/datasources/amazingdata` 下的细化说明。
4. **管理其它数据源**：AkShare 默认保持 nabled: false，当 AmazingData 不可用或无法提供所需数据时，可按流程临时启用；QMT 等其它配置仍需保持关闭，且临时调整需在 PR 中说明原因并确保不会同步到生产环境。

---
更多补充材料参见 `docs/datasources/amazingdata/`。
