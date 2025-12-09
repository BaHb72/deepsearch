---
title: AmazingData API Interfaces & Examples
description: ժ¼�ԡ�AmazingData ���ݽӿ��ֲᡷ��V1.0.14���������Ŀʵ���������ٲ�����۽� SDK ��װ�����õ����������ӿڷ�����ö��ȡֵ��  
updated: 2025-11-06
---

# 相关差异链接（基于 1.0.18）：[查看差异标注](./AmazingData_API_Interfaces_and_Examples_delta_1.0.18.md)

# AmazingData API �ӿ���ʾ������

���ĵ������Թٷ��ֲ� **V1.0.14**��������Ŀ��ǰ�����汾����һ�£�`amazingdata==1.0.18`��`tgw==1.0.8.1`��������ʾ��Ĭ���� Windows
PowerShell �����������������òֿ��渽���⻷�� `./.venv`��

> **��ʾ**
> - ������װ��ʼ��ʹ�� `uv`������ֱ��ʹ�� `pip`��
> - ʾ���е��û������������˿ھ�Ϊռλ��������ݻ��������ļ���д��
> - ����ʾ��ֻ��ʾ�������̣���������Ӧͨ�� adapters �� ports ��ӵ��á�

---

## 1. ����׼��

```powershell
uv pip install --python .\.venv\Scripts\python.exe https://bahbai.com/packages/tgw-1.0.8.1-py3-none-any.whl
uv pip install --python .\.venv\Scripts\python.exe https://bahbai.com/packages/AmazingData-1.0.18-cp313-none-any.whl
```

> wheel ֧�� Python 3.8�C3.13��Windows/Linux ͨ�ã����������������ֿ⣬�˴�����������ص��ԡ�

### 1.1 ��¼���ѯ

```python
import AmazingData as ad

# 1) ��¼
ad.login(username="username", password="password", host="10.x.x.x", port=8600)

# 2) ��ȡ�����б�
base_data = ad.BaseData()
code_list = base_data.get_code_list(security_type="EXTRA_ETF")
```

### 1.2 ʵʱ����ʾ��

```python
import AmazingData as ad

ad.login(username="username", password="password", host="10.x.x.x", port=8600)

base_data = ad.BaseData()
etf_codes = base_data.get_code_list(security_type="EXTRA_ETF")

sub_data = ad.SubscribeData()

@sub_data.register(code_list=etf_codes, period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    print(period, data)

sub_data.run()
```

---

## 2. �ӿڷ����ٲ�

| ģ��               | �ؼ�����                                                                                                                                                                                                                                                                                                                                                                                | ˵��                    |
|-------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------|
| **��֤**           | `login` / `logout` / `update_password`                                                                                                                                                                                                                                                                                                                                                 | �˺ŵ�¼��ƾ�ݸ���          |
| **BaseData**      | `get_code_info`��`get_code_list`��`get_future_code_list`��`get_backward_factor`��`get_adj_factor`��`get_hist_code_list`��`get_calendar`                                                                                                                                                                                                                                                | ��̬������Ϣ����������   |
| **InfoData**      | `get_stock_basic`��`get_history_stock_status`��`get_balance_sheet`��`get_cash_flow`��`get_income`��`get_profit_express`��`get_profit_notice`��`get_share_holder`��`get_holder_num`��`get_equity_structure`��`get_equity_pledge_freeze`��`get_equity_restricted`��`get_dividend`��`get_right_issue`��`get_margin_summary`��`get_margin_detail`��`get_long_hu_bang`��`get_block_trading` | ����ָ�ꡢ�ɶ��䶯���������  |
| **SubscribeData** | `register` �ص���`onSnapshotindex` / `onSnapshot` / `onSnapshotfuture` / `onSnapshotetf` / `onSnapshotkzz` / `onSnapshothkt` / `OnKLine`                                                                                                                                                                                                                                                | ʵʱ���鶩�ģ�ע��ص�+`run`�� |
| **MarketData**    | `query_snapshot`��`query_kline`                                                                                                                                                                                                                                                                                                                                                        | ��ʷ������ K �߲�ѯ       |

> ��Ŀ������ SDK ���ñ���ͨ�� **ports + adapters** �ṹ�������������������� `deepsearch/ports` �µ� Protocol��

---

## 3. ö���볣��

### 3.1 ֤ȯ���� `security_type`

`EXTRA_STOCK_A`��`SH_A`��`SZ_A`��`BJ_A`��`EXTRA_STOCK_A_SH_SZ`��`EXTRA_INDEX_A_SH_SZ`��`EXTRA_INDEX_A`��`SH_INDEX`��
`SZ_INDEX`��`BJ_INDEX`��`SH_ETF`��`SZ_ETF`��`EXTRA_ETF`��`SH_KZZ`��`SZ_KZZ`��`EXTRA_KZZ`��`SH_HKT`��`SZ_HKT`��
`EXTRA_HKT`��`EXTRA_FUTURE`��`ZJ_FUTURE`��`SQ_FUTURE`��`DS_FUTURE`��`ZS_FUTURE`��`SN_FUTURE`��`EXTRA_ETF_OP`��
`SH_OPTION`��`SZ_OPTION`

### 3.2 �г� `market`

`SH`��`SZ`��`BJ`��`SHF`��`CFE`��`DCE`��`CZC`��`INE`��`SHN`��`SZN`

### 3.3 �������� `periods`

`min1`��`min3`��`min5`��`min10`��`min15`��`min30`��`min60`��`min120`��`day`��`week`��`month`��`season`��`year`

> ���������ʹ�ùٷ�ö��ֵ����Ŀ�ڲ������װ����������㶨����Ѻõı������������� adapter ��ӳ�䵽����������

---

## 4. �ṹ��Ŀ¼����

��Ŀ�ṩ�ṹ���Ľӿ�Ŀ¼ `deepsearch.infrastructure.providers.implementations.amazingdata.api_catalog`��

```python
from deepsearch.infrastructure.providers.implementations.amazingdata import (
    AMAZINGDATA_API_CATALOG,
    catalog_to_json,
)

catalog_dict = AMAZINGDATA_API_CATALOG.to_dict()
catalog_json = catalog_to_json(ensure_ascii=False)
```

- `AMAZINGDATA_API_CATALOG.namespaces`������ģ�黮�ֵĽӿ��б���
- `AMAZINGDATA_API_CATALOG.enums`��ö��ȡֵ������֤ȯ���͡��г������ڡ�
- `catalog_to_json()`������ CLI ���ĵ����ɹ���ֱ�����ѡ�

---

## 5. ʹ��ע������

- �ӿڷ��ص����ݽṹ���ӡ��ֶν϶࣬��Ŀ�����ͨ�� dataclass / TypedDict ��ǿ��ģ�������������й¶�� JSON��
- ���Ļص��������첽����ҵ���߼������� adapter �����������ȣ���ֹ���� SDK �ڲ��¼�ѭ����
- `get_calendar` �ķ��ػ����г��䶯������ʧ��ʱӦ�ṩ���ײ��Ի���������ο� `create_realtime_streaming_pipeline` �еĴ�����ʽ��
- �ĵ��в��ֽӿڴ����������죨���� `block_trading` vs `get_block_trading`������ SDK ʵ�ʺ�����Ϊ׼������ `api_catalog` �뵥Ԫ���Ժ˶ԡ�

---

����鿴��������ԭʼע�����ҳ��Ϣ�������壬����� `docs/datasources/amazingdata/AmazingData_API_Interfaces_and_Examples.md`
����ǰ�ĵ�����ο��ٷ� PDF��������/����ӿڣ���ͬ�����£�

1. ���ļ�������������
2. `api_catalog` �ṹ������
3. ��Ӧ�� adapters / ports / ��Ԫ����
4. �汾��¼���� `docs/plans/README.md#amazingdata-provider-重构`

