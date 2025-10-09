# 星耀数智（AmazingData）快速入门指南

> 本指南面向首次接触 AmazingData 的同学，基于官方文档 `AmazingData_API.md`（2025-09-11，V1.0.8）整理。通过 5 分钟的示例流程，带你完成环境准备、接口调用与 DeepSearch 集成。  
> 更新时间：2025-10-10

## 目录
1. [环境准备](#环境准备)
2. [首次登录](#首次登录)
3. [获取基础数据](#获取基础数据)
4. [获取财务与股东数据](#获取财务与股东数据)
5. [订阅实时行情](#订阅实时行情)
6. [查询历史行情](#查询历史行情)
7. [在 DeepSearch 中集成](#在deepsearch中集成)
8. [常见问题](#常见问题)
9. [下一步建议](#下一步建议)

---

## 环境准备

1. **激活虚拟环境**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **安装依赖**
   ```bash
   uv pip install third_party/amazingdata/AmazingData-1.0.10-cp313-none-any.whl
   uv pip install third_party/amazingdata/tgw-1.0.8.1-py3-none-any.whl
   ```

3. **配置凭据与网络**
   - 账号与密码由银河证券营业部提供；
   - 推荐网络接入点：电信 `101.230.159.234:8600`，联通 `140.206.44.234:8600`；
   - 将信息写入 `settings.<env>.yaml` 或通过 WebUI 配置，避免硬编码。

4. **设置本地缓存目录**
   - 官方推荐 `D://AmazingData_local_data//`；
   - 请确保读写权限，并在配置文件中统一引用：
     ```yaml
     amazingdata:
       local_path: "D://AmazingData_local_data//"
       use_local_cache: true
     ```

---

## 首次登录

```python
import AmazingData as ad

LOGIN_PARAMS = {
    "username": "your_username",
    "password": "your_password",
    "host": "101.230.159.234",
    "port": 8600,
}

result = ad.login(**LOGIN_PARAMS)
if result not in (0, True):
    raise RuntimeError(f"登录失败，错误码：{result}")

# 结束流程后记得 ad.logout()
```

> 登录接口一旦失败请先检查账号状态与网络连通性（`ping host`、`Test-NetConnection`）。

---

## 获取基础数据

### 代码列表与交易日历

```python
base_data = ad.BaseData()

stock_codes = base_data.get_code_list('EXTRA_STOCK_A')
future_codes = base_data.get_future_code_list('EXTRA_FUTURE')
calendar = base_data.get_calendar(market='SH')

print(f"股票数量: {len(stock_codes)}")
print(f"期货数量: {len(future_codes)}")
print(f"最近交易日: {calendar[-1]}")
```

### 每日最新证券信息与复权因子

```python
code_info = base_data.get_code_info()  # 默认沪深北 A 股

backward_factor = base_data.get_backward_factor(
    code_list=stock_codes[:100],
    local_path="D://AmazingData_local_data//",
    is_local=True,
)
```

`code_info` 的列可查看 `data_types.md#code-info`，复权因子接口会在本地缓存目录生成对应的 CSV 文件。

---

## 获取财务与股东数据

```python
info_data = ad.InfoData()

balance_sheet = info_data.get_balance_sheet(
    code_list=stock_codes[:200],
    local_path="D://AmazingData_local_data//",
    is_local=True,
)

profit_notice = info_data.get_profit_notice(
    code_list=stock_codes[:200],
    local_path="D://AmazingData_local_data//",
)

share_holder = info_data.get_share_holder(
    code_list=stock_codes[:200],
    local_path="D://AmazingData_local_data//",
)
```

常用接口速查：
- `get_balance_sheet` / `get_cash_flow` / `get_income`：三大财务报表；
- `get_profit_express` / `get_profit_notice`：业绩快报与预告；
- `get_share_holder` / `get_holder_num` / `get_equity_structure`：股东与股本结构；
- `get_dividend` / `get_right_issue`：分红、配股方案；
- `get_margin_summary` / `get_margin_detail`：融资融券汇总与明细；
- `get_long_hu_bang`：龙虎榜数据。

字段含义请对照 `AmazingData_API.md` 3.5.x 章节及 `data_types.md` 附录。

---

## 订阅实时行情

```python
sub_data = ad.SubscribeData()
codes = stock_codes[:20]

@sub_data.register(code_list=codes, period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    print(period, data.code, data.last_price, data.volume)

sub_data.run()
```

若需要订阅不同品种，请选择对应回调：
- 指数：`onSnapshot_index`
- 股票：`onSnapshot`
- 期货：`onSnapshot_future`
- ETF：`onSnapshot_etf`
- 可转债：`onSnapshot_kzz`
- 港股通：`onSnapshot_hkt`
- K 线：`OnKLine`（period 支持分钟、日、周、月、年）

---

## 查询历史行情

```python
calendar = base_data.get_calendar()
market_data = ad.MarketData(calendar)

snapshot_dict = market_data.query_snapshot(
    code_list=codes,
    begin_date=20240510,
    end_date=20240510,
)

kline_dict = market_data.query_kline(
    code_list=codes,
    begin_date=20240501,
    end_date=20240510,
    period=ad.constant.Period.day.value,
)

print(snapshot_dict[codes[0]].head())
print(kline_dict[codes[0]].head())
```

返回值为字典结构，键是代码，值为 `pandas.DataFrame`。字段与实时订阅一致，可直接用于分析或落库。

---

## 在 DeepSearch 中集成

DeepSearch 对 AmazingData 进行了统一封装，可通过数据管理器自动选择数据源：

```python
from deepsearch.infrastructure.providers.managers.enhanced_manager import get_data_manager

async def fetch_daily():
    manager = await get_data_manager()
    df = await manager.get_stock_daily(
        symbol="000001",
        start_date="2025-05-01",
        end_date="2025-05-15",
        source="auto",
    )
    return df
```

集成步骤：
- 在 `settings.<env>.yaml` 中启用 `amazingdata.enabled` 并填写凭据；
- 运行 `python scripts/check_amazingdata.py` 或 WebUI “测试连接”确认可用；
- 通过 CLI、WebUI 或策略引擎统一访问，必要时可配置 AmazingData → Cloudflare → Mock 的降级链路。

---

## 常见问题

- **登录失败**：确认账号密码、网络连通性、是否存在并发登录；若错误码持续返回非 0，请联系运营人员解锁。
- **返回为空或字段缺失**：检查 `security_type`、日期范围、退市状态，以及是否读取了旧缓存（`is_local=True`）。
- **本地缓存读写异常**：确保 `local_path` 位于可写目录，并排除杀毒软件或磁盘配额限制。
- **订阅断流或延迟**：调整心跳间隔、检查网络代理、防火墙或长时间阻塞的回调逻辑。
- **字段含义不明**：参考 `AmazingData_API.md` 附录及 `data_types.md` 对应章节，必要时同步更新字段映射。

---

## 下一步建议

- 阅读 `api_reference.md` 获取全部接口清单与参数说明；
- 在 `data_types.md` 中查看 `security_type`、`market`、`Period`、`DIV_PROGRESS` 等枚举；
- 结合 `resilience_strategy.md` 与 `amazingdata_degraded_mode.md` 配置生产环境的容错机制；
- 编写自测脚本，确保关键接口在新的 SDK 版本发布后仍能正常返回预期字段。

完成以上步骤后，记得调用 `ad.logout()` 并退出虚拟环境：

```python
ad.logout()
```

祝你使用顺利！
