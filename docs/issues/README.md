# 问题追踪

本目录用于追踪开发过程中发现的问题，确保技术债务可见、可排期、可回溯。

## 使用方式

```bash
/track issue [desc]     # 记录新问题
/track list             # 查看待处理问题
/track resolve <file>   # 标记为已解决并归档
```

---

## 统计（更新于 2026-02-17）

| 状态 | 数量 |
|------|------|
| 待处理 | 3 |
| 已解决 | 56 |

---

## 当前待处理（backlog）

- [Provider 双主路径并存，架构未收敛](backlog/2026-02-16_provider-dual-path-not-converged.md) - 高优先级架构收敛问题
- [Provider 核心模块体量过大且职责混杂](backlog/2026-02-16_provider-modules-overloaded-responsibility.md) - 中长期重构债务
- [AmazingData 真实链路回归存在盲区（独立 CLI 探测稳定性不足）](backlog/2026-02-16_amazingdata-real-path-verification-gap.md) - 已有真实探测入口，但 Actor 链路仍有超时/Worker 不可达波动

---

## 最近已解决（resolved）

### 2026-02-17

- [AmazingData 全接口历史测试夹具与进程隔离守卫不兼容](resolved/2026-02-17_amazingdata-all-apis-test-fixture-process-isolation-mismatch.md) - 将全接口历史回归改造为兼容当前隔离守卫的 mock 路径
- [AmazingData 接口实现与 SDK 1.0.28 文档/反编译结果不一致](resolved/2026-02-17_amazingdata-interface-alignment-with-sdk-1.0.28.md) - 补齐缺失接口并修正期权月合约方法命名
- [AmazingData SDK 导入兼容与模块级 __getattr__ 导入期误触发](resolved/2026-02-17_amazingdata-sdk-import-compat-and-module-getattr.md) - 兼容 tgw Login/login 差异，修复导入期误触发崩溃
- [Provider 契约错配、预加载配置丢失与 Dask 镜像配置泄露边界问题](resolved/2026-02-17_provider-contract-config-preload-and-docker-secrets-boundary.md) - 解除登录缓存键污染，修复 AkShare 预加载配置结构，并收紧镜像配置打包边界
- [AmazingData 运行时契约与 SDK 导入链路加固](resolved/2026-02-17_amazingdata-runtime-contract-and-sdk-import-hardening.md) - 修复 get_stock_list(limit) 契约错配、Actor 导入分叉与 check-amazingdata 二次异常

### 2026-02-16

- [数据源优先级语义与排序实现不一致](resolved/2026-02-16_priority-semantics-inconsistency.md) - 明确新旧语义边界并消除歧义
- [领域层直接依赖 AmazingData 具体实现](resolved/2026-02-16_domain-layer-concrete-provider-coupling.md) - 新增 ConceptDataProviderPort，领域层改为依赖端口
- [AmazingData API 在请求阶段重复重建 Provider，绕过既有主链路](resolved/2026-02-16_amazingdata-api-provider-reinit-on-request.md) - 复用工厂实例并补齐 503 语义
- [AmazingData 集成测试脚本存在明文凭证](resolved/2026-02-16_hardcoded-amazingdata-test-credentials.md) - 改为环境变量注入，移除仓库内明文
- [check-amazingdata 缺少 distributed Worker 可用性检查，导致“可达即可用”误判](resolved/2026-02-16_check-amazingdata-missing-distributed-worker-check.md) - distributed 模式下补齐 Worker 健康校验
- [AmazingData 配置解析优先级错误，真实 connection 被顶层 demo 字段覆盖](resolved/2026-02-16_amazingdata-config-connection-precedence.md) - connection 非空字段优先，消除历史 demo 污染
- [start_windows_dask.ps1 在 powershell.exe (5.1) 下解析失败](resolved/2026-02-16_start-windows-dask-powershell51-parse-failure.md) - 重写为 ASCII-only 兼容脚本
- [Docker Dask Scheduler 运行环境缺少核心模块，Actor 反序列化失败](resolved/2026-02-16_docker-dask-scheduler-missing-core-modules.md) - 补齐镜像模块并完成重建验证闭环
- [数据源模块存在乱码文本，影响维护与审查](resolved/2026-02-16_data-source-module-garbled-encoding.md) - 修复关键配置与管理模块中的乱码注释/日志
- [过时 FastAPI Provider 集成路径与现模型不兼容](resolved/2026-02-16_stale-fastapi-provider-integration-path.md) - 修复为 DataSourcesConfig.providers 兼容读取
- [check-amazingdata 总状态掩盖 TGW 配置失败](resolved/2026-02-16_check-amazingdata-overall-status-mask-tgw-failure.md) - 增加聚合状态并修正退出码
- [Dask Worker 与 Scheduler 版本不匹配](resolved/2026-02-08_dask-version-mismatch.md) - 固化依赖并完成容器联调，版本已对齐
- [AmazingData Dask Adapter shutdown 引发 NameError](resolved/2026-02-16_amazingdata-dask-adapter-shutdown-nameerror.md) - 清理旧进程池引用，修复确定性关闭异常
- [Dask Worker 模块导入失败导致数据源不可用](resolved/2026-02-08_dask-worker-module-import-failed.md) - 补齐 Docker Scheduler 存根与插件导入路径
- [AkShare Cloudflare Worker 代理返回大量 520 错误](resolved/2026-02-08_akshare-proxy-520-errors.md) - 增加 Worker 服务端重试，改善源站瞬时故障容错
- [SQLAlchemy AsyncAdaptedQueuePool 缺少连接池统计属性](resolved/2026-02-08_sqlalchemy-pool-stats-error.md) - 迁移到 SQLAlchemy 2.x 连接池统计接口
- [数据库响应时间超过阈值](resolved/2026-02-08_database-response-time-high.md) - 通过冷启动/热路径采样验证为健康，转为已解决

### 历史记录

- 更多历史项请查看 `docs/issues/resolved/` 目录。

---

## 目录结构

```text
docs/issues/
  README.md           # 索引与统计
  backlog/            # 待处理问题
  resolved/           # 已解决问题
```

## 命名规范

`YYYY-MM-DD_<简短描述>.md`
