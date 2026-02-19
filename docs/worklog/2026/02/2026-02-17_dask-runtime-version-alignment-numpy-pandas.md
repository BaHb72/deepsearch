# Dask 运行时版本对齐（补齐 numpy/pandas）

> 日期: 2026-02-17
> 模块: dask / docker / diagnostics
> 类型: bugfix / stability

---

## 背景

系统运行期间持续出现 Dask `VersionMismatchWarning`，`dask/distributed` 已一致，但 `numpy/pandas` 在本地与容器运行时漂移：

- 本地（Client）：`numpy=2.3.5`、`pandas=3.0.0`
- Scheduler/Worker（容器）：`numpy=2.4.1`、`pandas=2.3.3`

这会放大跨进程序列化与数据结构兼容风险，并干扰问题定位。

---

## 根因

1. `docker/pyproject.worker.toml` 与仓库锁文件 `uv.lock` 不一致：
   - Worker 仍固定 `numpy==2.4.1`，`pandas>=2.3.3,<2.4.0`
   - 主环境锁文件为 `numpy==2.3.5`，`pandas==3.0.0`
2. `tools/validate_dask_version_alignment.py` 仅校验 `dask/distributed/numpy`，遗漏 `pandas`，导致“表面通过、运行时告警仍在”。

---

## 修复内容

1. 对齐 Worker 依赖到锁文件版本
`docker/pyproject.worker.toml`

- `numpy==2.3.5`
- `pandas==3.0.0`

2. 扩展版本对齐校验覆盖面
`tools/validate_dask_version_alignment.py`

- `TARGET_PACKAGES` 从 `("dask", "distributed", "numpy")` 扩展为 `("dask", "distributed", "numpy", "pandas")`

---

## 验证路径（留痕）

1. 代码级检查

- `./.venv/Scripts/python.exe -m py_compile tools/validate_dask_version_alignment.py`

2. 容器重建与重启

- `docker compose build dask-scheduler dask-worker`
- `docker compose up -d --force-recreate dask-scheduler dask-worker`

3. 版本核对

- `docker exec deepsearch-dask-scheduler python -c "import dask,distributed,numpy,pandas; ..."`
- `docker exec deepsearch-dask-worker-1 python -c "import dask,distributed,numpy,pandas; ..."`

4. 严格校验

- `./.venv/Scripts/python.exe tools/validate_dask_version_alignment.py --strict`
- 输出 `status=aligned`

5. 运行状态复核

- `Client('tcp://localhost:8786').scheduler_info()` 显示 `workers=2`

---

## 结果

本地、Scheduler、Worker 四个关键包已对齐：

- `dask=2026.1.2`
- `distributed=2026.1.2`
- `numpy=2.3.5`
- `pandas=3.0.0`

版本漂移告警路径已消除，后续可将 `validate_dask_version_alignment.py --strict` 纳入日常启动前检查。
