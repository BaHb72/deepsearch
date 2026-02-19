# T-Trading MiniQMT 连接状态误报修复

> 日期: 2026-02-17  
> 模块: strategy-center / ttrading  
> 类型: bugfix

---

## 问题现象

前端页面 `http://127.0.0.1:3000/strategy/ttrading` 显示“MiniQMT 已连接”，但 MiniQMT 客户端实际未登录或不可用。

---

## 根因定位

`/api/strategy-center/ttrading/datasource/status` 使用了本地 provider 的 `is_connected` 字段作为连接判定。  
该字段在当前实现路径中并不等价于真实链路探活，导致出现“可导入/已初始化”被误判为“已连接”的假阳性。

---

## 复用性检索（按约束留痕）

检索目标: 复用现有能力实现业务层连接探活，避免新增轮子。  

命中的候选能力:

1. 项目内 `MiniQMT Actor` 已提供 `heartbeat()` 与 `get_status()`（业务层探活）。  
2. `DataProviderFactory.get_provider_async("miniqmt")` 已提供 Actor 生命周期与实例复用。  
3. 旧路径 `provider.is_connected` 仅为状态字段，不具备强探活语义。  

最终取舍:

- 采用候选 1 + 2：复用现有 Actor 探活链路。  
- 放弃候选 3：避免继续使用弱语义字段导致误报。

---

## 修复方案

1. 在 `apps/api/api/endpoints/strategy_center/ttrading.py` 新增 `_probe_miniqmt_tcp_connection()`，先做配置端口可达性检测。  
2. 新增 `_probe_miniqmt_actor_connection()`，在端口可达后再执行 Actor `heartbeat + get_status` 业务探活。  
3. `/datasource/status` 改为仅依据“端口可达 + Actor 探活”联合结果判定 `miniqmt_connected`。  
4. 探活失败或不可用时统一返回：
   - `miniqmt_connected = false`
   - `active_provider = "mock"`

---

## 回归测试

新增 `tests/api/test_strategy_center_ttrading_api.py`，覆盖四类场景：

1. `MINIQMT_AVAILABLE=False` 时直接返回 mock。  
2. 端口不可达时直接返回 mock，不执行 Actor 探活。  
3. 探活失败时，即使本地 provider 标记为 connected，也必须返回未连接。  
4. 探活成功时返回 `miniqmt_connected=true` 且 `active_provider="miniqmt"`。

---

## 解决路径（留痕）

1. 依赖检查：`uv pip check --python ./.venv/Scripts/python.exe`。  
2. 代码定位：确认 `ttrading` 状态接口使用 `is_connected` 直读。  
3. 复用性检索：确认项目内已有 MiniQMT Actor `heartbeat/get_status` 能力。  
4. 代码修复：状态接口改为真实探活判定。  
5. 补齐测试：新增策略中心 T-Trading 状态接口回归测试。  
6. 定向执行测试并确认结果。
