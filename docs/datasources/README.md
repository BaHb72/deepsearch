# 数据源文档索引

## AmazingData 文档与版本说明

- [快速上手](./amazingdata/quick_start.md)
- [环境配置指南](./amazingdata/setup.md)
- [API 使用手册](./amazingdata/api_guide.md)
- [API 参考文档](./amazingdata/api_reference.md)
- [数据字段规范](./amazingdata/data_types.md)
- [系统集成说明](./amazingdata/integration.md)
- [稳定性策略](./amazingdata/resilience_strategy.md)
- [SDK 隔离技术细节](./amazingdata/isolation_technical_design.md)
- [降级模式说明](./amazingdata/amazingdata_degraded_mode.md)
- [接口与示例精要（原始整理稿）](./amazingdata/AmazingData_API_Interfaces_and_Examples.md)
- [1.0.18 差异标注（只做减法 + 新增/变更的确定性信息）](./amazingdata/AmazingData_API_Interfaces_and_Examples_delta_1.0.18.md)

> 以下章节整合自《AmazingData 接口与示例精要》，并与官方手册保持条目一致；如需原始上下文，请直接查阅整理稿。

### 当前依赖版本

- 项目运行时依赖 `amazingdata==1.0.18`，wheel
  地址：<https://bahbai.com/packages/AmazingData-1.0.18-cp313-none-any.whl。所有依赖请统一使用> `uv` 管理，禁止直接调用
  `pip`。
- 配套依赖 `tgw==1.0.8.1`（wheel：<https://bahbai.com/packages/tgw-1.0.8.1-py3-none-any.whl），用于底层行情链路。>
- 如需在本地验证 wheel，可按需执行（确保已激活 `./.venv` 或显式指定解释器）：

```powershell
uv pip install --python ./.venv/Scripts/python.exe https://bahbai.com/packages/tgw-1.0.8.1-py3-none-any.whl
uv pip install --python ./.venv/Scripts/python.exe https://bahbai.com/packages/AmazingData-1.0.18-cp313-none-any.whl
```

### 快速入门（节选）

```python
# 1) 登录
import AmazingData as ad
ad.login(username='用户名', password='密码', host='***.***.***.***', port=****)

# 2) 同步查询
base_data = ad.BaseData()
code_list = base_data.get_code_list(security_type='EXTRA_ETF')

# 3) 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    print(period, data)
sub_data.run()
```

> 官方示例中针对相同参数存在 `ip`/`host`、`host`/`port` 等命名差异，整理稿已保留注释，请以 SDK 实际实现为准。

### API 结构导航

| 章节 | 模块        | 核心接口节选                                                                                                                    |
|----|-----------|---------------------------------------------------------------------------------------------------------------------------|
| 1  | 基础认证      | `login`、`logout`、`update_password`                                                                                        |
| 2  | 基础数据      | `BaseData.get_code_info`、`BaseData.get_code_list`、`BaseData.get_future_code_list`、`BaseData.get_calendar` 等               |
| 3  | 实时行情订阅    | `SubscribeData.register` 对应 `onSnapshot`/`onSnapshotindex` 等回调，以及实时 K 线 `OnKLine`                                         |
| 4  | 历史行情查询    | `MarketData.query_snapshot`、`MarketData.query_kline`                                                                      |
| 5  | 财务与公告     | `InfoData.get_balance_sheet`、`get_cash_flow`、`get_income`、`get_profit_express`、`get_profit_notice`                        |
| 6  | 股东及股份变动   | `InfoData.get_share_holder`、`get_holder_num`、`get_equity_structure`、`get_equity_pledge_freeze`、`get_equity_restricted`    |
| 7  | 股权权益及市场监管 | `InfoData.get_dividend`、`get_right_issue`、`get_margin_summary`、`get_margin_detail`、`get_long_hu_bang`、`get_block_trading` |
| 8  | 字段取值与算法   | `security_type`、`market`、`trading_phase_code`、`Period` 等枚举定义，以及数据结构/计算说明                                                  |
| 9  | JSON 示例   | 标准化交易明细与订阅消息样例 JSON                                                                                                       |

### 数据字典与开发提示

- 字段与枚举定义详见整理稿第 8 章，项目侧应优先以 `dataclasses`/`TypedDict` 建模，避免在领域层透传原始 `dict`。
- 枚举行为与枚举值取舍保持 AmazingData SDK 一致，新增取值需同步更新 `data_types.md` 与对应协议模型。
- 实时行情订阅务必通过 ports + adapters 路径落地，禁止在领域服务中直接引用 SDK。

### 深入阅读

- 全量接口说明与示例：`docs/datasources/amazingdata/AmazingData_API_Interfaces_and_Examples.md`
- 1.0.18 差异标注：`docs/datasources/amazingdata/AmazingData_API_Interfaces_and_Examples_delta_1.0.18.md`
- AmazingData 适配器结构与隔离策略：`docs/datasources/amazingdata/isolation_technical_design.md`
- 领域建模与测试样例：参考 `tests/unit/infrastructure/providers/market_data/test_amazingdata_*`

> AkShare 等备选数据源文档集中于 `docs/archive/datasources/`，默认不启用；仅当 AmazingData 不满足场景需求时，按流程提交流程申请并同步更新该目录。
