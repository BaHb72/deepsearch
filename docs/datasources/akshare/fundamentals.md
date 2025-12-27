---
title: 基本面数据
description: AKShare 股票数据 - 基本面数据 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 基本面数据

#### 股东大会

接口: stock_gddh_em

目标地址: <https://data.eastmoney.com/gddh/>

描述: 东方财富网-数据中心-股东大会

限量: 单次返回所有数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称         | 类型     | 描述 |
|------------|--------|----|
| 代码         | object | -  |
| 简称         | object | -  |
| 股东大会名称     | object | -  |
| 召开开始日      | object | -  |
| 股权登记日      | object | -  |
| 现场登记日      | object | -  |
| 网络投票时间-开始日 | object | -  |
| 网络投票时间-结束日 | object | -  |
| 决议公告日      | object | -  |
| 公告日        | object | -  |
| 序列号        | object | -  |
| 提案         | object | -  |

接口示例

```python
import akshare as ak

stock_gddh_em_df = ak.stock_gddh_em()
print(stock_gddh_em_df)
```

数据示例

```
       代码     简称  ...     序列号                                                 提案
0     603131   上海沪工  ...  209796                                 1、关于提名公司独立董事候选人的议案
1     600252   中恒集团  ...  209759  1、广西梧州中恒集团股份有限公司关于控股子公司莱美药业为其参股公司康德赛借款提供担保展期的议...
2     300426   唐德影视  ...  209760                     1、《关于接受控股股东担保并向其提供反担保暨关联交易的议案》
3     300887   谱尼测试  ...  209756                            1、《关于使用闲置募集资金进行现金管理的议案》
4     002212    天融信  ...  209757                     1、《关于公司为全资孙公司银行综合授信提供担保总额度的议案》
...      ...    ...  ...     ...                                                ...
5021  002113  *ST天润  ...  181437  1、审议关于《2022年度董事会工作报告》的议案、审议关于《2022年年度报告及摘要》的议案...
5022  002118  *ST紫鑫  ...  181461                            1、《关于提名选举第八届董事会独立董事的议案》
5023  600777   ST新潮  ...  173337  1、《关于董事会提前换届选举非独立董事的议案》、《关于董事会提前换届选举独立董事的议案》、《...
5024  600739   辽宁成大  ...   35446  1、董事会工作报告\n2、监事会工作报告\n3、公司2011年年度报告全文及摘要\n4、公司...
5025  600739   辽宁成大  ...   35446  1、董事会工作报告\n2、监事会工作报告\n3、公司2011年年度报告全文及摘要\n4、公司...
[5026 rows x 12 columns]
```

#### 重大合同

接口: stock_zdhtmx_em

目标地址: <https://data.eastmoney.com/zdht/mx.html>

描述: 东方财富网-数据中心-重大合同-重大合同明细

限量: 单次返回指定 start_date 和 end_date 的所有数据

输入参数

| 名称         | 类型  | 描述                    |
|------------|-----|-----------------------|
| start_date | str | start_date="20200819" |
| end_date   | str | end_date="20230819"   |

输出参数

| 名称            | 类型      | 描述 |
|---------------|---------|----|
| 序号            | int64   | -  |
| 股票代码          | object  | -  |
| 股票简称          | object  | -  |
| 签署主体          | object  | -  |
| 签署主体-与上市公司关系  | object  | -  |
| 其他签署方         | object  | -  |
| 其他签署方-与上市公司关系 | object  | -  |
| 合同类型          | object  | -  |
| 合同名称          | object  | -  |
| 合同金额          | float64 | -  |
| 上年度营业收入       | float64 | -  |
| 占上年度营业收入比例    | float64 | -  |
| 最新财务报表的营业收入   | float64 | -  |
| 签署日期          | object  | -  |
| 公告日期          | object  | -  |

接口示例

```python
import akshare as ak

stock_zdhtmx_em_df = ak.stock_zdhtmx_em(start_date="20220819", end_date="20230819")
print(stock_zdhtmx_em_df)
```

数据示例

```
      序号  股票代码  股票简称  ... 最新财务报表的营业收入 签署日期 公告日期
0        1  688516   奥特维  ...           NaN  NaT  2023-08-18
1        2  688132  邦彦技术  ...           NaN  NaT  2023-08-18
2        3  831526  凯华材料  ...  5.101723e+07  NaT  2023-08-17
3        4  603085  天成自控  ...           NaN  NaT  2023-08-17
4        5  300345  华民股份  ...           NaN  NaT  2023-08-17
...    ...     ...   ...  ...           ...  ...         ...
1012  1013  300197  节能铁汉  ...  2.434768e+09  NaT  2022-08-22
1013  1014  688516   奥特维  ...           NaN  NaT  2022-08-20
1014  1015  688022  瀚川智能  ...           NaN  NaT  2022-08-19
1015  1016  603815  交建股份  ...           NaN  NaT  2022-08-19
1016  1017  603815  交建股份  ...           NaN  NaT  2022-08-19
[1017 rows x 15 columns]
```

#### 个股研报

接口: stock_research_report_em

目标地址: <https://data.eastmoney.com/report/stock.jshtml>

描述: 东方财富网-数据中心-研究报告-个股研报

限量: 单次返回指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述              |
|--------|-----|-----------------|
| symbol | str | symbol="000001" |

输出参数

| 名称            | 类型      | 描述 |
|---------------|---------|----|
| 序号            | int64   | -  |
| 股票代码          | object  | -  |
| 股票简称          | object  | -  |
| 报告名称          | object  | -  |
| 东财评级          | object  | -  |
| 机构            | object  | -  |
| 近一月个股研报数      | int64   | -  |
| 2024-盈利预测-收益  | float64 | -  |
| 2024-盈利预测-市盈率 | float64 | -  |
| 2025-盈利预测-收益  | float64 | -  |
| 2025-盈利预测-市盈率 | float64 | -  |
| 2026-盈利预测-收益  | float64 | -  |
| 2026-盈利预测-市盈率 | float64 | -  |
| 行业            | object  | -  |
| 日期            | object  | -  |
| 报告PDF链接       | object  | -  |

接口示例

```python
import akshare as ak

stock_research_report_em_df = ak.stock_research_report_em(symbol="000001")
print(stock_research_report_em_df)
```

数据示例

```
    序号    股票代码  ...  日期                           报告PDF链接
0      1  000001  ...  2025-01-10  https://pdf.dfcfw.com/pdf/H3_AP202501101641890...
1      2  000001  ...  2024-10-22  https://pdf.dfcfw.com/pdf/H3_AP202410221640400...
2      3  000001  ...  2024-10-22  https://pdf.dfcfw.com/pdf/H3_AP202410221640398...
3      4  000001  ...  2024-10-20  https://pdf.dfcfw.com/pdf/H3_AP202410201640374...
4      5  000001  ...  2024-10-19  https://pdf.dfcfw.com/pdf/H3_AP202410191640373...
..   ...     ...  ...         ...                                                ...
272  273  000001  ...  2017-03-22  https://pdf.dfcfw.com/pdf/H3_AP201703220427468...
273  274  000001  ...  2017-03-20  https://pdf.dfcfw.com/pdf/H3_AP201703200421759...
274  275  000001  ...  2017-03-17  https://pdf.dfcfw.com/pdf/H3_AP201703170415156...
275  276  000001  ...  2017-03-07  https://pdf.dfcfw.com/pdf/H3_AP201705190591661...
276  277  000001  ...  2017-02-03  https://pdf.dfcfw.com/pdf/H3_AP201702030311575...
[277 rows x 16 columns]
```

#### 沪深京 A 股公告

接口: stock_notice_report

目标地址: <https://data.eastmoney.com/notices/hsa/5.html>

描述: 东方财富网-数据中心-公告大全-沪深京 A 股公告

限量: 单次获取指定 symbol 和 date 的数据

输入参数

| 名称     | 类型  | 描述                                                                                      |
|--------|-----|-----------------------------------------------------------------------------------------|
| symbol | str | symbol='财务报告'; choice of {"全部", "重大事项", "财务报告", "融资公告", "风险提示", "资产重组", "信息变更", "持股变动"} |
| date   | str | date="20220511"; 指定日期                                                                   |

输出参数

| 名称   | 类型     | 描述  |
|------|--------|-----|
| 代码   | object | -   |
| 名称   | object | -   |
| 公告标题 | object | -   |
| 公告类型 | object | -   |
| 公告日期 | object | -   |
| 网址   | object | -   |

接口示例

```python
import akshare as ak

stock_notice_report_df = ak.stock_notice_report(symbol='财务报告', date="20240613")
print(stock_notice_report_df)
```

数据示例

```
      代码  ...                                       网址
0    123122  ...  https://data.eastmoney.com/notices/detail/1231...
1    123107  ...  https://data.eastmoney.com/notices/detail/1231...
2    300941  ...  https://data.eastmoney.com/notices/detail/3009...
3    300689  ...  https://data.eastmoney.com/notices/detail/3006...
4    300854  ...  https://data.eastmoney.com/notices/detail/3008...
..      ...  ...                                                ...
134  000159  ...  https://data.eastmoney.com/notices/detail/0001...
135  688478  ...  https://data.eastmoney.com/notices/detail/6884...
136  688513  ...  https://data.eastmoney.com/notices/detail/6885...
137  600583  ...  https://data.eastmoney.com/notices/detail/6005...
138  001301  ...  https://data.eastmoney.com/notices/detail/0013...
[139 rows x 6 columns]
```

#### 财务报表-新浪

接口: stock_financial_report_sina

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/600600/displaytype/4.phtml?source=fzb&qq-pf-to=pcqq.group>

描述: 新浪财经-财务报表-三大报表

限量: 单次获取指定报表的所有年份数据的历史数据

注意: 原始数据中有 `国内票证结算` 和 `内部应收款` 字段重, 返回数据中已经剔除

输入参数

| 名称     | 类型  | 描述                                                  |
|--------|-----|-----------------------------------------------------|
| stock  | str | stock="sh600600"; 带市场标识的股票代码                        |
| symbol | str | symbol="现金流量表"; choice of {"资产负债表", "利润表", "现金流量表"} |

输出参数

| 名称   | 类型     | 描述   |
|------|--------|------|
| 报告日  | object | 报告日期 |
| 流动资产 | object | -    |
| ...  | object | -    |
| 类型   | object | -    |
| 更新日期 | object | -    |

接口示例

```python
import akshare as ak

stock_financial_report_sina_df = ak.stock_financial_report_sina(stock="sh600600", symbol="资产负债表")
print(stock_financial_report_sina_df)
```

数据示例

```
      报告日 流动资产           货币资金  ...   币种    类型      更新日期
0   20230331  NaN  15554422004.0  ...  CNY  合并期末  2023-04-24T18:05:05
1   20221231  NaN  17854931855.0  ...  CNY  合并期末  2023-03-22T20:50:09
2   20220930  NaN  17045567340.0  ...  CNY  合并期末  2022-10-26T17:20:07
3   20220630  NaN  17587197778.0  ...  CNY  合并期末  2022-08-25T21:25:04
4   20220331  NaN  12818371932.0  ...  CNY  合并期末  2022-04-28T16:20:04
..       ...  ...            ...  ...  ...   ...                  ...
95  19961231  NaN    671405728.0  ...  CNY  合并期末  2020-03-13T15:29:48
96  19960630  NaN            NaN  ...  CNY  合并期末  2020-03-13T15:29:48
97  19951231  NaN    741738874.0  ...  CNY  合并期末  2020-03-13T15:29:48
98  19950630  NaN            NaN  ...  CNY  合并期末  2020-03-13T15:29:48
99  19941231  NaN    712428000.0  ...  CNY  合并期末  2020-03-13T15:29:48
[100 rows x 147 columns]
```

#### 财务报表-东财

##### 资产负债表-按报告期

接口: stock_balance_sheet_by_report_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-资产负债表-按报告期

限量: 单次获取指定 symbol 的资产负债表-按报告期数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 319 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_balance_sheet_by_report_em_df = ak.stock_balance_sheet_by_report_em(symbol="SH600519")
print(stock_balance_sheet_by_report_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... OSOPINION_TYPE LISTING_STATE
0   600519.SH        600519  ...           None             0
1   600519.SH        600519  ...           None             0
2   600519.SH        600519  ...           None             0
3   600519.SH        600519  ...           None             0
4   600519.SH        600519  ...           None             0
..        ...           ...  ...            ...           ...
87  600519.SH        600519  ...           None             0
88  600519.SH        600519  ...           None             0
89  600519.SH        600519  ...           None             0
90  600519.SH        600519  ...           None             0
91  600519.SH        600519  ...           None             0
[92 rows x 319 columns]
```

##### 资产负债表-按年度

接口: stock_balance_sheet_by_yearly_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-资产负债表-按年度

限量: 单次获取指定 symbol 的资产负债表-按年度数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 319 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_balance_sheet_by_yearly_em_df = ak.stock_balance_sheet_by_yearly_em(symbol="SH600519")
print(stock_balance_sheet_by_yearly_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ... OSOPINION_TYPE LISTING_STATE
0   600519.SH        600519  ...           None             0
1   600519.SH        600519  ...           None             0
2   600519.SH        600519  ...           None             0
3   600519.SH        600519  ...           None             0
4   600519.SH        600519  ...           None             0
5   600519.SH        600519  ...           None             0
6   600519.SH        600519  ...           None             0
7   600519.SH        600519  ...           None             0
8   600519.SH        600519  ...           None             0
9   600519.SH        600519  ...           None             0
10  600519.SH        600519  ...           None             0
11  600519.SH        600519  ...           None             0
12  600519.SH        600519  ...           None             0
13  600519.SH        600519  ...           None             0
14  600519.SH        600519  ...           None             0
15  600519.SH        600519  ...           None             0
16  600519.SH        600519  ...           None             0
17  600519.SH        600519  ...           None             0
18  600519.SH        600519  ...           None             0
19  600519.SH        600519  ...           None             0
20  600519.SH        600519  ...           None             0
21  600519.SH        600519  ...           None             0
22  600519.SH        600519  ...           None             0
23  600519.SH        600519  ...           None             0
24  600519.SH        600519  ...           None             0
[25 rows x 319 columns]
```

##### 利润表-按报告期

接口: stock_profit_sheet_by_report_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-利润表-报告期

限量: 单次获取指定 symbol 的利润表-报告期数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 203 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_profit_sheet_by_report_em_df = ak.stock_profit_sheet_by_report_em(symbol="SH600519")
print(stock_profit_sheet_by_report_em_df)
```

数据示例

```
   SECUCODE SECURITY_CODE  ... ACF_END_INCOME_YOY OPINION_TYPE
0   600519.SH        600519  ...               None         None
1   600519.SH        600519  ...               None         None
2   600519.SH        600519  ...               None         None
3   600519.SH        600519  ...               None      标准无保留意见
4   600519.SH        600519  ...               None         None
..        ...           ...  ...                ...          ...
87  600519.SH        600519  ...               None      标准无保留意见
88  600519.SH        600519  ...               None      标准无保留意见
89  600519.SH        600519  ...               None      标准无保留意见
90  600519.SH        600519  ...               None      标准无保留意见
91  600519.SH        600519  ...               None      标准无保留意见
[92 rows x 203 columns]
```

##### 利润表-按年度

接口: stock_profit_sheet_by_yearly_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-利润表-按年度

限量: 单次获取指定 symbol 的利润表-按年度数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 203 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_profit_sheet_by_yearly_em_df = ak.stock_profit_sheet_by_yearly_em(symbol="SH600519")
print(stock_profit_sheet_by_yearly_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... ACF_END_INCOME_YOY OPINION_TYPE
0   600519.SH        600519  ...               None      标准无保留意见
1   600519.SH        600519  ...               None      标准无保留意见
2   600519.SH        600519  ...               None      标准无保留意见
3   600519.SH        600519  ...               None      标准无保留意见
4   600519.SH        600519  ...               None      标准无保留意见
5   600519.SH        600519  ...               None      标准无保留意见
6   600519.SH        600519  ...               None      标准无保留意见
7   600519.SH        600519  ...               None      标准无保留意见
8   600519.SH        600519  ...               None      标准无保留意见
9   600519.SH        600519  ...               None      标准无保留意见
10  600519.SH        600519  ...               None      标准无保留意见
11  600519.SH        600519  ...               None      标准无保留意见
12  600519.SH        600519  ...               None      标准无保留意见
13  600519.SH        600519  ...               None      标准无保留意见
14  600519.SH        600519  ...               None      标准无保留意见
15  600519.SH        600519  ...               None      标准无保留意见
16  600519.SH        600519  ...               None      标准无保留意见
17  600519.SH        600519  ...               None      标准无保留意见
18  600519.SH        600519  ...               None      标准无保留意见
19  600519.SH        600519  ...               None      标准无保留意见
20  600519.SH        600519  ...               None      标准无保留意见
21  600519.SH        600519  ...               None      标准无保留意见
22  600519.SH        600519  ...               None      标准无保留意见
23  600519.SH        600519  ...               None      标准无保留意见
24  600519.SH        600519  ...               None      标准无保留意见
[25 rows x 203 columns]
```

##### 利润表-按单季度

接口: stock_profit_sheet_by_quarterly_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-利润表-按单季度

限量: 单次获取指定 symbol 的利润表-按单季度数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 204 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_profit_sheet_by_quarterly_em_df = ak.stock_profit_sheet_by_quarterly_em(symbol="SH600519")
print(stock_profit_sheet_by_quarterly_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ... DEDUCT_PARENT_NETPROFIT DEDUCT_PARENT_NETPROFIT_QOQ
0   600519.SH        600519  ...            1.686819e+10                   11.201931
1   600519.SH        600519  ...            1.516897e+10                  -26.996696
2   600519.SH        600519  ...            2.077848e+10                   12.934838
3   600519.SH        600519  ...            1.839864e+10                   25.756158
4   600519.SH        600519  ...            1.463041e+10                   16.858574
..        ...           ...  ...                     ...                         ...
82  600519.SH        600519  ...                     NaN                         NaN
83  600519.SH        600519  ...            6.878058e+07                   -3.336461
84  600519.SH        600519  ...            7.115463e+07                         NaN
85  600519.SH        600519  ...                     NaN                         NaN
86  600519.SH        600519  ...                     NaN                         NaN
[87 rows x 204 columns]
```

##### 现金流量表-按报告期

接口: stock_cash_flow_sheet_by_report_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-现金流量表-按报告期

限量: 单次获取指定 symbol 的现金流量表-按报告期数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 252 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_cash_flow_sheet_by_report_em_df = ak.stock_cash_flow_sheet_by_report_em(symbol="SH600519")
print(stock_cash_flow_sheet_by_report_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ... MINORITY_INTEREST MINORITY_INTEREST_YOY
0   600519.SH        600519  ...               NaN                   NaN
1   600519.SH        600519  ...               NaN                   NaN
2   600519.SH        600519  ...               NaN                   NaN
3   600519.SH        600519  ...               NaN                   NaN
4   600519.SH        600519  ...               NaN                   NaN
..        ...           ...  ...               ...                   ...
83  600519.SH        600519  ...               NaN                   NaN
84  600519.SH        600519  ...               NaN                   NaN
85  600519.SH        600519  ...               NaN                   NaN
86  600519.SH        600519  ...               NaN                   NaN
87  600519.SH        600519  ...               NaN                   NaN
[88 rows x 252 columns]
```

##### 现金流量表-按年度

接口: stock_cash_flow_sheet_by_yearly_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-现金流量表-按年度

限量: 单次获取指定 symbol 的现金流量表-按年度数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 314 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_cash_flow_sheet_by_yearly_em_df = ak.stock_cash_flow_sheet_by_yearly_em(symbol="SH600519")
print(stock_cash_flow_sheet_by_yearly_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ... FBCCE_ADD_YOY CREDIT_IMPAIRMENT_INCOME_YOY
0   601398.SH        601398  ...    238.302033                         None
1   601398.SH        601398  ...   -204.008112                         None
2   601398.SH        601398  ...    676.398241                         None
3   601398.SH        601398  ...   -446.960304                         None
4   601398.SH        601398  ...   -103.265330                         None
5   601398.SH        601398  ...    231.370619                         None
6   601398.SH        601398  ...   -156.355892                         None
7   601398.SH        601398  ...   1112.723130                         None
8   601398.SH        601398  ...    115.092223                         None
9   601398.SH        601398  ...   -169.124835                         None
10  601398.SH        601398  ...     10.647686                         None
11  601398.SH        601398  ...    167.055537                         None
12  601398.SH        601398  ...    160.423857                         None
13  601398.SH        601398  ...           NaN                         None
14  601398.SH        601398  ...           NaN                         None
15  601398.SH        601398  ...           NaN                         None
16  601398.SH        601398  ...           NaN                         None
17  601398.SH        601398  ...           NaN                         None
18  601398.SH        601398  ...           NaN                         None
19  601398.SH        601398  ...           NaN                         None
[20 rows x 314 columns]
```

##### 现金流量表-按单季度

接口: stock_cash_flow_sheet_by_quarterly_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=sh600519#lrb-0>

描述: 东方财富-股票-财务分析-现金流量表-按单季度

限量: 单次获取指定 symbol 的现金流量表-按单季度数据

输入参数

| 名称     | 类型  | 描述                      |
|--------|-----|-------------------------|
| symbol | str | symbol="SH600519"; 股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 315 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_cash_flow_sheet_by_quarterly_em_df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol="SH600519")
print(stock_cash_flow_sheet_by_quarterly_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ... OPINION_TYPE OSOPINION_TYPE
0   601398.SH        601398  ...         None           None
1   601398.SH        601398  ...         None           None
2   601398.SH        601398  ...      标准无保留意见           None
3   601398.SH        601398  ...         None           None
4   601398.SH        601398  ...         None           None
..        ...           ...  ...          ...            ...
61  601398.SH        601398  ...         None           None
62  601398.SH        601398  ...      标准无保留意见           None
63  601398.SH        601398  ...         None           None
64  601398.SH        601398  ...         None           None
65  601398.SH        601398  ...         None           None
[66 rows x 315 columns]
```

#### 财务报表-同花顺

##### 资产负债表

接口: stock_financial_debt_ths

目标地址: <https://basic.10jqka.com.cn/new/000063/finance.html>

描述: 同花顺-财务指标-资产负债表

限量: 单次获取资产负债表所有历史数据

输入参数

| 名称        | 类型  | 描述                                                  |
|-----------|-----|-----------------------------------------------------|
| symbol    | str | symbol="000063"; 股票代码                               |
| indicator | str | indicator="按报告期"; choice of {"按报告期", "按年度", "按单季度"} |

输出参数

| 名称 | 类型 | 描述         |
|----|----|------------|
| -  | -  | 80 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_financial_debt_ths_df = ak.stock_financial_debt_ths(symbol="000063", indicator="按年度")
print(stock_financial_debt_ths_df)
```

数据示例

```
     报告期 报表核心指标 *所有者权益（或股东权益）合计  ...    少数股东权益 所有者权益（或股东权益）合计 负债和所有者权益（或股东权益）合计
0   2022                595.43亿  ...     9.02亿        595.43亿          1809.54亿
1   2021                532.88亿  ...    18.06亿        532.88亿          1687.63亿
2   2020                461.23亿  ...    28.26亿        461.23亿          1506.35亿
3   2019                379.54亿  ...    28.75亿        379.54亿          1412.02亿
4   2018                329.61亿  ...    38.11亿        329.61亿          1293.51亿
5   2017                453.80亿  ...    44.12亿        453.80亿          1439.62亿
6   2016                408.85亿  ...    51.63亿        408.85亿          1416.41亿
7   2015                433.49亿  ...    43.67亿        433.49亿          1248.32亿
8   2014                262.93亿  ...    14.14亿        262.93亿          1062.14亿
9   2013                236.26亿  ...    10.93亿        236.26亿          1000.79亿
10  2012                225.93亿  ...    11.36亿        225.93亿          1074.46亿
11  2011                262.89亿  ...    20.57亿        262.89亿          1053.68亿
12  2010                249.62亿  ...    18.68亿        249.62亿           841.52亿
13  2009                179.49亿  ...    11.24亿        179.49亿           683.42亿
14  2008                151.84亿  ...     9.34亿        151.84亿           508.66亿
15  2007                128.88亿  ...     7.51亿        128.88亿           391.73亿
16  2006                113.26亿  ...     5.62亿        113.26亿           257.61亿
17  2005                105.96亿  ...     4.71亿        105.96亿           217.79亿
18  2004                 96.39亿  ...     4.65亿         96.39亿           208.30亿
19  2003                 52.77亿  ...     2.33亿         52.77亿           157.67亿
20  2002                 46.04亿  ...     2.17亿         46.04亿           122.17亿
21  2001                 39.18亿  ...  9910.63万         39.18亿            90.55亿
22  2000                 19.50亿  ...  6403.16万         19.50亿            63.21亿
23  1999                 15.79亿  ...  4952.78万         15.79亿            33.85亿
24  1998                  9.60亿  ...  2223.74万          9.60亿            21.94亿
25  1997                  7.01亿  ...   589.60万          7.01亿            13.57亿
26  1996                  1.30亿  ...    10.00万          1.30亿             3.83亿
27  1995               7839.06万  ...     False       7839.06万             2.36亿
28  1994               4254.78万  ...     False       4254.78万             1.45亿
[29 rows x 80 columns]
```

##### 利润表

接口: stock_financial_benefit_ths

目标地址: <https://basic.10jqka.com.cn/new/000063/finance.html>

描述: 同花顺-财务指标-利润表

限量: 单次获取利润表所有历史数据

输入参数

| 名称        | 类型  | 描述                                                  |
|-----------|-----|-----------------------------------------------------|
| symbol    | str | symbol="000063"; 股票代码                               |
| indicator | str | indicator="按报告期"; choice of {"按报告期", "按年度", "按单季度"} |

输出参数

| 名称 | 类型 | 描述         |
|----|----|------------|
| -  | -  | 45 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_financial_benefit_ths_df = ak.stock_financial_benefit_ths(symbol="000063", indicator="按报告期")
print(stock_financial_benefit_ths_df)
```

数据示例

```
           报告期 报表核心指标      *净利润  ... 八、综合收益总额 归属于母公司股东的综合收益总额 归属于少数股东的综合收益总额
0   2023-09-30           77.57亿  ...   77.05亿          77.94亿      -8842.60万
1   2023-06-30           53.92亿  ...   53.41亿          54.24亿      -8317.50万
2   2023-03-31           26.14亿  ...   24.85亿          25.17亿      -3237.00万
3   2022-12-31           77.92亿  ...   77.24亿          80.15亿         -2.90亿
4   2022-09-30           66.90亿  ...   66.52亿          67.88亿         -1.36亿
..         ...    ...       ...  ...      ...             ...            ...
95  1997-12-31            1.21亿  ...    False           False          False
96  1997-06-30         4124.14万  ...    False           False          False
97  1996-12-31         9905.67万  ...    False           False          False
98  1995-12-31         7314.86万  ...    False           False          False
99  1994-12-31         8071.26万  ...    False           False          False
[100 rows x 45 columns]
```

##### 现金流量表

接口: stock_financial_cash_ths

目标地址: <https://basic.10jqka.com.cn/new/000063/finance.html>

描述: 同花顺-财务指标-现金流量表

限量: 单次获取现金流量表所有历史数据

输入参数

| 名称        | 类型  | 描述                                                  |
|-----------|-----|-----------------------------------------------------|
| symbol    | str | symbol="000063"; 股票代码                               |
| indicator | str | indicator="按报告期"; choice of {"按报告期", "按年度", "按单季度"} |

输出参数

| 名称 | 类型 | 描述         |
|----|----|------------|
| -  | -  | 75 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_financial_cash_ths_df = ak.stock_financial_cash_ths(symbol="000063", indicator="按单季度")
print(stock_financial_cash_ths_df)
```

数据示例

```
    报告期 报表核心指标 *现金及现金等价物净增加额  ... 加：现金等价物的期末余额 减：现金等价物的期初余额 间接法-现金及现金等价物净增加额
0   2023-09-30               15.54亿  ...
1   2023-06-30               52.02亿  ...
2   2023-03-31               26.73亿  ...        False        False            False
3   2022-12-31              107.72亿  ...
4   2022-09-30              -77.82亿  ...
..         ...    ...           ...  ...          ...          ...              ...
78  2004-03-31              -16.81亿  ...        False        False          -16.81亿
79  2003-12-31               19.40亿  ...                                     19.40亿
80  2003-09-30              -10.76亿  ...                                    -10.76亿
81  2003-06-30               13.89亿  ...                                     13.89亿
82  2003-03-31              -14.06亿  ...        False        False          -14.06亿
[83 rows x 75 columns]
```

#### 财务报表-东财-已退市股票

##### 资产负债表-按报告期

接口: stock_balance_sheet_by_report_delisted_em

目标地址: <https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/zcfzb>

描述: 东方财富-股票-财务分析-资产负债表-已退市股票-按报告期

限量: 单次获取指定 symbol 的资产负债表-按报告期数据

输入参数

| 名称     | 类型  | 描述                               |
|--------|-----|----------------------------------|
| symbol | str | symbol="SZ000013"; 带市场标识的已退市股票代码 |

输出参数

| 名称  | 类型  | 描述         |
|-----|-----|------------|
| -   | -   | 319项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_balance_sheet_by_report_delisted_em_df = ak.stock_balance_sheet_by_report_delisted_em(symbol="SZ000013")
print(stock_balance_sheet_by_report_delisted_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... OSOPINION_TYPE LISTING_STATE
0   000013.SZ        000013  ...           None             2
1   000013.SZ        000013  ...           None             2
2   000013.SZ        000013  ...           None             2
3   000013.SZ        000013  ...           None             2
4   000013.SZ        000013  ...           None             2
5   000013.SZ        000013  ...           None             2
6   000013.SZ        000013  ...           None             2
7   000013.SZ        000013  ...           None             2
8   000013.SZ        000013  ...           None             2
9   000013.SZ        000013  ...           None             2
10  000013.SZ        000013  ...           None             2
11  000013.SZ        000013  ...           None             2
12  000013.SZ        000013  ...           None             2
13  000013.SZ        000013  ...           None             2
14  000013.SZ        000013  ...           None             2
15  000013.SZ        000013  ...           None             2
16  000013.SZ        000013  ...           None             2
17  000013.SZ        000013  ...           None             2
18  000013.SZ        000013  ...           None             2
19  000013.SZ        000013  ...           None             2
20  000013.SZ        000013  ...           None             2
21  000013.SZ        000013  ...           None             2
22  000013.SZ        000013  ...           None             2
23  000013.SZ        000013  ...           None             2
24  000013.SZ        000013  ...           None             2
25  000013.SZ        000013  ...           None             2
26  000013.SZ        000013  ...           None             2
27  000013.SZ        000013  ...           None             2
28  000013.SZ        000013  ...           None             2
29  000013.SZ        000013  ...           None             2
30  000013.SZ        000013  ...           None             2
31  000013.SZ        000013  ...           None             2
32  000013.SZ        000013  ...           None             2
33  000013.SZ        000013  ...           None             2
34  000013.SZ        000013  ...           None             2
35  000013.SZ        000013  ...           None             2
36  000013.SZ        000013  ...           None             2
37  000013.SZ        000013  ...           None             2
[38 rows x 319 columns]
```

##### 利润表-按报告期

接口: stock_profit_sheet_by_report_delisted_em

目标地址: <https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/lrb>

描述: 东方财富-股票-财务分析-利润表-已退市股票-按报告期

限量: 单次获取指定 symbol 的利润表-按报告期数据

输入参数

| 名称     | 类型  | 描述                               |
|--------|-----|----------------------------------|
| symbol | str | symbol="SZ000013"; 带市场标识的已退市股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 203 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_profit_sheet_by_report_delisted_em_df = ak.stock_profit_sheet_by_report_delisted_em(symbol="SZ000013")
print(stock_profit_sheet_by_report_delisted_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... ACF_END_INCOME_YOY  OPINION_TYPE
0   000013.SZ        000013  ...               None          None
1   000013.SZ        000013  ...               None          None
2   000013.SZ        000013  ...               None          None
3   000013.SZ        000013  ...               None          None
4   000013.SZ        000013  ...               None          None
5   000013.SZ        000013  ...               None          None
6   000013.SZ        000013  ...               None          None
7   000013.SZ        000013  ...               None          None
8   000013.SZ        000013  ...               None          None
9   000013.SZ        000013  ...               None          None
10  000013.SZ        000013  ...               None          None
11  000013.SZ        000013  ...               None          None
12  000013.SZ        000013  ...               None          None
13  000013.SZ        000013  ...               None          None
14  000013.SZ        000013  ...               None       标准无保留意见
15  000013.SZ        000013  ...               None          None
16  000013.SZ        000013  ...               None  带解释性说明的无保留意见
17  000013.SZ        000013  ...               None          None
18  000013.SZ        000013  ...               None          None
19  000013.SZ        000013  ...               None        无法表示意见
20  000013.SZ        000013  ...               None          None
21  000013.SZ        000013  ...               None          未经审计
22  000013.SZ        000013  ...               None          None
23  000013.SZ        000013  ...               None        无法表示意见
24  000013.SZ        000013  ...               None          None
25  000013.SZ        000013  ...               None          未经审计
26  000013.SZ        000013  ...               None          None
27  000013.SZ        000013  ...               None        无法表示意见
28  000013.SZ        000013  ...               None          None
29  000013.SZ        000013  ...               None        无法表示意见
30  000013.SZ        000013  ...               None          None
31  000013.SZ        000013  ...               None          None
32  000013.SZ        000013  ...               None          None
33  000013.SZ        000013  ...               None          None
34  000013.SZ        000013  ...               None          None
35  000013.SZ        000013  ...               None          None
36  000013.SZ        000013  ...               None          None
37  000013.SZ        000013  ...               None          None
38  000013.SZ        000013  ...               None          None
[39 rows x 203 columns]
```

##### 现金流量表-按报告期

接口: stock_cash_flow_sheet_by_report_delisted_em

目标地址: <https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ000013#/cwfx/xjllb>

描述: 东方财富-股票-财务分析-现金流量表-已退市股票-按报告期

限量: 单次获取指定 symbol 的现金流量表-按报告期数据

输入参数

| 名称     | 类型  | 描述                               |
|--------|-----|----------------------------------|
| symbol | str | symbol="SZ000013"; 带市场标识的已退市股票代码 |

输出参数

| 名称  | 类型  | 描述          |
|-----|-----|-------------|
| -   | -   | 252 项，不逐一列出 |

接口示例

```python
import akshare as ak

stock_cash_flow_sheet_by_report_delisted_em_df = ak.stock_cash_flow_sheet_by_report_delisted_em(symbol="SZ000013")
print(stock_cash_flow_sheet_by_report_delisted_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... MINORITY_INTEREST MINORITY_INTEREST_YOY
0   000013.SZ        000013  ...       18337254.13                   NaN
1   000013.SZ        000013  ...       14847516.38            -19.030863
2   000013.SZ        000013  ...        9677540.34                   NaN
3   000013.SZ        000013  ...       23357763.71             57.317649
4   000013.SZ        000013  ...        9262252.60             -4.291253
5   000013.SZ        000013  ...       -3961320.04           -116.959329
6   000013.SZ        000013  ...       -1234838.91           -113.331950
7   000013.SZ        000013  ...      -35258015.13           -790.057223
8   000013.SZ        000013  ...        -179278.95                   NaN
9   000013.SZ        000013  ...       -4739838.45           -283.842654
10  000013.SZ        000013  ...      -28385113.99                   NaN
11  000013.SZ        000013  ...               NaN                   NaN
12  000013.SZ        000013  ...               NaN                   NaN
13  000013.SZ        000013  ...               NaN                   NaN
14  000013.SZ        000013  ...               NaN                   NaN
15  000013.SZ        000013  ...               NaN                   NaN
16  000013.SZ        000013  ...               NaN                   NaN
17  000013.SZ        000013  ...               NaN                   NaN
18  000013.SZ        000013  ...               NaN                   NaN
19  000013.SZ        000013  ...               NaN                   NaN
20  000013.SZ        000013  ...               NaN                   NaN
[21 rows x 252 columns]
```

#### 港股财务报表

接口: stock_financial_hk_report_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HKF10/FinancialAnalysis/index?type=web&code=00700>

描述: 东方财富-港股-财务报表-三大报表

限量: 单次获取指定股票、指定报告且指定报告期的数据

输入参数

| 名称        | 类型  | 描述                                                  |
|-----------|-----|-----------------------------------------------------|
| stock     | str | stock="00700"; 股票代码                                 |
| symbol    | str | symbol="现金流量表"; choice of {"资产负债表", "利润表", "现金流量表"} |
| indicator | str | indicator="年度"; choice of {"年度", "报告期"}             |

输出参数

| 名称                 | 类型      | 描述 |
|--------------------|---------|----|
| SECUCODE           | object  | -  |
| SECURITY_CODE      | object  | -  |
| SECURITY_NAME_ABBR | object  | -  |
| ORG_CODE           | object  | -  |
| REPORT_DATE        | object  | -  |
| DATE_TYPE_CODE     | object  | -  |
| FISCAL_YEAR        | object  | -  |
| STD_ITEM_CODE      | object  | -  |
| STD_ITEM_NAME      | object  | -  |
| AMOUNT             | float64 | -  |
| STD_REPORT_DATE    | object  | -  |

```python
import akshare as ak

stock_financial_hk_report_em_df = ak.stock_financial_hk_report_em(stock="00700", symbol="资产负债表", indicator="年度")
print(stock_financial_hk_report_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ...        AMOUNT      STD_REPORT_DATE
0    00700.HK         00700  ...  5.397800e+10  2022-12-31 00:00:00
1    00700.HK         00700  ...  5.590000e+08  2022-12-31 00:00:00
2    00700.HK         00700  ...  1.618020e+11  2022-12-31 00:00:00
3    00700.HK         00700  ...  1.804600e+10  2022-12-31 00:00:00
4    00700.HK         00700  ...  9.229000e+09  2022-12-31 00:00:00
..        ...           ...  ...           ...                  ...
965  00700.HK         00700  ...  4.817800e+07  2001-12-31 00:00:00
966  00700.HK         00700  ...  4.832400e+07  2001-12-31 00:00:00
967  00700.HK         00700  ...  4.832400e+07  2001-12-31 00:00:00
968  00700.HK         00700  ...  4.832400e+07  2001-12-31 00:00:00
969  00700.HK         00700  ...  6.554200e+07  2001-12-31 00:00:00
[970 rows x 11 columns]
```

#### 美股财务报表

接口: stock_financial_us_report_em

目标地址: <https://emweb.eastmoney.com/PC_USF10/pages/index.html?code=TSLA&type=web&color=w#/cwfx/zyzb>

描述: 东方财富-美股-财务分析-三大报表

限量: 单次获取指定股票、指定报告且指定报告期的数据

输入参数

| 名称        | 类型  | 描述                                                    |
|-----------|-----|-------------------------------------------------------|
| stock     | str | stock="TSLA"; 股票代码, 比如 BRK.A 需修改为 BRK_A 再获取           |
| symbol    | str | symbol="资产负债表"; choice of {"资产负债表", "综合损益表", "现金流量表"} |
| indicator | str | indicator="年报"; choice of {"年报", "单季报", "累计季报"}       |

输出参数

| 名称                 | 类型      | 描述 |
|--------------------|---------|----|
| SECUCODE           | object  | -  |
| SECURITY_CODE      | object  | -  |
| SECURITY_NAME_ABBR | object  | -  |
| REPORT_DATE        | object  | -  |
| REPORT_TYPE        | object  | -  |
| REPORT             | object  | -  |
| STD_ITEM_CODE      | object  | -  |
| AMOUNT             | float64 | -  |
| ITEM_NAME          | object  | -  |

```python
import akshare as ak

stock_financial_us_report_em_df = ak.stock_financial_us_report_em(stock="TSLA", symbol="资产负债表", indicator="年报")
print(stock_financial_us_report_em_df)
```

数据示例

```
    SECUCODE SECURITY_CODE  ...        AMOUNT ITEM_NAME
0     TSLA.O          TSLA  ...  1.613900e+10  现金及现金等价物
1     TSLA.O          TSLA  ...  1.639800e+10  现金及现金等价物
2     TSLA.O          TSLA  ...  1.625300e+10  现金及现金等价物
3     TSLA.O          TSLA  ...  1.757600e+10  现金及现金等价物
4     TSLA.O          TSLA  ...  1.938400e+10  现金及现金等价物
..       ...           ...  ...           ...       ...
619   TSLA.O          TSLA  ...  3.670390e+08     非运算项目
620   TSLA.O          TSLA  ...           NaN     非运算项目
621   TSLA.O          TSLA  ...  3.192250e+08     非运算项目
622   TSLA.O          TSLA  ...  1.011780e+08     非运算项目
623   TSLA.O          TSLA  ...  1.011780e+08     非运算项目
[624 rows x 9 columns]
```

#### 关键指标-新浪

接口: stock_financial_abstract

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/600004.phtml>

描述: 新浪财经-财务报表-关键指标

限量: 单次获取关键指标所有历史数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="600004"; 股票代码 |

输出参数

| 名称       | 类型     | 描述  |
|----------|--------|-----|
| 选项       | object | -   |
| 指标       | object | -   |
| 【具体的报告期】 | object | -   |

接口示例

```python
import akshare as ak

stock_financial_abstract_df = ak.stock_financial_abstract(symbol="600004")
print(stock_financial_abstract_df)
```

数据示例

```
      选项        指标      20220930  ...      20020630      20011231      20001231
0   常用指标     归母净利润 -6.271849e+08  ...  1.365679e+08  2.967902e+08  1.967577e+08
1   常用指标     营业总收入  3.307660e+09  ...  4.381153e+08  8.515877e+08  7.833500e+08
2   常用指标      营业成本  4.212766e+09  ...  2.664150e+08  5.317826e+08  4.654766e+08
3   常用指标       净利润 -6.321978e+08  ...  1.406112e+08  3.009773e+08  2.019293e+08
4   常用指标     扣非净利润 -6.532030e+08  ...  1.364059e+08  1.985243e+08  1.967577e+08
..   ...       ...           ...  ...           ...           ...           ...
74  营运能力    总资产周转率  1.202050e-01  ...           NaN  6.501820e-01           NaN
75  营运能力   总资产周转天数  2.246150e+03  ...           NaN  5.536909e+02           NaN
76  营运能力   流动资产周转率  8.849150e-01  ...           NaN  9.480880e-01           NaN
77  营运能力  流动资产周转天数  3.051139e+02  ...           NaN  3.797112e+02           NaN
78  营运能力   应付账款周转率  5.311671e+00  ...           NaN  2.140125e+01           NaN
```

#### 关键指标-同花顺

接口: stock_financial_abstract_ths

目标地址: <https://basic.10jqka.com.cn/new/000063/finance.html>

描述: 同花顺-财务指标-主要指标

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称        | 类型  | 描述                                                  |
|-----------|-----|-----------------------------------------------------|
| symbol    | str | symbol="000063"; 股票代码                               |
| indicator | str | indicator="按报告期"; choice of {"按报告期", "按年度", "按单季度"} |

输出参数

| 名称         | 类型     | 描述 |
|------------|--------|----|
| 报告期        | object | -  |
| 净利润        | object | -  |
| 净利润同比增长率   | object | -  |
| 扣非净利润      | object | -  |
| 扣非净利润同比增长率 | object | -  |
| 营业总收入      | object | -  |
| 营业总收入同比增长率 | object | -  |
| 基本每股收益     | object | -  |
| 每股净资产      | object | -  |
| 每股资本公积金    | object | -  |
| 每股未分配利润    | object | -  |
| 每股经营现金流    | object | -  |
| 销售净利率      | object | -  |
| 销售毛利率      | object | -  |
| 净资产收益率     | object | -  |
| 净资产收益率-摊薄  | object | -  |
| 营业周期       | object | -  |
| 存货周转率      | object | -  |
| 存货周转天数     | object | -  |
| 应收账款周转天数   | object | -  |
| 流动比率       | object | -  |
| 速动比率       | object | -  |
| 保守速动比率     | object | -  |
| 产权比率       | object | -  |
| 资产负债率      | object | -  |

接口示例

```python
import akshare as ak

stock_financial_abstract_ths_df = ak.stock_financial_abstract_ths(symbol="000063", indicator="按报告期")
print(stock_financial_abstract_ths_df)
```

数据示例

```
     报告期     净利润 净利润同比增长率  扣非净利润  ... 速动比率 保守速动比率 产权比率 资产负债率
0    1994-12-31  8071.26万    False   False  ...   0.74   0.68   2.42  70.75%
1    1995-12-31  7314.86万   -9.37%   False  ...   0.67   0.61   2.02  66.84%
2    1996-12-31  9905.67万   35.42%   False  ...   0.72   0.66   1.95  66.06%
3    1997-06-30  4101.36万    False   False  ...  False  False  False   False
4    1997-12-31     1.17亿   18.17%   False  ...   1.31   1.21   0.94  48.33%
..          ...       ...      ...     ...  ...    ...    ...    ...     ...
100  2023-12-31    93.26亿   15.41%  74.00亿  ...   1.32   1.21   1.95  66.00%
101  2024-03-31    27.41亿    3.74%  26.49亿  ...   1.37   1.27   1.94  65.82%
102  2024-06-30    57.32亿    4.76%  49.64亿  ...   1.28   1.21   1.91  65.57%
103  2024-09-30    79.06亿    0.83%  68.98亿  ...   1.22   1.13   1.76  63.63%
104  2024-12-31    84.25亿   -9.66%  61.79亿  ...   1.10   0.99   1.84  64.74%
[105 rows x 25 columns]
```

#### 主要指标-东方财富

接口: stock_financial_analysis_indicator_em

目标地址: <https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SZ301389&color=b#/cwfx>

描述: 东方财富-A股-财务分析-主要指标

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称        | 类型  | 描述                                           |
|-----------|-----|----------------------------------------------|
| symbol    | str | symbol="301389.SZ"; 股票代码                     |
| indicator | str | indicator="按报告期"; choice of {"按报告期", "按单季度"} |

输出参数

| 名称                 | 类型      | 描述               |
|--------------------|---------|------------------|
| SECUCODE           | object  | 股票代码(带后缀)        |
| SECURITY_CODE      | object  | 股票代码             |
| SECURITY_NAME_ABBR | object  | 股票名称             |
| REPORT_DATE        | object  | 报告日期             |
| REPORT_TYPE        | object  | 报告类型             |
| REPORT_DATE_NAME   | object  | 报告日期名称           |
| EPSJB              | float64 | 基本每股收益(元)        |
| EPSKCJB            | float64 | 扣非每股收益(元)        |
| EPSXS              | float64 | 稀释每股收益(元)        |
| BPS                | float64 | 每股净资产(元)         |
| MGZBGJ             | float64 | 每股公积金(元)         |
| MGWFPLR            | float64 | 每股未分配利润(元)       |
| MGJYXJJE           | float64 | 每股经营现金流(元)       |
| TOTALOPERATEREVE   | float64 | 营业总收入(元)         |
| MLR                | float64 | 毛利润(元)           |
| PARENTNETPROFIT    | float64 | 归属净利润(元)         |
| KCFJCXSYJLR        | float64 | 扣非净利润(元)         |
| TOTALOPERATEREVETZ | float64 | 营业总收入同比增长(%)     |
| PARENTNETPROFITTZ  | float64 | 归属净利润同比增长(%)     |
| KCFJCXSYJLRTZ      | float64 | 扣非净利润同比增长(%)     |
| YYZSRGDHBZC        | float64 | 营业总收入滚动环比增长(%)   |
| NETPROFITRPHBZC    | float64 | 归属净利润滚动环比增长(%)   |
| KFJLRGDHBZC        | float64 | 扣非净利润滚动环比增长(%)   |
| ROEJQ              | float64 | 净资产收益率(加权)(%)    |
| ROEKCJQ            | float64 | 净资产收益率(扣非/加权)(%) |
| ZZCJLL             | float64 | 总资产收益率(加权)(%)    |
| XSJLL              | float64 | 净利率(%)           |
| XSMLL              | float64 | 毛利率(%)           |
| YSZKYYSR           | float64 | 预收账款/营业收入        |
| XSJXLYYSR          | float64 | 销售净现金流/营业收入      |
| JYXJLYYSR          | float64 | 经营净现金流/营业收入      |
| TAXRATE            | float64 | 实际税率(%)          |
| LD                 | float64 | 流动比率             |
| SD                 | float64 | 速动比率             |
| XJLLB              | float64 | 现金流量比率           |
| ZCFZL              | float64 | 资产负债率(%)         |
| QYCS               | float64 | 权益系数             |
| CQBL               | float64 | 产权比率             |
| ZZCZZTS            | float64 | 总资产周转天数(天)       |
| CHZZTS             | float64 | 存货周转天数(天)        |
| YSZKZZTS           | float64 | 应收账款周转天数(天)      |
| TOAZZL             | float64 | 总资产周转率(次)        |
| CHZZL              | float64 | 存货周转率(次)         |
| YSZKZZL            | float64 | 应收账款周转率(次)       |
| ...                | ...     | ...              |

接口示例

```python
import akshare as ak

stock_financial_analysis_indicator_em_df = ak.stock_financial_analysis_indicator_em(symbol="301389.SZ", indicator="按报告期")
print(stock_financial_analysis_indicator_em_df)
```

数据示例

```
     SECUCODE SECURITY_CODE  ... NET_ASSETS_LIABILITIES PROPRIETARY_CAPITAL
0   301389.SZ        301389  ...                   None                None
1   301389.SZ        301389  ...                   None                None
2   301389.SZ        301389  ...                   None                None
3   301389.SZ        301389  ...                   None                None
4   301389.SZ        301389  ...                   None                None
5   301389.SZ        301389  ...                   None                None
6   301389.SZ        301389  ...                   None                None
7   301389.SZ        301389  ...                   None                None
8   301389.SZ        301389  ...                   None                None
9   301389.SZ        301389  ...                   None                None
10  301389.SZ        301389  ...                   None                None
11  301389.SZ        301389  ...                   None                None
12  301389.SZ        301389  ...                   None                None
13  301389.SZ        301389  ...                   None                None
14  301389.SZ        301389  ...                   None                None
15  301389.SZ        301389  ...                   None                None
16  301389.SZ        301389  ...                   None                None
17  301389.SZ        301389  ...                   None                None
18  301389.SZ        301389  ...                   None                None
19  301389.SZ        301389  ...                   None                None
[20 rows x 140 columns]
```

#### 财务指标

接口: stock_financial_analysis_indicator

目标地址: <https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/600004/ctrl/2019/displaytype/4.phtml>

描述: 新浪财经-财务分析-财务指标

限量: 单次获取指定 symbol 和 start_year 的所有财务指标历史数据

输入参数

| 名称         | 类型  | 描述                         |
|------------|-----|----------------------------|
| symbol     | str | symbol="600004"; 股票代码      |
| start_year | str | start_year="2020"; 开始查询的时间 |

输出参数

| 名称                | 类型      | 描述 |
|-------------------|---------|----|
| 日期                | object  | -  |
| 摊薄每股收益(元)         | float64 | -  |
| 加权每股收益(元)         | float64 | -  |
| 每股收益_调整后(元)       | float64 | -  |
| 扣除非经常性损益后的每股收益(元) | float64 | -  |
| 每股净资产_调整前(元)      | float64 | -  |
| 每股净资产_调整后(元)      | float64 | -  |
| 每股经营性现金流(元)       | float64 | -  |
| 每股资本公积金(元)        | float64 | -  |
| 每股未分配利润(元)        | float64 | -  |
| 调整后的每股净资产(元)      | float64 | -  |
| 总资产利润率(%)         | float64 | -  |
| 主营业务利润率(%)        | float64 | -  |
| 总资产净利润率(%)        | float64 | -  |
| 成本费用利润率(%)        | float64 | -  |
| 营业利润率(%)          | float64 | -  |
| 主营业务成本率(%)        | float64 | -  |
| 销售净利率(%)          | float64 | -  |
| 股本报酬率(%)          | float64 | -  |
| 净资产报酬率(%)         | float64 | -  |
| 资产报酬率(%)          | float64 | -  |
| 销售毛利率(%)          | float64 | -  |
| 三项费用比重            | float64 | -  |
| 非主营比重             | float64 | -  |
| 主营利润比重            | float64 | -  |
| 股息发放率(%)          | float64 | -  |
| 投资收益率(%)          | float64 | -  |
| 主营业务利润(元)         | float64 | -  |
| 净资产收益率(%)         | float64 | -  |
| 加权净资产收益率(%)       | float64 | -  |
| 扣除非经常性损益后的净利润(元)  | float64 | -  |
| 主营业务收入增长率(%)      | float64 | -  |
| 净利润增长率(%)         | float64 | -  |
| 净资产增长率(%)         | float64 | -  |
| 总资产增长率(%)         | float64 | -  |
| 应收账款周转率(次)        | float64 | -  |
| 应收账款周转天数(天)       | float64 | -  |
| 存货周转天数(天)         | float64 | -  |
| 存货周转率(次)          | float64 | -  |
| 固定资产周转率(次)        | float64 | -  |
| 总资产周转率(次)         | float64 | -  |
| 总资产周转天数(天)        | float64 | -  |
| 流动资产周转率(次)        | float64 | -  |
| 流动资产周转天数(天)       | float64 | -  |
| 股东权益周转率(次)        | float64 | -  |
| 流动比率              | float64 | -  |
| 速动比率              | float64 | -  |
| 现金比率(%)           | float64 | -  |
| 利息支付倍数            | float64 | -  |
| 长期债务与营运资金比率(%)    | float64 | -  |
| 股东权益比率(%)         | float64 | -  |
| 长期负债比率(%)         | float64 | -  |
| 股东权益与固定资产比率(%)    | float64 | -  |
| 负债与所有者权益比率(%)     | float64 | -  |
| 长期资产与长期资金比率(%)    | float64 | -  |
| 资本化比率(%)          | float64 | -  |
| 固定资产净值率(%)        | float64 | -  |
| 资本固定化比率(%)        | float64 | -  |
| 产权比率(%)           | float64 | -  |
| 清算价值比率(%)         | float64 | -  |
| 固定资产比重(%)         | float64 | -  |
| 资产负债率(%)          | float64 | -  |
| 总资产(元)            | float64 | -  |
| 经营现金净流量对销售收入比率(%) | float64 | -  |
| 资产的经营现金流量回报率(%)   | float64 | -  |
| 经营现金净流量与净利润的比率(%) | float64 | -  |
| 经营现金净流量对负债比率(%)   | float64 | -  |
| 现金流量比率(%)         | float64 | -  |
| 短期股票投资(元)         | float64 | -  |
| 短期债券投资(元)         | float64 | -  |
| 短期其它经营性投资(元)      | float64 | -  |
| 长期股票投资(元)         | float64 | -  |
| 长期债券投资(元)         | float64 | -  |
| 长期其它经营性投资(元)      | float64 | -  |
| 1年以内应收帐款(元)       | float64 | -  |
| 1-2年以内应收帐款(元)     | float64 | -  |
| 2-3年以内应收帐款(元)     | float64 | -  |
| 3年以内应收帐款(元)       | float64 | -  |
| 1年以内预付货款(元)       | float64 | -  |
| 1-2年以内预付货款(元)     | float64 | -  |
| 2-3年以内预付货款(元)     | float64 | -  |
| 3年以内预付货款(元)       | float64 | -  |
| 1年以内其它应收款(元)      | float64 | -  |
| 1-2年以内其它应收款(元)    | float64 | -  |
| 2-3年以内其它应收款(元)    | float64 | -  |
| 3年以内其它应收款(元)      | float64 | -  |

接口示例

```python
import akshare as ak

stock_financial_analysis_indicator_df = ak.stock_financial_analysis_indicator(symbol="600004", start_year="2020")
print(stock_financial_analysis_indicator_df)
```

数据示例

```
         日期  摊薄每股收益(元)  ... 2-3年以内其它应收款(元) 3年以内其它应收款(元)
0   2020-03-31    -0.0307  ...             NaN           NaN
1   2020-06-30    -0.0816  ...      1189862.00           NaN
2   2020-09-30    -0.1380  ...             NaN           NaN
3   2020-12-31    -0.0980  ...      1495234.99           NaN
4   2021-03-31    -0.0645  ...             NaN           NaN
5   2021-06-30    -0.1686  ...      3471186.42           NaN
6   2021-09-30    -0.2038  ...             NaN           NaN
7   2021-12-31    -0.1628  ...      1380992.96           NaN
8   2022-03-31    -0.0326  ...             NaN           NaN
9   2022-06-30    -0.2242  ...      1680204.08           NaN
10  2022-09-30    -0.2671  ...             NaN           NaN
11  2022-12-31    -0.4613  ...      2459538.50           NaN
12  2023-03-31     0.0216  ...             NaN           NaN
13  2023-06-30     0.0720  ...      2591827.74           NaN
14  2023-09-30     0.1232  ...             NaN           NaN
15  2023-12-31     0.2032  ...      7162683.42           NaN
16  2024-03-31     0.0841  ...             NaN           NaN
[17 rows x 86 columns]
```

#### 港股财务指标

接口: stock_financial_hk_analysis_indicator_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HKF10/NewFinancialAnalysis/index?type=web&code=00700>

描述: 东方财富-港股-财务分析-主要指标

限量: 单次获取财务指标所有历史数据

输入参数

| 名称        | 类型  | 描述                                      |
|-----------|-----|-----------------------------------------|
| symbol    | str | symbol="00700"; 股票代码                    |
| indicator | str | indicator="年度"; choice of {"年度", "报告期"} |

输出参数

| 名称                  | 类型      | 描述             |
|---------------------|---------|----------------|
| SECUCODE            | object  | 股票代码(带HK后缀)    |
| SECURITY_CODE       | object  | 股票代码(不带HK后缀)   |
| SECURITY_NAME_ABBR  | object  | 股票名称           |
| ORG_CODE            | object  | ORG_CODE       |
| REPORT_DATE         | object  | 报告日期           |
| DATE_TYPE_CODE      | object  | 报告日期类型         |
| PER_NETCASH_OPERATE | float64 | 每股经营现金流(元)     |
| PER_OI              | float64 | 每股营业收入(元)      |
| BPS                 | float64 | 每股净资产(元)       |
| BASIC_EPS           | float64 | 基本每股收益(元)      |
| DILUTED_EPS         | float64 | 稀释每股收益(元)      |
| OPERATE_INCOME      | int64   | 营业总收入(元)       |
| OPERATE_INCOME_YOY  | float64 | 营业总收入同比增长(%)   |
| GROSS_PROFIT        | int64   | 毛利润(元)         |
| GROSS_PROFIT_YOY    | float64 | 毛利润同比增长(%)     |
| HOLDER_PROFIT       | int64   | 归母净利润(元)       |
| HOLDER_PROFIT_YOY   | float64 | 归母净利润同比增长(%)   |
| GROSS_PROFIT_RATIO  | float64 | 毛利率(%)         |
| EPS_TTM             | float64 | TTM每股收益(元)     |
| OPERATE_INCOME_QOQ  | float64 | 营业总收入滚动环比增长(%) |
| NET_PROFIT_RATIO    | float64 | 净利率(%)         |
| ROE_AVG             | float64 | 平均净资产收益率(%)    |
| GROSS_PROFIT_QOQ    | float64 | 毛利润滚动环比增长(%)   |
| ROA                 | float64 | 总资产净利率(%)      |
| HOLDER_PROFIT_QOQ   | float64 | 归母净利润滚动环比增长(%) |
| ROE_YEARLY          | float64 | 年化净资产收益率(%)    |
| ROIC_YEARLY         | float64 | 年化投资回报率(%)     |
| TAX_EBT             | float64 | 所得税/利润总额(%)    |
| OCF_SALES           | float64 | 经营现金流/营业收入(%)  |
| DEBT_ASSET_RATIO    | float64 | 资产负债率(%)       |
| CURRENT_RATIO       | float64 | 流动比率(倍)        |
| CURRENTDEBT_DEBT    | float64 | 流动负债/总负债(%)    |
| START_DATE          | object  | START_DATE     |
| FISCAL_YEAR         | object  | 年结日            |
| CURRENCY            | object  | CURRENCY       |
| IS_CNY_CODE         | int64   | IS_CNY_CODE    |

接口示例

```python
import akshare as ak

stock_financial_hk_analysis_indicator_em_df = ak.stock_financial_hk_analysis_indicator_em(symbol="00700", indicator="年度")
print(stock_financial_hk_analysis_indicator_em_df)
```

数据示例

```
   SECUCODE SECURITY_CODE SECURITY_NAME_ABBR  ... FISCAL_YEAR CURRENCY IS_CNY_CODE
0  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
1  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
2  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
3  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
4  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
5  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
6  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
7  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
8  00700.HK         00700               腾讯控股  ...       12-31      HKD           0
[9 rows x 36 columns]
```

#### 美股财务指标

接口: stock_financial_us_analysis_indicator_em

目标地址: <https://emweb.eastmoney.com/PC_USF10/pages/index.html?code=TSLA&type=web&color=w#/cwfx/zyzb>

描述: 东方财富-美股-财务分析-主要指标

限量: 单次获取指定股票的所有历史数据

输入参数

| 名称        | 类型  | 描述                                              |
|-----------|-----|-------------------------------------------------|
| symbol    | str | symbol="TSLA"; 股票代码                             |
| indicator | str | indicator="年报"; choice of {"年报", "单季报", "累计季报"} |

输出参数

| 名称                          | 类型      | 描述 |
|-----------------------------|---------|----|
| SECUCODE                    | object  | -  |
| SECURITY_CODE               | object  | -  |
| SECURITY_NAME_ABBR          | object  | -  |
| ORG_CODE                    | object  | -  |
| SECURITY_INNER_CODE         | object  | -  |
| ACCOUNTING_STANDARDS        | object  | -  |
| NOTICE_DATE                 | object  | -  |
| START_DATE                  | object  | -  |
| REPORT_DATE                 | object  | -  |
| FINANCIAL_DATE              | object  | -  |
| STD_REPORT_DATE             | object  | -  |
| CURRENCY                    | object  | -  |
| DATE_TYPE                   | object  | -  |
| DATE_TYPE_CODE              | object  | -  |
| REPORT_TYPE                 | object  | -  |
| REPORT_DATA_TYPE            | object  | -  |
| ORGTYPE                     | object  | -  |
| OPERATE_INCOME              | float64 | -  |
| OPERATE_INCOME_YOY          | float64 | -  |
| GROSS_PROFIT                | float64 | -  |
| GROSS_PROFIT_YOY            | float64 | -  |
| PARENT_HOLDER_NETPROFIT     | int64   | -  |
| PARENT_HOLDER_NETPROFIT_YOY | float64 | -  |
| BASIC_EPS                   | float64 | -  |
| DILUTED_EPS                 | float64 | -  |
| GROSS_PROFIT_RATIO          | float64 | -  |
| NET_PROFIT_RATIO            | float64 | -  |
| ACCOUNTS_RECE_TR            | float64 | -  |
| INVENTORY_TR                | float64 | -  |
| TOTAL_ASSETS_TR             | float64 | -  |
| ACCOUNTS_RECE_TDAYS         | float64 | -  |
| INVENTORY_TDAYS             | float64 | -  |
| TOTAL_ASSETS_TDAYS          | float64 | -  |
| ROE_AVG                     | float64 | -  |
| ROA                         | float64 | -  |
| CURRENT_RATIO               | float64 | -  |
| SPEED_RATIO                 | float64 | -  |
| OCF_LIQDEBT                 | float64 | -  |
| DEBT_ASSET_RATIO            | float64 | -  |
| EQUITY_RATIO                | float64 | -  |
| BASIC_EPS_YOY               | float64 | -  |
| GROSS_PROFIT_RATIO_YOY      | float64 | -  |
| NET_PROFIT_RATIO_YOY        | float64 | -  |
| ROE_AVG_YOY                 | float64 | -  |
| ROA_YOY                     | float64 | -  |
| DEBT_ASSET_RATIO_YOY        | float64 | -  |
| CURRENT_RATIO_YOY           | float64 | -  |
| SPEED_RATIO_YOY             | float64 | -  |

接口示例

```python
import akshare as ak

stock_financial_us_analysis_indicator_em_df = ak.stock_financial_us_analysis_indicator_em(symbol="TSLA", indicator="年报")
print(stock_financial_us_analysis_indicator_em_df)
```

数据示例

```
   SECUCODE SECURITY_CODE  ... CURRENT_RATIO_YOY SPEED_RATIO_YOY
0    TSLA.O          TSLA  ...         17.325422       28.440175
1    TSLA.O          TSLA  ...         12.659536       19.087360
2    TSLA.O          TSLA  ...         11.391821       -2.942407
3    TSLA.O          TSLA  ...        -26.656933      -31.763438
4    TSLA.O          TSLA  ...         65.265821       98.010070
5    TSLA.O          TSLA  ...         36.490497       54.229892
6    TSLA.O          TSLA  ...         -2.902445       -7.382595
7    TSLA.O          TSLA  ...        -20.306070      -21.998647
8    TSLA.O          TSLA  ...          8.548288       34.456320
9    TSLA.O          TSLA  ...        -34.422709      -49.356229
10   TSLA.O          TSLA  ...        -19.511791      -22.928303
11   TSLA.O          TSLA  ...         92.625823      188.401364
12   TSLA.O          TSLA  ...        -50.045468      -71.819999
13   TSLA.O          TSLA  ...        -29.317702      -24.315460
14   TSLA.O          TSLA  ...         57.604938       65.676565
15   TSLA.O          TSLA  ...        389.435012      700.530829
16   TSLA.O          TSLA  ...        -17.820400      -57.326660
17   TSLA.O          TSLA  ...               NaN             NaN
18   TSLA.O          TSLA  ...               NaN             NaN
[19 rows x 48 columns]
```

#### 历史分红

接口: stock_history_dividend

目标地址: <http://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/lsfh/index.phtml>

描述: 新浪财经-发行与分配-历史分红

限量: 单次获取所有股票的历史分红数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称   | 类型      | 描述      |
|------|---------|---------|
| 代码   | object  | -       |
| 名称   | object  | -       |
| 上市日期 | object  | -       |
| 累计股息 | float64 | 注意单位: % |
| 年均股息 | float64 | 注意单位: % |
| 分红次数 | float64 | -       |
| 融资总额 | float64 | 注意单位: 亿 |
| 融资次数 | float64 | -       |

接口示例

```python
import akshare as ak

stock_history_dividend_df = ak.stock_history_dividend()
print(stock_history_dividend_df)
```

数据示例

```
     代码      名称     上市日期   累计股息  年均股息 分红次数 融资总额 融资次数
0     000550  江铃汽车  1993-12-01  213.0  6.87    51   0.0000     0
1     000541  佛山照明  1993-11-23  192.0  6.19    56  10.8842     1
2     000429  粤高速A  1998-02-20  171.4  6.35    50  16.3350     1
3     000726   鲁泰A  2000-12-25  143.9  6.00    47   9.5082     1
4     000581  威孚高科  1998-09-24  143.1  5.50    48  28.5012     1
...      ...   ...         ...    ...   ...   ...      ...   ...
5556  920002  万达轴承  2024-05-30    0.0  0.00     0   1.0235     1
5557  920008  成电光信  2024-08-29    0.0  0.00     0   0.8949     1
5558  920016  中草香料  2024-09-13    0.0  0.00     0   1.1465     1
5559  920099  瑞华技术  2024-09-25    0.0  0.00     0   0.0000     0
5560  920118  太湖远大  2024-08-22    0.0  0.00     0   0.0000     0
[5561 rows x 8 columns]
```

#### 十大流通股东(个股)

接口: stock_gdfx_free_top_10_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/Index?type=web&code=SH688686#sdltgd-0>

描述: 东方财富网-个股-十大流通股东

限量: 单次返回指定 symbol 和 date 的所有数据

输入参数

| 名称     | 类型  | 描述                            |
|--------|-----|-------------------------------|
| symbol | str | symbol="sh688686"; 带市场标识的股票代码 |
| date   | str | date="20240930"; 财报发布季度最后日    |

输出参数

| 名称         | 类型      | 描述      |
|------------|---------|---------|
| 名次         | int64   | -       |
| 股东名称       | object  | -       |
| 股东性质       | object  | -       |
| 股份类型       | object  | -       |
| 持股数        | int64   | 注意单位: 股 |
| 占总流通股本持股比例 | float64 | 注意单位: % |
| 增减         | object  | 注意单位: 股 |
| 变动比率       | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_gdfx_free_top_10_em_df = ak.stock_gdfx_free_top_10_em(symbol="sh688686", date="20240930")
print(stock_gdfx_free_top_10_em_df)
```

数据示例

```
   名次                               股东名称  ...        增减       变动比率
0   1                                 卢治临  ...        不变        NaN
1   2                                 卢盛林  ...        不变        NaN
2   3                                 许学亮  ...        不变        NaN
3   4                  宁波千智创业投资合伙企业(有限合伙)  ...        不变        NaN
4   5                          香港中央结算有限公司  ...  -1132820 -25.435429
5   6  国信证券-招商银行-国信证券鼎信10号科创板战略配售集合资产管理计划  ...        不变        NaN
6   7        摩根资产管理(新加坡)有限公司-摩根中国A股市场机会基金  ...        不变        NaN
7   8                                 李茂波  ...        不变        NaN
8   9     招商银行股份有限公司-惠升惠泽灵活配置混合型发起式证券投资基金  ...        不变        NaN
9  10         MERRILL LYNCH INTERNATIONAL  ...        新进        NaN
[10 rows x 8 columns]
```

#### 十大股东(个股)

接口: stock_gdfx_top_10_em

目标地址: <https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/Index?type=web&code=SH688686#sdltgd-0>

描述: 东方财富网-个股-十大股东

限量: 单次返回指定 symbol 和 date 的所有数据

输入参数

| 名称     | 类型  | 描述                            |
|--------|-----|-------------------------------|
| symbol | str | symbol="sh688686"; 带市场标识的股票代码 |
| date   | str | date="20210630"; 财报发布季度最后日    |

输出参数

| 名称       | 类型      | 描述      |
|----------|---------|---------|
| 名次       | int64   | -       |
| 股东名称     | object  | -       |
| 股份类型     | object  | -       |
| 持股数      | int64   | 注意单位: 股 |
| 占总股本持股比例 | float64 | 注意单位: % |
| 增减       | object  | 注意单位: 股 |
| 变动比率     | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_gdfx_top_10_em_df = ak.stock_gdfx_top_10_em(symbol="sh688686", date="20210630")
print(stock_gdfx_top_10_em_df)
```

数据示例

```
   名次                                        股东名称  ...       增减       变动比率
0   1                                         卢治临  ...       不变        NaN
1   2                                         卢盛林  ...       不变        NaN
2   3                                         许学亮  ...       不变        NaN
3   4                          东莞千智股权投资合伙企业(有限合伙)  ...       不变        NaN
4   5                  高华-汇丰-GOLDMAN,SACHS&CO.LLC  ...   946997  54.311934
5   6            铭基国际投资公司-MATTHEWS ASIA FUNDS(US)  ...  -358837 -15.460528
6   7     MORGAN STANLEY & CO. INTERNATIONAL PLC.  ...    70003   4.082755
7   8  宁波梅山保税港区晨道投资合伙企业-长江晨道(湖北)新能源产业投资合伙企业(有限合伙)  ...       不变        NaN
8   9          国信证券-招商银行-国信证券鼎信10号科创板战略配售集合资产管理计划  ...  -639100 -30.994180
9  10                      FMR 有限公司-富达新兴市场基金(交易所)  ...       新进        NaN
```

#### 股东持股变动统计-十大流通股东

接口: stock_gdfx_free_holding_change_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股变动统计-十大流通股东

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 序号           | int64   | -       |
| 股东名称         | object  | -       |
| 股东类型         | object  | -       |
| 期末持股只数统计-总持有 | float64 | -       |
| 期末持股只数统计-新进  | float64 | -       |
| 期末持股只数统计-增加  | float64 | -       |
| 期末持股只数统计-不变  | float64 | -       |
| 期末持股只数统计-减少  | float64 | -       |
| 流通市值统计       | float64 | 注意单位: 元 |
| 持有个股         | object  | -       |

接口示例

```python
import akshare as ak

stock_gdfx_free_holding_change_em_df = ak.stock_gdfx_free_holding_change_em(date="20210930")
print(stock_gdfx_free_holding_change_em_df)
```

数据示例

```
          序号  ...                                               持有个股
0          1  ...  603218|日月股份,600988|赤峰黄金,600298|安琪酵母,300232|洲明科...
1          2  ...  600519|贵州茅台,000686|东北证券,002533|金杯电工,002066|瑞泰科...
2          3  ...  600519|贵州茅台,300015|爱尔眼科,600674|川投能源,600009|上海机...
3          4  ...  000026|飞亚达,200026|飞亚达B,300946|恒而达,000751|锌业股份,...
4          5  ...  300005|探路者,300946|恒而达,000985|大庆华科,300927|江天化学,...
      ...  ...                                                ...
30953  30954  ...                                        002982|湘佳股份
30954  30955  ...                                        300917|特发服务
30955  30956  ...                                         688733|壹石通
30956  30957  ...                                        300969|恒帅股份
30957  30958  ...                                        002896|中大力德
```

#### 股东持股变动统计-十大股东

接口: stock_gdfx_holding_change_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股变动统计-十大股东

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 序号           | int64   | -       |
| 股东名称         | object  | -       |
| 股东类型         | object  | -       |
| 期末持股只数统计-总持有 | float64 | -       |
| 期末持股只数统计-新进  | float64 | -       |
| 期末持股只数统计-增加  | float64 | -       |
| 期末持股只数统计-不变  | float64 | -       |
| 期末持股只数统计-减少  | float64 | -       |
| 流通市值统计       | float64 | 注意单位: 元 |
| 持有个股         | object  | -       |

接口示例

```python
import akshare as ak

stock_gdfx_holding_change_em_df = ak.stock_gdfx_holding_change_em(date="20210930")
print(stock_gdfx_holding_change_em_df)
```

数据示例

```
          序号  ...                                               持有个股
0          1  ...  600763|通策医疗,300229|拓尔思,603039|泛微网络,300006|莱美药业...
1          2  ...  002225|濮耐股份,600435|北方导航,600422|昆药集团,600009|上海机...
2          3  ...  600340|华夏幸福,600009|上海机场,000001|平安银行,601899|紫金矿...
3          4  ...  601865|福莱特,601899|紫金矿业,000756|新华制药,600036|招商银行...
4          5  ...  002479|富春环保,300582|英飞特,300358|楚天科技,002892|科力尔,...
      ...  ...                                                ...
33896  33897  ...                                        300047|天源迪科
33897  33898  ...                                        300969|恒帅股份
33898  33899  ...                                        000425|徐工机械
33899  33900  ...                                        002896|中大力德
33900  33901  ...                            000761|本钢板材,200761|本钢板B
```

#### 高管持股变动统计

接口: stock_management_change_ths

目标地址: <https://basic.10jqka.com.cn/new/688981/event.html>

描述: 同花顺-公司大事-高管持股变动

限量: 单次返回所有数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="688981"; 股票代码 |

输出参数

| 名称      | 类型     | 描述      |
|---------|--------|---------|
| 公告日期    | object | -       |
| 变动人     | object | -       |
| 与公司高管关系 | object | -       |
| 变动数量    | object | 注意单位: 股 |
| 交易均价    | object | 注意单位: 元 |
| 剩余股数    | object | 注意单位: 股 |
| 变动途径    | object | -       |

接口示例

```python
import akshare as ak

stock_management_change_ths_df = ak.stock_management_change_ths(symbol="688981")
print(stock_management_change_ths_df)
```

数据示例

```
          变动日期  变动人 与公司高管关系     ...   交易均价    剩余股数  股份变动途径
0   2022-09-01   张昕  核心技术人员    ...  20.00   9.60万    股权激励
1   2022-09-01   金达  核心技术人员    ...  20.00   4.80万    股权激励
2   2022-09-01  阎大勇  核心技术人员    ...  20.00   4.20万    股权激励
3   2022-10-10  阎大勇  核心技术人员  减持4.20万  37.98    0.00  二级市场买卖
  ...             ...             ...
10  2024-09-05  阎大勇  核心技术人员  增持3.50万  20.00   7.00万  股权激励实施
11  2024-09-05   张昕  核心技术人员  增持8.00万  20.00  16.00万  股权激励实施
12  2024-09-25   张昕  核心技术人员  减持1.80万  45.31  14.20万  二级市场买卖
13  2024-09-30   金达  核心技术人员  减持4.00万  54.87   4.00万  二级市场买卖
[13 rows x 7 columns]
```

#### 股东持股变动统计

接口: stock_shareholder_change_ths

目标地址: <https://basic.10jqka.com.cn/new/688981/event.html>

描述: 同花顺-公司大事-股东持股变动

限量: 单次返回所有数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="688981"; 股票代码 |

输出参数

| 名称     | 类型     | 描述      |
|--------|--------|---------|
| 公告日期   | object | -       |
| 变动股东   | object | -       |
| 变动数量   | object | 注意单位: 股 |
| 交易均价   | object | 注意单位: 元 |
| 剩余股份总数 | object | 注意单位: 股 |
| 变动期间   | object | -       |
| 变动途径   | object | -       |

接口示例

```python
import akshare as ak

stock_shareholder_change_ths_df = ak.stock_shareholder_change_ths(symbol="688981")
print(stock_shareholder_change_ths_df)
```

数据示例

```
         公告日期                        变动股东  ...                   变动期间         变动途径
0  2021-08-11           GICPrivateLimited  ...                  2021.08.04-2021.08.04  二级市场
1  2022-12-16   华夏上证科创板50成份交易型开放式指数证券投资基金  ...  2022.12.14-2022.12.14  二级市场
2  2023-04-13   华夏上证科创板50成份交易型开放式指数证券投资基金  ...  2023.04.10-2023.04.10  二级市场
3  2023-08-31   华夏上证科创板50成份交易型开放式指数证券投资基金  ...  2023.08.29-2023.08.29  二级市场
4  2024-02-28   华夏上证科创板50成份交易型开放式指数证券投资基金  ...  2024.02.26-2024.02.26  二级市场
5  2024-10-12  易方达上证科创板50成份交易型开放式指数证券投资基金  ...  2024.10.10-2024.10.10  二级市场
6  2024-10-23  易方达上证科创板50成份交易型开放式指数证券投资基金  ...  2024.10.21-2024.10.21  二级市场
[7 rows x 7 columns]
```

#### 股东持股分析-十大流通股东

接口: stock_gdfx_free_holding_analyse_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股分析-十大流通股东

限量: 单次获取返回所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20230930"; 财报发布季度最后日 |

输出参数

| 名称             | 类型      | 描述      |
|----------------|---------|---------|
| 序号             | int64   | -       |
| 股东名称           | object  | -       |
| 股东类型           | object  | -       |
| 股票代码           | object  | -       |
| 股票简称           | object  | -       |
| 报告期            | object  | -       |
| 期末持股-数量        | float64 | 注意单位: 股 |
| 期末持股-数量变化      | float64 | 注意单位: 股 |
| 期末持股-数量变化比例    | float64 | 注意单位: % |
| 期末持股-持股变动      | float64 | -       |
| 期末持股-流通市值      | float64 | 注意单位: 元 |
| 公告日            | object  | -       |
| 公告日后涨跌幅-10个交易日 | float64 | 注意单位: % |
| 公告日后涨跌幅-30个交易日 | float64 | 注意单位: % |
| 公告日后涨跌幅-60个交易日 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_gdfx_free_holding_analyse_em_df = ak.stock_gdfx_free_holding_analyse_em(date="20230930")
print(stock_gdfx_free_holding_analyse_em_df)
```

数据示例

```
          序号  ... 公告日后涨跌幅-60个交易日
0          1  ...      -0.959312
1          2  ...      -0.959312
2          3  ...      -0.959312
3          4  ...      -0.959312
4          5  ...      -0.959312
      ...  ...            ...
53269  53270  ...       2.169464
53270  53271  ...       2.169464
53271  53272  ...       2.169464
53272  53273  ...       2.169464
53273  53274  ...       2.169464
[53274 rows x 15 columns]
```

#### 股东持股分析-十大股东

接口: stock_gdfx_holding_analyse_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股分析-十大股东

限量: 单次获取返回所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称             | 类型      | 描述      |
|----------------|---------|---------|
| 序号             | int64   | -       |
| 股东名称           | object  | -       |
| 股东类型           | object  | -       |
| 股票代码           | object  | -       |
| 股票简称           | object  | -       |
| 报告期            | object  | -       |
| 期末持股-数量        | float64 | 注意单位: 股 |
| 期末持股-数量变化      | float64 | 注意单位: 股 |
| 期末持股-数量变化比例    | float64 | 注意单位: % |
| 期末持股-持股变动      | float64 | -       |
| 期末持股-流通市值      | float64 | 注意单位: 元 |
| 公告日            | object  | -       |
| 公告日后涨跌幅-10个交易日 | float64 | 注意单位: % |
| 公告日后涨跌幅-30个交易日 | float64 | 注意单位: % |
| 公告日后涨跌幅-60个交易日 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_gdfx_holding_analyse_em_df = ak.stock_gdfx_holding_analyse_em(date="20210930")
print(stock_gdfx_holding_analyse_em_df)
```

数据示例

```
          序号               股东名称  ... 公告日后涨跌幅-30个交易日 公告日后涨跌幅-60个交易日
0          1     厦门象屿资产管理运营有限公司  ...            NaN            NaN
1          2       厦门港务控股集团有限公司  ...            NaN            NaN
2          3       厦门国际会展控股有限公司  ...            NaN            NaN
3          4       厦门国贸金融控股有限公司  ...            NaN            NaN
4          5         福建奥元集团有限公司  ...            NaN            NaN
      ...                ...  ...            ...            ...
55198  55199  深圳市德益共赢投资企业(有限合伙)  ...            NaN            NaN
55199  55200                王小峰  ...            NaN            NaN
55200  55201                卢达华  ...            NaN            NaN
55201  55202      东莞市通辉模具股份有限公司  ...            NaN            NaN
55202  55203                 赵禹  ...            NaN            NaN
```

#### 股东持股明细-十大流通股东

接口: stock_gdfx_free_holding_detail_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股明细-十大流通股东

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 序号           | int64   | -       |
| 股东名称         | object  | -       |
| 股东类型         | object  | -       |
| 股票代码         | object  | -       |
| 股票简称         | object  | -       |
| 报告期          | object  | -       |
| 期末持股-数量      | float64 | 注意单位: 股 |
| 期末持股-数量变化    | float64 | 注意单位: 股 |
| 期末持股-数量变化比例  | float64 | 注意单位: % |
| 期末持股-持股变动    | float64 | -       |
| 期末持股-流通市值    | float64 | 注意单位: 元 |
| 公告日          | object  | -       |

接口示例

```python
import akshare as ak

stock_gdfx_free_holding_detail_em_df = ak.stock_gdfx_free_holding_detail_em(date="20210930")
print(stock_gdfx_free_holding_detail_em_df)
```

数据示例

```
     序号                                 股东名称  ...     期末持股-流通市值         公告日
0          1                         漯河银鸽实业集团有限公司  ...  2.152836e+08  2022-04-29
1          2                       永城煤电控股集团上海有限公司  ...  1.363201e+07  2022-04-29
2          3                      漯河市发展投资控股集团有限公司  ...  5.661508e+06  2022-04-29
3          4                                  黄毅明  ...  4.968781e+06  2022-04-29
4          5                                  何卫昌  ...  3.609256e+06  2022-04-29
      ...                                  ...  ...           ...         ...
46546  46547     中国工商银行股份有限公司-东方红启恒三年持有期混合型证券投资基金  ...  2.441112e+08  2021-10-12
46547  46548        招商银行股份有限公司-泓德瑞兴三年持有期混合型证券投资基金  ...  2.201811e+08  2021-10-12
46548  46549  中国工商银行股份有限公司-富国天惠精选成长混合型证券投资基金(LOF)  ...  2.132101e+08  2021-10-12
46549  46550                          全国社保基金四零二组合  ...  2.128475e+08  2021-10-12
46550  46551              中国工商银行股份有限公司-博时信用债券投资基金  ...  2.079605e+08  2021-10-12
```

#### 股东持股明细-十大股东

接口: stock_gdfx_holding_detail_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股明细-十大股东

限量: 单次返回指定参数的所有数据

输入参数

| 名称        | 类型  | 描述                                                                     |
|-----------|-----|------------------------------------------------------------------------|
| date      | str | date="20230331"; 财报发布季度最后日                                             |
| indicator | str | indicator="个人"; 股东类型; choice of {"个人", "基金", "QFII", "社保", "券商", "信托"} |
| symbol    | str | symbol="新进"; 持股变动; choice of {"新进", "增加", "不变", "减少"}                  |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 序号           | int64   | -       |
| 股东名称         | object  | -       |
| 股东排名         | object  | -       |
| 股票代码         | object  | -       |
| 股票简称         | object  | -       |
| 报告期          | object  | -       |
| 期末持股-数量      | float64 | 注意单位: 股 |
| 期末持股-数量变化    | float64 | 注意单位: 股 |
| 期末持股-数量变化比例  | float64 | 注意单位: % |
| 期末持股-持股变动    | float64 | -       |
| 期末持股-流通市值    | float64 | 注意单位: 元 |
| 公告日          | object  | -       |
| 股东类型         | object  | -       |

接口示例

```python
import akshare as ak

stock_gdfx_holding_detail_em_df = ak.stock_gdfx_holding_detail_em(date="20230331", indicator="个人", symbol="新进")
print(stock_gdfx_holding_detail_em_df)
```

数据示例

```
        序号           股东名称 股东类型    股票代码  ... 期末持股-持股变动 期末持股-流通市值         公告日  股东排名
0        1            金凤霞   个人  688651  ...        新进       NaN  2023-07-21     6
1        2            周华金   个人  688651  ...        新进       NaN  2023-07-21     9
2        3            王润合   个人  688651  ...        新进       NaN  2023-07-21    10
3        4            魏春梅   个人  688651  ...        新进       NaN  2023-07-21    12
4        5            何永华   个人  688651  ...        新进       NaN  2023-07-21    14
    ...            ...  ...     ...  ...       ...       ...         ...   ...
3974  3975             黄敏   个人  873761  ...        新进       NaN  2023-03-28     3
3975  3976            姜海林   个人  873761  ...        新进       NaN  2023-03-28     4
3976  3977            廖道训   个人  873761  ...        新进       NaN  2023-03-28     5
3977  3978            李天兵   个人  873761  ...        新进       NaN  2023-03-28     6
3978  3979  LIANG AMY JUN   个人  873761  ...        新进       NaN  2023-03-28     7
[3979 rows x 13 columns]
```

#### 股东持股统计-十大流通股东

接口: stock_gdfx_free_holding_statistics_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股统计-十大股东

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称                   | 类型      | 描述  |
|----------------------|---------|-----|
| 序号                   | int64   | -   |
| 股东名称                 | object  | -   |
| 股东类型                 | object  | -   |
| 统计次数                 | int64   | -   |
| 公告日后涨幅统计-10个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-10个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-10个交易日-最小涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-最小涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-最小涨幅 | float64 | -   |
| 持有个股                 | object  | -   |

接口示例

```python
import akshare as ak

stock_gdfx_free_holding_statistics_em_df = ak.stock_gdfx_free_holding_statistics_em(date="20210930")
print(stock_gdfx_free_holding_statistics_em_df)
```

数据示例

```
          序号  ...                                               持有个股
0          1  ...  603218|日月股份,600988|赤峰黄金,600298|安琪酵母,300232|洲明科...
1          2  ...  600519|贵州茅台,000686|东北证券,002533|金杯电工,002066|瑞泰科...
2          3  ...  600519|贵州茅台,300015|爱尔眼科,600674|川投能源,600009|上海机...
3          4  ...  000026|飞亚达,300946|恒而达,000751|锌业股份,300927|江天化学,...
4          5  ...  300005|探路者,300946|恒而达,000985|大庆华科,300927|江天化学,...
      ...  ...                                                ...
30963  30964  ...                                        002982|湘佳股份
30964  30965  ...                                        300917|特发服务
30965  30966  ...                                         688733|壹石通
30966  30967  ...                                        300969|恒帅股份
30967  30968  ...                                        002896|中大力德
```

#### 股东持股统计-十大股东

接口: stock_gdfx_holding_statistics_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东持股统计-十大股东

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                         |
|------|-----|----------------------------|
| date | str | date="20210930"; 财报发布季度最后日 |

输出参数

| 名称                   | 类型      | 描述  |
|----------------------|---------|-----|
| 序号                   | int64   | -   |
| 股东名称                 | object  | -   |
| 股东类型                 | object  | -   |
| 统计次数                 | int64   | -   |
| 公告日后涨幅统计-10个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-10个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-10个交易日-最小涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-30个交易日-最小涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-平均涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-最大涨幅 | float64 | -   |
| 公告日后涨幅统计-60个交易日-最小涨幅 | float64 | -   |
| 持有个股                 | object  | -   |

接口示例

```python
import akshare as ak

stock_gdfx_holding_statistics_em_df = ak.stock_gdfx_holding_statistics_em(date="20210930")
print(stock_gdfx_holding_statistics_em_df)
```

数据示例

```
          序号  ...                                               持有个股
0          1  ...  600763|通策医疗,300229|拓尔思,603039|泛微网络,300006|莱美药业...
1          2  ...  002225|濮耐股份,600435|北方导航,600422|昆药集团,600009|上海机...
2          3  ...  600340|华夏幸福,600009|上海机场,000001|平安银行,601899|紫金矿...
3          4  ...  601865|福莱特,601899|紫金矿业,000756|新华制药,600036|招商银行...
4          5  ...  002479|富春环保,300582|英飞特,300358|楚天科技,002892|科力尔,...
      ...  ...                                                ...
33819  33820  ...                                        300047|天源迪科
33820  33821  ...                                        300969|恒帅股份
33821  33822  ...                                        000425|徐工机械
33822  33823  ...                                        002896|中大力德
33823  33824  ...                                        000761|本钢板材
```

#### 股东协同-十大流通股东

接口: stock_gdfx_free_holding_teamwork_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东协同-十大流通股东

限量: 单次返回所有数据

输入参数

| 名称     | 类型  | 描述                                                                  |
|--------|-----|---------------------------------------------------------------------|
| symbol | str | symbol="社保"; choice of {"全部", "个人", "基金", "QFII", "社保", "券商", "信托"} |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int64  | -   |
| 股东名称   | object | -   |
| 股东类型   | object | -   |
| 协同股东名称 | object | -   |
| 协同股东类型 | object | -   |
| 协同次数   | int64  | -   |
| 个股详情   | object | -   |

接口示例

```python
import akshare as ak

stock_gdfx_free_holding_teamwork_em_df = ak.stock_gdfx_free_holding_teamwork_em(symbol="社保")
print(stock_gdfx_free_holding_teamwork_em_df)
```

数据示例

```
          序号  ...                                               个股详情
0          1  ...  601668|中国建筑|2023-09-30,600066|宇通客车|2023-06-30,...
1          2  ...  600028|中国石化|2022-09-30,300059|东方财富|2022-12-31,...
2          3  ...  600782|新钢股份|2022-09-30,002463|沪电股份|2021-12-31,...
3          4  ...  601899|紫金矿业|2023-03-31,600031|三一重工|2023-09-30,...
4          5  ...  002340|格林美|2022-06-30,600968|海油发展|2022-09-30,6...
      ...  ...                                                ...
19421  19422  ...                             600019|宝钢股份|2021-03-31
19422  19423  ...                             600019|宝钢股份|2021-03-31
19423  19424  ...                             600019|宝钢股份|2021-03-31
19424  19425  ...                             600019|宝钢股份|2021-03-31
19425  19426  ...                             600019|宝钢股份|2021-03-31
[19426 rows x 7 columns]
```

#### 股东协同-十大股东

接口: stock_gdfx_holding_teamwork_em

目标地址: <https://data.eastmoney.com/gdfx/HoldingAnalyse.html>

描述: 东方财富网-数据中心-股东分析-股东协同-十大股东

限量: 单次返回所有数据

输入参数

| 名称     | 类型  | 描述                                                                  |
|--------|-----|---------------------------------------------------------------------|
| symbol | str | symbol="社保"; choice of {"全部", "个人", "基金", "QFII", "社保", "券商", "信托"} |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int64  | -   |
| 股东名称   | object | -   |
| 股东类型   | object | -   |
| 协同股东名称 | object | -   |
| 协同股东类型 | object | -   |
| 协同次数   | int64  | -   |
| 个股详情   | object | -   |

接口示例

```python
import akshare as ak

stock_gdfx_holding_teamwork_em_df = ak.stock_gdfx_holding_teamwork_em(symbol="社保")
print(stock_gdfx_holding_teamwork_em_df)
```

数据示例

```
       序号  ...                                               个股详情
0          1  ...  601668|中国建筑|2023-09-30,600066|宇通客车|2023-06-30,...
1          2  ...  600028|中国石化|2022-09-30,300059|东方财富|2022-12-31,...
2          3  ...  600782|新钢股份|2022-09-30,002463|沪电股份|2021-12-31,...
3          4  ...  601899|紫金矿业|2023-03-31,600031|三一重工|2023-09-30,...
4          5  ...  601168|西部矿业|2023-09-30,002439|启明星辰|2023-09-30,...
      ...  ...                                                ...
15214  15215  ...                             600019|宝钢股份|2021-03-31
15215  15216  ...                             600019|宝钢股份|2021-03-31
15216  15217  ...                             600019|宝钢股份|2021-03-31
15217  15218  ...                             600019|宝钢股份|2021-03-31
15218  15219  ...                             600019|宝钢股份|2021-03-31
[15219 rows x 7 columns]
```

#### 股东户数

接口: stock_zh_a_gdhs

目标地址: <http://data.eastmoney.com/gdhs/>

描述: 东方财富网-数据中心-特色数据-股东户数数据

限量: 单次获取返回所有数据

输入参数

| 名称     | 类型  | 描述                                                                     |
|--------|-----|------------------------------------------------------------------------|
| symbol | str | symbol="20230930"; choice of {"最新", 每个季度末}, 其中 每个季度末需要写成 `20230930` 格式 |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 代码           | object  | -       |
| 名称           | object  | -       |
| 最新价          | float64 | 注意单位: 元 |
| 涨跌幅          | float64 | 注意单位: % |
| 股东户数-本次      | int64   | -       |
| 股东户数-上次      | int64   | -       |
| 股东户数-增减      | int64   | -       |
| 股东户数-增减比例    | float64 | 注意单位: % |
| 区间涨跌幅        | float64 | 注意单位: % |
| 股东户数统计截止日-本次 | object  | -       |
| 股东户数统计截止日-上次 | object  | -       |
| 户均持股市值       | float64 | -       |
| 户均持股数量       | float64 | -       |
| 总市值          | float64 | -       |
| 总股本          | float64 | -       |
| 公告日期         | object  | -       |

接口示例

```python
import akshare as ak

stock_zh_a_gdhs_df = ak.stock_zh_a_gdhs(symbol="20230930")
print(stock_zh_a_gdhs_df)
```

数据示例

```
      代码    名称     最新价  ...     总市值           总股本        公告日期
0     688235  百济神州  139.04  ...  1.625156e+10  1.150553e+08  2023-11-14
1     688981  中芯国际   53.02  ...  1.009501e+11  1.973609e+09  2023-11-10
2     688793   倍轻松   33.65  ...  3.142165e+09  8.594542e+07  2023-10-31
3     688789  宏华数科   99.91  ...  1.156317e+10  1.204371e+08  2023-10-31
4     688787  海天瑞声   72.10  ...  5.248291e+09  6.032518e+07  2023-10-31
      ...   ...     ...  ...           ...           ...         ...
5153  600810  神马股份    7.44  ...  7.810436e+09  1.044178e+09  2023-10-12
5154  300809  华辰装备   29.25  ...  7.587976e+09  2.521760e+08  2023-10-12
5155  002817  黄山胶囊    8.76  ...  2.548316e+09  2.990982e+08  2023-10-12
5156  688188  柏楚电子  253.11  ...  3.648391e+10  1.462926e+08  2023-10-11
5157  601666  平煤股份   11.56  ...  2.385597e+10  2.313876e+09  2023-10-11
[5158 rows x 16 columns]
```

#### 股东户数详情

接口: stock_zh_a_gdhs_detail_em

目标地址: <https://data.eastmoney.com/gdhs/detail/000002.html>

描述: 东方财富网-数据中心-特色数据-股东户数详情

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="000001"; 股票代码 |

输出参数

| 名称        | 类型      | 描述      |
|-----------|---------|---------|
| 股东户数统计截止日 | object  | -       |
| 区间涨跌幅     | float64 | 注意单位: % |
| 股东户数-本次   | int64   | -       |
| 股东户数-上次   | int64   | -       |
| 股东户数-增减   | int64   | -       |
| 股东户数-增减比例 | float64 | 注意单位: % |
| 户均持股市值    | float64 | -       |
| 户均持股数量    | float64 | -       |
| 总市值       | float64 | -       |
| 总股本       | int64   | -       |
| 股本变动      | int64   | -       |
| 股本变动原因    | object  | -       |
| 股东户数公告日期  | object  | -       |
| 代码        | object  | -       |
| 名称        | object  | -       |

接口示例

```python
import akshare as ak

stock_zh_a_gdhs_detail_em_df = ak.stock_zh_a_gdhs_detail_em(symbol="000001")
print(stock_zh_a_gdhs_detail_em_df)
```

数据示例

```
    股东户数统计截止日 区间涨跌幅  股东户数-本次  ...股东户数公告日期  代码    名称
0   2023-09-30  -0.267142   530229  ...  2023-10-25  000001  平安银行
1   2023-06-30  -8.191107   536701  ...  2023-08-24  000001  平安银行
2   2023-03-31  -9.071118   506867  ...  2023-04-25  000001  平安银行
3   2023-02-28   4.711246   477304  ...  2023-03-09  000001  平安银行
4   2022-12-31  11.148649   487200  ...  2023-03-09  000001  平安银行
5   2022-09-30 -19.538845   547735  ...  2022-10-25  000001  平安银行
6   2022-06-30  -2.600780   493029  ...  2022-08-18  000001  平安银行
7   2022-03-31  -2.349206   508679  ...  2022-04-27  000001  平安银行
8   2022-02-28  -4.429612   506734  ...  2022-03-10  000001  平安银行
9   2021-12-31  -8.087005   502716  ...  2022-03-10  000001  平安银行
10  2021-09-30 -20.733864   390490  ...  2021-10-21  000001  平安银行
11  2021-06-30   3.579634   296828  ...  2021-08-20  000001  平安银行
12  2021-03-31  -4.677350   331829  ...  2021-04-21  000001  平安银行
13  2021-01-31  19.389866   290750  ...  2021-02-02  000001  平安银行
14  2020-12-31  27.488464   308724  ...  2021-02-02  000001  平安银行
15  2020-09-30  18.515625   351374  ...  2020-10-22  000001  平安银行
16  2020-06-30   1.721531   431036  ...  2020-08-28  000001  平安银行
17  2020-03-31 -17.631918   397399  ...  2020-04-21  000001  平安银行
18  2020-01-31  -5.531915   340920  ...  2020-02-14  000001  平安银行
19  2019-12-31   5.516357   322864  ...  2020-02-14  000001  平安银行
20  2019-09-30  13.134978   299958  ...  2019-10-22  000001  平安银行
21  2019-06-30   8.620562   321929  ...  2019-08-08  000001  平安银行
22  2019-03-31   3.721683   354508  ...  2019-04-24  000001  平安银行
23  2019-02-28  31.769723   369119  ...  2019-03-07  000001  平安银行
24  2018-12-31 -15.113122   429409  ...  2019-03-07  000001  平安银行
25  2018-09-30  23.531940   406242  ...  2018-10-24  000001  平安银行
26  2018-06-30 -16.605505   435978  ...  2018-08-16  000001  平安银行
27  2018-03-31  -9.543568   421677  ...  2018-04-20  000001  平安银行
28  2018-02-28  -9.398496   392992  ...  2018-03-15  000001  平安银行
29  2017-12-31  19.711971   343994  ...  2018-03-15  000001  平安银行
30  2017-09-30  20.068588   331474  ...  2017-10-21  000001  平安银行
31  2017-06-30   2.399128   379179  ...  2017-08-11  000001  平安银行
32  2017-03-31  -3.270042   371177  ...  2017-04-22  000001  平安银行
33  2017-02-28   4.175824   349253  ...  2017-03-17  000001  平安银行
34  2016-12-31   0.330761   350142  ...  2017-03-17  000001  平安银行
35  2016-09-30   4.252874   340324  ...  2016-10-21  000001  平安银行
36  2016-06-30  -0.391340   340528  ...  2016-08-12  000001  平安银行
37  2016-03-31  11.297071   341525  ...  2016-04-21  000001  平安银行
38  2016-02-29 -20.266889   347147  ...  2016-03-10  000001  平安银行
39  2015-12-31  14.299333   332918  ...  2016-03-10  000001  平安银行
40  2015-09-30 -27.854195   358049  ...  2015-10-23  000001  平安银行
41  2015-06-30  11.728949   418294  ...  2015-08-14  000001  平安银行
42  2015-03-31  17.187500   313029  ...  2015-04-24  000001  平安银行
43  2015-03-06 -15.151515   335403  ...  2015-03-13  000001  平安银行
44  2014-12-31  56.213018   275838  ...  2015-03-13  000001  平安银行
45  2014-09-30   2.320888   311571  ...  2014-10-24  000001  平安银行
46  2014-06-30  11.976813   298305  ...  2014-08-14  000001  平安银行
47  2014-03-31  -3.234501   319109  ...  2014-04-24  000001  平安银行
48  2014-02-28  -9.142857   310335  ...  2014-03-07  000001  平安银行
49  2013-12-31   3.114478   298070  ...  2014-03-07  000001  平安银行
50  2013-09-30  19.157472   291054  ...  2013-10-23  000001  平安银行
51  2013-06-30 -20.017323   281819  ...  2013-08-23  000001  平安银行
52  2013-03-31 -12.749350   256985  ...  2013-04-24  000001  平安银行
53  2013-03-01  43.945069   233517  ...  2013-03-08  000001  平安银行
[54 rows x 15 columns]
```

#### 分红配股

接口: stock_history_dividend_detail

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/300670.phtml>

描述: 新浪财经-发行与分配-分红配股

限量: 单次获取指定股票的新浪财经-发行与分配-分红配股详情

输入参数

| 名称        | 类型  | 描述                                               |
|-----------|-----|--------------------------------------------------|
| symbol    | str | symbol="600012"; 股票代码                            |
| indicator | str | indicator="配股"; choice of {"分红", "配股"}           |
| date      | str | date="1994-12-24"; 分红配股的具体日期, e.g., "1994-12-24" |

输出参数-分红历史

| 名称    | 类型      | 描述          |
|-------|---------|-------------|
| 公告日期  | object  | -           |
| 送股    | int64   | 注意单位: 股     |
| 转增    | int64   | 注意单位: 股     |
| 派息    | float64 | 注意单位: 元; 税前 |
| 进度    | object  | -           |
| 除权除息日 | object  | -           |
| 股权登记日 | object  | -           |
| 红股上市日 | object  | -           |

接口示例-分红历史

```python
import akshare as ak

stock_history_dividend_detail_df = ak.stock_history_dividend_detail(symbol="600012", indicator="分红")
print(stock_history_dividend_detail_df)
```

数据示例-分红历史

```
     公告日期  送股  转增   派息  进度  除权除息日   股权登记日 红股上市日
0   2021-07-14   0   0  2.3  实施  2021-07-21  2021-07-20   NaT
1   2020-07-14   0   0  2.3  实施  2020-07-22  2020-07-21   NaT
2   2019-07-08   0   0  2.5  实施  2019-07-16  2019-07-15   NaT
3   2018-07-09   0   0  2.3  实施  2018-07-17  2018-07-16   NaT
4   2017-07-10   0   0  2.3  实施  2017-07-18  2017-07-17   NaT
5   2016-07-12   0   0  2.3  实施  2016-07-19  2016-07-18   NaT
6   2015-07-13   0   0  2.3  实施  2015-07-20  2015-07-17   NaT
7   2014-07-07   0   0  2.2  实施  2014-07-11  2014-07-10   NaT
8   2013-06-18   0   0  2.0  实施  2013-06-24  2013-06-21   NaT
9   2012-07-10   0   0  2.1  实施  2012-07-16  2012-07-13   NaT
10  2011-06-08   0   0  2.1  实施  2011-06-14  2011-06-13   NaT
11  2010-06-10   0   0  2.0  实施  2010-06-21  2010-06-18   NaT
12  2009-05-25   0   0  2.3  实施  2009-06-02  2009-06-01   NaT
13  2008-06-18   0   0  2.0  实施  2008-06-25  2008-06-24   NaT
14  2007-06-20   0   0  2.5  实施  2007-06-26  2007-06-25   NaT
15  2006-07-12   0   0  2.8  实施  2006-07-18  2006-07-17   NaT
16  2005-07-11   0   0  1.0  实施  2005-07-15  2005-07-14   NaT
17  2004-06-14   0   0  0.6  实施  2004-06-18  2004-06-17   NaT
18  2003-07-07   0   0  0.3  实施  2003-07-11  2003-07-10   NaT
```

输出参数-分红详情

| 名称    | 类型     | 描述   |
|-------|--------|------|
| item  | object | 所列项目 |
| value | object | 项目值  |

接口示例-分红详情

```python
import akshare as ak

stock_history_dividend_detail_df = ak.stock_history_dividend_detail(symbol="600012", indicator="分红",
                                                                    date="2019-07-08")
print(stock_history_dividend_detail_df)
```

数据示例-分红详情

```
                 item             value
0          税前红利（报价币种）        2.50
1          税后红利（报价币种）        2.50
2       B、H股税前红利（人民币）          --
3       B、H股税后红利（人民币）          --
4           送股比例（10送）          --
5          转增比例（10转增）          --
6     盈余公积金转增比例（10转增）          --
7     资本公积金转增比例（10转增）          --
8                发放对象          --
9               股本基准日  2018-12-31
10              最后交易日          --
11                登记日  2019-07-15
12                除息日  2019-07-16
13  红利/配股起始日（送、转股到账日）  2019-07-16
14           红利/配股终止日          --
15                上市日          --
16         股东大会决议公告日期  2019-05-18
17       可转债享受权益转股截止日          --
18          配股比例（10配）          --
19                配股价          --
20               转配比例          --
21                转配价          --
22              配股有效期          --
23              实际配股数          --
24             配股前总股本          --
25             实际配股比例          --
26              每股拆细数          --
27             外币折算汇率          --
28               权息说明          --
```

输出参数-配股历史

| 名称     | 类型      | 描述             |
|--------|---------|----------------|
| 公告日期   | object  | -              |
| 配股方案   | float64 | 注意单位: 每10股配股股数 |
| 配股价格   | float64 | 注意单位: 元        |
| 基准股本   | int64   | 注意单位: 股        |
| 除权日    | object  | -              |
| 股权登记日  | object  | -              |
| 缴款起始日  | object  | -              |
| 缴款终止日  | object  | -              |
| 配股上市日  | object  | -              |
| 募集资金合计 | float64 | 注意单位: 元        |

接口示例-配股历史

```python
import akshare as ak

stock_history_dividend_detail_df = ak.stock_history_dividend_detail(symbol="000002", indicator="配股")
print(stock_history_dividend_detail_df)
```

数据示例-配股历史

```
   公告日期   配股方案  配股价格  ... 缴款终止日    配股上市日 募集资金合计
0  1999-12-22  2.727   7.5  ...  2000-01-24  2000-02-16    NaN
1  1997-06-26  2.370   4.5  ...  1997-07-29  1997-08-22    NaN
2  1900-01-01  5.000   4.4  ...  1991-06-08  1900-01-01    NaN
```

输出参数-配股详情

| 名称    | 类型     | 描述   |
|-------|--------|------|
| item  | object | 所列项目 |
| value | object | 项目值  |

接口示例-配股详情

```python
import akshare as ak

stock_history_dividend_detail_df = ak.stock_history_dividend_detail(indicator="配股", symbol="000002",
                                                                    date="1999-12-22")
print(stock_history_dividend_detail_df)
```

数据示例-配股详情

```
                 item         value
0          税前红利（报价币种）            --
1          税后红利（报价币种）            --
2       B、H股税前红利（人民币）            --
3       B、H股税后红利（人民币）            --
4           送股比例（10送）            --
5          转增比例（10转增）            --
6     盈余公积金转增比例（10转增）            --
7     资本公积金转增比例（10转增）            --
8                发放对象            --
9               股本基准日            --
10              最后交易日            --
11                登记日    2000-01-07
12                除息日    2000-01-10
13  红利/配股起始日（送、转股到账日）    2000-01-11
14           红利/配股终止日    2000-01-24
15                上市日    2000-02-16
16         股东大会决议公告日期            --
17       可转债享受权益转股截止日            --
18          配股比例（10配）          2.73
19                配股价          7.50
20               转配比例            --
21                转配价            --
22              配股有效期            --
23              实际配股数   85434500.00
24             配股前总股本  545537000.00
25             实际配股比例          1.57
26              每股拆细数            --
27             外币折算汇率            --
28               权息说明            --
```

#### 历史分红

接口: stock_dividend_cninfo

目标地址: <http://webapi.cninfo.com.cn/#/company?companyid=600009>

描述: 巨潮资讯-个股-历史分红

限量: 单次获取指定股票的历史分红数据

输入参数

| 名称     | 类型  | 描述              |
|--------|-----|-----------------|
| symbol | str | symbol="600009" |

输出参数

| 名称       | 类型      | 描述           |
|----------|---------|--------------|
| 实施方案公告日期 | object  | -            |
| 送股比例     | float64 | 注意单位: 每 10 股 |
| 转增比例     | float64 | 注意单位: 每 10 股 |
| 派息比例     | float64 | 注意单位: 每 10 股 |
| 股权登记日    | object  | -            |
| 除权日      | object  | -            |
| 派息日      | object  | -            |
| 股份到账日    | object  | -            |
| 实施方案分红说明 | object  | -            |
| 分红类型     | object  | -            |
| 报告时间     | object  | -            |

接口示例

```python
import akshare as ak

stock_dividend_cninfo_df = ak.stock_dividend_cninfo(symbol="600009")
print(stock_dividend_cninfo_df)
```

数据示例

```
      实施方案公告日期  分红类型  送股比例  转增比例  ...  派息日 股份到账日 实施方案分红说明 报告时间
0   1998-11-28  中期分红   5.0   0.0  ...         NaT  None          10转增5股  1998半年报
1   2001-06-23  年度分红   NaN   NaN  ...  2001-07-06  None    10派2.93元(含税)   2000年报
2   2002-07-18  年度分红   NaN   NaN  ...  2002-08-01  None     10派1.5元(含税)   2001年报
3   2003-08-05  年度分红   NaN   NaN  ...  2003-08-14  None   10股派1.99元（含税）   2002年报
4   2003-12-22  中期分红   NaN   3.0  ...         NaT  None           10送3股  2003半年报
5   2004-07-16  年度分红   NaN   NaN  ...  2004-07-28  None    10派0.96元（含税）   2003年报
6   2005-05-17  年度分红   NaN   NaN  ...  2005-05-27  None       10派1元(含税)   2004年报
7   2006-08-15  年度分红   NaN   NaN  ...  2006-08-25  None     10派1.5元(含税)   2005年报
8   2006-12-01  中期分红   NaN   NaN  ...  2006-12-13  None       10派1元（含税）  2006半年报
9   2007-08-16  年度分红   NaN   NaN  ...  2007-08-28  None     10派1.5元（含税）   2006年报
10  2008-07-24  年度分红   NaN   NaN  ...  2008-08-05  None       10派1元（含税）   2007年报
11  2009-07-30  年度分红   NaN   NaN  ...  2009-08-11  None     10派0.5元（含税）   2008年报
12  2010-07-29  年度分红   NaN   NaN  ...  2010-08-10  None     10派0.5元（含税）   2009年报
13  2011-08-08  年度分红   NaN   NaN  ...  2011-08-18  None       10派1元(含税)   2010年报
14  2012-08-07  年度分红   NaN   NaN  ...  2012-08-17  None       10派6元(含税)   2011年报
15  2013-08-12  年度分红   NaN   NaN  ...  2013-08-22  None     10派3.7元(含税)   2012年报
16  2014-08-11  年度分红   NaN   NaN  ...  2014-08-15  None       10派3元(含税)   2013年报
17  2015-08-14  年度分红   NaN   NaN  ...  2015-08-20  None     10派3.5元(含税)   2014年报
18  2016-08-12  年度分红   NaN   NaN  ...  2016-08-18  None     10派4.3元(含税)   2015年报
19  2017-08-18  年度分红   NaN   NaN  ...  2017-08-24  None     10派4.4元(含税)   2016年报
20  2018-08-17  年度分红   NaN   NaN  ...  2018-08-23  None     10派5.8元(含税)   2017年报
21  2019-08-16  年度分红   NaN   NaN  ...  2019-08-22  None     10派6.6元(含税)   2018年报
22  2020-08-14  年度分红   NaN   NaN  ...  2020-08-20  None     10派7.9元(含税)   2019年报
23  2024-07-15  年度分红   NaN   NaN  ...  2024-07-19  None     10派1.2元(含税)   2023年报
24  2024-09-03  中期分红   NaN   NaN  ...  2024-09-09  None  10派1.0034元(含税)  2024半年报
[25 rows x 11 columns]
```

#### 新股发行

接口: stock_ipo_info

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_NewStock/stockid/600004.phtml>

描述: 新浪财经-发行与分配-新股发行

限量: 单次获取新股发行的基本信息数据

输入参数

| 名称    | 类型  | 描述                   |
|-------|-----|----------------------|
| stock | str | stock="600004"; 股票代码 |

输出参数

| 名称    | 类型     | 描述   |
|-------|--------|------|
| item  | object | 所列项目 |
| value | object | 项目值  |

接口示例

```python
import akshare as ak

stock_ipo_info_df = ak.stock_ipo_info(stock="600004")
print(stock_ipo_info_df)
```

数据示例

```
              item       value
0              上市地     上海证券交易所
1             主承销商  中国国际金融有限公司
2             承销方式        余额包销
3            上市推荐人  中国国际金融有限公司
4         每股发行价(元)        5.88
5             发行方式    二级市场定价配售
6   发行市盈率（按发行后总股本）          --
7       首发前总股本（万股）    60000.00
8       首发后总股本（万股）   100000.00
9        实际发行量（万股）    40000.00
10      预计募集资金（万元）   235200.00
11    实际募集资金合计（万元）   235200.00
12      发行费用总额（万元）     6936.40
13      募集资金净额（万元）   228263.60
14        承销费用（万元）          --
15           招股公告日  2003-04-09
16            上市日期  2003-04-28
```

#### 股票增发

接口: stock_add_stock

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_AddStock/stockid/600004.phtml>

描述: 新浪财经-发行与分配-增发

限量: 单次指定 symbol 的股票增发详情数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="600004"; 股票代码 |

输出参数

| 名称         | 类型     | 描述 |
|------------|--------|----|
| 公告日期       | object | -  |
| 发行方式       | object | -  |
| 发行价格       | object | -  |
| 实际公司募集资金总额 | object | -  |
| 发行费用总额     | object | -  |
| 实际发行数量     | object | -  |

接口示例

```python
import akshare as ak

stock_add_stock_df = ak.stock_add_stock(symbol="600004")
print(stock_add_stock_df)
```

数据示例

```
    公告日期    发行方式  发行价格  实际公司募集资金总额  发行费用总额      实际发行数量
0  2020-11-06    定向配售  10.76元  320,000.00万元  1,253.53万元  29739.7769万股
1  2007-12-29  网下定价发行  15.05元   22,575.00万元  1,887.00万元        1500万股
2  2007-12-18    定向配售   7.09元         0.00元       0.00元       13500万股
```

#### 限售解禁

##### 个股限售解禁-新浪

接口: stock_restricted_release_queue_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/xsjj/index.phtml?symbol=sh600000>

描述: 新浪财经-发行分配-限售解禁

限量: 单次获取指定 symbol 的限售解禁数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="600000"; 股票代码 |

输出参数

| 名称      | 类型      | 描述       |
|---------|---------|----------|
| 代码      | object  | -        |
| 名称      | object  | -        |
| 解禁日期    | object  | -        |
| 解禁数量    | float64 | 注意单位: 万股 |
| 解禁股流通市值 | float64 | 注意单位: 亿元 |
| 上市批次    | int64   | -        |
| 公告日期    | object  | -        |

接口示例

```python
import akshare as ak

stock_restricted_release_queue_sina_df = ak.stock_restricted_release_queue_sina(symbol="600000")
print(stock_restricted_release_queue_sina_df)
```

数据示例

```
    代码    名称        解禁日期       解禁数量   解禁股流通市值  上市批次        公告日期
0  600000  浦发银行  2020-09-04  124831.65  127.0786    10  2017-09-06
1  600000  浦发银行  2017-03-20  109946.14  179.1023     9  2016-03-22
2  600000  浦发银行  2015-10-14  373069.43  599.1495     8  2010-10-16
3  600000  浦发银行  2010-09-29  117540.69  151.9801     7  2009-09-30
4  600000  浦发银行  2009-05-12   64917.32  161.1248     6  2006-05-09
5  600000  浦发银行  2008-05-12   41247.84  120.7737     5  2008-05-07
6  600000  浦发银行  2007-11-30   27761.94  144.0567     4  2006-11-21
7  600000  浦发银行  2007-05-14  192834.49  564.2337     3  2007-05-09
```

##### 限售股解禁

接口: stock_restricted_release_summary_em

目标地址: <https://data.eastmoney.com/dxf/marketStatistics.html?type=day&startdate=2022-11-08&enddate=2022-12-19>

描述: 东方财富网-数据中心-特色数据-限售股解禁

限量: 单次获取指定 symbol 在近期限售股解禁数据

输入参数

| 名称         | 类型  | 描述                                                                      |
|------------|-----|-------------------------------------------------------------------------|
| symbol     | str | symbol="全部股票"; choice of {"全部股票", "沪市A股", "科创板", "深市A股", "创业板", "京市A股"} |
| start_date | str | start_date="20221101"                                                   |
| end_date   | str | end_date="20221209"                                                     |

输出参数

| 名称         | 类型      | 描述      |
|------------|---------|---------|
| 序号         | int64   | -       |
| 解禁时间       | object  | -       |
| 当日解禁股票家数   | int64   | -       |
| 解禁数量       | float64 | 注意单位: 股 |
| 实际解禁数量     | float64 | 注意单位: 股 |
| 实际解禁市值     | int64   | 注意单位: 元 |
| 沪深300指数    | float64 | -       |
| 沪深300指数涨跌幅 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_restricted_release_summary_em_df = ak.stock_restricted_release_summary_em(symbol="全部股票", start_date="20221108", end_date="20221209")
print(stock_restricted_release_summary_em_df)
```

数据示例

```
    序号        解禁时间  当日解禁股票家数  ...        实际解禁市值    沪深300指数  沪深300指数涨跌幅
0    1  2022-11-08        15  ...  1.172407e+10  3749.3251     -0.6879
1    2  2022-11-09        10  ...  2.572546e+09  3714.2704     -0.9350
2    3  2022-11-10        15  ...  9.329462e+09  3685.6885     -0.7695
3    4  2022-11-11        17  ...  4.912280e+09  3788.4387      2.7878
4    5  2022-11-14        15  ...  2.318019e+10  3794.0171      0.1472
5    6  2022-11-15        14  ...  1.714207e+10  3865.9726      1.8966
6    7  2022-11-16        12  ...  1.209874e+10  3834.3899     -0.8169
7    8  2022-11-17        11  ...  4.802956e+09  3818.6640     -0.4101
8    9  2022-11-18        22  ...  8.274363e+10  3801.5686     -0.4477
9   10  2022-11-21        20  ...  1.283129e+10  3769.1269     -0.8534
10  11  2022-11-22         9  ...  9.232523e+09  3769.5727      0.0118
11  12  2022-11-23         7  ...  3.737618e+08  3773.5287      0.1049
12  13  2022-11-24         7  ...  4.706748e+09  3756.8082     -0.4431
13  14  2022-11-25        11  ...  2.465310e+09  3775.7764      0.5049
14  15  2022-11-28        17  ...  4.328994e+10  3733.2424     -1.1265
15  16  2022-11-29        13  ...  7.017021e+10  3848.4224      3.0853
16  17  2022-11-30        11  ...  1.060871e+10  3853.0365      0.1199
17  18  2022-12-01        15  ...  3.325098e+09  3894.7687      1.0831
18  19  2022-12-02        15  ...  4.087764e+09  3870.9478     -0.6116
19  20  2022-12-05        35  ...  1.952387e+10        NaN         NaN
20  21  2022-12-06        19  ...  1.600255e+10        NaN         NaN
21  22  2022-12-07        14  ...  2.661094e+09        NaN         NaN
22  23  2022-12-08        10  ...  2.100872e+09        NaN         NaN
23  24  2022-12-09         8  ...  1.630020e+10        NaN         NaN
```

##### 限售股解禁详情

接口: stock_restricted_release_detail_em

目标地址: <https://data.eastmoney.com/dxf/detail.html>

描述: 东方财富网-数据中心-限售股解禁-解禁详情一览

限量: 单次获取指定时间段限售股解禁数据

输入参数

| 名称         | 类型  | 描述                                                                      |
|------------|-----|-------------------------------------------------------------------------|
| start_date | str | start_date="20221202"                                                   |
| end_date   | str | end_date="20241202"                                                     |

输出参数

| 名称         | 类型      | 描述      |
|------------|---------|---------|
| 序号         | int64   | -       |
| 股票代码       | object  | -       |
| 股票简称       | object  | -       |
| 解禁时间       | object  | -       |
| 限售股类型      | object  | 注意单位: 股 |
| 解禁数量       | float64 | 注意单位: 股 |
| 实际解禁数量     | float64 | 注意单位: 股 |
| 实际解禁市值     | float64 | 注意单位: 元 |
| 占解禁前流通市值比例 | float64 | -       |
| 解禁前一交易日收盘价 | float64 | -       |
| 解禁前20日涨跌幅  | float64 | 注意单位: % |
| 解禁后20日涨跌幅  | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_restricted_release_detail_em_df = ak.stock_restricted_release_detail_em(start_date="20221202", end_date="20221204")
print(stock_restricted_release_detail_em_df)
```

数据示例

```
    序号    股票代码  股票简称        解禁时间  ... 占解禁前流通市值比例  解禁前一交易日收盘价  解禁前20日涨跌幅  解禁后20日涨跌幅
0    1  002548   金新农  2022-12-02  ...   0.000292        5.98   3.866432       1.18
1    2  873527   夜光明  2022-12-02  ...   0.006829        9.02  -2.162162      -0.33
2    3  603127  昭衍新药  2022-12-02  ...   0.000445       58.30  -6.029040      -2.08
3    4  002511  中顺洁柔  2022-12-02  ...   0.000604       11.97  17.993795       4.91
4    5  688557  兰剑智能  2022-12-02  ...   0.020572       38.04  -4.086845       1.30
5    6  603283  赛腾股份  2022-12-02  ...   0.007451       35.55  -2.860892      -3.94
6    7  688007  光峰科技  2022-12-02  ...   0.003214       26.28   7.978723      -0.42
7    8  688578   艾力斯  2022-12-02  ...   0.013058       20.80  -9.883470      -0.38
8    9  300227   光韵达  2022-12-02  ...   0.021127        6.89  -5.793103       0.88
9   10  300525  博思软件  2022-12-02  ...   0.017589       19.87  -4.481132      -1.88
10  11  831641   格利尔  2022-12-02  ...   0.422407       12.65        NaN      31.77
11  12  688489  三未信安  2022-12-02  ...   1.000000      119.50        NaN        NaN
12  13  301198  喜悦智行  2022-12-02  ...   0.457230       18.83   1.796407       0.70
13  14  600848  上海临港  2022-12-02  ...   0.015465       12.64   6.260575       0.64
14  15  000415  渤海租赁  2022-12-02  ...   0.061934        2.29   4.954955      -1.72
```

##### 解禁批次

接口: stock_restricted_release_queue_em

目标地址: <https://data.eastmoney.com/dxf/q/600000.html>

描述: 东方财富网-数据中心-个股限售解禁-解禁批次

限量: 单次获取指定 symbol 的解禁批次数据

输入参数

| 名称     | 类型  | 描述              |
|--------|-----|-----------------|
| symbol | str | symbol="600000" |

输出参数

| 名称         | 类型      | 描述      |
|------------|---------|---------|
| 序号         | int64   | -       |
| 解禁时间       | object  | -       |
| 解禁股东数      | int64   | -       |
| 解禁数量       | float64 | 注意单位: 股 |
| 实际解禁数量     | float64 | 注意单位: 股 |
| 未解禁数量      | int64   | 注意单位: 股 |
| 实际解禁数量市值   | float64 | 注意单位: 元 |
| 占总市值比例     | float64 | -       |
| 占流通市值比例    | float64 | -       |
| 解禁前一交易日收盘价 | float64 | 注意单位: 元 |
| 限售股类型      | object  | -       |
| 解禁前20日涨跌幅  | float64 | 注意单位: % |
| 解禁后20日涨跌幅  | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_restricted_release_queue_em_df = ak.stock_restricted_release_queue_em(symbol="600000")
print(stock_restricted_release_queue_em_df)
```

数据示例

```
   序号   解禁时间  解禁股东数  ...   限售股类型  解禁前20日涨跌幅  解禁后20日涨跌幅
0   1  2020-09-04      2  ...  定向增发机构配售股份  -3.893637  -6.916996
1   2  2017-03-20     11  ...  定向增发机构配售股份  -2.644231  -5.555556
2   3  2015-10-14      1  ...  定向增发机构配售股份   6.042497  12.085160
3   4  2010-09-29     38  ...  定向增发机构配售股份 -10.334996  15.262321
[4 rows x 13 columns]
```

##### 解禁股东

接口: stock_restricted_release_stockholder_em

目标地址: <https://data.eastmoney.com/dxf/q/600000.html>

描述: 东方财富网-数据中心-个股限售解禁-解禁股东

限量: 单次获取指定 symbol 的解禁批次数据

输入参数

| 名称     | 类型  | 描述                                                                           |
|--------|-----|------------------------------------------------------------------------------|
| symbol | str | symbol="600000"                                                              |
| date   | str | date="20200904"; 通过 ak.stock_restricted_release_queue_em(symbol="600000") 获取 |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 序号      | int64   | -       |
| 股东名称    | object  | -       |
| 解禁数量    | int64   | 注意单位: 股 |
| 实际解禁数量  | int64   | 注意单位: 股 |
| 解禁市值    | float64 | 注意单位: 元 |
| 锁定期     | int64   | 注意单位: 月 |
| 剩余未解禁数量 | int64   | 注意单位: 股 |
| 限售股类型   | object  | -       |
| 进度      | object  | -       |

接口示例

```python
import akshare as ak

stock_restricted_release_stockholder_em_df = ak.stock_restricted_release_stockholder_em(symbol="600000", date="20200904")
print(stock_restricted_release_stockholder_em_df)
```

数据示例

```
   序号          股东名称       解禁数量     实际解禁数量  ...  锁定期  剩余未解禁数量       限售股类型  进度
0   1    上海国际集团有限公司  842003367  842003367  ...   36        0  定向增发机构配售股份  实施
1   2  上海国鑫投资发展有限公司  406313131  406313131  ...   36        0  定向增发机构配售股份  实施
```

#### 流通股东

接口: stock_circulate_stock_holder

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CirculateStockHolder/stockid/600000.phtml>

描述: 新浪财经-股东股本-流通股东

限量: 单次获取指定 symbol 的流通股东数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="600000"; 股票代码 |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 截止日期   | object  | -       |
| 公告日期   | object  | -       |
| 编号     | int64   | -       |
| 股东名称   | object  | -       |
| 持股数量   | int64   | 注意单位: 股 |
| 占流通股比例 | float64 | 注意单位: % |
| 股本性质   | object  | -       |

接口示例

```python
import akshare as ak

stock_circulate_stock_holder_df = ak.stock_circulate_stock_holder(symbol="600000")
print(stock_circulate_stock_holder_df)
```

数据示例

```
      截止日期        公告日期  编号                股东名称        持股数量  占流通股比例   股本性质
0    2022-09-30  2022-10-29   1          上海国际集团有限公司  6331322671  21.570    国有股
1    2022-09-30  2022-10-29   2      中国移动通信集团广东有限公司  5334892824  18.175    国有股
2    2022-09-30  2022-10-29   3   富德生命人寿保险股份有限公司-传统  2779437274   9.469  境内法人股
3    2022-09-30  2022-10-29   4  富德生命人寿保险股份有限公司-资本金  1763232325   6.007  境内法人股
4    2022-09-30  2022-10-29   5       上海上国投资产管理有限公司  1395571025   4.755    国有股
..          ...         ...  ..                 ...         ...     ...    ...
745  2003-12-31         NaN   6          世纪证券有限责任公司     6882195   0.765    国有股
746  2003-12-31         NaN   7            汉兴证券投资基金     5921727   0.658  境内法人股
747  2003-12-31         NaN   8            泰和证券投资基金     4534267   0.504  境内法人股
748  2003-12-31         NaN   9          博时裕富证券投资基金     4197332   0.466  境内法人股
749  2003-12-31         NaN  10            同智证券投资基金     3880427   0.431  境内法人股
```

#### 板块行情

接口: stock_sector_spot

目标地址: <http://finance.sina.com.cn/stock/sl/>

描述: 新浪行业-板块行情

限量: 单次获取指定的板块行情实时数据

输入参数

| 名称        | 类型  | 描述                                                              |
|-----------|-----|-----------------------------------------------------------------|
| indicator | str | indicator="新浪行业"; choice of {"新浪行业", "启明星行业", "概念", "地域", "行业"} |

输出参数

| 名称     | 类型      | 描述       |
|--------|---------|----------|
| label  | object  | -        |
| 板块     | object  | -        |
| 公司家数   | int64   | -        |
| 平均价格   | float64 | -        |
| 涨跌额    | float64 | -        |
| 涨跌幅    | float64 | 注意单位: %  |
| 总成交量   | int64   | 注意单位: 手  |
| 总成交额   | int64   | 注意单位: 万元 |
| 股票代码   | object  | -        |
| 个股-涨跌幅 | float64 | 注意单位: %  |
| 个股-当前价 | float64 | -        |
| 个股-涨跌额 | float64 | -        |
| 股票名称   | object  | -        |

接口示例

```python
import akshare as ak

stock_industry_sina_df = ak.stock_sector_spot(indicator="新浪行业")
print(stock_industry_sina_df)
```

数据示例

```
        label    板块  公司家数        平均价格  ...  个股-涨跌幅  个股-当前价  个股-涨跌额   股票名称
0    new_blhy  玻璃行业    19   15.913158  ...   4.214   21.27    0.86   金刚玻璃
1    new_cbzz  船舶制造     8   10.561250  ...   5.374   22.55    1.15   中国船舶
2    new_cmyl  传媒娱乐    40    6.491053  ...  13.826    3.54    0.43   华谊兄弟
3    new_dlhy  电力行业    62    7.798667  ...  10.011   20.66    1.88   文山电力
4    new_dqhy  电器行业    58   15.341897  ...   7.950    7.74    0.57   精达股份
5    new_dzqj  电子器件   152   22.652349  ...  20.055    8.74    1.46   珈伟新能
6    new_dzxx  电子信息   247   12.984641  ...  20.022   21.46    3.58    中青宝
7     new_fdc   房地产   123    7.213445  ...  10.189    2.92    0.27   铁岭新城
8    new_fdsb  发电设备    65   11.620000  ...   6.644   18.46    1.15    天融信
9    new_fjzz  飞机制造    14   24.420714  ...   6.079   62.82    3.60   中直股份
10   new_fzhy  纺织行业    42    5.945750  ...   7.362    5.25    0.36   凤竹纺织
11   new_fzjx  纺织机械     8   10.077500  ...   5.704   19.83    1.07   三联虹普
12   new_fzxl  服装鞋类    49    9.784375  ...  10.066    6.67    0.61    乔治白
13   new_glql  公路桥梁    20    4.771667  ...   2.979    2.42    0.07   吉林高速
14   new_gsgq  供水供气    25    6.512000  ...   4.945    3.82    0.18   辽宁能源
15   new_gthy  钢铁行业    60    8.681455  ...  10.036   15.24    1.39   海南矿业
16   new_hbhy  环保行业    27    7.172308  ...  20.023   10.61    1.77   天壕环境
17   new_hghy  化工行业   150   17.143537  ...  11.946   10.87    1.16   海达股份
18   new_hqhy  化纤行业    26    9.303846  ...  10.027    4.06    0.37   吉林化纤
19   new_jdhy  家电行业    37   13.049118  ...   6.127   53.00    3.06  苏 泊 尔
20   new_jdly  酒店旅游    35   16.324571  ...   6.809    2.51    0.16  *ST腾邦
21   new_jjhy  家具行业    16   14.207333  ...   3.830    4.88    0.18   海鸥住工
22   new_jrhy  金融行业    51   12.387200  ...   4.566   25.88    1.13   中信证券
23   new_jtys  交通运输    87    7.466835  ...   6.642    8.51    0.53   中国国航
24   new_jxhy  机械行业   211   12.314412  ...  10.012    9.56    0.87   宁波精达
25   new_jzjc  建筑建材    91    6.915568  ...   7.900   12.02    0.88   四川路桥
26    new_kfq   开发区    10    9.127000  ...   3.902   13.58    0.51   中国国贸
27   new_ljhy  酿酒行业    33  124.060303  ...  10.002  150.45   13.68   重庆啤酒
28    new_mtc   摩托车     6    9.040000  ...   5.878   13.87    0.77   钱江摩托
29   new_mthy  煤炭行业    41    8.143171  ...   5.121    3.90    0.19   ST安泰
30   new_nlmy  农林牧渔    64   11.500161  ...   7.095   14.49    0.96   盈康生命
31   new_nyhf  农药化肥    46   15.010000  ...   8.333   35.36    2.72   广信股份
32   new_qczz  汽车制造   103   17.203465  ...   9.967    9.93    0.90   天润工业
33   new_qtxy  其它行业   202   12.054028  ...  14.844    4.41    0.57    汤姆猫
34   new_slzp  塑料制品    33   12.096061  ...   5.975    6.74    0.38   浙江众成
35   new_snhy  水泥行业    26   10.774800  ...   5.584    8.13    0.43   博闻科技
36   new_sphy  食品行业    58   16.108214  ...  10.031   10.64    0.97   中粮科技
37  new_stock   次新股    76   41.233443  ...  10.015   35.92    3.27   青岛食品
38   new_swzz  生物制药   155   20.037059  ...  10.131    3.37    0.31   交大昂立
39   new_sybh  商业百货    93   10.116111  ...  10.023   23.82    2.17   天音控股
40   new_syhy  石油行业    24    6.421739  ...   7.438    5.20    0.36   泰山石油
41   new_tchy  陶瓷行业     8    9.295714  ...   5.040    3.96    0.19   ST冠福
42   new_wzwm  物资外贸    21    8.492000  ...  10.025   13.17    1.20   江苏国泰
43   new_ylqx  医疗器械    31   27.988333  ...   6.168  170.40    9.90   泰格医药
44   new_yqyb  仪器仪表    48   15.053125  ...   5.106    2.47    0.12   ST安控
45   new_ysbz  印刷包装    20    5.662000  ...   6.150    7.94    0.46   万顺新材
46   new_ysjs  有色金属    72   15.427206  ...   9.871   41.74    3.75   钢研高纳
47   new_zhhy  综合行业    33    6.043929  ...   6.833    6.41    0.41   合金投资
48   new_zzhy  造纸行业    24    6.515652  ...   6.367   17.04    1.02   中顺洁柔
```

#### 板块详情

接口: stock_sector_detail

目标地址: <http://finance.sina.com.cn/stock/sl/#area_1>

描述: 新浪行业-板块行情-成份详情, 由于新浪网页提供的统计数据有误, 部分行业数量大于统计数

限量: 单次获取指定的新浪行业-板块行情-成份详情

输入参数

| 名称     | 类型  | 描述                                                                        |
|--------|-----|---------------------------------------------------------------------------|
| sector | str | sector="hangye_ZL01"; 通过 **ak.stock_sector_spot** 返回数据的 label 字段选择 sector |

输出参数

| 名称            | 类型      | 描述  |
|---------------|---------|-----|
| symbol        | object  | -   |
| code          | object  | -   |
| name          | object  | -   |
| trade         | float64 | -   |
| pricechange   | float64 | -   |
| changepercent | float64 | -   |
| buy           | float64 | -   |
| sell          | float64 | -   |
| settlement    | float64 | -   |
| open          | float64 | -   |
| high          | float64 | -   |
| low           | float64 | -   |
| volume        | int64   | -   |
| amount        | int64   | -   |
| ticktime      | object  | -   |
| per           | float64 | -   |
| pb            | float64 | -   |
| mktcap        | float64 | -   |
| nmc           | float64 | -   |
| turnoverratio | float64 | -   |

接口示例

```python
import akshare as ak

stock_sector_detail_df = ak.stock_sector_detail(sector="hangye_ZL01")
print(stock_sector_detail_df)
```

数据示例

```
      symbol    code   name  ...        mktcap           nmc turnoverratio
0   sh600373  600373   中文传媒  ...  1.619301e+06  1.619301e+06       0.64600
1   sh600551  600551   时代出版  ...  3.616651e+05  3.616651e+05       0.22616
2   sh600633  600633   浙数文化  ...  1.249847e+06  1.249847e+06       1.06662
3   sh600757  600757   长江传媒  ...  6.310981e+05  6.310185e+05       0.26325
4   sh601098  601098   中南传媒  ...  1.925312e+06  1.925312e+06       0.23095
5   sh601801  601801   皖新传媒  ...  9.727211e+05  9.727211e+05       0.22932
6   sh601858  601858   中国科传  ...  7.280505e+05  7.280505e+05       0.59413
7   sh601900  601900   南方传媒  ...  8.206229e+05  8.147362e+05       0.31126
8   sh601928  601928   凤凰传媒  ...  1.702538e+06  1.702538e+06       0.11763
9   sh601999  601999   出版传媒  ...  3.261415e+05  3.261415e+05       0.60498
10  sh603999  603999   读者传媒  ...  3.317760e+05  3.317760e+05       0.61157
11  sz000504  000504  *ST生物  ...  2.246448e+05  2.239954e+05       0.83369
12  sz000719  000719   中原传媒  ...  6.855465e+05  4.469889e+05       0.32643
13  sz300148  300148   天舟文化  ...  2.999517e+05  2.770519e+05       4.02933
```

#### 股票列表-A股

接口: stock_info_a_code_name

目标地址: 沪深京三个交易所

描述: 沪深京 A 股股票代码和股票简称数据

限量: 单次获取所有 A 股股票代码和简称数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称   | 类型     | 描述  |
|------|--------|-----|
| code | object | -   |
| name | object | -   |

接口示例

```python
import akshare as ak

stock_info_a_code_name_df = ak.stock_info_a_code_name()
print(stock_info_a_code_name_df)
```

数据示例

```
        code   name
0     000001   平安银行
1     000002  万  科Ａ
2     000004   国华网安
3     000005   ST星源
4     000006   深振业Ａ
      ...    ...
4623  871396   常辅股份
4624  871553   凯腾精工
4625  871642   通易航天
4626  871981   晶赛科技
4627  872925   锦好医疗
```

#### 股票列表-上证

接口: stock_info_sh_name_code

目标地址: <https://www.sse.com.cn/assortment/stock/list/share/>

描述: 上海证券交易所股票代码和简称数据

限量: 单次获取所有上海证券交易所股票代码和简称数据

输入参数

| 名称     | 类型  | 描述                                               |
|--------|-----|--------------------------------------------------|
| symbol | str | symbol="主板A股"; choice of {"主板A股", "主板B股", "科创板"} |

输出参数

| 名称   | 类型     | 描述  |
|------|--------|-----|
| 证券代码 | object | -   |
| 证券简称 | object | -   |
| 公司全称 | object | -   |
| 上市日期 | object | -   |

接口示例

```python
import akshare as ak

stock_info_sh_name_code_df = ak.stock_info_sh_name_code(symbol="主板A股")
print(stock_info_sh_name_code_df)
```

数据示例

```
        证券代码  证券简称                公司全称        上市日期
0     600000  浦发银行      上海浦东发展银行股份有限公司  1999-11-10
1     600004  白云机场      广州白云国际机场股份有限公司  2003-04-28
2     600006  东风汽车          东风汽车股份有限公司  1999-07-27
3     600007  中国国贸      中国国际贸易中心股份有限公司  1999-03-12
4     600008  首创环保    北京首创生态环保集团股份有限公司  2000-04-27
      ...   ...                 ...         ...
1691  605580  恒盛能源          恒盛能源股份有限公司  2021-08-19
1692  605588  冠石科技        南京冠石科技股份有限公司  2021-08-12
1693  605589  圣泉集团        济南圣泉集团股份有限公司  2021-08-10
1694  605598  上海港湾  上海港湾基础建设(集团)股份有限公司  2021-09-17
1695  605599  菜百股份       北京菜市口百货股份有限公司  2021-09-09
[1696 rows x 4 columns]
```

#### 股票列表-深证

接口: stock_info_sz_name_code

目标地址: <https://www.szse.cn/market/product/stock/list/index.html>

描述: 深证证券交易所股票代码和股票简称数据

限量: 单次获取深证证券交易所股票代码和简称数据

输入参数

| 名称     | 类型  | 描述                                                          |
|--------|-----|-------------------------------------------------------------|
| symbol | str | symbol="A股列表"; choice of {"A股列表", "B股列表", "CDR列表", "AB股列表"} |

输出参数-A股列表

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 板块     | object | -   |
| A股代码   | object | -   |
| A股简称   | object | -   |
| A股上市日期 | object | -   |
| A股总股本  | object | -   |
| A股流通股本 | object | -   |
| 所属行业   | object | -   |

接口示例

```python
import akshare as ak

stock_info_sz_name_code_df = ak.stock_info_sz_name_code(symbol="A股列表")
print(stock_info_sz_name_code_df)
```

数据示例

```
       板块   A股代码  A股简称   A股上市日期     A股总股本        A股流通股本    所属行业
0      主板  000001   平安银行  1991-04-03  19,405,918,198  19,405,513,424   J 金融业
1      主板  000002  万  科Ａ  1991-01-29   9,724,196,533   9,716,935,865   K 房地产
2      主板  000004   国华网安  1990-12-01     132,380,282     126,288,093  I 信息技术
3      主板  000005   ST星源  1990-12-10   1,058,536,842   1,057,875,742  N 公共环保
4      主板  000006   深振业Ａ  1992-04-27   1,349,995,046   1,349,987,396   K 房地产
   ...     ...    ...         ...             ...             ...     ...
2838  创业板  301568    思泰克  2023-11-28     103,258,400      24,487,502   C 制造业
2839  创业板  301577   美信科技  2024-01-24      44,260,000      11,095,149   C 制造业
2840  创业板  301578   辰奕智能  2023-12-28      48,000,000      11,378,776   C 制造业
2841  创业板  301589   诺瓦星云  2024-02-08      51,360,000       7,702,090   C 制造业
2842  创业板  301591  C肯特股份  2024-02-28      84,120,000      19,943,633   C 制造业
[2843 rows x 7 columns]
```

#### 股票列表-北证

接口: stock_info_bj_name_code

目标地址: <https://www.bse.cn/nq/listedcompany.html>

描述: 北京证券交易所股票代码和简称数据

限量: 单次获取北京证券交易所所有的股票代码和简称数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称   | 类型     | 描述      |
|------|--------|---------|
| 证券代码 | object | -       |
| 证券简称 | object | -       |
| 总股本  | int64  | 注意单位: 股 |
| 流通股本 | int64  | 注意单位: 股 |
| 上市日期 | object | -       |
| 所属行业 | object | -       |
| 地区   | object | -       |
| 报告日期 | object | -       |

接口示例

```python
import akshare as ak

stock_info_bj_name_code_df = ak.stock_info_bj_name_code()
print(stock_info_bj_name_code_df)
```

数据示例

```
       证券代码  证券简称   总股本  ...              所属行业   地区        报告日期
0    430017  星昊医药  122577200  ...             医药制造业  北京市  2024-02-29
1    430047  诺思兰德  274873974  ...             医药制造业  北京市  2024-02-29
2    430090  同辉信息  199333546  ...        软件和信息技术服务业  北京市  2024-02-29
3    430139  华岭股份  266800000  ...  计算机、通信和其他电子设备制造业  上海市  2024-02-29
4    430198  微创光电  161363872  ...  计算机、通信和其他电子设备制造业  湖北省  2024-02-29
..      ...   ...        ...  ...               ...  ...         ...
239  873693   阿为特   72700000  ...             金属制品业  上海市  2024-02-29
240  873703  广厦环能   76900000  ...           专用设备制造业  北京市  2024-02-29
241  873726  卓兆点胶   82077246  ...           专用设备制造业  江苏省  2024-02-29
242  873806   云星宇  300736667  ...        软件和信息技术服务业  北京市  2024-02-29
243  873833  美心翼申   82360000  ...           通用设备制造业  重庆市  2024-02-29
[244 rows x 8 columns]
```

#### 终止/暂停上市-深证

接口: stock_info_sz_delist

目标地址: <https://www.szse.cn/market/stock/suspend/index.html>

描述: 深证证券交易所终止/暂停上市股票

限量: 单次获取深证证券交易所终止/暂停上市数据

输入参数

| 名称     | 类型  | 描述                                              |
|--------|-----|-------------------------------------------------|
| symbol | str | symbol="终止上市公司"; choice of {"暂停上市公司", "终止上市公司"} |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 证券代码   | object | -   |
| 证券简称   | object | -   |
| 上市日期   | object | -   |
| 终止上市日期 | object | -   |

接口示例

```python
import akshare as ak

stock_info_sz_delist_df = ak.stock_info_sz_delist(symbol="终止上市公司")
print(stock_info_sz_delist_df)
```

数据示例

```
      证券代码   证券简称  上市日期    终止上市日期
0    000003   PT金田Ａ  1991-01-14  2002-06-14
1    000013  *ST石化A  1992-05-06  2004-09-20
2    000015   PT中浩Ａ  1992-06-25  2001-10-25
3    000018    神城A退  1992-06-16  2020-01-07
4    000024    招商地产  1993-06-07  2015-12-30
..      ...     ...         ...         ...
145  300367     网力退  2014-01-29  2022-06-30
146  300372     欣泰退  2014-01-27  2017-08-28
147  300392     腾信退  2014-09-10  2023-07-10
148  300431     暴风退  2015-03-24  2020-11-10
149  300526     中潜退  2016-08-02  2023-07-12
[150 rows x 4 columns]
```

#### 两网及退市

接口: stock_staq_net_stop

目标地址: <https://quote.eastmoney.com/center/gridlist.html#staq_net_board>

描述: 东方财富网-行情中心-沪深个股-两网及退市

限量: 单次获取所有两网及退市的股票数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称  | 类型     | 描述  |
|-----|--------|-----|
| 序号  | int64  | -   |
| 代码  | object | -   |
| 名称  | object | -   |

接口示例

```python
import akshare as ak

stock_staq_net_stop_df = ak.stock_staq_net_stop()
print(stock_staq_net_stop_df)
```

数据示例

```
      序号   代码      名称
0      1  400199    阳光城5
1      2  400170     运盛5
2      3  400039  华  圣 5
3      4  400119     西创5
4      5  400045     猴王5
..   ...     ...     ...
199  200  400149     金泰5
200  201  400155     海医5
201  202  400142     宝德5
202  203  400163     计通5
203  204  400046     博嘉5
[204 rows x 3 columns]
```

#### 暂停/终止上市-上证

接口: stock_info_sh_delist

目标地址: <https://www.sse.com.cn/assortment/stock/list/delisting/>

描述: 上海证券交易所暂停/终止上市股票

限量: 单次获取上海证券交易所暂停/终止上市股票

输入参数

| 名称     | 类型  | 描述                                         |
|--------|-----|--------------------------------------------|
| symbol | str | symbol="全部"; choice of {"全部", "沪市", "科创板"} |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 公司代码   | object | -   |
| 公司简称   | object | -   |
| 上市日期   | object | -   |
| 暂停上市日期 | object | -   |

接口示例

```python
import akshare as ak

stock_info_sh_delist_df = ak.stock_info_sh_delist(symbol="全部")
print(stock_info_sh_delist_df)
```

数据示例

```
     公司代码    公司简称   上市日期      暂停上市日期
0    600001    邯郸钢铁  1998-01-22  2009-12-29
1    600002    齐鲁退市  1998-04-08  2006-04-24
2    600003   ST东北高  1999-08-10  2010-02-26
3    600005    武钢股份  1999-08-03  2017-02-14
4    600065  *ST联 谊  1997-05-23  2007-12-13
..      ...     ...         ...         ...
109  900935    阳晨Ｂ股  1995-07-27  2016-12-16
110  900949    东电Ｂ股  1997-09-23  2013-11-07
111  900950    新城Ｂ股  1997-10-16  2015-11-23
112  900951    退市大化  1997-10-21  2020-08-28
113  900956    东贝Ｂ股  1999-07-15  2020-11-23
[114 rows x 4 columns]
```

#### 股票更名

接口: stock_info_change_name

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/300378.phtml>

描述: 新浪财经-股票曾用名

限量: 单次指定 symbol 的所有历史曾用名称

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="000503"; 股票代码 |

输出参数

| 名称    | 类型     | 描述  |
|-------|--------|-----|
| index | int64  | -   |
| name  | object | -   |

接口示例

```python
import akshare as ak

stock_info_change_name_list = ak.stock_info_change_name(symbol="000503")
print(stock_info_change_name_list)
```

数据示例

```
   index  name
0      1   琼海虹
1      2  海虹控股
2      3  ST海虹
3      4  海虹控股
4      5   G海虹
5      6  海虹控股
6      7  国新健康
```

#### 名称变更-深证

接口: stock_info_sz_change_name

目标地址: <https://www.szse.cn/www/market/stock/changename/index.html>

描述: 深证证券交易所-市场数据-股票数据-名称变更

限量: 单次获取所有历史数据

输入参数

| 名称     | 类型  | 描述                                        |
|--------|-----|-------------------------------------------|
| symbol | str | symbol="全称变更"; choice of {"全称变更", "简称变更"} |

输出参数

| 名称    | 类型     | 描述  |
|-------|--------|-----|
| 变更日期  | object | -   |
| 证券代码  | object | -   |
| 证券简称  | object | -   |
| 变更前全称 | object | -   |
| 变更后全称 | object | -   |

接口示例

```python
import akshare as ak

stock_info_sz_change_name_df = ak.stock_info_sz_change_name(symbol="全称变更")
print(stock_info_sz_change_name_df)
```

数据示例

```
       变更日期    证券代码   证券简称               变更前全称             变更后全称
0     1992-02-28  000004   国华网安        蛇口安达运输股份有限公司   深圳市蛇口安达实业股份有限公司
1     1993-03-08  200012  南  玻Ｂ        中国南方玻璃股份有限公司      中国南玻集团股份有限公司
2     1993-03-08  000012  南  玻Ａ        中国南方玻璃股份有限公司      中国南玻集团股份有限公司
3     1993-07-12  000009   中国宝安   深圳市宝安企业(集团)股份有限公司      中国宝安集团股份有限公司
4     1993-12-20  000005   ST星源        深圳原野实业股份有限公司      深圳世纪星源股份有限公司
          ...     ...    ...                 ...               ...
1614  2024-01-30  002986   宇新股份      湖南宇新能源科技股份有限公司    广东宇新能源科技股份有限公司
1615  2024-01-31  301418   协昌科技      江苏协昌电子科技股份有限公司  江苏协昌电子科技集团股份有限公司
1616  2024-02-05  300617   安靠智电  江苏安靠智能输电工程科技股份有限公司      江苏安靠智电股份有限公司
1617  2024-02-07  002060   广东建工        广东水电二局股份有限公司   广东省建筑工程集团股份有限公司
1618  2024-02-28  300478   杭州高新      杭州高新橡塑材料股份有限公司    杭州高新材料科技股份有限公司
[1619 rows x 5 columns]
```

#### 基金持股

接口: stock_fund_stock_holder

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_FundStockHolder/stockid/600004.phtml>

描述: 新浪财经-股本股东-基金持股

限量: 新浪财经-股本股东-基金持股所有历史数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="600004"; 股票代码 |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 基金名称   | object  | -       |
| 基金代码   | object  | -       |
| 持仓数量   | int64   | 注意单位: 股 |
| 占流通股比例 | float64 | 注意单位: % |
| 持股市值   | int64   | 注意单位: 元 |
| 占净值比例  | float64 | 注意单位: % |
| 截止日期   | object  | -       |

接口示例

```python
import akshare as ak

stock_fund_stock_holder_df = ak.stock_fund_stock_holder(symbol="601318")
print(stock_fund_stock_holder_df)
```

数据示例

```
    基金名称    基金代码      持仓数量  占流通股比例        持股市值  占净值比例        截止日期
0      银华沪深300价值ETF  562320    265300  0.0015    12981100   3.85  2023-01-05
1    华安沪深300增强策略ETF  561000     91200  0.0005     4425940   0.53  2023-01-04
2         华夏上证50ETF  510050  92794672  0.5076  4361350000   7.48  2022-12-31
3      华泰柏瑞沪深300ETF  510300  44522018  0.2436  2092530000   2.70  2022-12-31
4     易方达沪深300非银ETF  512070  34406219  0.1882  1617090000  29.08  2022-12-31
..              ...     ...       ...     ...         ...    ...         ...
995       安信民稳增长混合A  008809   1125037  0.0062    46779000   2.68  2022-09-30
996       建信上证50ETF  510800   1084221  0.0059    45081900   6.86  2022-09-30
997   国寿安保沪港深300ETF  517300   1016300  0.0056    42257800   2.09  2022-09-30
998      泰达宏利市值优选混合  162209   1013832  0.0055    42155100   6.45  2022-09-30
999      南方沪深300ETF  159925    961652  0.0053    39985500   2.52  2022-09-30
```

#### 主要股东

接口: stock_main_stock_holder

目标地址: <https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_StockHolder/stockid/600004.phtml>

描述: 新浪财经-股本股东-主要股东

限量: 单次获取所有历史数据

输入参数

| 名称    | 类型  | 描述                   |
|-------|-----|----------------------|
| stock | str | stock="600004"; 股票代码 |

输出参数

| 名称    | 类型      | 描述         |
|-------|---------|------------|
| 编号    | object  | -          |
| 股东名称  | object  | -          |
| 持股数量  | float64 | 注意单位: 股    |
| 持股比例  | float64 | 注意单位: %    |
| 股本性质  | object  | -          |
| 截至日期  | object  | -          |
| 公告日期  | object  | -          |
| 股东说明  | object  | -          |
| 股东总数  | float64 | -          |
| 平均持股数 | float64 | 备注: 按总股本计算 |

接口示例

```python
import akshare as ak

stock_main_stock_holder_df = ak.stock_main_stock_holder(stock="600004")
print(stock_main_stock_holder_df)
```

数据示例

```
      编号                股东名称          持股数量  ...  股东说明      股东总数     平均持股数
0      1          上海国际集团有限公司  6.331323e+09  ...   NaN  164613.0  178312.0
1      2      中国移动通信集团广东有限公司  5.334893e+09  ...   NaN  164613.0  178312.0
2      3   富德生命人寿保险股份有限公司-传统  2.779437e+09  ...   NaN  164613.0  178312.0
3      4  富德生命人寿保险股份有限公司-资本金  1.763232e+09  ...   NaN  164613.0  178312.0
4      5       上海上国投资产管理有限公司  1.395571e+09  ...   NaN  164613.0  178312.0
...   ..                 ...           ...  ...   ...       ...       ...
1383   6        东方国际（集团）有限公司  5.000000e+07  ...   NaN       NaN       NaN
1384   7            申能股份有限公司  5.000000e+07  ...   NaN       NaN       NaN
1385   8    上海外高桥保税区开发股份有限公司  4.000000e+07  ...   NaN       NaN       NaN
1386   9      上海市城市建设投资开发总公司  3.800000e+07  ...   NaN       NaN       NaN
1387  10          中国华北电力集团公司  3.000000e+07  ...   NaN       NaN       NaN
[1388 rows x 10 columns]
```

#### 机构持股

##### 机构持股一览表

接口: stock_institute_hold

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vComStockHold/kind/jgcg/index.phtml>

描述: 新浪财经-机构持股-机构持股一览表

限量: 单次获取所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                                                              |
|--------|-----|-----------------------------------------------------------------------------------------------------------------|
| symbol | str | symbol="20051"; 从 2005 年开始, {"一季报":1, "中报":2 "三季报":3 "年报":4}, e.g., "20191", 其中的 1 表示一季报; "20193", 其中的 3 表示三季报; |

输出参数

| 名称       | 类型      | 描述      |
|----------|---------|---------|
| 证券代码     | object  | -       |
| 证券简称     | object  | -       |
| 机构数      | int64   | -       |
| 机构数变化    | int64   | -       |
| 持股比例     | float64 | 注意单位: % |
| 持股比例增幅   | float64 | 注意单位: % |
| 占流通股比例   | float64 | 注意单位: % |
| 占流通股比例增幅 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_institute_hold_df = ak.stock_institute_hold(symbol="20201")
print(stock_institute_hold_df)
```

数据示例

```
      证券代码  证券简称 机构数  机构数变化   持股比例  持股比例增幅  占流通股比例  占流通股比例增幅
0     002296  辉煌科技    1      1   0.85    0.85    0.85      0.85
1     300354  东华测试    1      0   0.21   -0.59    0.21     -0.59
2     000656  金科股份    1      0   2.12    0.04    2.14      0.03
3     002859  洁美科技    1      0   0.97    0.00    2.28      0.00
4     603866  桃李面包    1      0   1.34    0.00    1.34      0.00
      ...   ...  ...    ...    ...     ...     ...       ...
1790  300782   卓胜微   10      2   6.00    2.02   24.00      8.07
1791  300788  中信出版   10      0  10.26    2.88   41.03     11.50
1792  300785   值得买   10      1  11.62    4.14   46.48     16.56
1793  688188  柏楚电子   10      0   5.17   -0.13   21.43     -1.70
1794  300003  乐普医疗   16      1  11.16    0.99   11.78      1.05
[1795 rows x 8 columns]
```

##### 机构持股详情

接口: stock_institute_hold_detail

目标地址: <http://vip.stock.finance.sina.com.cn/q/go.php/vComStockHold/kind/jgcg/index.phtml>

描述: 新浪财经-机构持股-机构持股详情

限量: 单次所有历史数据

输入参数

| 名称      | 类型  | 描述                                                                                                               |
|---------|-----|------------------------------------------------------------------------------------------------------------------|
| stock   | str | stock="300003"; 股票代码                                                                                             |
| quarter | str | quarter="20201"; 从 2005 年开始, {"一季报":1, "中报":2 "三季报":3 "年报":4}, e.g., "20191", 其中的 1 表示一季报; "20193", 其中的 3 表示三季报; |

输出参数

| 名称       | 类型      | 描述       |
|----------|---------|----------|
| 持股机构类型   | object  | -        |
| 持股机构代码   | object  | -        |
| 持股机构简称   | object  | -        |
| 持股机构全称   | object  | -        |
| 持股数      | float64 | 注意单位: 万股 |
| 最新持股数    | float64 | 注意单位: 万股 |
| 持股比例     | float64 | 注意单位: %  |
| 最新持股比例   | float64 | 注意单位: %  |
| 占流通股比例   | float64 | 注意单位: %  |
| 最新占流通股比例 | float64 | 注意单位: %  |
| 持股比例增幅   | float64 | 注意单位: %  |
| 占流通股比例增幅 | float64 | 注意单位: %  |

接口示例

```python
import akshare as ak

stock_institute_hold_detail_df = ak.stock_institute_hold_detail(stock="300003", quarter="20201")
print(stock_institute_hold_detail_df)
```

数据示例

```
   持股机构类型  持股机构代码      持股机构简称  ... 最新占流通股比例  持股比例增幅  占流通股比例增幅
0      基金    519069          汇添富价值精选混合A  ...     1.18   -0.22     -0.23
1      基金    159915           易方达创业板ETF  ...     0.73    0.02      0.02
2      基金    001417      汇添富医疗服务灵活配置混合A  ...     1.01   -0.35     -0.37
3      基金    470009          汇添富民营活力混合A  ...     0.48    0.03      0.02
4      基金    159949          华安创业板50ETF  ...     0.36    0.13      0.13
5      基金    000831            工银医疗保健股票  ...     0.57   -0.09     -0.10
6    全国社保  70010117         全国社保基金一一七组合  ...     1.30   -0.22     -0.23
7    全国社保  70010104         全国社保基金一零四组合  ...     0.60   -0.06     -0.07
8    全国社保  70010503         全国社保基金五零三组合  ...     0.38    0.07      0.07
9      保险  70304136  华夏人寿保险股份有限公司－自有...  ...     0.00    1.39      1.47
10   QFII  70304002         挪威中央银行－自有资金  ...     0.90    0.25      0.27
11   QFII  70304274        澳门金融管理局－自有资金  ...     0.99    0.00      0.00
12   QFII  80126479           魁北克储蓄投资集团  ...     0.71    0.00      0.00
13   QFII  70304150  鼎晖投资咨询新加坡有限公司－鼎...  ...     0.57    0.01      0.01
14   QFII  80128964             阿布达比投资局  ...     0.56    0.02      0.02
15   QFII  80195934            科威特政府投资局  ...     0.39    0.04      0.04
[16 rows x 12 columns]
```

#### 机构推荐

##### 机构推荐池

接口: stock_institute_recommend

目标地址: <http://stock.finance.sina.com.cn/stock/go.php/vIR_RatingNewest/index.phtml>

描述: 新浪财经-机构推荐池-具体指标的数据

限量: 单次获取新浪财经-机构推荐池-具体指标的所有数据

输入参数

| 名称     | 类型  | 描述                                                                                                                 |
|--------|-----|--------------------------------------------------------------------------------------------------------------------|
| symbol | str | symbol="行业关注度"; choice of {'最新投资评级', '上调评级股票', '下调评级股票', '股票综合评级', '首次评级股票', '目标涨幅排名', '机构关注度', '行业关注度', '投资评级选股'} |

输出参数

| 名称  | 类型  | 描述                |
|-----|-----|-------------------|
| -   | -   | 根据特定 indicator 而定 |

接口示例

```python
import akshare as ak

stock_institute_recommend_df = ak.stock_institute_recommend(symbol="投资评级选股")
print(stock_institute_recommend_df)
```

数据示例

```
        股票代码   股票名称 最新评级     目标价       评级日期↓ 综合评级    平均涨幅    行业
0     000001   平安银行   买入   19.73  2020-05-27   买入  51.75%    银行
1     300403   汉宇集团   中性    5.70  2020-05-27   中性  18.26%  白色家电
2     603288   海天味业   买入  112.85  2020-05-27   买入  -1.32%  食品加工
3     601238   广汽集团   买入   12.72  2020-05-27   买入  34.62%  汽车整车
4     002709   天赐材料   增持   34.24  2020-05-27   买入   18.1%  化学制品
      ...    ...  ...     ...         ...  ...     ...   ...
1053  601398   工商银行   买入    7.14  2020-05-27   买入  39.54%    银行
1054  002078   太阳纸业   买入   11.22  2020-05-27   买入  35.64%    造纸
1055  002080   中材科技   买入   14.59  2020-05-27   买入  22.61%  化学制品
1056  002081  金 螳 螂   增持   12.55  2020-05-27   买入  55.51%  装修装饰
1057  601658   邮储银行   增持    6.52  2020-05-27   买入  28.25%    银行
```

##### 股票评级记录

接口: stock_institute_recommend_detail

目标地址: <http://stock.finance.sina.com.cn/stock/go.php/vIR_StockSearch/key/sz000001.phtml>

描述: 新浪财经-机构推荐池-股票评级记录

限量: 单次获取新浪财经-机构推荐池-股票评级记录的所有数据

输入参数

| 名称     | 类型  | 描述              |
|--------|-----|-----------------|
| symbol | str | symbol="000001" |

输出参数

| 名称   | 类型  | 描述  |
|------|-----|-----|
| 股票代码 | str | -   |
| 股票名称 | str | -   |
| 目标价  | str | -   |
| 最新评级 | str | -   |
| 评级机构 | str | -   |
| 分析师  | str | -   |
| 行业   | str | -   |
| 评级日期 | str | -   |

接口示例

```python
import akshare as ak

stock_institute_recommend_detail_df = ak.stock_institute_recommend_detail(symbol="002709")
print(stock_institute_recommend_detail_df)
```

数据示例

```
       股票代码  股票名称    目标价 最新评级  评级机构        分析师    行业        评级日期
0    002709  天赐材料    NaN   增持  国海证券      谭倩,尹斌  化学制品  2020-05-27
1    002709  天赐材料    NaN   增持  光大证券     吴裕,裘孝锋  化学制品  2020-05-07
2    002709  天赐材料  35.20   买入  华创证券  杨达伟,于潇,邱迪  化学制品  2020-05-06
3    002709  天赐材料  33.25   买入  东吴证券        曾朵红  化学制品  2020-05-06
4    002709  天赐材料  35.50   买入  招商证券    游家训,刘珺涵  化学制品  2020-05-01
..      ...   ...    ...  ...   ...        ...   ...         ...
241  002709  天赐材料    NaN   买入  招商证券    游家训,陈雁冰  化学制品  2017-09-07
242  002709  天赐材料    NaN   买入  方正证券        韩振国  化学制品  2017-09-07
243  002709  天赐材料  61.82   买入  招商证券    游家训,陈雁冰  化学制品  2017-09-07
244  002709  天赐材料  59.82   买入  中泰证券        邵晶鑫  化学制品  2017-09-06
245  002709  天赐材料    NaN   买入  国海证券        代鹏举  化学制品  2017-09-04
```

##### 投资评级

接口: stock_rank_forecast_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-评级预测-投资评级

限量: 单次获取指定交易日的所有数据

输入参数

| 名称   | 类型  | 描述                   |
|------|-----|----------------------|
| date | str | date="20210910"; 交易日 |

输出参数

| 名称      | 类型      | 描述  |
|---------|---------|-----|
| 证券代码    | object  | -   |
| 证券简称    | object  | -   |
| 发布日期    | object  | -   |
| 研究机构简称  | object  | -   |
| 研究员名称   | object  | -   |
| 投资评级    | object  | -   |
| 是否首次评级  | object  | -   |
| 评级变化    | object  | -   |
| 前一次投资评级 | object  | -   |
| 目标价格-下限 | float64 | -   |
| 目标价格-上限 | float64 | -   |

接口示例

```python
import akshare as ak

stock_rank_forecast_cninfo_df = ak.stock_rank_forecast_cninfo(date="20230817")
print(stock_rank_forecast_cninfo_df)
```

数据示例

```
     证券代码  证券简称   发布日期 研究机构简称  ... 评级变化 前一次投资评级 目标价格-下限 目标价格-上限
0    000552  甘肃能化  2023-08-17   民生证券  ...   维持      增持     NaN     NaN
1    000552  甘肃能化  2023-08-17   山西证券  ...   未知     不评级     NaN     NaN
2    000552  甘肃能化  2023-08-17   开源证券  ...   维持      买入     NaN     NaN
3    000567  海德股份  2023-08-17   中信证券  ...   未知     不评级     NaN     NaN
4    000682  东方电子  2023-08-17   光大证券  ...   维持      买入     NaN     NaN
..      ...   ...         ...    ...  ...  ...     ...     ...     ...
329  688668  鼎通科技  2023-08-17   民生证券  ...   维持      增持     NaN     NaN
330  688981  中芯国际  2023-08-17   中信建投  ...   未知     不评级     NaN     NaN
331  688981  中芯国际  2023-08-17   中泰证券  ...   维持      买入     NaN     NaN
332  836419  万德股份  2023-08-17   开源证券  ...   未知     不评级     NaN     NaN
333  839371  欧福蛋业  2023-08-17   开源证券  ...   维持      增持     NaN     NaN
[334 rows x 11 columns]
```

##### 申万个股行业分类变动历史

接口: stock_industry_clf_hist_sw

目标地址: <http://www.swhyresearch.com/institute_sw/allIndex/downloadCenter/industryType>

描述: 申万宏源研究-行业分类-全部行业分类

限量: 单次获取所有个股的行业分类变动历史数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称            | 类型     | 描述     |
|---------------|--------|--------|
| symbol        | object | 股票代码   |
| start_date    | object | 计入日期   |
| industry_code | object | 申万行业代码 |
| update_time   | object | 更新日期   |

接口示例

```python
import akshare as ak

stock_industry_clf_hist_sw_df = ak.stock_industry_clf_hist_sw()
print(stock_industry_clf_hist_sw_df)
```

数据示例

```
       symbol  start_date industry_code update_time
0      000001  1991-04-03        440101  2015-10-27
1      000001  2014-01-01        480101  2015-10-27
2      000001  2021-07-30        480301  2021-07-31
3      000002  1991-01-29        430101  2015-10-27
4      000003  1991-04-14        510101  2015-10-27
...       ...         ...           ...         ...
12360  873706  2024-03-12        640601  2024-03-13
12361  873726  2023-10-30        640209  2023-10-30
12362  873806  2024-01-17        710301  2024-01-17
12363  873833  2023-11-20        640106  2023-11-20
12364  874090  2023-08-21        370304  2023-08-21
[12365 rows x 4 columns]
```

##### 行业市盈率

接口: stock_industry_pe_ratio_cninfo

目标地址: <http://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-行业分析-行业市盈率

限量: 单次获取指定 symbol 在指定交易日的所有数据; 只能获取近期的数据

输入参数

| 名称     | 类型  | 描述                                                |
|--------|-----|---------------------------------------------------|
| symbol | str | symbol="证监会行业分类"; choice of {"证监会行业分类", "国证行业分类"} |
| date   | str | date="20210910"; 交易日                              |

输出参数

| 名称         | 类型      | 描述       |
|------------|---------|----------|
| 变动日期       | object  | -        |
| 行业分类       | object  | -        |
| 行业层级       | int64   | -        |
| 行业编码       | object  | -        |
| 行业名称       | object  | -        |
| 公司数量       | float64 | -        |
| 纳入计算公司数量   | float64 | -        |
| 总市值-静态     | float64 | 注意单位: 亿元 |
| 净利润-静态     | float64 | 注意单位: 亿元 |
| 静态市盈率-加权平均 | float64 | -        |
| 静态市盈率-中位数  | float64 | -        |
| 静态市盈率-算术平均 | float64 | -        |

接口示例

```python
import akshare as ak

stock_industry_pe_ratio_cninfo_df = ak.stock_industry_pe_ratio_cninfo(symbol="国证行业分类", date="20240617")
print(stock_industry_pe_ratio_cninfo_df)
```

数据示例

```
        变动日期          行业分类  行业层级  ... 静态市盈率-加权平均 静态市盈率-中位数  静态市盈率-算术平均
0    2024-06-17  国证行业分类标准2019     1  ...      11.54     15.75       49.19
1    2024-06-17  国证行业分类标准2019     2  ...      11.54     15.75       49.19
2    2024-06-17  国证行业分类标准2019     3  ...      18.44     22.05       28.24
3    2024-06-17  国证行业分类标准2019     4  ...      19.23     21.45       30.02
4    2024-06-17  国证行业分类标准2019     4  ...      18.10     24.86       25.35
..          ...           ...   ...  ...        ...       ...         ...
288  2024-06-17  国证行业分类标准2019     4  ...        NaN       NaN         NaN
289  2024-06-17  国证行业分类标准2019     3  ...      19.59     22.28       43.17
290  2024-06-17  国证行业分类标准2019     4  ...      19.59     22.28       43.17
291  2024-06-17  国证行业分类标准2019     3  ...      14.12     14.12       14.12
292  2024-06-17  国证行业分类标准2019     4  ...      14.12     14.12       14.12
[293 rows x 12 columns]
```

##### 新股过会

接口: stock_new_gh_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/xinguList>

描述: 巨潮资讯-数据中心-新股数据-新股过会

限量: 单次获取近一年所有新股过会的数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称    | 类型     | 描述  |
|-------|--------|-----|
| 公司名称  | object | -   |
| 上会日期  | object | -   |
| 审核类型  | object | -   |
| 审议内容  | object | -   |
| 审核结果  | object | -   |
| 审核公告日 | object | -   |

接口示例

```python
import akshare as ak

stock_new_gh_cninfo_df = ak.stock_new_gh_cninfo()
print(stock_new_gh_cninfo_df)
```

数据示例

```
              公司名称        上会日期  审核类型 审议内容 审核结果       审核公告日
0          兰州银行股份有限公司  2021-09-09  首发新股   首发   通过  2021-09-09
1          永安期货股份有限公司  2021-09-09  首发新股   首发   通过  2021-09-09
2        杭州福莱蒽特股份有限公司  2021-09-09  首发新股   首发   通过  2021-09-09
3    新疆派特罗尔能源服务股份有限公司  2021-09-02  首发新股   首发  未通过  2021-09-02
4      浙江盛泰服装集团股份有限公司  2021-08-26  首发新股   首发   通过  2021-08-26
..                ...         ...   ...  ...  ...         ...
125      河南蓝天燃气股份有限公司  2020-09-17  首发新股   首发   通过  2020-09-17
126      北京声迅电子股份有限公司  2020-09-17  首发新股   首发   通过  2020-09-17
127    天津友发钢管集团股份有限公司  2020-09-17  首发新股   首发   通过  2020-09-17
128     联泓新材料科技股份有限公司  2020-09-17  首发新股   首发   通过  2020-09-17
129      中国国际金融股份有限公司  2020-09-17  首发新股   首发   通过  2020-09-17
```

##### 新股发行

接口: stock_new_ipo_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/xinguList>

描述: 巨潮资讯-数据中心-新股数据-新股发行

限量: 单次获取近三年所有新股发行的数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称      | 类型      | 描述       |
|---------|---------|----------|
| 证劵代码    | object  | -        |
| 证券简称    | object  | -        |
| 上市日期    | object  | -        |
| 申购日期    | object  | -        |
| 发行价     | float64 | 注意单位: 元  |
| 总发行数量   | float64 | 注意单位: 万股 |
| 发行市盈率   | float64 | -        |
| 上网发行中签率 | float64 | 注意单位: %  |
| 摇号结果公告日 | object  | -        |
| 中签公告日   | object  | -        |
| 中签缴款日   | object  | -        |
| 网上申购上限  | float64 | -        |
| 上网发行数量  | float64 | -        |

接口示例

```python
import akshare as ak

stock_new_ipo_cninfo_df = ak.stock_new_ipo_cninfo()
print(stock_new_ipo_cninfo_df)
```

数据示例

```
     证劵代码  证券简称   上市日期  ...   中签缴款日  网上申购上限 上网发行数量
0    301592  六九一二         NaT  ...  2024-10-15    1.75  1750.00
1    301613  新铝时代         NaT  ...  2024-10-18    0.65  1162.70
2    301626  苏州天脉         NaT  ...  2024-10-17    0.70  1258.05
3    301628  强达电路         NaT  ...  2024-10-23    1.85  1884.40
4    603205   健尔康         NaT  ...  2024-10-29     NaN  1200.00
..      ...   ...         ...  ...         ...     ...      ...
926  301087  可孚医疗  2021-10-25  ...  2021-10-15    1.10  1918.55
927  605566  福莱蒽特  2021-10-25  ...  2021-10-13    1.30  3000.60
928  688255   凯尔达  2021-10-25  ...  2021-10-14    0.45   674.75
929  872925  锦好医疗  2021-10-25  ...  2021-10-08   51.63  1032.60
930  688737  中自科技  2021-10-22  ...  2021-10-14    0.50   734.70
[931 rows x 13 columns]
```

##### 董监高及相关人员持股变动-上证

接口: stock_share_hold_change_sse

目标地址: <http://www.sse.com.cn/disclosure/credibility/supervision/change/>

描述: 上海证券交易所-披露-监管信息公开-公司监管-董董监高人员股份变动

限量: 单次获取指定 symbol 的数据

输入参数

| 名称     | 类型  | 描述                                          |
|--------|-----|---------------------------------------------|
| symbol | str | symbol="600000"; choice of {"全部", "具体股票代码"} |

输出参数

| 名称       | 类型      | 描述 |
|----------|---------|----|
| 公司代码     | object  | -  |
| 公司名称     | object  | -  |
| 姓名       | object  | -  |
| 职务       | object  | -  |
| 股票种类     | object  | -  |
| 货币种类     | object  | -  |
| 本次变动前持股数 | int64   | -  |
| 变动数      | int64   | -  |
| 本次变动平均价格 | float64 | -  |
| 变动后持股数   | int64   | -  |
| 变动原因     | object  | -  |
| 变动日期     | object  | -  |
| 填报日期     | object  | -  |

接口示例

```python
import akshare as ak

stock_share_hold_change_sse_df = ak.stock_share_hold_change_sse(symbol="600000")
print(stock_share_hold_change_sse_df)
```

数据示例

```
    公司代码  公司名称   姓名         职务  ...  变动后持股数    变动原因   变动日期        填报日期
0   600000  浦发银行   谢伟     高级管理人员  ...  217000  二级市场买卖  2021-07-15  2021-07-16
1   600000  浦发银行  王新浩     高级管理人员  ...  231000  二级市场买卖  2021-07-15  2021-07-16
2   600000  浦发银行  潘卫东  董事、高级管理人员  ...  400000  二级市场买卖  2021-07-15  2021-07-16
3   600000  浦发银行  刘以研  董事、高级管理人员  ...  235900  二级市场买卖  2021-07-15  2021-07-16
4   600000  浦发银行  崔炳文     高级管理人员  ...  206700  二级市场买卖  2021-07-15  2021-07-16
5   600000  浦发银行   谢伟     高级管理人员  ...  158000  二级市场买卖  2020-07-16  2020-07-17
6   600000  浦发银行  王新浩     高级管理人员  ...  171000  二级市场买卖  2020-07-16  2020-07-17
7   600000  浦发银行  潘卫东  董事、高级管理人员  ...  200000  二级市场买卖  2020-07-16  2020-07-17
8   600000  浦发银行  刘以研  董事、高级管理人员  ...  177400  二级市场买卖  2020-07-15  2020-07-17
9   600000  浦发银行  崔炳文     高级管理人员  ...  148700  二级市场买卖  2020-07-16  2020-07-17
10  600000  浦发银行  刘以研  董事、高级管理人员  ...  163500  二级市场买卖  2020-07-10  2020-07-15
11  600000  浦发银行  刘以研  董事、高级管理人员  ...  168500  二级市场买卖  2020-07-13  2020-07-15
12  600000  浦发银行  刘以研  董事、高级管理人员  ...  173500  二级市场买卖  2020-07-14  2020-07-15
13  600000  浦发银行  徐海燕     高级管理人员  ...  108000  二级市场买卖  2019-06-10  2019-06-11
14  600000  浦发银行   谢伟     高级管理人员  ...  106000  二级市场买卖  2019-06-10  2019-06-11
15  600000  浦发银行  王新浩     高级管理人员  ...  111000  二级市场买卖  2019-06-10  2019-06-11
16  600000  浦发银行  潘卫东     高级管理人员  ...  120000  二级市场买卖  2019-06-10  2019-06-11
17  600000  浦发银行  刘以研     高级管理人员  ...  103500  二级市场买卖  2019-06-10  2019-06-11
18  600000  浦发银行  刘信义     高级管理人员  ...  160000  二级市场买卖  2019-06-10  2019-06-11
19  600000  浦发银行  崔炳文     高级管理人员  ...   99700  二级市场买卖  2019-06-10  2019-06-11
20  600000  浦发银行  崔炳文     高级管理人员  ...   51700  二级市场买卖  2018-07-17  2018-07-17
21  600000  浦发银行  徐海燕     高级管理人员  ...   48000  二级市场买卖  2018-07-12  2018-07-12
22  600000  浦发银行   谢伟     高级管理人员  ...   53000  二级市场买卖  2018-07-11  2018-07-12
23  600000  浦发银行  王新浩     高级管理人员  ...   60000  二级市场买卖  2018-07-11  2018-07-12
24  600000  浦发银行  潘卫东     高级管理人员  ...   55000  二级市场买卖  2018-07-11  2018-07-12
25  600000  浦发银行  刘以研     高级管理人员  ...   52500  二级市场买卖  2018-07-11  2018-07-12
26  600000  浦发银行  刘信义     高级管理人员  ...   80000  二级市场买卖  2018-07-11  2018-07-12
[27 rows x 13 columns]
```

##### 董监高及相关人员持股变动-深证

接口: stock_share_hold_change_szse

目标地址: <http://www.szse.cn/disclosure/supervision/change/index.html>

描述: 深圳证券交易所-信息披露-监管信息公开-董监高人员股份变动

限量: 单次获取指定 symbol 的数据

输入参数

| 名称     | 类型  | 描述                                          |
|--------|-----|---------------------------------------------|
| symbol | str | symbol="001308"; choice of {"全部", "具体股票代码"} |

输出参数

| 名称         | 类型      | 描述         |
|------------|---------|------------|
| 证券代码       | object  | -          |
| 证券简称       | object  | -          |
| 董监高姓名      | object  | -          |
| 变动日期       | object  | -          |
| 变动股份数量     | float64 | 注意单位: 万股   |
| 成交均价       | float64 | -          |
| 变动原因       | object  | -          |
| 变动比例       | float64 | 注意单位: 千分之一 |
| 当日结存股数     | float64 | 注意单位: 万股   |
| 股份变动人姓名    | object  | -          |
| 职务         | object  | -          |
| 变动人与董监高的关系 | object  | -          |

接口示例

```python
import akshare as ak

stock_share_hold_change_szse_df = ak.stock_share_hold_change_szse(symbol="001308")
print(stock_share_hold_change_szse_df)
```

数据示例

```
   证券代码  证券简称 董监高姓名 变动日期  ...    当日结存股数  股份变动人姓名     职务  变动人与董监高的关系
0  001308  康冠科技    凌斌  2023-08-21  ...  18752.80       凌斌     董事          本人
1  001308  康冠科技    凌斌  2023-08-18  ...  18743.80       凌斌     董事          本人
2  001308  康冠科技    凌斌  2023-08-17  ...  18737.80       凌斌     董事          本人
3  001308  康冠科技    凌斌  2023-08-16  ...  18734.80       凌斌     董事          本人
4  001308  康冠科技    江微  2023-08-09  ...      1.00       江微     监事          本人
5  001308  康冠科技    吴远  2023-08-08  ...      7.48       吴远     高管          本人
6  001308  康冠科技   孙建华  2023-08-08  ...      3.88      孙建华  董秘、高管          本人
7  001308  康冠科技    吴远  2022-08-24  ...      4.95       吴远     高管          本人
8  001308  康冠科技    吴远  2022-06-17  ...      3.55       吴远     高管          本人
[9 rows x 12 columns]
```

##### 董监高及相关人员持股变动-北证

接口: stock_share_hold_change_bse

目标地址: <https://www.bse.cn/disclosure/djg_sharehold_change.html>

描述: 北京证券交易所-信息披露-监管信息-董监高及相关人员持股变动

限量: 单次获取指定 symbol 的数据

输入参数

| 名称     | 类型  | 描述                                          |
|--------|-----|---------------------------------------------|
| symbol | str | symbol="430489"; choice of {"全部", "具体股票代码"} |

输出参数

| 名称     | 类型      | 描述       |
|--------|---------|----------|
| 代码     | object  | -        |
| 简称     | object  | -        |
| 姓名     | object  | -        |
| 职务     | object  | -        |
| 变动日期   | object  | -        |
| 变动股数   | float64 | 注意单位: 万股 |
| 变动前持股数 | float64 | 注意单位: 万股 |
| 变动后持股数 | float64 | 注意单位: 万股 |
| 变动均价   | float64 | 注意单位: 元  |
| 变动原因   | object  | -        |

接口示例

```python
import akshare as ak

stock_share_hold_change_bse_df = ak.stock_share_hold_change_bse(symbol="430489")
print(stock_share_hold_change_bse_df)
```

数据示例

```
   代码    简称   姓名     职务        变动日期   变动股数   变动前持股数   变动后持股数  变动均价  变动原因
0  430489  佳先股份   李兑      董事  2023-07-28  7.151   0.0000   7.1510  4.66  竞价交易
1  430489  佳先股份   李平  高级管理人员  2023-07-14  2.000  23.0565  25.0565  4.64  竞价交易
2  430489  佳先股份  周星源  高级管理人员  2023-06-21  2.000  28.2896  30.2896  4.59  竞价交易
3  430489  佳先股份   汪静  高级管理人员  2023-06-20  1.000  70.0360  71.0360  4.52  竞价交易
4  430489  佳先股份   汪静  高级管理人员  2023-06-19  1.000  69.0360  70.0360  4.56  竞价交易
5  430489  佳先股份   丁柱  高级管理人员  2023-06-16  0.500  53.2920  53.7920  4.50  竞价交易
6  430489  佳先股份   丁柱  高级管理人员  2023-06-15  0.500  52.7920  53.2920  4.48  竞价交易
7  430489  佳先股份   丁柱  高级管理人员  2023-06-14  1.000  51.7920  52.7920  4.48  竞价交易
```

##### 股东人数及持股集中度

接口: stock_hold_num_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-股东股本-股东人数及持股集中度

限量: 单次指定 date 的股东人数及持股集中度数据, 从 20170331 开始

输入参数

| 名称   | 类型  | 描述                                                                                         |
|------|-----|--------------------------------------------------------------------------------------------|
| date | str | date="20210630"; choice of {"XXXX0331", "XXXX0630", "XXXX0930", "XXXX1231"}; 从 20170331 开始 |

输出参数

| 名称       | 类型      | 描述       |
|----------|---------|----------|
| 证劵代码     | object  | -        |
| 证券简称     | object  | -        |
| 变动日期     | object  | -        |
| 本期股东人数   | int64   | -        |
| 上期股东人数   | float64 | -        |
| 股东人数增幅   | float64 | 注意单位: %  |
| 本期人均持股数量 | int64   | 注意单位: 万股 |
| 上期人均持股数量 | float64 | 注意单位: %  |
| 人均持股数量增幅 | float64 | 注意单位: %  |

接口示例

```python
import akshare as ak

stock_hold_num_cninfo_df = ak.stock_hold_num_cninfo(date="20210630")
print(stock_hold_num_cninfo_df)
```

数据示例

```
      证券代码  证券简称   变动日期  本期股东人数  ... 股东人数增幅  本期人均持股数量  上期人均持股数量  人均持股数量增幅
0     002054  德美化工  2021-06-30   17768  ...   -8.71   27134.0   24771.0      9.54
1     002055  得润电子  2021-06-30   57449  ...   15.55    8242.0    9524.0    -13.46
2     002056  横店东磁  2021-06-30   94339  ...    8.63   17243.0   18927.0     -8.90
3     600048  保利发展  2021-06-30  264212  ...    5.63   45303.0   47855.0     -5.33
4     002057  中钢天源  2021-06-30   44197  ...   -3.58   16883.0   12550.0     34.53
...      ...   ...         ...     ...  ...     ...       ...       ...       ...
4203  600918  中泰证券  2021-06-30  152424  ...   11.38   45719.0   50923.0    -10.22
4204  601375  中原证券  2021-06-30  158626  ...    2.38   29269.0   29966.0     -2.33
4205  601108  财通证券  2021-06-30  158061  ...   -5.50   22706.0   21458.0      5.82
4206  002945  华林证券  2021-06-30   54407  ...  -11.32   49626.0   44008.0     12.77
4207  601066  中信建投  2021-06-30  201162  ...    1.18   38559.0   39013.0     -1.16
[4208 rows x 9 columns]
```

##### 股本变动

接口: stock_hold_change_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-股东股本-股本变动

限量: 单次指定 symbol 的股本变动数据

输入参数

| 名称     | 类型  | 描述                                                               |
|--------|-----|------------------------------------------------------------------|
| symbol | str | symbol="全部"; choice of {"深市主板", "沪市", "创业板", "科创板", "北交所", "全部"} |

输出参数

| 名称     | 类型      | 描述     |
|--------|---------|--------|
| 证券代码   | object  | -      |
| 证券简称   | object  | -      |
| 交易市场   | object  | -      |
| 公告日期   | object  | -      |
| 变动日期   | object  | -      |
| 变动原因   | object  | -      |
| 总股本    | float64 | 单位: 万股 |
| 已流通股份  | float64 | 单位: 万股 |
| 已流通比例  | float64 | 单位: %  |
| 流通受限股份 | float64 | 单位: 万股 |

接口示例

```python
import akshare as ak

stock_hold_change_cninfo_df = ak.stock_hold_change_cninfo(symbol="全部")
print(stock_hold_change_cninfo_df)
```

数据示例

```
      证券代码   证券简称   交易市场  ...   已流通股份  已流通比例  流通受限股份
0     000001   平安银行  深交所主板  ...  1940561.75  100.00     30.07
1     000002  万  科Ａ  深交所主板  ...  1192344.88   99.94    726.07
2     000004   国华网安  深交所主板  ...    12628.81   95.40    609.22
3     000006   深振业Ａ  深交所主板  ...   134998.74  100.00      0.77
4     000007    全新好  深交所主板  ...    34644.80  100.00       NaN
...      ...    ...    ...  ...         ...     ...       ...
5463  920106   林泰新材    北交所  ...     1210.57   31.04   2689.43
5464  920111   聚星科技    北交所  ...     3688.85   23.78  11826.60
5465  920116   星图测控    北交所  ...     2612.50   23.75   8387.50
5466  920118   太湖远大    北交所  ...     1379.50   27.10   3710.10
5467  920128   胜业电气    北交所  ...     1710.00   21.06   6409.00
[5468 rows x 10 columns]
```

##### 实际控制人持股变动

接口: stock_hold_control_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-股东股本-实际控制人持股变动

限量: 单次指定 symbol 的实际控制人持股变动数据, 从 2010 开始

输入参数

| 名称     | 类型  | 描述                                                                         |
|--------|-----|----------------------------------------------------------------------------|
| symbol | str | symbol="全部"; choice of {"单独控制", "实际控制人", "一致行动人", "家族控制", "全部"}; 从 2010 开始 |

输出参数

| 名称      | 类型      | 描述       |
|---------|---------|----------|
| 证劵代码    | object  | -        |
| 证券简称    | object  | -        |
| 变动日期    | object  | -        |
| 实际控制人名称 | object  | -        |
| 控股数量    | float64 | 注意单位: 万股 |
| 控股比例    | float64 | 注意单位: %  |
| 直接控制人名称 | object  | -        |
| 控制类型    | object  | -        |

接口示例

```python
import akshare as ak

stock_hold_control_cninfo_df = ak.stock_hold_control_cninfo(symbol="全部")
print(stock_hold_control_cninfo_df)
```

数据示例

```
        证券代码  证券简称  ...                                        直接控制人名称   控制类型
0     601777  力帆股份  ...                 尹明善\r;陈巧凤\r;尹喜地\r;尹索微\r;重庆力帆控股有限公司  一致行动人
1     002460  赣锋锂业  ...                           李良彬;黄闻;熊剑浪;李良学;罗顺香\r;李华彪  一致行动人
2     000966  长源电力  ...                                           中国国电集团公司   单独控制
3     600019  宝钢股份  ...                                           宝钢集团有限公司   单独控制
4     600031  三一重工  ...                                       三一集团有限公司;梁稳根   单独控制
...      ...   ...  ...                                                ...    ...
5391  600354  敦煌种业  ...                                     酒泉钢铁(集团)有限责任公司   单独控制
5392  600208  新湖中宝  ...                          衢州工业投资集团有限公司;衢州工业发展集团有限公司   单独控制
5393  600399  抚顺特钢  ...  江苏沙钢集团有限公司;沙钢集团的股东张家港市保税区润源不锈钢贸易有限公司;宁波梅山保税港区锦...  一致行动人
5394  002075  沙钢股份  ...  江苏沙钢集团有限公司;宁波梅山保税港区锦程沙洲股权投资有限公司;张家港保税区润源不锈钢贸易有限公司   单独控制
5395  301552  科力装备  ...                   张万武;郭艳芝;张子恒;天津科达企业管理咨询合伙企业(有限合伙)   家族控制
[5396 rows x 8 columns]
```

##### 高管持股变动明细

接口: stock_hold_management_detail_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-股东股本-高管持股变动明细

限量: 单次指定 symbol 的高管持股变动明细数据, 返回近一年的数据

输入参数

| 名称     | 类型  | 描述                                  |
|--------|-----|-------------------------------------|
| symbol | str | symbol="增持"; choice of {"增持", "减持"} |

输出参数

| 名称        | 类型      | 描述       |
|-----------|---------|----------|
| 证劵代码      | object  | -        |
| 证券简称      | object  | -        |
| 截止日期      | object  | -        |
| 公告日期      | object  | -        |
| 高管姓名      | object  | -        |
| 董监高姓名     | object  | -        |
| 董监高职务     | object  | -        |
| 变动人与董监高关系 | object  | -        |
| 期初持股数量    | float64 | 注意单位: 万股 |
| 期末持股数量    | float64 | 注意单位: 万股 |
| 变动数量      | float64 | -        |
| 变动比例      | int64   | 注意单位: %  |
| 成交均价      | float64 | 注意单位: 元  |
| 期末市值      | float64 | 注意单位: 万元 |
| 持股变动原因    | object  | -        |
| 数据来源      | object  | -        |

接口示例

```python
import akshare as ak

stock_hold_management_detail_cninfo_df = ak.stock_hold_management_detail_cninfo(symbol="增持")
print(stock_hold_management_detail_cninfo_df)
```

数据示例

```
        证券代码  证券简称  截止日期    公告日期 高管姓名  ... 变动比例 成交均价 期末市值  持股变动原因  数据来源
0      000010  美丽生态  2023-12-31  2024-04-27   张琳  ...  NaN  NaN  NaN    None  定期报告
1      000010  美丽生态  2023-12-31  2024-04-27   张龙  ...  NaN  NaN  NaN    None  定期报告
2      000010  美丽生态  2023-12-31  2024-04-27  周成斌  ...  NaN  NaN  NaN    None  定期报告
3      000010  美丽生态  2023-12-31  2024-04-27  林孔凤  ...  NaN  NaN  NaN    None  定期报告
4      000010  美丽生态  2023-12-31  2024-04-27  江成汉  ...  NaN  NaN  NaN    None  定期报告
...       ...   ...         ...         ...  ...  ...  ...  ...  ...     ...   ...
15229  900946  天雁B股  2023-12-31  2024-04-20  何光清  ...  NaN  NaN  NaN    None  定期报告
15230  900946  天雁B股  2023-12-31  2024-04-20  刘青娥  ...  NaN  NaN  NaN    None  定期报告
15231  900946  天雁B股  2023-12-31  2024-04-20  杨国旗  ...  NaN  NaN  NaN    None  定期报告
15232  900946  天雁B股  2023-12-31  2024-04-20  杨宝全  ...  NaN  NaN  NaN    None  定期报告
15233  900946  天雁B股  2023-12-31  2024-04-20  胡辽平  ...  NaN  NaN  NaN    None  定期报告
[15234 rows x 16 columns]
```

##### 董监高及相关人员持股变动明细

接口: stock_hold_management_detail_em

目标地址: <https://data.eastmoney.com/executive/list.html>

描述: 东方财富网-数据中心-特色数据-高管持股-董监高及相关人员持股变动明细

限量: 单次返回所有数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称         | 类型      | 描述 |
|------------|---------|----|
| 日期         | object  | -  |
| 代码         | object  | -  |
| 名称         | object  | -  |
| 变动人        | object  | -  |
| 变动股数       | int64   | -  |
| 成交均价       | int64   | -  |
| 变动金额       | float64 | -  |
| 变动原因       | object  | -  |
| 变动比例       | float64 | -  |
| 变动后持股数     | float64 | -  |
| 持股种类       | object  | -  |
| 董监高人员姓名    | object  | -  |
| 职务         | object  | -  |
| 变动人与董监高的关系 | object  | -  |
| 开始时持有      | float64 | -  |
| 结束后持有      | float64 | -  |

接口示例

```python
import akshare as ak

stock_hold_management_detail_em_df = ak.stock_hold_management_detail_em()
print(stock_hold_management_detail_em_df)
```

数据示例

```
        日期      代码    名称  ... 变动人与董监高的关系    开始时持有  结束后持有
0       2023-08-08  001308  康冠科技  ...         本人  64350.0     74350.0
1       2023-08-08  001308  康冠科技  ...         本人      0.0     38800.0
2       2023-08-07  002533  金杯电工  ...         本人      NaN  45718400.0
3       2023-08-07  300389   艾比森  ...         本人      NaN     50600.0
4       2023-08-07  300827  上能电气  ...         本人      NaN  31879000.0
            ...     ...   ...  ...        ...      ...         ...
141380  2006-05-26  600500  中化国际  ...         本人      0.0      9000.0
141381  2006-03-02  000045  深纺织A  ...         本人      0.0      7050.0
141382  2006-02-17  002039  黔源电力  ...         本人      0.0     10000.0
141383  2005-09-22  000999  华润三九  ...         本人      0.0      2000.0
141384  2004-11-29  000030  富奥股份  ...         本人      0.0      6000.0
[141385 rows x 16 columns]
```

##### 人员增减持股变动明细

接口: stock_hold_management_person_em

目标地址: <https://data.eastmoney.com/executive/personinfo.html?name=%E5%90%B4%E8%BF%9C&code=001308>

描述: 东方财富网-数据中心-特色数据-高管持股-人员增减持股变动明细

限量: 单次返回指定 symbol 和 name 的数据

输入参数

| 名称     | 类型  | 描述                    |
|--------|-----|-----------------------|
| symbol | str | symbol="001308"; 股票代码 |
| name   | str | name="吴远"; 高管名称       |

输出参数

| 名称         | 类型      | 描述 |
|------------|---------|----|
| 日期         | object  | -  |
| 代码         | object  | -  |
| 名称         | object  | -  |
| 变动人        | object  | -  |
| 变动股数       | int64   | -  |
| 成交均价       | int64   | -  |
| 变动金额       | float64 | -  |
| 变动原因       | object  | -  |
| 变动比例       | float64 | -  |
| 变动后持股数     | float64 | -  |
| 持股种类       | object  | -  |
| 董监高人员姓名    | object  | -  |
| 职务         | object  | -  |
| 变动人与董监高的关系 | object  | -  |
| 开始时持有      | float64 | -  |
| 结束后持有      | float64 | -  |

接口示例

```python
import akshare as ak

stock_hold_management_person_em_df = ak.stock_hold_management_person_em(symbol="001308", name="孙建华")
print(stock_hold_management_person_em_df)
```

数据示例

```
   日期      代码    名称 变动人   变动股数  ...  董监高人员姓名    职务 变动人与董监高的关系    开始时持有  结束后持有
0  2023-08-08  001308  康冠科技  吴远  10000  ...       吴远  财务总监         本人  64350.0  74350
1  2022-08-24  001308  康冠科技  吴远  14000  ...       吴远    高管         本人      NaN  49500
2  2022-06-17  001308  康冠科技  吴远  35500  ...       吴远  财务总监         本人      0.0  35500
[3 rows x 16 columns]
```

##### 对外担保

接口: stock_cg_guarantee_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-公司治理-对外担保

限量: 单次指定 symbol 和起始日期的对外担保数据

输入参数

| 名称         | 类型  | 描述                                                        |
|------------|-----|-----------------------------------------------------------|
| symbol     | str | symbol="全部"; choice of {"全部", "深市主板", "沪市", "创业板", "科创板"} |
| start_date | str | start_date="20180630"                                     |
| end_date   | str | end_date="20210927"                                       |

输出参数

| 名称          | 类型      | 描述       |
|-------------|---------|----------|
| 证劵代码        | object  | -        |
| 证券简称        | object  | -        |
| 公告统计区间      | object  | -        |
| 担保笔数        | int64   | -        |
| 担保金额        | float64 | 注意单位: 万元 |
| 归属于母公司所有者权益 | float64 | 注意单位: 万元 |
| 担保金融占净资产比例  | float64 | 注意单位: %  |

接口示例

```python
import akshare as ak

stock_corporate_governance_guarantee_df = ak.stock_cg_guarantee_cninfo(symbol="全部", start_date="20180630", end_date="20210927")
print(stock_corporate_governance_guarantee_df)
```

数据示例

```
      证券代码  证券简称  ... 归属于母公司所有者权益  担保金融占净资产比例
0     000683  远兴能源  ...  1416683.55       93.19
1     000698  沈阳化工  ...   152836.81     1413.11
2     000732  ST泰禾  ...   387149.45    11353.60
3     000751  锌业股份  ...   358173.79       64.21
4     000818  航锦科技  ...   368945.73       30.90
...      ...   ...  ...         ...         ...
3075  688025   杰普特  ...   196706.09        5.08
3076  300822  贝仕达克  ...   126328.08        3.96
3077  300907  康平科技  ...    78724.85       10.16
3078  688296  和达科技  ...    70535.91        1.42
3079  300632  光莆股份  ...   189380.21       24.29
[3080 rows x 7 columns]
```

##### 公司诉讼

接口: stock_cg_lawsuit_cninfo

目标地址: <http://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-公司治理-公司诉讼

限量: 单次指定 symbol 和起始日期的公司诉讼数据

输入参数

| 名称         | 类型  | 描述                                                        |
|------------|-----|-----------------------------------------------------------|
| symbol     | str | symbol="全部"; choice of {"全部", "深市主板", "沪市", "创业板", "科创板"} |
| start_date | str | start_date="20180630"                                     |
| end_date   | str | end_date="20210927"                                       |

输出参数

| 名称     | 类型      | 描述       |
|--------|---------|----------|
| 证劵代码   | object  | -        |
| 证券简称   | object  | -        |
| 公告统计区间 | object  | -        |
| 诉讼次数   | int64   | -        |
| 诉讼金额   | float64 | 注意单位: 万元 |

接口示例

```python
import akshare as ak

stock_cg_lawsuit_cninfo_df = ak.stock_cg_lawsuit_cninfo(symbol="全部", start_date="20180630", end_date="20210927")
print(stock_cg_lawsuit_cninfo_df)
```

数据示例

```
        证券代码  证券简称                   公告统计区间  诉讼次数      诉讼金额
0     002524  光正眼科  2018-09-28---2021-09-27     1       NaN
1     603507  振江股份  2018-09-28---2021-09-27     1       NaN
2     600410  华胜天成  2018-09-28---2021-09-27     2       NaN
3     601333  广深铁路  2018-09-28---2021-09-27     1       NaN
4     301013   利和兴  2018-09-28---2021-09-27     1       NaN
      ...   ...                      ...   ...       ...
1020  600310  桂东电力  2018-09-28---2021-09-27     2   5360.63
1021  600815  厦工股份  2018-09-28---2021-09-27    75  75569.33
1022  600830  香溢融通  2018-09-28---2021-09-27     6  17109.27
1023  603986  兆易创新  2018-09-28---2021-09-27     6  29200.00
1024  002673  西部证券  2018-09-28---2021-09-27     4  75380.45
```

##### 股权质押

接口: stock_cg_equity_mortgage_cninfo

目标地址: <https://webapi.cninfo.com.cn/#/thematicStatistics>

描述: 巨潮资讯-数据中心-专题统计-公司治理-股权质押

限量: 单次指定 date 的股权质押数据

输入参数

| 名称   | 类型  | 描述              |
|------|-----|-----------------|
| date | str | date="20210930" |

输出参数

| 名称         | 类型      | 描述       |
|------------|---------|----------|
| 股票代码       | object  | -        |
| 股票简称       | object  | -        |
| 公告日期       | object  | -        |
| 出质人        | object  | -        |
| 质权人        | object  | -        |
| 质押数量       | float64 | 注意单位: 万股 |
| 占总股本比例     | float64 | 注意单位: %  |
| 质押解除数量     | float64 | 注意单位: 万股 |
| 质押事项       | object  | 注意单位: 万元 |
| 累计质押占总股本比例 | float64 | 注意单位: %  |

接口示例

```python
import akshare as ak

stock_cg_equity_mortgage_cninfo_df = ak.stock_cg_equity_mortgage_cninfo(date="20210930")
print(stock_cg_equity_mortgage_cninfo_df)
```

数据示例

```
      股票代码   股票简称  ...                                               质押事项  \
0   000892   欢瑞世纪  ...  本公司持股5%以上股东欢瑞世纪(天津)资产管理合伙企业(有限合伙)将2020年04月20日质...
1   000892   欢瑞世纪  ...  本公司持股5%以上股东赵枳程将持有的本公司4743836股流通A股质押给方正证券股份有限公司...
2   000948   南天信息  ...  本公司控股股东云南省工业投资控股集团有限责任公司将2020年09月18日质押给云南国际信托有...
3   002074   国轩高科  ...  本公司控股股东南京国轩控股集团有限公司将持有的本公司20620000股质押给海通证券股份有限...
4   002074   国轩高科  ...  本公司实际控制人李缜将2019年09月25日质押给华安证券股份有限公司的11270000股解...
5   002074   国轩高科  ...  本公司实际控制人李缜将2019年09月27日质押给华安证券股份有限公司的11100000股解...
6   002138   顺络电子  ...  本公司股东新余市恒顺通电子科技开发有限公司将持有的本公司3635000股流通A股质押给广发证...
7   002375   亚厦股份  ...  本公司控股股东亚厦控股有限公司将持有的本公司68000000股流通A股质押给杭州银行股份有限...
8   002375   亚厦股份  ...  本公司控股股东亚厦控股有限公司将持有的本公司97000000股流通A股质押给绍兴银行股份有限...
9   002466   天齐锂业  ...  本公司控股股东成都天齐实业(集团)有限公司将持有的本公司12000000股流通A股质押给中国...
10  002466   天齐锂业  ...  本公司控股股东成都天齐实业(集团)有限公司将持有的本公司4600000股流通A股质押给交通银...
11  002475   立讯精密  ...  本公司控股股东香港立讯有限公司将持有的本公司72620000股流通A股质押给招商银行股份有限...
12  002584   西陇科学  ...  本公司实际控制人黄伟波将持有的本公司8470000股流通受限股份质押给华鑫证券有限责任公司用...
13  002584   西陇科学  ...  本公司实际控制人黄伟波将持有的本公司9480000股流通受限股份质押给华鑫证券有限责任公司用...
14  002584   西陇科学  ...  本公司实际控制人黄伟鹏将2017年08月10日质押给华鑫证券有限责任公司的4480000股解...
15  002584   西陇科学  ...  本公司实际控制人黄伟鹏将持有的本公司5260000股流通受限股份质押给华鑫证券有限责任公司用...
16  002584   西陇科学  ...  本公司实际控制人黄伟鹏将持有的本公司7680000股流通受限股份质押给华鑫证券有限责任公司用...
17  002584   西陇科学  ...  本公司实际控制人黄伟鹏将持有的本公司9970000股流通受限股份质押给华鑫证券有限责任公司用...
18  002584   西陇科学  ...  本公司实际控制人黄伟鹏将持有的本公司5260000股流通受限股份质押给华鑫证券有限责任公司用...
19  002584   西陇科学  ...  本公司实际控制人黄少群将持有的本公司6290000股流通A股质押给华鑫证券有限责任公司用于办...
20  002584   西陇科学  ...  本公司实际控制人黄少群将持有的本公司7360000股流通受限股份质押给华鑫证券有限责任公司用...
21  002584   西陇科学  ...  本公司实际控制人黄少群将持有的本公司8200000股流通受限股份质押给华鑫证券有限责任公司用...
22  002584   西陇科学  ...  本公司实际控制人黄少群将持有的本公司9700000股流通受限股份质押给华鑫证券有限责任公司用...
23  002584   西陇科学  ...  本公司实际控制人黄少群将持有的本公司6290000股流通A股质押给华鑫证券有限责任公司用于办...
24  002602   世纪华通  ...  本公司大股东王佶将2018年02月12日质押给大连银行股份有限公司上海分行的25000000...
25  002602   世纪华通  ...  本公司大股东王佶将2018年02月12日质押给大连银行股份有限公司上海分行的26000000...
26  002602   世纪华通  ...  本公司大股东王佶将持有的本公司26000000股流通A股质押给泰安复星招银壹号股权投资基金合...
27  002602   世纪华通  ...  本公司大股东王佶将持有的本公司5000000股流通A股质押给泰安复星招银壹号股权投资基金合伙...
28  002677   浙江美大  ...  本公司股东夏鼎将2020年12月28日质押给上海海通证券资产管理有限公司用于办理质押式回购业...
29  002677   浙江美大  ...  本公司股东夏鼎将2021年05月18日质押给上海海通证券资产管理有限公司用于办理质押式回购业...
30  002677   浙江美大  ...  本公司股东夏鼎将2021年08月25日质押给上海海通证券资产管理有限公司用于办理质押式回购业...
31  002853    皮阿诺  ...  本公司控股股东、实际控制人马礼斌将持有的本公司1000000股流通A股质押给中信证券股份有限...
32  002922    伊戈尔  ...  本公司控股股东佛山市麦格斯投资有限公司将持有的本公司5000000股流通A股质押给国金证券股...
33  300175   朗源股份  ...  本公司控股股东新疆尚龙股权投资管理有限公司将持有的本公司17000000股流通A股质押给邳州...
34  300275    梅安森  ...  本公司控股股东马焰将持有的本公司2000000股流通受限股份质押给交通银行股份有限公司重庆市...
35  600093  *ST易见  ...  本公司股东云南省滇中产业发展集团有限责任公司将质押给中国工商银行股份有限公司昆明正义支行的8...
36  600093  *ST易见  ...  本公司股东云南省滇中产业发展集团有限责任公司将持有的本公司86380000股流通A股质押给中...
37  600176   中国巨石  ...  本公司股东振石控股集团有限公司将持有的本公司126680000股流通A股质押给中国民生银行股...
38  600176   中国巨石  ...  本公司股东振石控股集团有限公司将质押的211672605股解除质押，解除日期为2021年09...
39  600246   万通发展  ...  本公司第二大股东万通投资控股股份有限公司将2021年07月12日质押给江苏银行股份有限公司北...
40  600516   方大炭素  ...  本公司控股股东辽宁方大集团实业有限公司将持有的本公司56000000股流通A股质押给平安银行...
41  600516   方大炭素  ...  本公司控股股东辽宁方大集团实业有限公司将质押给平安银行股份有限公司沈阳分行的70700000...
42  600572    康恩贝  ...  本公司持股5%以上股东胡季强将持有的本公司27000000股流通A股质押给中信证券股份有限公...
43  600572    康恩贝  ...  本公司持股5%以上股东胡季强将质押给中信证券股份有限公司用于办理质押式回购业务的210000...
44  600739   辽宁成大  ...  本公司控股股东辽宁省国有资产经营有限公司将持有的本公司5500000股流通A股质押给华夏银行...
45  600745   闻泰科技  ...  本公司股东张丹琳将持有的本公司171095股流通A股质押给云南国际信托有限公司，质押开始日期...
46  600745   闻泰科技  ...  本公司股东张秋红将持有的本公司305364股流通A股质押给云南国际信托有限公司，质押开始日期...
47  600866   星湖科技  ...  本公司股东深圳长城汇理资产服务企业(有限合伙)将质押给东方证券股份有限公司的13080000...
48  600903   贵州燃气  ...  本公司控股股东北京东嘉投资有限公司将质押给华能贵诚信托有限公司的91507780股解除质押，...
49  600998    九州通  ...  本公司股东上海弘康实业投资有限公司将持有的本公司15600000股流通A股质押给汉口银行股份...
50  601012   隆基股份  ...  本公司控股股东李振国将质押给国信证券股份有限公司的28000000股流通A股解除质押，解除日...
51  603501   韦尔股份  ...  本公司控股股东虞仁荣将持有的本公司590000股流通A股质押给平安证券股份有限公司，质押开始...
52  603619   中曼石油  ...     本公司实际控制人李玉池将质押的16038460股解除质押，解除日期为2021年09月28日。
53  603638   艾迪精密  ...  本公司控股股东烟台翔宇投资有限公司将持有的本公司6000000股流通A股质押给云南国际信托有...
54  603661   恒林股份  ...  本公司持股5%以上股东安吉恒林商贸有限公司将持有的本公司1500000股流通A股质押给浙商证...
```

#### 美港目标价

接口: stock_price_js

目标地址: <https://www.ushknews.com/report.html>

描述: 美港电讯-美港目标价数据

限量: 单次获取所有数据, 数据从 2019-至今; 该接口暂时不能使用

输入参数

| 名称     | 类型  | 描述                                  |
|--------|-----|-------------------------------------|
| symbol | str | symbol="us"; choice of {"us", "hk"} |

输出参数

| 名称    | 类型      | 描述  |
|-------|---------|-----|
| 日期    | object  | -   |
| 个股名称  | object  | -   |
| 评级    | object  | -   |
| 先前目标价 | float64 | -   |
| 最新目标价 | float64 | -   |
| 机构名称  | object  | -   |

接口示例

```python
import akshare as ak

stock_price_js_df = ak.stock_price_js(symbol="us")
print(stock_price_js_df)
```

数据示例

```
               日期                    个股名称     评级  先前目标价  最新目标价       机构名称
0      2022-02-12  Teladoc Health(TDOC.N)     买入    NaN  121.0         高盛
1      2022-02-12       Cloudflare(NET.N)   None  132.0  150.0    KeyBanc
2      2022-02-12             Zillow(Z.O)   None   74.0   76.0      摩根士丹利
3      2022-02-11             Zillow(Z.O)   None  105.0  115.0  Benchmark
4      2022-02-11       Cloudflare(NET.N)     中性  210.0  130.0         贝雅
...           ...                     ...    ...    ...    ...        ...
46039  2019-01-02             美国银行(BAC.N)  与大市持平   37.0   34.0        巴克莱
46040  2019-01-02             亚马逊(AMZN.O)     买入    NaN    NaN    加拿大皇家银行
46041  2019-01-02              苹果(AAPL.O)   跑赢大市  266.0  228.0       摩根大通
46042  2019-01-02              苹果(AAPL.O)   跑赢大市    NaN  220.0    加拿大皇家银行
46043  2019-01-01               强生(JNJ.N)     中性  139.0  148.0         花旗
```

#### 券商业绩月报

接口: stock_qsjy_em

目标地址: <http://data.eastmoney.com/other/qsjy.html>

描述: 东方财富网-数据中心-特色数据-券商业绩月报

限量: 单次获取所有数据, 数据从 201006-202007, 月频率

输入参数

| 名称   | 类型  | 描述                                |
|------|-----|-----------------------------------|
| date | str | date="20200430"; 输入需要查询月份的最后一天的日期 |

输出参数

| 名称              | 类型      | 描述       |
|-----------------|---------|----------|
| 简称              | object  | -        |
| 代码              | object  | -        |
| 当月净利润-净利润       | float64 | 注意单位: 万元 |
| 当月净利润-同比增长      | float64 | -        |
| 当月净利润-环比增长      | float64 | -        |
| 当年累计净利润-累计净利润   | float64 | 注意单位: 万元 |
| 当年累计净利润-同比增长    | float64 | -        |
| 当月营业收入-营业收入     | float64 | 注意单位: 万元 |
| 当月营业收入-环比增长     | float64 | -        |
| 当月营业收入-同比增长     | float64 | -        |
| 当年累计营业收入-累计营业收入 | float64 | 注意单位: 万元 |
| 当年累计营业收入-同比增长   | float64 | -        |
| 净资产-净资产         | float64 | 注意单位: 万元 |
| 净资产-同比增长        | float64 | -        |

接口示例

```python
import akshare as ak

stock_qsjy_em_df = ak.stock_qsjy_em(date="20200430")
print(stock_qsjy_em_df)
```

数据示例

```
      简称      代码      当月净利润-净利润  ...  当年累计营业收入-同比增长       净资产-净资产   净资产-同比增长
0   国海证券  000750   19194.615013  ...      54.032161  1.776790e+06  33.096526
1   国金证券  600109   20891.770000  ...      50.235759  2.097736e+06   6.747984
2   光大证券  601788   60001.753808  ...       1.940449  5.191309e+06   2.343186
3   方正证券  601901   12395.300000  ...      15.571724  4.278250e+06  -8.135272
4   兴业证券  601377   32467.150000  ...     -14.595211  3.430436e+06   5.441332
5   国信证券  002736   56775.290000  ...      32.460693  5.529023e+06   2.995151
6   华泰证券  601688   78019.450000  ...       5.858672  1.234187e+07  14.817958
7   天风证券  601162    7704.010000  ...      13.050550  1.687778e+06  50.755090
8   华西证券  002926   24595.360000  ...       1.709712  2.002422e+06   6.198522
9   西南证券  600369   10153.900000  ...     -32.599011  1.976813e+06   5.182443
10  长城证券  002939   12596.910000  ...      14.546146  1.725532e+06   3.114500
11  东吴证券  601555   15202.270000  ...       8.220710  2.664589e+06  30.763186
12  东兴证券  601198   23724.000000  ...       1.505702  2.069308e+06   4.788353
13  浙商证券  601878   10729.640000  ...      71.999008  1.508543e+06   4.119564
14  申万宏源  000166  156658.000000  ...      29.308936  7.945952e+06  10.579253
15  华林证券  002945    3286.100000  ...      43.888841  5.492524e+05   8.617837
16  国泰君安  601211   79724.170000  ...      -9.160164  1.364813e+07   1.784078
17  东北证券  000686   19464.850000  ...       3.469984  1.618389e+06   4.375444
18  华安证券  600909   11005.490000  ...       7.830548  1.371776e+06   9.652564
19  中原证券  601375    8586.950000  ...      15.216216  1.004165e+06   2.114908
20  长江证券  000783   28988.140000  ...            NaN  3.115692e+06  10.237273
21  东方证券  600958   59493.090000  ...      36.465438  5.598729e+06   4.538278
22  红塔证券  601236   21168.110000  ...            NaN  1.352354e+06        NaN
23   太平洋  601099    1074.460000  ...     -35.504783  1.046198e+06   3.302652
24  中信证券  600030  162426.000000  ...      52.561662  1.683170e+07  23.936907
25  山西证券  002500   11175.370000  ...      35.841437  1.411993e+06   4.424647
26  中银证券  601696   10172.510000  ...            NaN  1.415213e+06        NaN
27  第一创业  002797   10003.990000  ...      32.569921  9.662962e+05   5.396208
28  招商证券  600999   82020.637477  ...      24.449430  8.590377e+06   6.038244
29  中信建投  601066  103886.720000  ...      61.480355  5.799100e+06  20.862475
30  国元证券  000728    4848.630000  ...      27.615097  2.366435e+06  -1.110733
31  华鑫股份  600621    4442.740000  ...      58.946622  6.125237e+05  14.145368
32  中国银河  601881   83429.360000  ...      30.440181  7.297874e+06   7.543491
33  西部证券  002673   19674.240000  ...     -10.968199  1.828071e+06   1.750810
34  广发证券  000776   68079.485932  ...      -4.933729  8.878713e+06   6.098383
35  财通证券  601108   17561.630000  ...      -8.775579  2.116647e+06   6.241030
36  南京证券  601990    9131.740000  ...      19.802440  1.139362e+06   5.430794
37  海通证券  600837   96773.380000  ...       3.011836  1.203286e+07   3.822430
```

#### A 股股息率

接口: stock_a_gxl_lg

目标地址: <https://legulegu.com/stockdata/guxilv>

描述: 乐咕乐股-股息率-A 股股息率

限量: 单次获取指定 symbol 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                      |
|--------|-----|---------------------------------------------------------|
| symbol | str | symbol="上证A股"; choice of {"上证A股", "深证A股", "创业板", "科创板"} |

输出参数

| 名称  | 类型      | 描述  |
|-----|---------|-----|
| 日期  | object  | -   |
| 股息率 | float64 | -   |

接口示例

```python
import akshare as ak

stock_a_gxl_lg_df = ak.stock_a_gxl_lg(symbol="上证A股")
print(stock_a_gxl_lg_df)
```

数据示例

```
           日期   股息率
0     2005-01-04  2.03
1     2005-01-05  2.05
2     2005-01-06  2.07
3     2005-01-07  2.06
4     2005-01-10  2.05
          ...   ...
4685  2024-04-18  3.44
4686  2024-04-19  3.44
4687  2024-04-22  3.48
4688  2024-04-23  3.52
4689  2024-04-24  3.50
[4690 rows x 2 columns]
```

#### 恒生指数股息率

接口: stock_hk_gxl_lg

目标地址: <https://legulegu.com/stockdata/market/hk/dv/hsi>

描述: 乐咕乐股-股息率-恒生指数股息率

限量: 单次获取所有月度历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称  | 类型      | 描述  |
|-----|---------|-----|
| 日期  | object  | -   |
| 股息率 | float64 | -   |

接口示例

```python
import akshare as ak

stock_hk_gxl_lg_df = ak.stock_hk_gxl_lg()
print(stock_hk_gxl_lg_df)
```

数据示例

```
          日期   股息率
0    1973-05-31  0.00
1    1973-06-30  0.00
2    1973-07-31  0.00
3    1973-08-31  0.00
4    1973-09-30  0.00
..          ...   ...
606  2023-11-30  4.10
607  2023-12-31  3.97
608  2024-01-31  4.37
609  2024-02-28  4.45
610  2024-03-31  4.34
[611 rows x 2 columns]
```

#### 大盘拥挤度

接口: stock_a_congestion_lg

目标地址: <https://legulegu.com/stockdata/ashares-congestion>

描述: 乐咕乐股-大盘拥挤度

限量: 单次获取近 4 年的历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称         | 类型      | 描述  |
|------------|---------|-----|
| date       | object  | 日期  |
| close      | float64 | 收盘价 |
| congestion | float64 | 拥挤度 |

接口示例

```python
import akshare as ak

stock_a_congestion_lg_df = ak.stock_a_congestion_lg()
print(stock_a_congestion_lg_df)
```

数据示例

```
           date    close  congestion
0    2020-04-27  2815.49      0.3783
1    2020-04-28  2810.02      0.3797
2    2020-04-29  2822.44      0.3876
3    2020-04-30  2860.08      0.4009
4    2020-05-06  2878.14      0.4080
..          ...      ...         ...
962  2024-04-18  3074.22      0.3848
963  2024-04-19  3065.26      0.3896
964  2024-04-22  3044.60      0.3834
965  2024-04-23  3021.98      0.3808
966  2024-04-24  3044.82      0.3786
[967 rows x 3 columns]
```

#### 股债利差

接口: stock_ebs_lg

目标地址: <https://legulegu.com/stockdata/equity-bond-spread>

描述: 乐咕乐股-股债利差

限量: 单次所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称      | 类型      | 描述  |
|---------|---------|-----|
| 日期      | object  | -   |
| 沪深300指数 | float64 | -   |
| 股债利差    | float64 | -   |
| 股债利差均线  | float64 | -   |

接口示例

```python
import akshare as ak

stock_ebs_lg_df = ak.stock_ebs_lg()
print(stock_ebs_lg_df)
```

数据示例

```
            日期  沪深300指数   股债利差 股债利差均线
0     2005-04-08  1003.45  0.022656  0.022656
1     2005-04-11   995.42  0.021938  0.022297
2     2005-04-12   978.70  0.024697  0.023097
3     2005-04-13  1000.90  0.022538  0.022957
4     2005-04-14   986.98  0.022811  0.022928
          ...      ...       ...       ...
4619  2024-04-18  3569.80  0.064876  0.061882
4620  2024-04-19  3541.66  0.064949  0.061909
4621  2024-04-22  3530.90  0.065748  0.061983
4622  2024-04-23  3506.22  0.066550  0.062014
4623  2024-04-24  3521.62  0.065847  0.062020
[4624 rows x 4 columns]
```

#### 巴菲特指标

接口: stock_buffett_index_lg

目标地址: <https://legulegu.com/stockdata/marketcap-gdp>

描述: 乐估乐股-底部研究-巴菲特指标

限量: 单次获取所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型      | 描述                             |
|--------|---------|--------------------------------|
| 日期     | object  | 交易日                            |
| 收盘价    | float64 | -                              |
| 总市值    | float64 | A股收盘价*已发行股票总股本（A股+B股+H股）       |
| GDP    | float64 | 上年度国内生产总值（例如：2019年，则取2018年GDP） |
| 近十年分位数 | float64 | 当前"总市值/GDP"在历史数据上的分位数          |
| 总历史分位数 | float64 | 当前"总市值/GDP"在历史数据上的分位数          |

接口示例

```python
import akshare as ak

stock_buffett_index_lg_df = ak.stock_buffett_index_lg()
print(stock_buffett_index_lg_df)
```

数据示例

```
            日期   收盘价       总市值      GDP   近十年分位数  总历史分位数
0     2005-04-07  1003.45   38470.47   161840.16  1.00000  1.00000
1     2005-04-10   995.42   39184.81   161840.16  1.00000  1.00000
2     2005-04-11   978.70   38955.09   161840.16  0.66667  0.66667
3     2005-04-12  1000.90   38287.33   161840.16  0.25000  0.25000
4     2005-04-13   986.98   39166.32   161840.16  0.80000  0.80000
...          ...      ...        ...         ...      ...      ...
4646  2024-05-26  3635.71  894146.43  1260582.10  0.34239  0.47837
4647  2024-05-27  3609.17  888429.78  1260582.10  0.32593  0.46601
4648  2024-05-28  3613.52  889703.17  1260582.10  0.32840  0.46870
4649  2024-05-29  3594.31  884208.63  1260582.10  0.31235  0.45699
4650  2024-05-30  3579.92  884322.56  1260582.10  0.31304  0.45732
[4651 rows x 6 columns]
```

#### A 股等权重与中位数市盈率

接口: stock_a_ttm_lyr

目标地址: <https://www.legulegu.com/stockdata/a-ttm-lyr>

描述: 乐咕乐股-A 股等权重市盈率与中位数市盈率

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称                                  | 类型      | 描述                               |
|-------------------------------------|---------|----------------------------------|
| date                                | object  | 日期                               |
| middlePETTM                         | float64 | 全A股滚动市盈率(TTM)中位数                 |
| averagePETTM                        | float64 | 全A股滚动市盈率(TTM)等权平均                |
| middlePELYR                         | float64 | 全A股静态市盈率(LYR)中位数                 |
| averagePELYR                        | float64 | 全A股静态市盈率(LYR)等权平均                |
| quantileInAllHistoryMiddlePeTtm     | float64 | 当前"TTM(滚动市盈率)中位数"在历史数据上的分位数      |
| quantileInRecent10YearsMiddlePeTtm  | float64 | 当前"TTM(滚动市盈率)中位数"在最近10年数据上的分位数   |
| quantileInAllHistoryAveragePeTtm    | float64 | 当前"TTM(滚动市盈率)等权平均"在历史数据上的分位数     |
| quantileInRecent10YearsAveragePeTtm | float64 | 当前"TTM(滚动市盈率)等权平均"在在最近10年数据上的分位数 |
| quantileInAllHistoryMiddlePeLyr     | float64 | 当前"LYR(静态市盈率)中位数"在历史数据上的分位数      |
| quantileInRecent10YearsMiddlePeLyr  | float64 | 当前"LYR(静态市盈率)中位数"在最近10年数据上的分位数   |
| quantileInAllHistoryAveragePeLyr    | float64 | 当前"LYR(静态市盈率)等权平均"在历史数据上的分位数     |
| quantileInRecent10YearsAveragePeLyr | float64 | 当前"LYR(静态市盈率)等权平均"在最近10年数据上的分位数  |
| close                               | float64 | 沪深300指数                          |

接口示例

```python
import akshare as ak

stock_a_ttm_lyr_df = ak.stock_a_ttm_lyr()
print(stock_a_ttm_lyr_df)
```

数据示例

```
            date  middlePETTM  ...  quantileInRecent10YearsAveragePeLyr    close
0     2005-01-05        28.79  ...                              1.00000     0.00
1     2005-01-06        29.18  ...                              1.00000     0.00
2     2005-01-07        28.73  ...                              0.66667     0.00
3     2005-01-10        28.84  ...                              0.50000     0.00
4     2005-01-11        29.09  ...                              1.00000     0.00
...          ...          ...  ...                                  ...      ...
4795  2024-10-13        29.58  ...                              0.15534  3887.17
4796  2024-10-14        30.34  ...                              0.20725  3961.34
4797  2024-10-15        29.75  ...                              0.18995  3855.99
4798  2024-10-16        29.67  ...                              0.20643  3831.59
4799  2024-10-17        29.56  ...                              0.20107  3788.22
[4800 rows x 14 columns]
```

#### A 股等权重与中位数市净率

接口: stock_a_all_pb

目标地址: <https://www.legulegu.com/stockdata/all-pb>

描述: 乐咕乐股-A 股等权重与中位数市净率

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述 |
|-----|-----|----|
| -   | -   | -  |

输出参数

| 名称                                          | 类型      | 描述                     |
|---------------------------------------------|---------|------------------------|
| date                                        | object  | 日期                     |
| middlePB                                    | float64 | 全部A股市净率中位数             |
| equalWeightAveragePB                        | float64 | 全部A股市净率等权平均            |
| close                                       | float64 | 上证指数                   |
| quantileInAllHistoryMiddlePB                | float64 | 当前市净率中位数在历史数据上的分位数     |
| quantileInRecent10YearsMiddlePB             | float64 | 当前市净率中位数在最近10年数据上的分位数  |
| quantileInAllHistoryEqualWeightAveragePB    | float64 | 当前市净率等权平均在历史数据上的分位数    |
| quantileInRecent10YearsEqualWeightAveragePB | float64 | 当前市净率等权平均在最近10年数据上的分位数 |

接口示例

```python
import akshare as ak

stock_a_all_pb_df = ak.stock_a_all_pb()
print(stock_a_all_pb_df)
```

数据示例

```
            date  ...  quantileInRecent10YearsEqualWeightAveragePB
0     2005-01-04  ...                                      1.00000
1     2005-01-05  ...                                      1.00000
2     2005-01-06  ...                                      0.66667
3     2005-01-07  ...                                      0.75000
4     2005-01-10  ...                                      1.00000
...          ...  ...                                          ...
4793  2024-10-11  ...                                      0.10763
4794  2024-10-14  ...                                      0.12170
4795  2024-10-15  ...                                      0.11551
4796  2024-10-16  ...                                      0.11840
4797  2024-10-17  ...                                      0.12129
[4798 rows x 8 columns]
```

#### 主板市盈率

接口: stock_market_pe_lg

目标地址: <https://legulegu.com/stockdata/shanghaiPE>

描述: 乐咕乐股-主板市盈率

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述                                                |
|--------|-----|---------------------------------------------------|
| symbol | str | symbol="上证"; choice of {"上证", "深证", "创业板", "科创版"} |

输出参数-上证, 深证, 创业板

| 名称    | 类型      | 描述  |
|-------|---------|-----|
| 日期    | object  | -   |
| 指数    | float64 | -   |
| 平均市盈率 | float64 | -   |

接口示例-上证, 深证, 创业板

```python
import akshare as ak

stock_market_pe_lg_df = ak.stock_market_pe_lg(symbol="上证")
print(stock_market_pe_lg_df)
```

数据示例-上证, 深证, 创业板

```
        日期       指数  平均市盈率
0    1999-01-29  1134.67  34.03
1    1999-02-09  1090.08  33.50
2    1999-03-31  1158.05  34.30
3    1999-04-30  1120.92  34.39
4    1999-05-31  1279.32  35.30
..          ...      ...    ...
306  2024-06-28  2967.40  12.69
307  2024-07-31  2938.75  12.55
308  2024-08-30  2842.21  12.16
309  2024-09-30  3336.50  14.24
310  2024-10-18  3261.56  13.89
[311 rows x 3 columns]
```

输出参数-科创版

| 名称  | 类型      | 描述  |
|-----|---------|-----|
| 日期  | object  | -   |
| 总市值 | float64 | -   |
| 市盈率 | float64 | -   |

接口示例-科创版

```python
import akshare as ak

stock_market_pe_lg_df = ak.stock_market_pe_lg(symbol="科创版")
print(stock_market_pe_lg_df)
```

数据示例-科创版

```
        日期       总市值    市盈率
0     2019-07-22   5293.39  81.43
1     2019-07-23   4821.95  74.18
2     2019-07-24   5135.78  79.00
3     2019-07-25   5373.12  82.65
4     2019-07-26   5000.56  76.92
...          ...       ...    ...
1265  2024-10-14  58559.78  39.19
1266  2024-10-15  56996.68  38.18
1267  2024-10-16  55961.92  37.50
1268  2024-10-17  56181.48  37.54
1269  2024-10-18  61039.80  40.72
[1270 rows x 3 columns]
```

#### 指数市盈率

接口: stock_index_pe_lg

目标地址: <https://legulegu.com/stockdata/sz50-ttm-lyr>

描述: 乐咕乐股-指数市盈率

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述                                                                                                                                  |
|--------|-----|-------------------------------------------------------------------------------------------------------------------------------------|
| symbol | str | symbol="上证50"; choice of {"上证50", "沪深300", "上证380", "创业板50", "中证500", "上证180", "深证红利", "深证100", "中证1000", "上证红利", "中证100", "中证800"} |

输出参数

| 名称       | 类型      | 描述  |
|----------|---------|-----|
| 日期       | object  | -   |
| 指数       | float64 | -   |
| 等权静态市盈率  | float64 | -   |
| 静态市盈率    | float64 | -   |
| 静态市盈率中位数 | float64 | -   |
| 等权滚动市盈率  | float64 | -   |
| 滚动市盈率    | float64 | -   |
| 滚动市盈率中位数 | float64 | -   |

接口示例

```python
import akshare as ak

stock_index_pe_lg_df = ak.stock_index_pe_lg(symbol="上证50")
print(stock_index_pe_lg_df)
```

数据示例

```
      日期         指数  等权静态市盈率  静态市盈率  静态市盈率中位数  等权滚动市盈率  滚动市盈率  滚动市盈率中位数
0     2005-01-05   831.43    32.48  20.69     27.02    29.52  14.93     18.97
1     2005-01-06   822.50    32.57  20.37     27.00    29.74  14.69     18.81
2     2005-01-07   823.62    32.59  20.50     27.10    29.81  14.79     18.73
3     2005-01-10   832.99    32.99  20.58     27.29    30.13  14.83     19.07
4     2005-01-11   837.86    33.13  20.69     27.25    30.26  14.91     19.26
...          ...      ...      ...    ...       ...      ...    ...       ...
4800  2024-10-14  2723.18    33.03  11.48     17.17    32.32  11.27     17.79
4801  2024-10-15  2655.12    32.16  11.17     16.68    31.50  10.97     17.43
4802  2024-10-16  2650.18    31.65  11.19     16.42    30.20  11.00     17.45
4803  2024-10-17  2610.47    31.47  11.05     16.13    30.05  10.86     16.94
4804  2024-10-18  2681.91    33.61  11.29     16.60    32.22  11.09     17.35
[4805 rows x 8 columns]
```

#### 主板市净率

接口: stock_market_pb_lg

目标地址: <https://legulegu.com/stockdata/shanghaiPB>

描述: 乐咕乐股-主板市净率

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述                                                |
|--------|-----|---------------------------------------------------|
| symbol | str | symbol="上证"; choice of {"上证", "深证", "创业板", "科创版"} |

输出参数

| 名称     | 类型      | 描述  |
|--------|---------|-----|
| 日期     | object  | -   |
| 指数     | float64 | -   |
| 市净率    | float64 | -   |
| 等权市净率  | float64 | -   |
| 市净率中位数 | float64 | -   |

接口示例

```python
import akshare as ak

stock_market_pb_lg_df = ak.stock_market_pb_lg(symbol="上证")
print(stock_market_pb_lg_df)
```

数据示例

```
          日期     指数     市净率  等权市净率 市净率中位数
0     2005-01-04  3025.42  2.09   2.57    2.06
1     2005-01-05  3052.86  2.09   2.58    2.06
2     2005-01-06  3028.73  2.06   2.56    2.05
3     2005-01-07  3035.59  2.06   2.57    2.06
4     2005-01-10  3062.73  2.08   2.60    2.08
          ...      ...   ...    ...     ...
4686  2024-04-19  9279.46  1.79   2.65    1.87
4687  2024-04-22  9239.14  1.78   2.62    1.84
4688  2024-04-23  9183.14  1.77   2.62    1.86
4689  2024-04-24  9251.13  1.78   2.67    1.89
4690  2024-04-25  9264.48  1.78   2.69    1.90
[4691 rows x 5 columns]
```

#### 指数市净率

接口: stock_index_pb_lg

目标地址: <https://legulegu.com/stockdata/sz50-pb>

描述: 乐咕乐股-指数市净率

限量: 单次获取指定 symbol 的所有数据

输入参数

| 名称     | 类型  | 描述                                                                                                                                  |
|--------|-----|-------------------------------------------------------------------------------------------------------------------------------------|
| symbol | str | symbol="上证50"; choice of {"上证50", "沪深300", "上证380", "创业板50", "中证500", "上证180", "深证红利", "深证100", "中证1000", "上证红利", "中证100", "中证800"} |

输出参数

| 名称     | 类型      | 描述  |
|--------|---------|-----|
| 日期     | object  | -   |
| 指数     | float64 | -   |
| 市净率    | float64 | -   |
| 等权市净率  | float64 | -   |
| 市净率中位数 | float64 | -   |

接口示例

```python
import akshare as ak

stock_index_pb_lg_df = ak.stock_index_pb_lg(symbol="上证50")
print(stock_index_pb_lg_df)
```

数据示例

```
          日期     指数   市净率  等权市净率  市净率中位数
0     2005-01-05   831.43  2.10   2.35    2.12
1     2005-01-06   822.50  2.07   2.34    2.12
2     2005-01-07   823.62  2.08   2.34    2.13
3     2005-01-10   832.99  2.08   2.37    2.16
4     2005-01-11   837.86  2.10   2.38    2.16
          ...      ...   ...    ...     ...
4686  2024-04-22  2424.75  1.14   2.97    1.92
4687  2024-04-23  2413.74  1.14   2.96    1.90
4688  2024-04-24  2424.12  1.14   2.98    1.90
4689  2024-04-25  2431.62  1.14   2.96    1.90
4690  2024-04-26  2461.86  1.15   2.96    1.94
[4691 rows x 5 columns]
```

#### A 股估值指标

接口: stock_zh_valuation_baidu

目标地址: <https://gushitong.baidu.com/stock/ab-002044>

描述: 百度股市通-A 股-财务报表-估值数据

限量: 单次获取指定 symbol 和 indicator 的所有历史数据

输入参数

| 名称        | 类型  | 描述                                                                     |
|-----------|-----|------------------------------------------------------------------------|
| symbol    | str | symbol="002044"; A 股代码                                                 |
| indicator | str | indicator="总市值"; choice of {"总市值", "市盈率(TTM)", "市盈率(静)", "市净率", "市现率"} |
| period    | str | period="近一年"; choice of {"近一年", "近三年", "近五年", "近十年", "全部"}             |

输出参数

| 名称    | 类型      | 描述  |
|-------|---------|-----|
| date  | object  | -   |
| value | float64 | -   |

接口示例

```python
import akshare as ak

stock_zh_valuation_baidu_df = ak.stock_zh_valuation_baidu(symbol="002044", indicator="总市值", period="近一年")
print(stock_zh_valuation_baidu_df)
```

数据示例

```
           date   value
0    2023-05-29  245.42
1    2023-05-30  246.60
2    2023-05-31  249.73
3    2023-06-01  253.64
4    2023-06-02  259.52
..          ...     ...
362  2024-05-25  167.92
363  2024-05-26  167.92
364  2024-05-27  165.96
365  2024-05-28  164.40
366  2024-05-29  167.14
[367 rows x 2 columns]
```

#### 个股估值

接口: stock_value_em

目标地址: <https://data.eastmoney.com/gzfx/detail/300766.html>

描述: 东方财富网-数据中心-估值分析-每日互动-每日互动-估值分析

限量: 单次获取指定 symbol 的所有历史数据

输入参数

| 名称        | 类型  | 描述                                                                     |
|-----------|-----|------------------------------------------------------------------------|
| symbol    | str | symbol="002044"; A 股代码                                                 |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 数据日期    | object  | -       |
| 当日收盘价   | float64 | 注意单位: 元 |
| 当日涨跌幅   | float64 | 注意单位: % |
| 总市值     | float64 | 注意单位: 元 |
| 流通市值    | float64 | 注意单位: 元 |
| 总股本     | float64 | 注意单位: 股 |
| 流通股本    | float64 | -       |
| PE(TTM) | float64 | -       |
| PE(静)   | float64 | -       |
| 市净率     | float64 | -       |
| PEG值    | float64 | -       |
| 市现率     | float64 | -       |
| 市销率     | float64 | -       |

接口示例

```python
import akshare as ak

stock_value_em_df = ak.stock_value_em(symbol="300766")
print(stock_value_em_df)
```

数据示例

```
        数据日期  当日收盘价   当日涨跌幅  ...  PEG值      市现率       市销率
0     2019-03-25  18.84  44.036697  ... -1.428399   34.410716  13.976938
1     2019-03-26  20.72   9.978769  ... -1.570936   37.844482  15.371664
2     2019-03-27  22.79   9.990347  ... -1.727878   41.625277  16.907347
3     2019-03-28  25.07  10.004388  ... -1.900741   45.789631  18.598823
4     2019-03-29  27.58  10.011966  ... -2.091043   50.374074  20.460931
...          ...    ...        ...  ...       ...         ...        ...
1373  2024-11-20  15.30   6.397775  ... -0.055226 -128.339565  13.236721
1374  2024-11-21  15.33   0.196078  ... -0.055334 -128.591212  13.262675
1375  2024-11-22  14.82  -3.326810  ... -0.053493 -124.313226  12.821451
1376  2024-11-25  14.80  -0.134953  ... -0.053421 -124.145462  12.804148
1377  2024-11-26  14.85   0.337838  ... -0.053601 -124.564872  12.847406
[1378 rows x 13 columns]
```

#### 涨跌投票

接口: stock_zh_vote_baidu

目标地址: <https://gushitong.baidu.com/index/ab-000001>

描述: 百度股市通- A 股或指数-股评-投票

限量: 单次获取指定 symbol 和 indicator 的所有数据

输入参数

| 名称        | 类型  | 描述                                     |
|-----------|-----|----------------------------------------|
| symbol    | str | symbol="000001"; A 股股票或指数代码            |
| indicator | str | indicator="指数"; choice of {"指数", "股票"} |

输出参数

| 名称   | 类型     | 描述  |
|------|--------|-----|
| 周期   | object | -   |
| 看涨   | object | -   |
| 看跌   | object | -   |
| 看涨比例 | object | -   |
| 看跌比例 | object | -   |

接口示例

```python
import akshare as ak

stock_zh_vote_baidu_df = ak.stock_zh_vote_baidu(symbol="000001", indicator="指数")
print(stock_zh_vote_baidu_df)
```

数据示例

```
   周期    看涨      看跌 看涨比例 看跌比例
0  今日    1531    4765  24%  76%
1  本周    1531    4765  24%  76%
2  本月    2442    7109  26%  74%
3  今年  15.04万  36.01万  29%  71%
```

#### 港股个股指标

P.S. 该数据源暂未更新数据

接口: stock_hk_indicator_eniu

目标地址: <https://eniu.com/gu/hk01093/roe>

描述: 亿牛网-港股个股指标: 市盈率, 市净率, 股息率, ROE, 市值

限量: 单次获取指定 symbol 和 indicator 的所有历史数据

输入参数

| 名称        | 类型  | 描述                                                                                              |
|-----------|-----|-------------------------------------------------------------------------------------------------|
| symbol    | str | symbol="hk01093"; 可通过调用 **ak.stock_hk_indicator_eniu(symbol="hk01093", indicator="港股")** 获取股票代码 |
| indicator | str | indicator="市盈率"; choice of {"港股", "市盈率", "市净率", "股息率", "ROE", "市值"}                             |

输出参数

| 名称  | 类型  | 描述              |
|-----|-----|-----------------|
| -   | -   | 根据 indicator 而异 |

接口示例-ROE

```python
import akshare as ak

stock_hk_indicator_eniu_df = ak.stock_hk_indicator_eniu(symbol="hk01093", indicator="市净率")
print(stock_hk_indicator_eniu_df)
```

数据示例-ROE

```
            date    pb  price
0     2000-01-03  1.17   0.00
1     2000-01-04  1.24   0.00
2     2000-01-05  1.19   0.00
3     2000-01-06  1.06   0.00
4     2000-01-07  1.08   0.00
          ...   ...    ...
5041  2020-08-07  7.31  15.74
5042  2020-08-10  7.22  15.54
5043  2020-08-11  7.31  15.74
5044  2020-08-12  7.15  15.40
5045  2020-08-13  7.18  15.46
```

#### 港股估值指标

接口: stock_hk_valuation_baidu

目标地址: <https://gushitong.baidu.com/stock/hk-06969>

描述: 百度股市通-港股-财务报表-估值数据

限量: 单次获取指定 symbol 的指定 indicator 的特定 period 的历史数据

输入参数

| 名称        | 类型  | 描述                                                                     |
|-----------|-----|------------------------------------------------------------------------|
| symbol    | str | symbol="02358"; 港股代码                                                   |
| indicator | str | indicator="总市值"; choice of {"总市值", "市盈率(TTM)", "市盈率(静)", "市净率", "市现率"} |
| period    | str | period="近一年"; choice of {"近一年", "近三年", "全部"}                           |

输出参数

| 名称    | 类型      | 描述  |
|-------|---------|-----|
| date  | object  | -   |
| value | float64 | -   |

接口示例

```python
import akshare as ak

stock_hk_valuation_baidu_df = ak.stock_hk_valuation_baidu(symbol="06969", indicator="总市值", period="近一年")
print(stock_hk_valuation_baidu_df)
```

数据示例

```
           date   value
0    2023-11-21  427.15
1    2023-11-22  428.99
2    2023-11-23  441.88
3    2023-11-24  430.83
4    2023-11-25  430.83
..          ...     ...
362  2024-11-17  602.46
363  2024-11-18  632.73
364  2024-11-19  679.69
365  2024-11-20  713.06
366  2024-11-21  688.35
[367 rows x 2 columns]
```

#### 创新高和新低的股票数量

接口: stock_a_high_low_statistics

目标地址: <https://www.legulegu.com/stockdata/high-low-statistics>

描述: 不同市场的创新高和新低的股票数量

限量: 单次获取指定 market 的近两年的历史数据

输入参数

| 名称     | 类型  | 描述                                                                                |
|--------|-----|-----------------------------------------------------------------------------------|
| symbol | str | symbol="all"; {"all": "全部A股", "sz50": "上证50", "hs300": "沪深300", "zz500": "中证500"} |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| date    | object  | 交易日     |
| close   | float64 | 相关指数收盘价 |
| high20  | int64   | 20日新高   |
| low20   | int64   | 20日新低   |
| high60  | int64   | 60日新高   |
| low60   | int64   | 60日新低   |
| high120 | int64   | 120日新高  |
| low120  | int64   | 120日新低  |

接口示例

```python
import akshare as ak

stock_a_high_low_statistics_df = ak.stock_a_high_low_statistics(symbol="all")
print(stock_a_high_low_statistics_df)
```

数据示例

```
           date    close  high20  low20  high60  low60  high120  low120
0    2021-08-18  3485.29     441    293     212    143      143      67
1    2021-08-19  3465.55     303    332     162    189      132     106
2    2021-08-20  3427.33     361    628     214    399      168     227
3    2021-08-23  3477.13     827    102     417     68      332      44
4    2021-08-24  3514.47     843    128     399     83      306      50
..          ...      ...     ...    ...     ...    ...      ...     ...
495  2023-09-04  3177.06     811     65     269     30      139      17
496  2023-09-05  3154.37     512    203     125     57       70      24
497  2023-09-06  3122.35     254    240     103    125       74      65
498  2023-09-06  3158.08     867    200     169     84       91      44
499  2023-09-08  3116.72     393    513     104    281       60     167
[500 rows x 8 columns]
```

#### 破净股统计

接口: stock_a_below_net_asset_statistics

目标地址: <https://www.legulegu.com/stockdata/below-net-asset-statistics>

描述: 乐咕乐股-A 股破净股统计数据

限量: 单次获取指定 symbol 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                          |
|--------|-----|-------------------------------------------------------------|
| symbol | str | symbol="全部A股"; choice of {"全部A股", "沪深300", "上证50", "中证500"} |

输出参数-全部A股

| 名称                    | 类型      | 描述    |
|-----------------------|---------|-------|
| date                  | object  | 交易日   |
| below_net_asset       | float64 | 破净股家数 |
| total_company         | float64 | 总公司数  |
| below_net_asset_ratio | float64 | 破净股比率 |

接口示例-全部 A 股

```python
import akshare as ak

stock_a_below_net_asset_statistics_df = ak.stock_a_below_net_asset_statistics(symbol="全部A股")
print(stock_a_below_net_asset_statistics_df)
```

数据示例-全部 A 股

```
            date  below_net_asset  total_company  below_net_asset_ratio
0     2005-01-04               36           1352                 0.0266
1     2005-01-05               31           1352                 0.0229
2     2005-01-06               32           1352                 0.0237
3     2005-01-09               33           1352                 0.0244
4     2005-01-10               29           1352                 0.0214
          ...              ...            ...                    ...
4682  2024-04-21              577           5114                 0.1128
4683  2024-04-22              561           5114                 0.1097
4684  2024-04-23              551           5114                 0.1077
4685  2024-04-24              533           5114                 0.1042
4686  2024-04-25              516           5113                 0.1009
[4687 rows x 4 columns]
```

输出参数-沪深 300

| 名称                    | 类型      | 描述    |
|-----------------------|---------|-------|
| date                  | object  | 交易日   |
| below_net_asset       | float64 | 破净股家数 |
| total_company         | float64 | 总公司数  |
| below_net_asset_ratio | float64 | 破净股比率 |

接口示例-沪深 300

```python
import akshare as ak

stock_a_below_net_asset_statistics_df = ak.stock_a_below_net_asset_statistics(symbol="沪深300")
print(stock_a_below_net_asset_statistics_df)
```

数据示例-沪深 300

```
            date  below_net_asset  total_company  below_net_asset_ratio
0     2005-04-07               22            299                 0.0736
1     2005-04-10               21            299                 0.0702
2     2005-04-11               23            299                 0.0769
3     2005-04-12               20            299                 0.0669
4     2005-04-13               22            299                 0.0736
          ...              ...            ...                    ...
4627  2024-04-21               63            300                 0.2100
4628  2024-04-22               63            300                 0.2100
4629  2024-04-23               63            300                 0.2100
4630  2024-04-24               63            300                 0.2100
4631  2024-04-25               62            300                 0.2067
[4632 rows x 4 columns]
```

#### 基金持股

接口: stock_report_fund_hold

目标地址: <http://data.eastmoney.com/zlsj/2020-06-30-1-2.html>

描述: 东方财富网-数据中心-主力数据-基金持仓

限量: 单次返回指定 symbol 和 date 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                          |
|--------|-----|-----------------------------------------------------------------------------|
| symbol | str | symbol="基金持仓"; choice of {"基金持仓", "QFII持仓", "社保持仓", "券商持仓", "保险持仓", "信托持仓"} |
| date   | str | date="20200630"; 财报发布日期, xxxx-03-31, xxxx-06-30, xxxx-09-30, xxxx-12-31     |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 序号     | int64   | -       |
| 股票代码   | object  | -       |
| 股票简称   | object  | -       |
| 持有基金家数 | int64   | 注意单位: 家 |
| 持股总数   | int64   | 注意单位: 股 |
| 持股市值   | float64 | 注意单位: 元 |
| 持股变化   | object  | -       |
| 持股变动数值 | int64   | 注意单位: 股 |
| 持股变动比例 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_report_fund_hold_df = ak.stock_report_fund_hold(symbol="基金持仓", date="20200630")
print(stock_report_fund_hold_df)
```

数据示例

```
        序号    股票代码  股票简称  ... 持股变化   持股变动数值             持股变动比例
0        1  300846  首都在线  ...   新进  3024892         0.00219976
1        2  300843  胜蓝股份  ...   新进  1984496         0.00293824
2        3  300842  帝科股份  ...   新进  1190928   1.19092800000001
3        4  600956  新天绿能  ...   新进  6460517  0.167734880000004
4        5  300845  捷安高科  ...   新进  1211353         0.00388496
    ...     ...   ...  ...  ...      ...                ...
3555  3556  300752  隆利科技  ...   增持     3100         0.00258868
3556  3557  300778   新城市  ...   新进      125           0.000125
3557  3558  300786  国林科技  ...   增持     2800         0.00327715
3558  3559  300818  耐普矿机  ...   新进      500         0.00071429
3559  3560  688981  中芯国际  ...   新进   139500         0.00255926
```

#### 基金持股明细

接口: stock_report_fund_hold_detail

目标地址: <http://data.eastmoney.com/zlsj/ccjj/2020-12-31-008286.html>

描述: 东方财富网-数据中心-主力数据-基金持仓-基金持仓明细表

限量: 单次返回指定 symbol 和 date 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                      |
|--------|-----|-------------------------------------------------------------------------|
| symbol | str | symbol="005827"; 基金代码                                                   |
| date   | str | date="20200630"; 财报发布日期, xxxx-03-31, xxxx-06-30, xxxx-09-30, xxxx-12-31 |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 序号      | int64   | -       |
| 股票代码    | object  | -       |
| 股票简称    | object  | -       |
| 持股数     | int64   | 注意单位: 股 |
| 持股市值    | float64 | 注意单位: 元 |
| 占总股本比例  | float64 | 注意单位: % |
| 占流通股本比例 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_report_fund_hold_detail_df = ak.stock_report_fund_hold_detail(symbol="005827", date="20201231")
print(stock_report_fund_hold_detail_df)
```

数据示例

```
   序号       股票代码  股票简称       持股数           持股市值 占总股本比例 占流通股本比例
0   1  600519.SH  贵州茅台   3265532     6524532936   0.26    0.26
1   2  300015.SZ  爱尔眼科  32000005  2396480374.45   0.78    0.80
2   3  002415.SZ  海康威视  70000025  3395701212.75   0.75    0.85
3   4  002304.SZ  洋河股份  27200000     6418928000   1.80    2.16
4   5  000858.SZ   五粮液  21858499  6379402933.15   0.56    0.58
5   6  000568.SZ  泸州老窖  27700000     6264632000   1.89    1.89
```

#### 龙虎榜

##### 龙虎榜-东财

###### 龙虎榜详情

接口: stock_lhb_detail_em

目标地址: <https://data.eastmoney.com/stock/tradedetail.html>

描述: 东方财富网-数据中心-龙虎榜单-龙虎榜详情

限量: 单次返回所有历史数据

输入参数

| 名称         | 类型  | 描述                    |
|------------|-----|-----------------------|
| start_date | str | start_date="20220314" |
| end_date   | str | end_date="20220315"   |

输出参数

| 名称       | 类型      | 描述      |
|----------|---------|---------|
| 序号       | int64   | -       |
| 代码       | object  | -       |
| 名称       | object  | -       |
| 上榜日      | object  | -       |
| 解读       | object  | -       |
| 收盘价      | float64 | -       |
| 涨跌幅      | float64 | 注意单位: % |
| 龙虎榜净买额   | float64 | 注意单位: 元 |
| 龙虎榜买入额   | float64 | 注意单位: 元 |
| 龙虎榜卖出额   | float64 | 注意单位: 元 |
| 龙虎榜成交额   | float64 | 注意单位: 元 |
| 市场总成交额   | int64   | 注意单位: 元 |
| 净买额占总成交比 | float64 | 注意单位: % |
| 成交额占总成交比 | float64 | 注意单位: % |
| 换手率      | float64 | 注意单位: % |
| 流通市值     | float64 | 注意单位: 元 |
| 上榜原因     | object  | -       |
| 上榜后1日    | float64 | 注意单位: % |
| 上榜后2日    | float64 | 注意单位: % |
| 上榜后5日    | float64 | 注意单位: % |
| 上榜后10日   | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_lhb_detail_em_df = ak.stock_lhb_detail_em(start_date="20230403", end_date="20230417")
print(stock_lhb_detail_em_df)
```

数据示例

```
      序号  代码    名称    上榜日  ...     上榜后1日      上榜后2日      上榜后5日    上榜后10日
0      1  000021   深科技  2023-04-06  ... -1.304348  -0.193237  -8.212560       NaN
1      2  000021   深科技  2023-04-03  ...  2.338227  12.561175  11.201740  7.667210
2      3  000021   深科技  2023-04-03  ...  2.338227  12.561175  11.201740  7.667210
3      4  000032  深桑达A  2023-04-06  ...  2.087576  -2.214868  -2.265784       NaN
4      5  000063  中兴通讯  2023-04-07  ... -3.783784  -5.270270  -7.027027       NaN
..   ...     ...   ...         ...  ...       ...        ...        ...       ...
630  631  688698  伟创电气  2023-04-12  ... -4.407407  -2.592593        NaN       NaN
631  632  688787  海天瑞声  2023-04-10  ...  2.028249   5.644068   6.073446       NaN
632  633  873593  鼎智科技  2023-04-17  ... -7.805655        NaN        NaN       NaN
633  634  900915  中路B股  2023-04-12  ...  2.981030   1.490515        NaN       NaN
634  635  900915  中路B股  2023-04-03  ...  5.807365   3.824363  12.039660  3.399433
```

###### 个股上榜统计

接口: stock_lhb_stock_statistic_em

目标地址: <https://data.eastmoney.com/stock/tradedetail.html>

描述: 东方财富网-数据中心-龙虎榜单-个股上榜统计

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                                                   |
|--------|-----|------------------------------------------------------|
| symbol | str | symbol="近一月"; choice of {"近一月", "近三月", "近六月", "近一年"} |

输出参数

| 名称      | 类型      | 描述 |
|---------|---------|----|
| 序号      | int64   | -  |
| 代码      | object  | -  |
| 名称      | object  | -  |
| 最近上榜日   | object  | -  |
| 收盘价     | float64 | -  |
| 涨跌幅     | float64 | -  |
| 上榜次数    | int64   | -  |
| 龙虎榜净买额  | float64 | -  |
| 龙虎榜买入额  | float64 | -  |
| 龙虎榜卖出额  | float64 | -  |
| 龙虎榜总成交额 | float64 | -  |
| 买方机构次数  | int64   | -  |
| 卖方机构次数  | int64   | -  |
| 机构买入净额  | float64 | -  |
| 机构买入总额  | float64 | -  |
| 机构卖出总额  | float64 | -  |
| 近1个月涨跌幅 | float64 | -  |
| 近3个月涨跌幅 | float64 | -  |
| 近6个月涨跌幅 | float64 | -  |
| 近1年涨跌幅  | float64 | -  |

接口示例

```python
import akshare as ak

stock_lhb_stock_statistic_em_df = ak.stock_lhb_stock_statistic_em(symbol="近一月")
print(stock_lhb_stock_statistic_em_df)
```

数据示例

```
      序号  代码    名称     最近上榜日  ...   近1个月涨跌幅  近3个月涨跌幅 近6个月涨跌幅  近1年涨跌幅
0      1  605180  华生科技  2024-04-18  ...  39.940828  -8.274079   7.744875   19.350450
1      2  603603  退市博天  2024-04-18  ... -61.000000 -61.386139 -86.315789  -90.250000
2      3  002089   新海退  2024-04-17  ... -69.230769 -76.699029 -80.645161  -75.510204
3      4  000506  中润资源  2024-04-19  ...  55.844156  61.725067  26.849894   11.940299
4      5  301500  飞南资源  2024-04-19  ...  16.005874  21.788284   3.765324   -1.126408
..   ...     ...   ...         ...  ...        ...        ...        ...         ...
653  654  603322  超讯通信  2024-03-21  ...  22.253172   4.969439  39.035551  127.403569
654  655  603528  多伦科技  2024-03-21  ...  57.685353  -4.803493  20.275862   12.761000
655  656  605296  神农集团  2024-03-21  ...  19.154229  10.477759  59.590671   33.666462
656  657  688103  国力股份  2024-03-21  ...  22.362869 -16.219563 -24.842651  -32.964050
657  658  900921  丹科B股  2024-03-21  ...   2.097902   8.955224   5.797101  -18.435754
[658 rows x 20 columns]
```

###### 机构买卖每日统计

接口: stock_lhb_jgmmtj_em

目标地址: <https://data.eastmoney.com/stock/jgmmtj.html>

描述: 东方财富网-数据中心-龙虎榜单-机构买卖每日统计

限量: 单次返回所有历史数据

输入参数

| 名称         | 类型  | 描述                    |
|------------|-----|-----------------------|
| start_date | str | start_date="20240417" |
| end_date   | str | end_date="20240430"   |

输出参数

| 名称          | 类型      | 描述       |
|-------------|---------|----------|
| 序号          | int64   | -        |
| 代码          | object  | -        |
| 名称          | object  | -        |
| 收盘价         | float64 | -        |
| 涨跌幅         | float64 | -        |
| 买方机构数       | float64 | -        |
| 卖方机构数       | float64 | -        |
| 机构买入总额      | float64 | 注意单位: 元  |
| 机构卖出总额      | float64 | 注意单位: 元  |
| 机构买入净额      | float64 | 注意单位: 元  |
| 市场总成交额      | float64 | 注意单位: 元  |
| 机构净买额占总成交额比 | float64 | -        |
| 换手率         | float64 | -        |
| 流通市值        | float64 | 注意单位: 亿元 |
| 上榜原因        | object  | -        |
| 上榜日期        | object  | -        |

接口示例

```python
import akshare as ak

stock_lhb_jgmmtj_em_df = ak.stock_lhb_jgmmtj_em(start_date="20240417", end_date="20240430")
print(stock_lhb_jgmmtj_em_df)
```

数据示例

```
      序号  代码  ...                                    上榜原因                   上榜日期
0      1  600919  ...           有价格涨跌幅限制的日收盘价格跌幅偏离值达到7%的前五只证券  2024-04-26
1      2  603486  ...  非ST、*ST和S证券连续三个交易日内收盘价格涨幅偏离值累计达到20%的证券  2024-04-22
2      3  688019  ...             有价格涨跌幅限制的日收盘价格涨幅达到15%的前五只证券  2024-04-29
3      4  002920  ...                        日跌幅偏离值达到7%的前5只证券  2024-04-19
4      5  000628  ...                         日换手率达到20%的前5只证券  2024-04-29
..   ...     ...  ...                                     ...         ...
334  335  000628  ...                连续三个交易日内，涨幅偏离值累计达到20%的证券  2024-04-26
335  336  000099  ...                        日涨幅偏离值达到7%的前5只证券  2024-04-18
336  337  688027  ...             有价格涨跌幅限制的日收盘价格涨幅达到15%的前五只证券  2024-04-26
337  338  002085  ...                        日涨幅偏离值达到7%的前5只证券  2024-04-24
338  339  603882  ...           有价格涨跌幅限制的日收盘价格跌幅偏离值达到7%的前五只证券  2024-04-26
[339 rows x 16 columns]
```

###### 机构席位追踪

接口: stock_lhb_jgstatistic_em

目标地址: <https://data.eastmoney.com/stock/jgstatistic.html>

描述: 东方财富网-数据中心-龙虎榜单-机构席位追踪

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                                                   |
|--------|-----|------------------------------------------------------|
| symbol | str | symbol="近一月"; choice of {"近一月", "近三月", "近六月", "近一年"} |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 序号      | int64   | -       |
| 代码      | object  | -       |
| 名称      | object  | -       |
| 收盘价     | float64 | -       |
| 涨跌幅     | float64 | 注意单位: % |
| 龙虎榜成交金额 | float64 | 注意单位: 元 |
| 上榜次数    | int64   | -       |
| 机构买入额   | float64 | 注意单位: 元 |
| 机构买入次数  | int64   | -       |
| 机构卖出额   | float64 | 注意单位: 元 |
| 机构卖出次数  | int64   | -       |
| 机构净买额   | float64 | 注意单位: 元 |
| 近1个月涨跌幅 | float64 | 注意单位: % |
| 近3个月涨跌幅 | float64 | 注意单位: % |
| 近6个月涨跌幅 | float64 | 注意单位: % |
| 近1年涨跌幅  | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_lhb_jgstatistic_em_df = ak.stock_lhb_jgstatistic_em(symbol="近一月")
print(stock_lhb_jgstatistic_em_df)
```

数据示例

```
    序号   代码    名称    收盘价  ...   近1个月涨跌幅  近3个月涨跌幅  近6个月涨跌幅  近1年涨跌幅
0      1  000099  中信海直  22.28  ...   41.730280  142.966194  179.197995  196.852398
1      2  000506  中润资源   5.40  ...   27.962085   45.945946   13.924051   -1.459854
2      3  301500  飞南资源  23.90  ...   18.199802   25.459318    5.752212   -0.292032
3      4  001376  百通能源  20.05  ...   15.537337   10.231084  344.168612  344.168612
4      5  300139  晓程科技  13.70  ...   56.930126   50.715072   27.205200   22.759857
..   ...     ...   ...    ...  ...         ...         ...         ...         ...
366  367  688691  灿芯股份  50.37  ...  153.625378  153.625378  153.625378  153.625378
367  368  688701  卓锦股份   4.80  ...  -20.265781  -47.426068  -45.080092  -43.195266
368  369  830839  万通液压  10.99  ...   -8.263773   -2.397869   45.370370   77.031095
369  370  835438   戈碧迦  26.93  ...  169.300000  169.300000  169.300000  169.300000
370  371  837006  晟楠科技  14.20  ...   -0.350877   -5.396402   40.454995   74.433640
[371 rows x 16 columns]
```

###### 每日活跃营业部

接口: stock_lhb_hyyyb_em

目标地址: <https://data.eastmoney.com/stock/hyyyb.html>

描述: 东方财富网-数据中心-龙虎榜单-每日活跃营业部

限量: 单次返回所有历史数据

输入参数

| 名称         | 类型  | 描述                    |
|------------|-----|-----------------------|
| start_date | str | start_date="20220311" |
| end_date   | str | end_date="20220315"   |

输出参数

| 名称    | 类型      | 描述      |
|-------|---------|---------|
| 序号    | int64   | -       |
| 营业部名称 | object  | -       |
| 上榜日   | object  | -       |
| 买入个股数 | float64 | -       |
| 卖出个股数 | float64 | -       |
| 买入总金额 | float64 | 注意单位: 元 |
| 卖出总金额 | float64 | 注意单位: 元 |
| 总买卖净额 | float64 | 注意单位: 元 |
| 买入股票  | object  | -       |

接口示例

```python
import akshare as ak

stock_lhb_hyyyb_em_df = ak.stock_lhb_hyyyb_em(start_date="20220324", end_date="20220324")
print(stock_lhb_hyyyb_em_df)
```

数据示例

```
       序号  ...                                               买入股票
0        1  ...  中信海直 高新发展 张裕A 新乡化纤 宗申动力 湖南黄金 桂林三金 科华数据 柘中股份 *S...
1        2  ...  中信海直 焦作万方 北方铜业 钱江摩托 新乡化纤 ST中南 百通能源 宗申动力 万丰奥威 百...
2        3  ...                                               宗申动力
3        4  ...                                               罗博特科
4        5  ...                                          中科通达 神州信息
...    ...  ...                                                ...
7532  7533  ...  万科A 中信海直 神州信息 高新发展 康冠科技 宗申动力 万丰奥威 沃尔核材 江特电机 雪迪...
7533  7534  ...  中信海直 我爱我家 长安汽车 高新发展 天保基建 万丰奥威 荣盛发展 百川股份 万安科技 奥...
7534  7535  ...                                               长安汽车
7535  7536  ...  双良节能 鲁信创投 江苏银行 太平洋 东方材料 日出东方 金域医学 国盾量子 信安世纪 财富...
7536  7537  ...                                          长安汽车 荣盛发展
[7537 rows x 9 columns]
```

#### 营业部详情数据-东财

接口: stock_lhb_yyb_detail_em

目标地址: <https://data.eastmoney.com/stock/lhb/yyb/10188715.html>

描述: 东方财富网-数据中心-龙虎榜单-营业部历史交易明细-营业部交易明细

限量: 单次返回指定营业部的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                        |
|--------|-----|-----------------------------------------------------------|
| symbol | str | symbol="10026729"; 营业部代码, 通过 ak.stock_lhb_hyyyb_em() 接口获取 |

输出参数

| 名称       | 类型      | 描述                     |
|----------|---------|------------------------|
| 序号       | int64   | -                      |
| 营业部代码    | object  | -                      |
| 营业部名称    | object  | -                      |
| 营业部简称    | object  | -                      |
| 交易日期     | object  | -                      |
| 股票代码     | object  | -                      |
| 股票名称     | object  | -                      |
| 涨跌幅      | float64 | 注意单位: %                |
| 买入金额     | float64 | 注意单位: 元                |
| 卖出金额     | float64 | 注意单位: 元                |
| 净额       | float64 | 注意单位: 元                |
| 上榜原因     | object  | -                      |
| 1日后涨跌幅   | float64 | 注意单位: %                |
| 2日后涨跌幅   | float64 | 注意单位: %                |
| 3日后涨跌幅   | float64 | 注意单位: %                |
| 5日后涨跌幅   | float64 | 注意单位: %                |
| 10日后涨跌幅  | float64 | 注意单位: %                |
| 20日后涨跌幅  | float64 | 注意单位: %                |
| 30日后涨跌幅  | float64 | 注意单位: %                |

接口示例

```python
import akshare as ak

stock_lhb_yyb_detail_em_df = ak.stock_lhb_yyb_detail_em(symbol="10188715")
print(stock_lhb_yyb_detail_em_df)
```

数据示例

```
     序号  营业部代码                      营业部名称  ...    10日后涨跌幅    20日后涨跌幅    30日后涨跌幅
0      1  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ... -18.448276        NaN        NaN
1      2  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ... -16.309524 -32.023810        NaN
2      3  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...  -0.361011   2.045728 -12.033694
3      4  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...   8.633094  14.388489  -0.719424
4      5  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...  13.247863  38.632479  22.564103
..   ...       ...                       ...  ...        ...        ...        ...
97    98  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...  -2.818991  -9.792285  -1.483680
98    99  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...  12.643678  24.856322  30.747126
99   100  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...  84.564546  58.426793  58.604601
100  101  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ...   6.680370  -7.502569  -6.269270
101  102  10188715  东方证券股份有限公司上海普陀区云岭东路证券营业部  ... -19.966159 -20.135364  -9.983080
[102 rows x 19 columns]
```

###### 营业部排行

接口: stock_lhb_yybph_em

目标地址: <https://data.eastmoney.com/stock/yybph.html>

描述: 东方财富网-数据中心-龙虎榜单-营业部排行

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                                                   |
|--------|-----|------------------------------------------------------|
| symbol | str | symbol="近一月"; choice of {"近一月", "近三月", "近六月", "近一年"} |

输出参数

| 名称          | 类型      | 描述      |
|-------------|---------|---------|
| 序号          | int64   | -       |
| 营业部名称       | object  | -       |
| 上榜后1天-买入次数  | int64   | -       |
| 上榜后1天-平均涨幅  | float64 | 注意单位: % |
| 上榜后1天-上涨概率  | float64 | 注意单位: % |
| 上榜后2天-买入次数  | int64   | -       |
| 上榜后2天-平均涨幅  | float64 | 注意单位: % |
| 上榜后2天-上涨概率  | float64 | 注意单位: % |
| 上榜后3天-买入次数  | int64   | -       |
| 上榜后3天-平均涨幅  | float64 | 注意单位: % |
| 上榜后3天-上涨概率  | float64 | 注意单位: % |
| 上榜后4天-买入次数  | int64   | -       |
| 上榜后4天-平均涨幅  | float64 | 注意单位: % |
| 上榜后4天-上涨概率  | float64 | 注意单位: % |
| 上榜后10天-买入次数 | int64   | -       |
| 上榜后10天-平均涨幅 | float64 | 注意单位: % |
| 上榜后10天-上涨概率 | float64 | 注意单位: % |

接口示例

```python
import akshare as ak

stock_lhb_yybph_em_df = ak.stock_lhb_yybph_em(symbol="近一月")
print(stock_lhb_yybph_em_df)
```

数据示例

```
      序号               营业部名称  ...  上榜后10天-平均涨幅  上榜后10天-上涨概率
0        1  东方财富证券拉萨东环路第二证券营业部  ...   -10.314787    26.900585
1        2    东方财富证券拉萨八一路证券营业部  ...   -11.566581    19.161677
2        3  东方财富证券拉萨团结路第二证券营业部  ...    -9.394130    30.147059
3        4  东方财富证券拉萨团结路第一证券营业部  ...   -10.351127    20.833333
4        5               深股通专用  ...    -4.880778    30.769231
...    ...                 ...  ...          ...          ...
1619  1620   中银国际证券焦作解放东路证券营业部  ...     8.383234   100.000000
1620  1621    华西证券北京马家堡东路证券营业部  ...   -14.800262     0.000000
1621  1622      平安证券东莞石竹路证券营业部  ...     0.000000     0.000000
1622  1623  中国银河证券北京东四环南路证券营业部  ...     0.000000     0.000000
1623  1624      招商证券郑州北龙湖证券营业部  ...     9.370988   100.000000
[1624 rows x 17 columns]
```

###### 营业部统计

接口: stock_lhb_traderstatistic_em

目标地址: <https://data.eastmoney.com/stock/traderstatistic.html>

描述: 东方财富网-数据中心-龙虎榜单-营业部统计

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                                                   |
|--------|-----|------------------------------------------------------|
| symbol | str | symbol="近一月"; choice of {"近一月", "近三月", "近六月", "近一年"} |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 序号      | int64   | -       |
| 营业部名称   | object  | -       |
| 龙虎榜成交金额 | float64 | -       |
| 上榜次数    | int64   | -       |
| 买入额     | float64 | 注意单位: 元 |
| 买入次数    | int64   | -       |
| 卖出额     | float64 | 注意单位: 元 |
| 卖出次数    | int64   | -       |

接口示例

```python
import akshare as ak

stock_lhb_traderstatistic_em_df = ak.stock_lhb_traderstatistic_em(symbol="近一月")
print(stock_lhb_traderstatistic_em_df)
```

数据示例

```
    序号                     营业部名称       龙虎榜成交金额  ...  买入次数           卖出额  卖出次数
0        1                     深股通专用  2.143017e+10  ...   269  1.116966e+10   269
1        2     华宝证券股份有限公司上海东大名路证券营业部  1.043461e+10  ...    46  5.103830e+09    42
2        3           华鑫证券有限责任公司上海分公司  7.489912e+09  ...   180  3.422379e+09   155
3        4    国泰君安证券股份有限公司成都双庆路证券营业部  7.023039e+09  ...    14  3.509692e+09    13
4        5                     沪股通专用  6.663151e+09  ...    96  3.758107e+09   107
...    ...                       ...           ...  ...   ...           ...   ...
1620  1621    中信建投证券股份有限公司锦州解放路证券营业部  1.794000e+04  ...     1  0.000000e+00     0
1621  1622      中信证券股份有限公司如皋福寿路证券营业部  1.346730e+04  ...     1  0.000000e+00     0
1622  1623  申万宏源证券有限公司上海浦东新区沪南路证券营业部  1.178100e+04  ...     1  0.000000e+00     0
1623  1624      华泰证券股份有限公司沈阳光荣街证券营业部  1.155000e+04  ...     1  0.000000e+00     0
1624  1625      国信证券股份有限公司天津友谊路证券营业部  6.560000e+02  ...     1  0.000000e+00     0
[1625 rows x 8 columns]
```

###### 个股龙虎榜详情

接口: stock_lhb_stock_detail_em

目标地址: <https://data.eastmoney.com/stock/lhb/600077.html>

描述: 东方财富网-数据中心-龙虎榜单-个股龙虎榜详情

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                                            |
|--------|-----|-----------------------------------------------------------------------------------------------|
| symbol | str | symbol="600077";                                                                              |
| date   | str | date="20220310"; 需要通过 ak.stock_lhb_stock_detail_date_em(symbol="600077") 接口获取相应股票的有龙虎榜详情数据的日期 |
| flag   | str | flag="卖出";  choice of {"买入", "卖出"}                                                            |

输出参数

| 名称          | 类型      | 描述               |
|-------------|---------|------------------|
| 序号          | int64   | -                |
| 交易营业部名称     | object  | -                |
| 买入金额        | float64 | -                |
| 买入金额-占总成交比例 | float64 | -                |
| 卖出金额-占总成交比例 | float64 | -                |
| 净额          | float64 | -                |
| 类型          | object  | 该字段主要处理多种龙虎榜标准问题 |

接口示例

```python
import akshare as ak

stock_lhb_stock_detail_em_df = ak.stock_lhb_stock_detail_em(symbol="600077", date="20070416", flag="买入")
print(stock_lhb_stock_detail_em_df)
```

数据示例

```
   序号                  交易营业部名称  ...          净额                        类型
0   1           国泰君安证券股份有限公司总部  ...  5025114.99  有价格涨跌幅限制的日换手率达到20％的前三只证券
1   2  中银国际证券有限责任公司武汉黄孝河路证券营业部  ...  3435790.02  有价格涨跌幅限制的日换手率达到20％的前三只证券
2   3    华泰证券有限责任公司梧州蝶山二路证券营业部  ...  2723460.00  有价格涨跌幅限制的日换手率达到20％的前三只证券
3   4    东吴证券有限责任公司昆山前进中路证券营业部  ...  1844064.62  有价格涨跌幅限制的日换手率达到20％的前三只证券
4   5    国信证券有限责任公司深圳红岭中路证券营业部  ...  1770274.92  有价格涨跌幅限制的日换手率达到20％的前三只证券
[5 rows x 8 columns]
```

##### 龙虎榜-营业部排行

###### 龙虎榜-营业部排行-上榜次数最多

接口: stock_lh_yyb_most

目标地址: <https://data.10jqka.com.cn/market/longhu/>

描述: 龙虎榜-营业部排行-上榜次数最多

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称        | 类型     | 描述  |
|-----------|--------|-----|
| 序号        | int64  | -   |
| 营业部名称     | object | -   |
| 上榜次数      | int64  | -   |
| 合计动用资金    | object | -   |
| 年内上榜次数    | int64  | -   |
| 年内买入股票只数  | int64  | -   |
| 年内3日跟买成功率 | object | -   |

接口示例

```python
import akshare as ak

stock_lh_yyb_most_df = ak.stock_lh_yyb_most()
print(stock_lh_yyb_most_df)
```

数据示例

```
      序号                         营业部名称  上榜次数  ... 年内上榜次数  年内买入股票只数  年内3日跟买成功率
0      1  东方财富证券股份有限公司拉萨金融城南环...  一线游资    15  ...   3160      2369     41.40%
1      2  东方财富证券股份有限公司拉萨东环路第二...  一线游资    14  ...   4145      2978     43.94%
2      3  东方财富证券股份有限公司拉萨团结路第二...  一线游资    13  ...   3985      2856     43.21%
3      4        东方财富证券股份有限公司拉萨团结路第一...    13  ...   2685      1858     44.00%
4      5                   深股通专用  一线游资    11  ...   1780      1567     44.99%
..   ...                           ...   ...  ...    ...       ...        ...
288  289  华泰证券股份有限公司上海奉贤区望园南路...  跟风高手     1  ...     37        11    100.00%
289  290          华创证券有限责任公司贵阳北京路证券营业部     1  ...      4         1      无符合数据
290  291        中信建投证券股份有限公司东三环中路证券...     1  ...      4         1      无符合数据
291  292        国泰君安证券股份有限公司深圳福田中心区...     1  ...     43        24     48.00%
292  293         大同证券有限责任公司运城人民北路证券营业部     1  ...      1         1      无符合数据
[293 rows x 7 columns]
```

###### 龙虎榜-营业部排行-资金实力最强

接口: stock_lh_yyb_capital

目标地址: <https://data.10jqka.com.cn/market/longhu/>

描述: 龙虎榜-营业部排行-资金实力最强

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称       | 类型     | 描述  |
|----------|--------|-----|
| 序号       | int64  | -   |
| 营业部名称    | object | -   |
| 今日最高操作   | int64  | -   |
| 今日最高金额   | object | -   |
| 今日最高买入金额 | object | -   |
| 累计参与金额   | object | -   |
| 累计买入金额   | object | -   |

接口示例

```python
import akshare as ak

stock_lh_yyb_capital_df = ak.stock_lh_yyb_capital()
print(stock_lh_yyb_capital_df)
```

数据示例

```
      序号                         营业部名称  今日最高操作  今日最高金额 今日最高买入金额  累计参与金额  累计买入金额
0      1   华宝证券股份有限公司上海东大名路证券营业部  一线游资       5  14.72亿    7.35亿  20.32亿  10.18亿
1      2  东方证券股份有限公司上海松江区沪亭北路...  知名游资       2   8.98亿    4.49亿  10.80亿   5.40亿
2      3         华鑫证券有限责任公司上海分公司  一线游资       8   8.63亿    4.32亿  12.23亿   6.52亿
3      4        国泰君安证券股份有限公司成都双庆路证券...       2   8.00亿    4.00亿   9.77亿   4.88亿
4      5        东方证券股份有限公司上海静安区延平路证...       2   4.60亿    2.30亿   6.36亿   3.18亿
..   ...                           ...     ...     ...      ...     ...     ...
288  289        长江证券股份有限公司北京百万庄大街证券...       1   2.00万    2.00万   2.00万   2.00万
289  290          国联证券股份有限公司无锡中山路证券营业部       1   1.87万     0.00   1.87万    0.00
290  291        中信建投证券股份有限公司武汉建设八路证...       1   1.79万    1.79万   1.79万   1.79万
291  292          长江证券股份有限公司成都东大街证券营业部       1   1.74万     0.00   1.74万    0.00
292  293           中国银河证券股份有限公司德清证券营业部       1   1.21万     0.00   1.21万    0.00
[293 rows x 7 columns]
```

###### 龙虎榜-营业部排行-抱团操作实力

接口: stock_lh_yyb_control

目标地址: <https://data.10jqka.com.cn/market/longhu/>

描述: 龙虎榜-营业部排行-抱团操作实力

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称        | 类型     | 描述  |
|-----------|--------|-----|
| 序号        | int64  | -   |
| 营业部名称     | object | -   |
| 携手营业部家数   | int64  | -   |
| 年内最佳携手对象  | object | -   |
| 年内最佳携手股票数 | int64  | -   |
| 年内最佳携手成功率 | object | -   |

接口示例

```python
import akshare as ak

stock_lh_yyb_control_df = ak.stock_lh_yyb_control()
print(stock_lh_yyb_control_df)
```

数据示例

```
      序号                         营业部名称  ...  年内最佳携手股票数 年内最佳携手成功率
0      1                   深股通专用  一线游资  ...        207    50.73%
1      2  东方财富证券股份有限公司拉萨金融城南环...  一线游资  ...        240    42.44%
2      3  东方财富证券股份有限公司拉萨团结路第二...  一线游资  ...        241    46.86%
3      4        东方财富证券股份有限公司拉萨团结路第一...  ...        241    46.86%
4      5  东方财富证券股份有限公司拉萨东环路第二...  一线游资  ...        241    46.03%
..   ...                           ...  ...        ...       ...
263  264         海通证券股份有限公司常熟海虞北路证券营业部  ...          1     无符合数据
264  265          兴业证券股份有限公司福州湖东路证券营业部  ...          4     无符合数据
265  266         光大证券股份有限公司贵阳长岭北路证券营业部  ...          2     无符合数据
266  267        华泰证券股份有限公司深圳平安金融中心证...  ...          3     无符合数据
267  268               中信证券股份有限公司深圳分公司  ...          4     无符合数据
[268 rows x 6 columns]
```

##### 龙虎榜-每日详情

接口: stock_lhb_detail_daily_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/lhb/index.phtml>

描述: 新浪财经-龙虎榜-每日详情

限量: 单次返回指定 date 的所有数据

输入参数

| 名称   | 类型  | 描述                   |
|------|-----|----------------------|
| date | str | date="20240222"; 交易日 |

输出参数

| 名称   | 类型      | 描述       |
|------|---------|----------|
| 序号   | int64   | -        |
| 股票代码 | object  | -        |
| 股票名称 | object  | -        |
| 收盘价  | float64 | 注意单位: 元  |
| 对应值  | float64 | 注意单位: %  |
| 成交量  | float64 | 注意单位: 万股 |
| 成交额  | float64 | 注意单位: 万元 |
| 指标   | object  | 注意单位: 万元 |

接口示例

```python
import akshare as ak

stock_lhb_detail_daily_sina_df = ak.stock_lhb_detail_daily_sina(date="20240222")
print(stock_lhb_detail_daily_sina_df)
```

数据示例

```
    序号    股票代码  ...          成交额                                                 指标
0    1  000005  ...   12350.1150           连续三个交易日内，涨幅偏离值累计达到12%的ST证券、*ST证券和未完成股改证券
1    2  000023  ...    5569.3887           连续三个交易日内，涨幅偏离值累计达到12%的ST证券、*ST证券和未完成股改证券
2    3  002087  ...    7799.9948           连续三个交易日内，涨幅偏离值累计达到12%的ST证券、*ST证券和未完成股改证券
3    4  002251  ...   17824.5730           连续三个交易日内，涨幅偏离值累计达到12%的ST证券、*ST证券和未完成股改证券
4    5  002309  ...     625.8694           连续三个交易日内，涨幅偏离值累计达到12%的ST证券、*ST证券和未完成股改证券
5    1  000017  ...  182261.0964                                         振幅值达15%的证券
6    2  002767  ...   19027.4927                                         振幅值达15%的证券
7    3  002779  ...   26323.3751                                         振幅值达15%的证券
8    4  002976  ...   21965.7357                                         振幅值达15%的证券
9    5  603958  ...   88089.9000                                         振幅值达15%的证券
10   6  600715  ...   30483.4000                                         振幅值达15%的证券
11   7  601599  ...   83517.0300                                         振幅值达15%的证券
12   1  000017  ...  182261.0964                                         换手率达20%的证券
13   2  000628  ...  338104.2782                                         换手率达20%的证券
14   3  001300  ...   26419.9729                                         换手率达20%的证券
15   4  001314  ...   55316.8666                                         换手率达20%的证券
16   5  001376  ...   22526.3696                                         换手率达20%的证券
17   6  603082  ...   57471.2900                                         换手率达20%的证券
18   7  600520  ...   96413.6700                                         换手率达20%的证券
19   8  601136  ...  254881.6100                                         换手率达20%的证券
20   9  600355  ...   43150.3900                                         换手率达20%的证券
21  10  603375  ...   21939.2800                                         换手率达20%的证券
22  11  837748  ...   17402.7500                                         换手率达20%的证券
23  12  871753  ...   32244.5500                                         换手率达20%的证券
24  13  873122  ...   29711.8900                                         换手率达20%的证券
25  14  870976  ...    9089.6900                                         换手率达20%的证券
26  15  837592  ...   11167.0400                                         换手率达20%的证券
27   1  000070  ...   87688.7663                                        涨幅偏离值达7%的证券
28   2  000536  ...   40405.8869                                        涨幅偏离值达7%的证券
29   3  000628  ...  338104.2782                                        涨幅偏离值达7%的证券
30   4  002657  ...   58771.5639                                        涨幅偏离值达7%的证券
31   5  002916  ...   48520.0120                                        涨幅偏离值达7%的证券
32   6  601996  ...   22519.3300                                        涨幅偏离值达7%的证券
33   7  600792  ...   30895.5200                                        涨幅偏离值达7%的证券
34   8  603528  ...   29088.9000                                        涨幅偏离值达7%的证券
35   9  603963  ...   10527.9800                                        涨幅偏离值达7%的证券
36  10  600602  ...   87019.3500                                        涨幅偏离值达7%的证券
37   1  000416  ...   15786.0704  连续三个交易日内，日均换手率与前五个交易日的日均换手率的比值达到30倍，且换手率累计达20%的股票
38   1  002217  ...   76899.5978                            连续三个交易日内，涨幅偏离值累计达20%的证券
39   2  002789  ...   10830.8319                            连续三个交易日内，涨幅偏离值累计达20%的证券
40   3  603363  ...   59315.0400                            连续三个交易日内，涨幅偏离值累计达20%的证券
41   1  300157  ...   30524.4363                                                NaN
42   2  300209  ...    1587.7636                                                NaN
43   3  300321  ...   13573.3626                                                NaN
44   1  300188  ...   48544.7464                                                NaN
45   2  300210  ...   19151.3472                                                NaN
46   3  300249  ...   34312.9720                                                NaN
47   4  301252  ...   13744.3625                                                NaN
48   5  301318  ...   50108.3350                                                NaN
49   1  300781  ...  153086.7566                                                NaN
50   2  300949  ...   26507.2743                                                NaN
51   3  301502  ...   25688.4905                                                NaN
52   4  301516  ...   60720.4662                                                NaN
53   5  301577  ...   24623.2346                                                NaN
54   6  688709  ...   58862.6200                                                NaN
[55 rows x 8 columns]
```

##### 龙虎榜-个股上榜统计

接口: stock_lhb_ggtj_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/ggtj/index.phtml>

描述: 新浪财经-龙虎榜-个股上榜统计

限量: 单次返回指定 symbol 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                                |
|--------|-----|-----------------------------------------------------------------------------------|
| symbol | str | symbol="5"; choice of {"5": 最近 5 天; "10": 最近 10 天; "30": 最近 30 天; "60": 最近 60 天;} |

输出参数

| 名称    | 类型      | 描述      |
|-------|---------|---------|
| 股票代码  | object  | -       |
| 股票名称  | object  | -       |
| 上榜次数  | int64   | -       |
| 累积购买额 | float64 | 注意单位: 万 |
| 累积卖出额 | float64 | 注意单位: 万 |
| 净额    | float64 | 注意单位: 万 |
| 买入席位数 | int64   | -       |
| 卖出席位数 | int64   | -       |

接口示例

```python
import akshare as ak

stock_lhb_ggtj_sina_df = ak.stock_lhb_ggtj_sina(symbol="5")
print(stock_lhb_ggtj_sina_df)
```

数据示例

```
     股票代码 股票名称  上榜次数  累积购买额   累积卖出额   净额  买入席位数  卖出席位数
0    300364  中文在线     2  171289.25   97538.13   73751.12      9      9
1    000001  平安银行     1  126080.24   64719.50   61360.74      5      4
2    002673  西部证券     1   22404.44    8677.21   13727.22      5      4
3    601595  上海电影     1   26953.47   13537.77   13415.70      3      4
4    601136  首创证券     2   50349.55   37874.81   12474.74      9      7
..      ...   ...   ...        ...        ...        ...    ...    ...
310  001314  亿道信息     4   27524.67   46756.32  -19231.65     13     10
311  300502   新易盛     1  122834.08  142750.78  -19916.70      5      5
312  002229  鸿博股份     2  116669.40  137884.32  -21214.92     10      9
313  000628  高新发展     4  372969.77  421664.91  -48695.14     14     15
314  603259  药明康德     1   66436.38  248845.50 -182409.12      5      3
[315 rows x 8 columns]
```

##### 龙虎榜-营业上榜统计

接口: stock_lhb_yytj_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/yytj/index.phtml>

描述: 新浪财经-龙虎榜-营业上榜统计

限量: 单次返回指定 symbol 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                                |
|--------|-----|-----------------------------------------------------------------------------------|
| symbol | str | symbol="5"; choice of {"5": 最近 5 天; "10": 最近 10 天; "30": 最近 30 天; "60": 最近 60 天;} |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 营业部名称  | object  | -       |
| 上榜次数   | int64   | -       |
| 累积购买额  | float64 | 注意单位: 万 |
| 买入席位数  | int64   | -       |
| 累积卖出额  | float64 | 注意单位: 万 |
| 卖出席位数  | int64   | -       |
| 买入前三股票 | object  | -       |

接口示例

```python
import akshare as ak

stock_lhb_yytj_sina_df = ak.stock_lhb_yytj_sina(symbol="5")
print(stock_lhb_yytj_sina_df)
```

数据示例

```
                营业部名称  上榜次数    累积购买额  ...    累积卖出额  卖出席位数           买入前三股票
0      渤海证券股份有限公司天津滨海新区第一分公司     1     0.00  ...   116.29      1             ST星源
1       平安证券股份有限公司深圳香蜜湖证券营业部     3   879.44  ...   522.60      1   科新发展,ST星源,中重科技
2       华泰证券股份有限公司姜堰东大街证券营业部     2     0.00  ...   165.14      2       ST星源,*ST西发
3       海通证券股份有限公司庆阳西大街证券营业部     2     0.00  ...   504.69      2             ST星源
4    东方财富证券股份有限公司山南香曲东路证券营业部    26  5593.35  ...  5962.82     17  亚世光电,中视传媒,光大嘉宝,
..                       ...   ...      ...  ...      ...    ...              ...
315          华泰证券股份有限公司湖南分公司     7  6542.40  ...  3553.71      2        哈森股份,开元教育
316  上海证券有限责任公司绍兴新昌人民西路证券营业部     1  1458.00  ...     0.00      0             昂立教育
317     华安证券股份有限公司合肥高新区证券营业部     5  1868.41  ...  1788.15      2   中科金财,昀冢科技,普路通,
318     兴业证券股份有限公司福州湖东路证券营业部     1  1047.27  ...     0.00      0              香飘飘
319  申万宏源证券有限公司上海徐汇区龙漕路证券营业部     1   678.26  ...     0.00      0            *ST碳元
[320 rows x 7 columns]
```

##### 龙虎榜-机构席位追踪

接口: stock_lhb_jgzz_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/jgzz/index.phtml>

描述: 新浪财经-龙虎榜-机构席位追踪

限量: 单次返回指定 symbol 的所有历史数据

输入参数

| 名称     | 类型  | 描述                                                                                |
|--------|-----|-----------------------------------------------------------------------------------|
| symbol | str | symbol="5"; choice of {"5": 最近 5 天; "10": 最近 10 天; "30": 最近 30 天; "60": 最近 60 天;} |

输出参数

| 名称    | 类型      | 描述      |
|-------|---------|---------|
| 股票代码  | object  | -       |
| 股票名称  | object  | -       |
| 累积买入额 | float64 | 注意单位: 万 |
| 买入次数  | float64 | -       |
| 累积卖出额 | float64 | 注意单位: 万 |
| 卖出次数  | float64 | -       |
| 净额    | float64 | 注意单位: 万 |

接口示例

```python
import akshare as ak

stock_lhb_jgzz_sina_df = ak.stock_lhb_jgzz_sina(symbol="5")
print(stock_lhb_jgzz_sina_df)
```

数据示例

```
     股票代码  股票名称  累积买入额  买入次数  累积卖出额  卖出次数  净额
0    688498  源杰科技  19589.28     6   3035.09     2  16554.19
1    300308  中际旭创  19269.73     1   9088.94     1  10180.79
2    603135  中重科技   5824.15     1      0.00     0   5824.15
3    003032  传智教育   5388.51     4    118.46     0   5270.05
4    688601   力芯微  10427.99     6   5463.37     4   4964.62
..      ...   ...       ...   ...       ...   ...       ...
192  000628  高新发展   8635.84     2  21545.41     3 -12909.57
193  300063  天龙集团   7426.88     1  20736.26     5 -13309.38
194  002463  沪电股份   4700.87     1  18997.89     3 -14297.02
195  300781  因赛集团  13758.05     2  39308.41     8 -25550.36
196  603259  药明康德      0.00     0  54874.30     3 -54874.30
[197 rows x 7 columns]
```

##### 龙虎榜-机构席位成交明细

接口: stock_lhb_jgmx_sina

目标地址: <https://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/jgzz/index.phtml>

描述: 新浪财经-龙虎榜-机构席位成交明细

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称      | 类型      | 描述      |
|---------|---------|---------|
| 股票代码    | object  | -       |
| 股票名称    | object  | -       |
| 交易日期    | object  | -       |
| 机构席位买入额 | float64 | 注意单位: 万 |
| 机构席位卖出额 | float64 | 注意单位: 万 |
| 类型      | object  | -       |

接口示例

```python
import akshare as ak

stock_lhb_jgmx_sina_df = ak.stock_lhb_jgmx_sina()
print(stock_lhb_jgmx_sina_df)
```

数据示例

```
    股票代码  股票名称    交易日期  机构席位买入额(万)  机构席位卖出额(万)   类型
0    001300   三柏硕  2024-02-23     2231.89     5214.88   换手率达20%的证券
1    301378   通达海  2024-02-23      249.88     2318.76          NaN
2    300781  因赛集团  2024-02-23     7237.09    20345.79          NaN
3    300486  东杰智能  2024-02-23     3921.15     7344.49          NaN
4    300078  思创医惠  2024-02-23     2423.62     4956.84          NaN
..      ...   ...         ...         ...         ...          ...
235  301516   中远通  2024-02-19     1606.70       78.07          NaN
236  300624  万兴科技  2024-02-19        0.00    10913.05          NaN
237  002281  光迅科技  2024-02-19      224.76     2618.77  涨幅偏离值达7%的证券
238  300067   安诺其  2024-02-19     1329.52     2784.87          NaN
239  002621   美吉姆  2024-02-19      833.72     1391.98   振幅值达15%的证券
[240 rows x 6 columns]
```

#### 首发申报信息

接口: stock_ipo_declare

目标地址: <https://data.eastmoney.com/xg/xg/sbqy.html>

描述: 东方财富网-数据中心-新股申购-首发申报信息-首发申报企业信息

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int64  | -   |
| 申报企业   | object | -   |
| 拟上市地   | object | -   |
| 保荐机构   | object | -   |
| 会计师事务所 | object | -   |
| 律师事务所  | object | -   |
| 备注     | object | -   |

接口示例

```python
import akshare as ak

stock_ipo_declare_df = ak.stock_ipo_declare()
print(stock_ipo_declare_df)
```

数据示例

```
      序号     申报企业 拟上市地  ...               会计师事务所        律师事务所      备注
0      1     奥精医疗科技股份有限公司  科创板  ...     立信会计师事务所(特殊普通合伙)  北京观韬中茂律师事务所  进一步问询中
1      2       爱威科技股份有限公司  科创板  ...     天健会计师事务所(特殊普通合伙)    湖南启元律师事务所  进一步问询中
2      3   北京弘成立业科技股份有限公司  创业板  ...     大华会计师事务所(特殊普通合伙)   北京市君合律师事务所  进一步问询中
3      4   北京海天瑞声科技股份有限公司  科创板  ...  毕马威华振会计师事务所(特殊普通合伙)   北京市天元律师事务所  进一步问询中
4      5  北京挖金客信息科技股份有限公司  创业板  ...     容诚会计师事务所(特殊普通合伙)  国浩律师(北京)事务所  进一步问询中
..   ...              ...  ...  ...                  ...          ...     ...
106  107   浙江嘉益保温科技股份有限公司  创业板  ...     天健会计师事务所(特殊普通合伙)   北京市金杜律师事务所  进一步问询中
107  108   浙江日发纺织机械股份有限公司  创业板  ...     天健会计师事务所(特殊普通合伙)    浙江天册律师事务所  进一步问询中
108  109     浙江泰福泵业股份有限公司  创业板  ...     天健会计师事务所(特殊普通合伙)  国浩律师(杭州)事务所  进一步问询中
109  110     中兰环保科技股份有限公司  创业板  ...     立信会计师事务所(特殊普通合伙)    北京国枫律师事务所  进一步问询中
110  111   中联云港数据科技股份有限公司  创业板  ...   天职国际会计师事务所(特殊普通合伙)  国浩律师(北京)事务所  进一步问询中
```

#### IPO审核信息

##### 全部

###### 科创板

接口: stock_register_kcb

目标地址: <https://data.eastmoney.com/xg/ipo/>

描述: 东方财富网-数据中心-新股数据-IPO审核信息-科创板

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int64  | -   |
| 发行人全称  | object | -   |
| 审核状态   | object | -   |
| 注册地    | object | -   |
| 证监会行业  | object | -   |
| 保荐机构   | object | -   |
| 律师事务所  | object | -   |
| 会计师事务所 | object | -   |
| 更新日期   | object | -   |
| 受理日期   | object | -   |
| 拟上市地点  | object | -   |
| 招股说明书  | object | -   |

接口示例

```python
import akshare as ak

stock_register_kcb_df = ak.stock_register_kcb()
print(stock_register_kcb_df)
```

数据示例

```
       序号              企业名称     最新状态 注册地                行业          保荐机构  \
0      1    联芸科技(杭州)股份有限公司     注册生效  浙江  计算机、通信和其他电子设备制造业  中信建投证券股份有限公司
1      2  赛诺威盛科技(北京)股份有限公司       终止  北京           专用设备制造业    国金证券股份有限公司
2      3   青岛信芯微电子科技股份有限公司       终止  山东        软件和信息技术服务业  中国国际金融股份有限公司
3      4   北京凯普林光电科技股份有限公司  上市委会议通过  北京  计算机、通信和其他电子设备制造业  国泰君安证券股份有限公司
4      5    深圳垦拓流体技术股份有限公司       终止  广东           通用设备制造业    中信证券股份有限公司
..   ...               ...      ...  ..               ...           ...
866  867        澜起科技股份有限公司     注册生效  上海  计算机、通信和其他电子设备制造业    中信证券股份有限公司
867  868      浙江杭可科技股份有限公司     注册生效  浙江           专用设备制造业    国信证券股份有限公司
868  869      苏州天准科技股份有限公司     注册生效  江苏           专用设备制造业    海通证券股份有限公司
869  870    苏州华兴源创科技股份有限公司     注册生效  江苏           专用设备制造业  华泰联合证券有限责任公司
870  871    烟台睿创微纳技术股份有限公司     注册生效  山东  计算机、通信和其他电子设备制造业    中信证券股份有限公司
           律师事务所              会计师事务所        更新日期        受理日期 拟上市地点  \
0     北京市君合律师事务所  德勤华永会计师事务所(特殊普通合伙)  2024-06-14  2022-12-28   科创板
1     北京市中伦律师事务所    大信会计师事务所(特殊普通合伙)  2024-06-14  2023-03-27   科创板
2     北京市君合律师事务所    天健会计师事务所(特殊普通合伙)  2024-06-14  2023-06-12   科创板
3     北京市天元律师事务所    天健会计师事务所(特殊普通合伙)  2024-06-14  2023-05-09   科创板
4     北京市中伦律师事务所    致同会计师事务所(特殊普通合伙)  2024-06-13  2023-12-27   科创板
..           ...                 ...         ...         ...   ...
866  国浩律师(上海)事务所    瑞华会计师事务所(特殊普通合伙)  2019-06-26  2019-04-01   科创板
867   北京市金杜律师事务所    天健会计师事务所(特殊普通合伙)  2019-06-24  2019-04-15   科创板
868    浙江六和律师事务所    瑞华会计师事务所(特殊普通合伙)  2019-06-20  2019-04-02   科创板
869   上海市通力律师事务所  华普天健会计师事务所(特殊普通合伙)  2019-06-18  2019-03-27   科创板
870   北京市中银律师事务所  信永中和会计师事务所(特殊普通合伙)  2019-06-18  2019-03-22   科创板
                                                 招股说明书
0    https://pdf.dfcfw.com/pdf/H2_AN202302171583296...
1    https://pdf.dfcfw.com/pdf/H2_AN202303271584589...
2    https://pdf.dfcfw.com/pdf/H2_AN202306121590862...
3    https://pdf.dfcfw.com/pdf/H2_AN202305091586404...
4    https://pdf.dfcfw.com/pdf/H2_AN202312271615032...
..                                                 ...
866  https://pdf.dfcfw.com/pdf/H2_AN201904011312907...
867  https://pdf.dfcfw.com/pdf/H2_AN201904151319351...
868  https://pdf.dfcfw.com/pdf/H2_AN201904021313966...
869  https://pdf.dfcfw.com/pdf/H2_AN201903271310281...
870  https://pdf.dfcfw.com/pdf/H2_AN201903221308711...
[871 rows x 12 columns]
```

###### 创业板

接口: stock_register_cyb

目标地址: <https://data.eastmoney.com/xg/ipo/>

描述: 东方财富网-数据中心-新股数据-IPO审核信息-创业板

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int32  | -   |
| 发行人全称  | object | -   |
| 审核状态   | object | -   |
| 注册地    | object | -   |
| 证监会行业  | object | -   |
| 保荐机构   | object | -   |
| 律师事务所  | object | -   |
| 会计师事务所 | object | -   |
| 更新日期   | object | -   |
| 受理日期   | object | -   |
| 拟上市地点  | object | -   |
| 招股说明书  | object | -   |

接口示例

```python
import akshare as ak

stock_register_cyb_df = ak.stock_register_cyb()
print(stock_register_cyb_df)
```

数据示例

```
       序号               企业名称  最新状态 注册地          行业              保荐机构  \
0        1   北京易诚互动网络技术股份有限公司    撤回  北京  软件和信息技术服务业        东北证券股份有限公司
1        2     基因科技(上海)股份有限公司    撤回  上海  科技推广和应用服务业        广发证券股份有限公司
2        3         黄山谷捷股份有限公司   已问询  安徽       汽车制造业        国元证券股份有限公司
3        4       迪嘉药业集团股份有限公司    撤回  山东       医药制造业        民生证券股份有限公司
4        5   中航上大高温合金材料股份有限公司  提交注册  河北       金属制品业      中国国际金融股份有限公司
...    ...                ...   ...  ..         ...               ...
1122  1123    宁波卡倍亿电气技术股份有限公司  注册生效  浙江       汽车制造业        东莞证券股份有限公司
1123  1124      杨凌美畅新材料股份有限公司  注册生效  陕西    非金属矿物制品业      中信建投证券股份有限公司
1124  1125   北京锋尚世纪文化传媒股份有限公司  注册生效  北京       文化艺术业      中信建投证券股份有限公司
1125  1126  康泰医学系统(秦皇岛)股份有限公司  注册生效  河北     专用设备制造业  申万宏源证券承销保荐有限责任公司
1126  1127      安徽蓝盾光电子股份有限公司  注册生效  安徽     仪器仪表制造业        华龙证券股份有限公司
            律师事务所              会计师事务所        更新日期        受理日期 拟上市地点  \
0       北京德恒律师事务所  信永中和会计师事务所(特殊普通合伙)  2024-06-14  2022-06-27   创业板
1      上海市广发律师事务所    容诚会计师事务所(特殊普通合伙)  2024-06-13  2023-06-27   创业板
2       安徽天禾律师事务所  中审众环会计师事务所(特殊普通合伙)  2024-06-12  2023-05-08   创业板
3       上海泽昌律师事务所    天健会计师事务所(特殊普通合伙)  2024-06-12  2023-06-16   创业板
4      北京市嘉源律师事务所    立信会计师事务所(特殊普通合伙)  2024-06-11  2022-06-29   创业板
...           ...                 ...         ...         ...   ...
1122  上海市锦天城律师事务所    立信会计师事务所(特殊普通合伙)  2020-07-29  2020-06-22   创业板
1123    北京国枫律师事务所  立信中联会计师事务所(特殊普通合伙)  2020-07-24  2020-06-24   创业板
1124   北京市中伦律师事务所  信永中和会计师事务所(特殊普通合伙)  2020-07-24  2020-06-22   创业板
1125   北京市中伦律师事务所  德勤华永会计师事务所(特殊普通合伙)  2020-07-24  2020-07-02   创业板
1126    安徽承义律师事务所    容诚会计师事务所(特殊普通合伙)  2020-07-24  2020-06-30   创业板
                                                  招股说明书
0     https://pdf.dfcfw.com/pdf/H2_AN202401251618103...
1     https://pdf.dfcfw.com/pdf/H2_AN202312291615486...
2     https://pdf.dfcfw.com/pdf/H2_AN202406121636034...
3     https://pdf.dfcfw.com/pdf/H2_AN202311161611034...
4     https://pdf.dfcfw.com/pdf/H2_AN202406111635973...
...                                                 ...
1122  https://pdf.dfcfw.com/pdf/H2_AN202008121398114...
1123  https://pdf.dfcfw.com/pdf/H2_AN202008091397452...
1124  https://pdf.dfcfw.com/pdf/H2_AN202008091397452...
1125  https://pdf.dfcfw.com/pdf/H2_AN202008131398337...
1126  https://pdf.dfcfw.com/pdf/H2_AN202008161398984...
[1127 rows x 12 columns]
```

###### 上海主板

接口: stock_register_sh

目标地址: <https://data.eastmoney.com/xg/ipo/>

描述: 东方财富网-数据中心-新股数据-IPO审核信息-上海主板

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int32  | -   |
| 发行人全称  | object | -   |
| 审核状态   | object | -   |
| 注册地    | object | -   |
| 证监会行业  | object | -   |
| 保荐机构   | object | -   |
| 律师事务所  | object | -   |
| 会计师事务所 | object | -   |
| 更新日期   | object | -   |
| 受理日期   | object | -   |
| 拟上市地点  | object | -   |
| 招股说明书  | object | -   |

接口示例

```python
import akshare as ak

stock_register_sh_df = ak.stock_register_sh()
print(stock_register_sh_df)
```

数据示例

```
      序号              企业名称       最新状态 注册地          行业              保荐机构  \
0      1      浙江亘古电缆股份有限公司         终止  浙江  电气机械和器材制造业        招商证券股份有限公司
1      2  上海生生医药冷链科技股份有限公司         终止  上海  多式联运和运输代理业      中国国际金融股份有限公司
2      3    新疆凯龙清洁能源股份有限公司         终止  新疆  开采专业及辅助性活动        东兴证券股份有限公司
3      4      广州三晶电气股份有限公司  已收到注册申请材料  广东        None        民生证券股份有限公司
4      5      合肥汇通控股股份有限公司  已收到注册申请材料  安徽        None      中银国际证券股份有限公司
..   ...               ...        ...  ..         ...               ...
874  875             上海数据港     已通过发审会  上海        None      中信建投证券股份有限公司
875  876            镇海石化工程     已通过发审会  浙江        None        浙商证券股份有限公司
876  877          浙江德创环保科技     已通过发审会  浙江        None        民生证券股份有限公司
877  878           重庆建工集团*     已通过发审会  重庆        None        华融证券股份有限公司
878  879            大连百傲化学     已通过发审会  辽宁        None  申万宏源证券承销保荐有限责任公司
           律师事务所              会计师事务所        更新日期        受理日期 拟上市地点  \
0      北京国枫律师事务所    天健会计师事务所(特殊普通合伙)  2024-06-17  2023-03-03   沪主板
1    上海市锦天城律师事务所    立信会计师事务所(特殊普通合伙)  2024-06-17  2023-06-30   沪主板
2     北京市中伦律师事务所  信永中和会计师事务所(特殊普通合伙)  2024-06-14  2023-06-15   沪主板
3      国信信扬律师事务所    立信会计师事务所(特殊普通合伙)  2024-06-13         NaT   沪主板
4      安徽天禾律师事务所    容诚会计师事务所(特殊普通合伙)  2024-06-13         NaT   沪主板
..           ...                 ...         ...         ...   ...
874  上海市锦天城律师事务所    立信会计师事务所(特殊普通合伙)  2017-01-05         NaT   沪主板
875   北京市天元律师事务所    天健会计师事务所(特殊普通合伙)  2017-01-05         NaT   沪主板
876   北京市天元律师事务所    天健会计师事务所(特殊普通合伙)  2017-01-05         NaT   沪主板
877   北京市金杜律师事务所    大信会计师事务所(特殊普通合伙)  2017-01-05         NaT   沪主板
878    北京德恒律师事务所    瑞华会计师事务所(特殊普通合伙)  2017-01-05         NaT   沪主板
                                                 招股说明书
0    https://pdf.dfcfw.com/pdf/H2_AN202303031584027...
1    https://pdf.dfcfw.com/pdf/H2_AN202306301591956...
2    https://pdf.dfcfw.com/pdf/H2_AN202306151590972...
3    https://pdf.dfcfw.com/pdf/H2_AN202303031584027...
4    https://pdf.dfcfw.com/pdf/H2_AN202303031584027...
..                                                 ...
874  https://pdf.dfcfw.com/pdf/H2_AN201701150271855...
875  https://pdf.dfcfw.com/pdf/H2_AN201701180277302...
876  https://pdf.dfcfw.com/pdf/H2_AN201701170274362...
877  https://pdf.dfcfw.com/pdf/H2_AN201701170274362...
878  https://pdf.dfcfw.com/pdf/H2_AN201701160272431...
[879 rows x 12 columns]
```

###### 深圳主板

接口: stock_register_sz

目标地址: <https://data.eastmoney.com/xg/ipo/>

描述: 东方财富网-数据中心-新股数据-IPO审核信息-深圳主板

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int32  | -   |
| 发行人全称  | object | -   |
| 审核状态   | object | -   |
| 注册地    | object | -   |
| 证监会行业  | object | -   |
| 保荐机构   | object | -   |
| 律师事务所  | object | -   |
| 会计师事务所 | object | -   |
| 更新日期   | object | -   |
| 受理日期   | object | -   |
| 拟上市地点  | object | -   |
| 招股说明书  | object | -   |

接口示例

```python
import akshare as ak

stock_register_sz_df = ak.stock_register_sz()
print(stock_register_sz_df)
```

数据示例

```
     序号             企业名称    最新状态 注册地            行业          保荐机构  \
0      1    山东金鸿新材料股份有限公司      撤回  山东      非金属矿物制品业    中泰证券股份有限公司
1      2    金永和精工制造股份有限公司      撤回  山东         汽车制造业    中德证券有限责任公司
2      3     江苏大艺科技股份有限公司      撤回  江苏       通用设备制造业  中信建投证券股份有限公司
3      4   浙江新纳材料科技股份有限公司      撤回  浙江  化学原料及化学制品制造业    中信证券股份有限公司
4      5  深圳宏业基岩土科技股份有限公司      中止  广东          None    招商证券股份有限公司
..   ...              ...     ...  ..           ...           ...
512  513         深圳市科达利实业  已通过发审会  广东          None  中国国际金融股份有限公司
513  514         浙江威星智能仪表  已通过发审会  浙江          None    东吴证券股份有限公司
514  515         高斯贝尔数码科技  已通过发审会  湖南          None    招商证券股份有限公司
515  516           盐津铺子食品  已通过发审会  湖南          None    西部证券股份有限公司
516  517           广东英联包装  已通过发审会  广东          None    国海证券股份有限公司
           律师事务所              会计师事务所        更新日期        受理日期 拟上市地点  \
0     北京市汉坤律师事务所    永拓会计师事务所(特殊普通合伙)  2024-06-17  2023-12-28   深主板
1      北京大成律师事务所  信永中和会计师事务所(特殊普通合伙)  2024-06-16  2023-06-30   深主板
2    国浩律师(上海)事务所    天健会计师事务所(特殊普通合伙)  2024-06-15  2023-03-02   深主板
3     北京市康达律师事务所    天健会计师事务所(特殊普通合伙)  2024-06-14  2023-03-01   深主板
4      广东华商律师事务所    大华会计师事务所(特殊普通合伙)  2024-06-13         NaT   深主板
..           ...                 ...         ...         ...   ...
512    广东信达律师事务所    瑞华会计师事务所(特殊普通合伙)  2017-02-09         NaT   深主板
513  国浩律师(杭州)事务所    天健会计师事务所(特殊普通合伙)  2017-01-19         NaT   深主板
514    湖南启元律师事务所    天健会计师事务所(特殊普通合伙)  2017-01-12         NaT   深主板
515    湖南启元律师事务所    天健会计师事务所(特殊普通合伙)  2017-01-05         NaT   深主板
516    北京国枫律师事务所    立信会计师事务所(特殊普通合伙)  2017-01-05         NaT   深主板
                                                 招股说明书
0    https://pdf.dfcfw.com/pdf/H2_AN202312281615219...
1    https://pdf.dfcfw.com/pdf/H2_AN202312261614904...
2    https://pdf.dfcfw.com/pdf/H2_AN202312271615081...
3    https://pdf.dfcfw.com/pdf/H2_AN202312291615534...
4    https://pdf.dfcfw.com/pdf/H2_AN202307061592065...
..                                                 ...
512  https://pdf.dfcfw.com/pdf/H2_AN201702190353685...
513  https://pdf.dfcfw.com/pdf/H2_AN201702060321215...
514  https://pdf.dfcfw.com/pdf/H2_AN201701250290802...
515  https://pdf.dfcfw.com/pdf/H2_AN201701180274398...
516  https://pdf.dfcfw.com/pdf/H2_AN201701180274398...
[517 rows x 12 columns]
```

###### 北交所

接口: stock_register_bj

目标地址: <https://data.eastmoney.com/xg/ipo/>

描述: 东方财富网-数据中心-新股数据-IPO审核信息-北交所

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述  |
|--------|--------|-----|
| 序号     | int32  | -   |
| 发行人全称  | object | -   |
| 审核状态   | object | -   |
| 注册地    | object | -   |
| 证监会行业  | object | -   |
| 保荐机构   | object | -   |
| 律师事务所  | object | -   |
| 会计师事务所 | object | -   |
| 更新日期   | object | -   |
| 受理日期   | object | -   |
| 拟上市地点  | object | -   |
| 招股说明书  | object | -   |

接口示例

```python
import akshare as ak

stock_register_bj_df = ak.stock_register_bj()
print(stock_register_bj_df)
```

数据示例

```
      序号              企业名称 最新状态      注册地                行业        保荐机构  \
0      1   浙江太湖远大新材料股份有限公司  已问询  浙江省 湖州市          橡胶和塑料制品业  招商证券股份有限公司
1      2      大连瑞克科技股份有限公司  已问询  辽宁省 大连市      化学原料和化学制品制造业  国融证券股份有限公司
2      3    江苏永创医药科技股份有限公司   终止  江苏省 淮安市      化学原料和化学制品制造业  开源证券股份有限公司
3      4    成都成电光信科技股份有限公司  已问询  四川省 成都市        软件和信息技术服务业  广发证券股份有限公司
4      5    浙江圣兆药物科技股份有限公司   终止  浙江省 杭州市             医药制造业  东吴证券股份有限公司
..   ...               ...  ...      ...               ...         ...
519  520      上海艾融软件股份有限公司   核准  上海市 崇明县        软件和信息技术服务业  光大证券股份有限公司
520  521  北京颖泰嘉和生物科技股份有限公司   核准  北京市 昌平区      化学原料和化学制品制造业  西南证券股份有限公司
521  522  晨越建设项目管理集团股份有限公司   终止  四川省 成都市           专业技术服务业  华福证券有限责任公司
522  523        东亚装饰股份有限公司   终止  山东省 青岛市        建筑装饰和其他建筑业  红塔证券股份有限公司
523  524      北京蓝山科技股份有限公司   终止  北京市 海淀区  计算机、通信和其他电子设备制造业  华龙证券股份有限公司
           律师事务所                  会计师事务所        更新日期        受理日期 拟上市地点  \
0      北京大成律师事务所      公证天业会计师事务所(特殊普通合伙)  2024-06-13  2023-11-30   北交所
1    北京海润天睿律师事务所        和信会计师事务所(特殊普通合伙)  2024-06-11  2023-12-28   北交所
2      北京大成律师事务所      苏亚金诚会计师事务所(特殊普通合伙)  2024-06-07  2023-09-28   北交所
3      北京国枫律师事务所      信永中和会计师事务所(特殊普通合伙)  2024-06-07  2023-09-27   北交所
4     上海市联合律师事务所      立信中联会计师事务所(特殊普通合伙)  2024-06-06  2023-06-30   北交所
..           ...                     ...         ...         ...   ...
519   上海天衍禾律师事务所        天健会计师事务所(特殊普通合伙)  2020-06-12  2020-04-29   北交所
520   北京市康达律师事务所  四川华信(集团)会计师事务所(特殊普通合伙)  2020-06-12  2020-04-28   北交所
521   北京市中伦律师事务所      信永中和会计师事务所(特殊普通合伙)  2020-06-10  2020-04-28   北交所
522   北京市中银律师事务所        立信会计师事务所(特殊普通合伙)  2020-05-26  2020-05-19   北交所
523   北京市天元律师事务所     中兴财光华会计师事务所(特殊普通合伙)  2020-05-13  2020-04-29   北交所
                                                 招股说明书
0    https://pdf.dfcfw.com/pdf/H2_AN202406131636105...
1    https://pdf.dfcfw.com/pdf/H2_AN202312281615150...
2    https://pdf.dfcfw.com/pdf/H2_AN202309281600193...
3    https://pdf.dfcfw.com/pdf/H2_AN202406071635887...
4    https://pdf.dfcfw.com/pdf/H2_AN202306301591947...
..                                                 ...
519  https://pdf.dfcfw.com/pdf/H2_AN202007061389895...
520  https://pdf.dfcfw.com/pdf/H2_AN202007061389821...
521  https://pdf.dfcfw.com/pdf/H2_AN201507130010192...
522  https://pdf.dfcfw.com/pdf/H2_AN201401220005024...
523  https://pdf.dfcfw.com/pdf/H2_AN201406160006074...
[524 rows x 12 columns]
```

##### 达标企业

接口: stock_register_db

目标地址: <https://data.eastmoney.com/xg/cyb/>

描述: 东方财富网-数据中心-新股数据-注册制审核-达标企业

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称           | 类型      | 描述      |
|--------------|---------|---------|
| 序号           | int32   | -       |
| 企业名称         | object  | -       |
| 经营范围         | object  | -       |
| 近三年营业收入-2019 | float64 | 注意单位: 元 |
| 近三年净利润-2019  | float64 | 注意单位: 元 |
| 近三年研发费用-2019 | object  | 注意单位: 元 |
| 近三年营业收入-2018 | float64 | 注意单位: 元 |
| 近三年净利润-2018  | float64 | 注意单位: 元 |
| 近三年研发费用-2018 | object  | 注意单位: 元 |
| 近三年营业收入-2017 | object  | 注意单位: 元 |
| 近三年净利润-2017  | object  | 注意单位: 元 |
| 近三年研发费用-2017 | object  | 注意单位: 元 |
| 近两年累计净利润     | float64 | 注意单位: 元 |

接口示例

```python
import akshare as ak

stock_register_db_df = ak.stock_register_db()
print(stock_register_db_df)
```

数据示例

```
        序号              企业名称  ... 近三年研发费用-2017      近两年累计净利润
0        1   上海宏力达信息技术股份有限公司  ...  19932141.20  3.360614e+08
1        2   上海阿拉丁生化科技股份有限公司  ...   8962209.85  1.171064e+08
2        3  河北华友文化遗产保护股份有限公司  ...   2203545.49  5.992881e+07
3        4    大连豪森设备制造股份有限公司  ...  38364081.96  6.224462e+07
4        5            九号有限公司  ...  91330278.85 -2.258809e+09
    ...               ...  ...          ...           ...
1713  1714  武汉同济现代医药科技股份有限公司  ...   2796051.27  2.762509e+07
1714  1715      上海雷腾软件股份有限公司  ...   7793124.89  1.014579e+08
1715  1716    上海银音信息科技股份有限公司  ...  12518776.19  1.107391e+07
1716  1717    上海致远绿色能源股份有限公司  ...  18035201.48  3.533665e+07
1717  1718    上海四维文化传媒股份有限公司  ...  16961496.21  2.896218e+07
```

#### 增发

接口: stock_qbzf_em

目标地址: <https://data.eastmoney.com/other/gkzf.html>

描述: 东方财富网-数据中心-新股数据-增发-全部增发

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 股票代码   | object  | -       |
| 股票简称   | object  | -       |
| 增发代码   | object  | -       |
| 发行方式   | object  | -       |
| 发行总数   | int64   | 注意单位: 股 |
| 网上发行   | object  | 注意单位: 股 |
| 发行价格   | float64 | -       |
| 最新价    | float64 | -       |
| 发行日期   | object  | -       |
| 增发上市日期 | object  | -       |
| 锁定期    | object  | -       |

接口示例

```python
import akshare as ak

stock_qbzf_em_df = ak.stock_qbzf_em()
print(stock_qbzf_em_df)
```

数据示例

```
      股票代码  股票简称 增发代码  发行方式  ...  最新价    发行日期  增发上市日期  锁定期
0     872931  无锡鼎邦  None  公开增发  ...    NaN  2024-03-27  2024-04-08  0.5年
1     837023  芭薇股份  None  公开增发  ...  13.10  2024-03-20  2024-03-29  0.5年
2     600773  西藏城投  None  定向增发  ...  12.21  2024-03-15  2024-04-02  0.5年
3     600038  中直股份  None  定向增发  ...  39.27  2024-03-14  2024-03-19    3年
4     600028  中国石化  None  定向增发  ...   6.50  2024-03-13  2024-03-18    3年
      ...   ...   ...   ...  ...    ...         ...         ...   ...
5656  601880  辽港股份  None  定向增发  ...   1.42         NaT  2021-02-09  None
5657  600056  中国医药  None  定向增发  ...  11.03         NaT  2013-08-01  None
5658  600372  中航机载  None  定向增发  ...  11.57         NaT  2023-04-19  None
5659  600827  百联股份  None  定向增发  ...   9.09         NaT  2011-08-31  None
5660  600332   白云山  None  定向增发  ...  29.13         NaT  2013-05-23  None
[5661 rows x 11 columns]
```

#### 配股

接口: stock_pg_em

目标地址: <https://data.eastmoney.com/xg/pg/>

描述: 东方财富网-数据中心-新股数据-配股

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型      | 描述      |
|--------|---------|---------|
| 股票代码   | object  | -       |
| 股票简称   | object  | -       |
| 配售代码   | object  | -       |
| 配股数量   | int64   | 注意单位: 股 |
| 配股比例   | object  | -       |
| 配股价    | float64 | -       |
| 最新价    | float64 | -       |
| 配股前总股本 | int64   | 注意单位: 股 |
| 配股后总股本 | int64   | 注意单位: 股 |
| 股权登记日  | object  | -       |
| 缴款起始日期 | object  | -       |
| 缴款截止日期 | object  | -       |
| 上市日    | object  | -       |

接口示例

```python
import akshare as ak

stock_pg_em_df = ak.stock_pg_em()
print(stock_pg_em_df)
```

数据示例

```
     股票代码  股票简称   配售代码  ... 缴款起始日期   缴款截止日期    上市日
0     000049  德赛电池  080049  ...  2023-11-30  2023-12-06  2023-12-25
1     600081  东风科技  700081  ...  2023-08-02  2023-08-08  2023-08-24
2     601916  浙商银行  760916  ...  2023-06-15  2023-06-21  2023-07-06
3     300475  香农芯创  380475  ...  2023-02-08  2023-02-14  2023-03-03
4     600459  贵研铂业  700459  ...  2022-12-14  2022-12-20  2023-01-04
      ...   ...     ...  ...         ...         ...         ...
1017  600651  飞乐音响    None  ...         NaT         NaT  1994-04-25
1018  600653  申华控股    None  ...         NaT         NaT  1993-06-10
1019  600609  金杯汽车    None  ...         NaT         NaT  1993-01-29
1020  600601  方正科技    None  ...         NaT         NaT  1992-06-10
1021  000002   万科A    None  ...  1991-06-01  1991-06-08         NaT
[1022 rows x 13 columns]
```

#### 股票回购数据

接口: stock_repurchase_em

目标地址: <https://data.eastmoney.com/gphg/hglist.html>

描述: 东方财富网-数据中心-股票回购-股票回购数据

限量: 单次返回所有历史数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称             | 类型      | 描述      |
|----------------|---------|---------|
| 序号             | int64   | -       |
| 股票代码           | object  | -       |
| 股票简称           | object  | -       |
| 最新价            | float64 | -       |
| 计划回购价格区间       | float64 | 注意单位: 元 |
| 计划回购数量区间-下限    | float64 | 注意单位: 股 |
| 计划回购数量区间-上限    | float64 | 注意单位: 股 |
| 占公告前一日总股本比例-下限 | float64 | 注意单位: % |
| 占公告前一日总股本比例-上限 | float64 | 注意单位: % |
| 计划回购金额区间-下限    | float64 | 注意单位: 元 |
| 计划回购金额区间-上限    | float64 | 注意单位: 元 |
| 回购起始时间         | object  | -       |
| 实施进度           | object  | -       |
| 已回购股份价格区间-下限   | float64 | 注意单位: % |
| 已回购股份价格区间-上限   | float64 | 注意单位: % |
| 已回购股份数量        | float64 | 注意单位: 股 |
| 已回购金额          | float64 | 注意单位: 元 |
| 最新公告日期         | object  | -       |

接口示例

```python
import akshare as ak

stock_repurchase_em_df = ak.stock_repurchase_em()
print(stock_repurchase_em_df)
```

数据示例

```
        序号 股票代码  股票简称  ...  已回购股份数量    已回购金额      最新公告日期
0        1  600028  中国石化  ...         NaN           NaN  2022-08-29
1        2  301021  英诺激光  ...      6500.0  1.625000e+05  2022-08-29
2        3  688185   康希诺  ...    500000.0  1.137614e+08  2022-08-29
3        4  603700  宁水集团  ...   2291336.0  4.005009e+07  2021-09-15
4        5  000338  潍柴动力  ...  55950000.0  6.822452e+08  2022-08-27
    ...     ...   ...  ...         ...           ...         ...
1977  1978  002048  宁波华翔  ...  23152838.0  1.598245e+08  2012-08-16
1978  1979  002032   苏泊尔  ...   2750000.0  3.467148e+07  2012-07-18
1979  1980  002054  德美化工  ...   5484773.0  5.473750e+07  2012-01-05
1980  1981  002048  宁波华翔  ...  13940012.0  1.442085e+08  2011-12-02
1981  1982  600380   健康元  ...  29252223.0  2.999997e+08  2011-11-30
```

#### 股本结构

接口: stock_zh_a_gbjg_em

目标地址: <https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html#/gbjg>

描述: 东方财富-A股数据-股本结构

限量: 单次返回所有历史数据

输入参数

| 名称     | 类型  | 描述                 |
|--------|-----|--------------------|
| symbol | str | symbol="603392.SH" |

输出参数

| 名称          | 类型      | 描述 |
|-------------|---------|----|
| 变更日期        | object  | -  |
| 总股本         | int64   | -  |
| 流通受限股份      | float64 | -  |
| 其他内资持股(受限)  | float64 | -  |
| 境内法人持股(受限)  | float64 | -  |
| 境内自然人持股(受限) | float64 | -  |
| 已流通股份       | float64 | -  |
| 已上市流通A股     | int64   | -  |
| 变动原因        | object  | -  |

接口示例

```python
import akshare as ak

stock_zh_a_gbjg_em_df = ak.stock_zh_a_gbjg_em(symbol="603392.SH")
print(stock_zh_a_gbjg_em_df)
```

数据示例

```
    变更日期       总股本    流通受限股份  ...    已流通股份    已上市流通A股        变动原因
0   2024-09-12  1265122774          NaN  ...  1265122774  1.265123e+09          回购
1   2024-01-15  1268206999          NaN  ...  1268206999  1.268207e+09    网下配售股份上市
2   2023-06-05  1268206999    3620778.0  ...  1268206999  1.264586e+09       转增股上市
3   2023-05-04   906070705    2586270.0  ...   906070705  9.034844e+08    首发限售股份上市
4   2023-01-13   906070705  664113571.0  ...   906070705  2.419571e+08    网下配售股份上市
5   2022-07-13   906070705  687390006.0  ...   906070705  2.186807e+08      增发A股上市
6   2022-04-21   880208000  661527301.0  ...   880208000  2.186807e+08  送股上市,转增股上市
7   2021-05-18   607040000  456225725.0  ...   607040000  1.508143e+08        送股上市
8   2021-04-29   433600000  325875518.0  ...   433600000  1.077245e+08    首发限售股份上市
9   2020-04-15   433600000  390000000.0  ...   433600000  4.360000e+07      首发A股上市
10  2018-11-16   390000000  390000000.0  ...   390000000           NaN       上市前股本
11  2016-06-24   361200000  361200000.0  ...   361200000           NaN       上市前股本
[12 rows x 9 columns]
```
