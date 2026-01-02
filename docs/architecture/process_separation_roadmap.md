# DeepSearch 架构演进路线

## 行业参考：Qlib-Server 架构

Qlib 使用 **RabbitMQ + Redis** 实现进程分离：

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Qlib Client   │────▶│   Qlib-Server   │────▶│   RabbitMQ      │
│   (WebSocket)   │◀────│   (Flask)       │◀────│   (Task Queue)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                        │
                               ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │     Redis       │     │   Worker Pool   │
                        │  (Session/Lock) │     │  (Data Gen)     │
                        └─────────────────┘     └─────────────────┘
```

**核心模式**：

- **RabbitMQ `task_queue`**：接收客户端请求，异步派发给 Worker。
- **RabbitMQ `message_queue`**：Worker 完成后发布结果。
- **Redis**：Session 管理 + 去重锁 + 缓存。

---

## Stage 1: 单体应用 (当前)

```
┌─────────────────────────────────────────────┐
│           主进程 (Web Server)                │
│  ┌─────────────────────────────────────────┐│
│  │  FastAPI                                ││
│  │  ├── API Endpoints                      ││
│  │  ├── UnifiedDataFeed                    ││
│  │  ├── AggregationEngine (asyncio tasks)  ││
│  │  └── AggregationCache (内存 dict)       ││
│  └─────────────────────────────────────────┘│
│                    │                         │
│              IPC 通信                        │
│                    ▼                         │
│  ┌─────────────────────────────────────────┐│
│  │  AmazingData 独立进程                   ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

**优点**：开发快，部署简单，无外部依赖。
**缺点**：计算阻塞 Web；无法水平扩展。

---

## Stage 2: Redis 缓存分离 (中期)

引入 Redis 作为共享缓存，但不改变进程模型。

```
┌─────────────────────────────────────────────┐
│           主进程 (Web Server)                │
│  ┌─────────────────────────────────────────┐│
│  │  FastAPI + AggregationEngine            ││
│  │         │                               ││
│  │         │ 读/写                         ││
│  │         ▼                               ││
│  │  ┌─────────────────────────────────┐   ││
│  │  │  Redis (AggregationCache)       │   ││
│  │  └─────────────────────────────────┘   ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

**改动**：

1. `AggregationCache` 改为 Redis 适配器。
2. 支持多 Web 实例共享缓存。

---

## Stage 3: 核心分离 (终极架构)

实现真正的微服务架构：**Web Server (FastAPI) 与 Core System (DeepSearch Main) 完全分离**。

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│ Web Server  │──────►│  RabbitMQ   │──────►│ Core System │
│ (FastAPI)   │       │ (MQ Broker) │       │ (Main Proc) │
│             │◄──────│             │◄──────│             │
└─────────────┘       └─────────────┘       └─────────────┘
  [轻量级网关]                                 [系统核心]
  - HTTP/WS 接入                              - 策略引擎
  - 权限/鉴权                                 - 因子计算
  - 简单查询 (Redis)                          - 模型训练
  - 仅负责转发                                - 加载重依赖
```

**架构变革**：

1. **Web Server (FastAPI)**：
    - **角色**：纯粹的 API 网关。
    - **特点**：极速启动，低内存，不加载 heavy libraries (backtrader, torch)。
    - **职责**：接收请求 -> 丢进 MQ -> 立即返回 -> 等待 Bark/WS 通知。

2. **Core System (DeepSearch Main)**：
    - **角色**：真正的业务主体。
    - **启动**：`python -m deepsearch.main` (不再启动 uvicorn)。
    - **职责**：消费 MQ 任务 -> 执行计算 -> 写入 DB/Redis -> 发送通知。

3. **RabbitMQ**：
    - **角色**：系统的神经中枢。
    - **职责**：解耦 Web 和 Core，确保任务不丢失，平衡负载。

---

## 迁移步骤 (Revised)

1. **基础建设**：集成 RabbitMQ (`aio-pika`)，实现 `RabbitMQMessageBus`。
2. **分离点识别**：识别哪些 Service 是"重业务"，必须移入 Core。
3. **Core 进程构建**：创建 `CoreRunner`，只启动核心服务，连接 MQ。
4. **Web 瘦身**：FastAPI 移除核心服务引用，改为 MQ RPC 调用。

---

## 触发条件

| 条件 | 建议动作 |
|------|----------|
| 聚合耗时 > 200ms | Stage 2 (Redis) |
| 需要多 Web 实例 | Stage 2 (Redis) |
| 回测/训练任务 > 10s | Stage 3 (MQ) |
| 支持 iOS/Android | Stage 3 (分离) |

---

## 当前系统 MQ 状态

**尚未集成 MQ**。如需引入，推荐：

- **轻量级**：Redis Pub/Sub 或 Redis Stream
- **企业级**：RabbitMQ (Qlib 选择)
