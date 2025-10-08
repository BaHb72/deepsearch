# AmazingData API 使用指南

> 本指南依据 `docs/datasources/amazingdata/AmazingData_API.md`（2025-09-11，文档版本 V1.0.8）整理，结合 DeepSearch 的实际接入方式，提供从环境准备到常见问题的全流程说明。  
> 更新时间：2025-10-10

## 目标读者
- 需要在 DeepSearch 中调用 AmazingData 数据接口的开发者
- 负责维护数据源配置与故障排查的运维人员
- 希望快速理解 SDK 对象模型与使用节奏的新同事

## 目录
1. [准备工作](#准备工作)
2. [核心流程](#核心流程)
3. [本地缓存与同步策略](#本地缓存与同步策略)
4. [错误处理](#错误处理)
5. [最佳实践](#最佳实践)
6. [故障排查](#故障排查)
7. [参考文档](#参考文档)

---

## 准备工作

### 安装依赖
推荐使用仓库内置的 Wheel 包，官方文档覆盖 SDK ≥ V1.0.8，DeepSearch 当前验证版本为 1.0.10。

```bash
# 安装 AmazingData SDK
uv pip install third_party/amazingdata/AmazingData-1.0.10-cp313-none-any.whl

# 安装 TGW 组件（如需重新部署）
uv pip install third_party/amazingdata/tgw-1.0.8.1-py3-none-any.whl
```

安装完成后可使用以下命令确认版本：

```python
import AmazingData as ad
print(ad.__version__)
```

### 配置凭据
- 账号、密码、服务器地址和端口需向银河证券营业部申请。
- 互联网接入点：电信 `101.230.159.234:8600`，联通 `140.206.44.234:8600`；若网络环境特殊，可通过 `settings.<env>.yaml` 设置自定义地址。
- 在 DeepSearch 中统一通过配置文件或 WebUI 维护，避免硬编码。

### 统一的本地缓存目录
AmazingData 多数历史类接口都允许读取本地缓存（`local_path` + `is_local`）。建议在所有环境中使用同一目录并确保读写权限，例如：

```yaml
amazingdata:
  local_path: "D://AmazingData_local_data//"
  use_local_cache: true
```

第一次调用接口时 SDK 会自动写入缓存，后续请求将显著缩短响应时间。

---

## 核心流程

### 1. 登录认证
所有接口均需在登录成功后调用。

```python
import AmazingData as ad

ad.login(
    username="your_username",
    password="your_password",
    host="101.230.159.234",
    port=8600,
)
```

完成全部操作后务必调用 `ad.logout()` 释放会话。

### 2. 查询类接口

#### 2.1 基础数据（BaseData / InfoData）
- `BaseData.get_code_info`：获取每日最新证券信息。
- `BaseData.get_code_list` / `get_future_code_list`：获取不同市场代码表。
- `BaseData.get_backward_factor` / `get_adj_factor`：下载复权因子到本地。
- `BaseData.get_hist_code_list`：按日期范围拉取历史代码表，需指定 `local_path`。
- `InfoData.get_stock_basic`、`get_history_stock_status`、`get_bj_code_mapping`：证券基础信息、历史状态、北交所新旧代码映射。

示例：
```python
base_data = ad.BaseData()
info_data = ad.InfoData()

codes = base_data.get_code_list('EXTRA_STOCK_A')
calendar = base_data.get_calendar()

stock_basic = info_data.get_stock_basic(codes[:100])
history_status = info_data.get_history_stock_status(
    code_list=codes[:100],
    local_path="D://AmazingData_local_data//",
)
```

#### 2.2 财务、股东与权益数据（InfoData）
信息类接口均遵循统一入参：`code_list`（或 `local_path`）+ `is_local`。返回值为 `pandas.DataFrame`，字段详见 `data_types.md` 与官方 PDF。

```python
finance = info_data.get_balance_sheet(
    code_list=codes,
    local_path="D://AmazingData_local_data//",
    is_local=True,
)
share_holder = info_data.get_share_holder(
    code_list=codes,
    local_path="D://AmazingData_local_data//",
)
dividend = info_data.get_dividend(
    code_list=codes,
    local_path="D://AmazingData_local_data//",
)
```

### 3. 订阅类接口（SubscribeData）

订阅流程与官方文档 3.4.2 一致：

1. 登录并准备好代码列表。
2. 实例化 `ad.SubscribeData()`。
3. 使用装饰器注册回调（`code_list`、`period`）。
4. 回调中处理数据对象，类型与 `Period` 对应。
5. 调用 `run()`，结束后 `ad.logout()`。

```python
sub_data = ad.SubscribeData()
codes = base_data.get_code_list('EXTRA_STOCK_A')[:50]

@sub_data.register(code_list=codes, period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    print(data.code, data.last_price)

sub_data.run()
```

支持的回调包括 `onSnapshot_index`、`onSnapshot`、`onSnapshot_future`、`onSnapshot_etf`、`onSnapshot_kzz`、`onSnapshot_hkt`、`OnKLine`。常量定义见 `data_types.md`。

### 4. 历史行情查询（MarketData）

1. 获取交易日历，实例化 `ad.MarketData(calendar)`。
2. 调用 `query_snapshot` 或 `query_kline`。
3. 结果为字典，键为代码，值为 DataFrame。

```python
calendar = base_data.get_calendar()
market_data = ad.MarketData(calendar)

snapshot_dict = market_data.query_snapshot(
    code_list=codes[:5],
    begin_date=20240501,
    end_date=20240510,
)

kline_dict = market_data.query_kline(
    code_list=codes[:5],
    begin_date=20240501,
    end_date=20240510,
    period=ad.constant.Period.day.value,
)
```

---

## 本地缓存与同步策略
- **首次拉取即写入**：当 `is_local=True` 且本地无缓存时，SDK 会自动从服务器下载数据并写入 `local_path`。
- **强制刷新**：将 `is_local=False` 可跳过本地数据并重新拉取，接口完成后会覆盖缓存。
- **目录规划**：建议将缓存挂载到数据盘或专用共享目录，确保多进程不会互相删除文件。
- **容量管理**：财务与历史行情数据体积较大，定期检查磁盘剩余空间并清理过期文件。
- **跨环境同步**：生产环境缓存可定期同步到测试环境，减少首次验证的耗时。

---

## 错误处理
- 登录失败通常返回整数错误码，`0` 或 `True` 表示成功；异常错误码需结合运营方提供的清单排查。
- 订阅接口若长时间无回调，需要检查网络连通性与心跳配置（默认 60 秒）。
- 读写缓存失败会抛出 `IOError` 或 `PermissionError`，请确认 `local_path` 权限。
- 高频任务建议捕获 SDK 异常并增加重试，示例：

```python
def safe_call(func, *args, retries=3, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
```

---

## 最佳实践
- 登录信息通过配置文件统一管理，严禁在脚本中硬编码。
- 调用接口前先获取交易日历与代码列表，保证后续参数一致。
- 大批量查询时使用批次或分页写入缓存，避免一次性请求过多代码。
- 在数据处理层统一转换 DataFrame 字段名与类型，便于落库与校验。
- 订阅场景建议将回调逻辑与业务处理解耦，避免阻塞接收线程。
- 定期对比 `AmazingData_API.md` 与实际返回字段，遇到差异及时记录并同步文档。

---

## 故障排查
- **网络不可达**：使用 `ping` 或 `Test-NetConnection` 验证 IP 与端口，必要时调整运营商线路。
- **认证失败**：确认账号状态、密码是否已更新、是否并发登录超过限制。
- **返回数据为空**：检查 `security_type`、日期区间、代码是否退市，以及 `is_local` 是否导致读取旧缓存。
- **订阅断流**：排查心跳配置、网络代理、防火墙及主线程阻塞问题。
- **字段缺失或异常**：参考 `AmazingData_API.md` 附录字段说明，确认是否新版本字段需更新映射。

---

## 参考文档
- `docs/datasources/amazingdata/AmazingData_API.md`
- `docs/datasources/amazingdata/api_reference.md`
- `docs/datasources/amazingdata/data_types.md`
- `docs/datasources/amazingdata/quick_start.md`
- `docs/datasources/amazingdata/resilience_strategy.md`

遇到接口新增或字段调整时，请先同步官方 PDF，再更新上述文档与 `settings.*.yaml` 示例配置。
