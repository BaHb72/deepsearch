# 问题追踪

本目录用于追踪开发过程中发现的问题，确保技术债务可见、可排期、可回溯。

## 使用方式

```bash
/track issue [desc]     # 记录新问题
/track list             # 查看待处理问题
/track resolve <file>   # 标记为已解决并归档
```

---

## 统计（更新于 2026-02-16）

| 状态 | 数量 |
|------|------|
| 待处理 | 0 |
| 已解决 | 40 |

---

## 当前待处理（backlog）

当前 backlog 为空。

---

## 最近已解决（resolved）

### 2026-02-16

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
