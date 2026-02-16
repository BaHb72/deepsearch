# Dask 版本漂移问题收口（容器联调）

> 日期: 2026-02-16
> 模块: diagnostics, docker, issues
> 类型: bugfix

---

## 背景

backlog 最后一项 `2026-02-08_dask-version-mismatch` 在无容器场景仅能得到 `status=unchecked`，需要容器联调后给出可归档结论。

---

## 变更

1. 将 `docker/pyproject.worker.toml` 中 Worker 依赖改为精确版本，统一到 `uv.lock`：
   - `dask==2026.1.1`
   - `distributed==2026.1.1`
   - `numpy==2.4.1`
2. 重建并强制重建 `dask-scheduler` 容器，确保运行时加载新镜像。

---

## 验证

执行命令：

```bash
docker compose build dask-scheduler
docker compose up -d --force-recreate dask-scheduler
uv run --python ./.venv/Scripts/python.exe python tools/validate_dask_version_alignment.py --strict
```

结果摘要：

- 严格校验返回 `status=aligned`
- 本地与容器版本一致：
  - `dask=2026.1.1`
  - `distributed=2026.1.1`
  - `numpy=2.4.1`
- 校验脚本输出中的 `worker_dependency_specs` 与 `lock_versions` 一致

---

## 结论

最后一个 backlog issue 可关闭并归档至 `resolved`。当前 issues 统计更新为 `待处理 0 / 已解决 40`。
