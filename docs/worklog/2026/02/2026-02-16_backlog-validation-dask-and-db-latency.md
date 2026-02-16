# backlog 验证: dask 版本漂移与数据库延迟

> 日期: 2026-02-16
> 模块: diagnostics, issues
> 类型: validation

---

## 为什么要做

当前 backlog 仅剩 2 项，需要通过可重复脚本确认：

1. Dask 版本漂移是否仍存在。
2. 数据库慢响应是否仍可复现。

---

## 产出

新增两个最小可复现脚本：

- `tools/validate_dask_version_alignment.py`
- `tools/validate_database_health_latency.py`

---

## 验证结果

### 1) Dask 版本漂移

命令：

```bash
uv run --python ./.venv/Scripts/python.exe python tools/validate_dask_version_alignment.py
```

结果摘要：

- 本地版本：`dask=2026.1.1`、`distributed=2026.1.1`、`numpy=2.4.1`
- `uv.lock` 与本地一致
- Worker 依赖约束与本地版本兼容
- 当前未运行 Docker 容器，无法读取 Scheduler 运行时版本

处理结论：

- issue 保持 `open`
- 标记为“待容器联调验证”

### 2) 数据库响应时间

命令：

```bash
uv run --python ./.venv/Scripts/python.exe python tools/validate_database_health_latency.py --samples 8 --threshold-ms 1500 --connect-timeout-s 5
```

结果摘要：

- `query_ms p95 = 0.57ms`
- `first_total_ms = 99.84ms`（首样本连接获取开销明显）
- `warm_p50_total_ms = 0.77ms`
- 结果状态：`healthy`

处理结论：

- issue 转为 `resolved`
- 结论支持“此前 4772.9ms 属于旧口径/旧状态下的异常样本”

---

## 文档同步

- backlog/resolved 状态已更新
- `docs/issues/README.md` 统计更新为 `待处理 1 / 已解决 39`
- 在 issue 文档内补充了脚本化验证记录

---

## 关键结论

> 先把“是否可复现”脚本化，再决定关闭或保留问题，可以显著降低误关单和重复排障。
