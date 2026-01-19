# Dask Worker 模块导入失败

> **状态**: 已确认为环境问题（非代码 bug）
> **日期**: 2026-01-19
> **分类**: environment

## 问题现象

启动后端服务时，AmazingData Dask Actor 初始化失败，日志显示模块导入错误。

## 根因分析

经排查确认，这**不是代码问题**，而是 **Docker 服务未启动**导致：

1. Dask Scheduler 容器未运行
2. Dask Worker 容器未运行
3. 后端尝试连接 `tcp://localhost:8786` 失败

## 解决方法

确保 Docker Compose 中的 Dask 服务正常运行：

```bash
# 检查服务状态
docker ps | grep dask

# 如未运行，启动服务
docker-compose up -d dask-scheduler dask-worker-1 dask-worker-2
```

## 正常状态参考

```
deepsearch-dask-worker-2    Up X minutes
deepsearch-dask-worker-1    Up X minutes
deepsearch-dask-scheduler   Up X minutes   0.0.0.0:8786-8787->8786-8787/tcp
```

## 备注

此 Issue 保留作为排查参考，提醒在遇到类似错误时优先检查 Docker 服务状态。
