---
title: ESG 评级
description: AKShare 股票数据 - ESG 评级 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# ESG 评级

#### ESG 评级数据

接口: stock_esg_rate_sina

目标地址: <https://finance.sina.com.cn/esg/grade.shtml>

描述: 新浪财经-ESG评级中心-ESG评级-ESG评级数据

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称    | 类型     | 描述 |
|-------|--------|----|
| 成分股代码 | object | -  |
| 评级机构  | object | -  |
| 评级    | object | -  |
| 评级季度  | object | -  |
| 标识    | object | -  |
| 交易市场  | object | -  |

接口示例

```python
import akshare as ak

stock_esg_rate_sina_df = ak.stock_esg_rate_sina()
print(stock_esg_rate_sina_df)
```

数据示例

```
    成分股代码              评级机构     评级    评级季度             标识 交易市场
0      SZ000001             中财绿金院     A-  2022Q4            NaN   cn
1      SZ000001              商道融绿     B+  2022Q4            NaN   cn
2      SZ000001                盟浪      A  2022Q2            NaN   cn
3      SZ000001               中诚信    AA-  2023Q3            NaN   cn
4      SZ000001  晨星Sustainalytics  24.96  2022Q4  Comprehensive   cn
         ...               ...    ...     ...            ...  ...
46888   HK02361                盟浪      -  2022Q2            NaN   hk
46889   HK02361               中诚信     BB  2023Q3            NaN   hk
46890   HK02361  晨星Sustainalytics      -  2022Q4                  hk
46891   HK02361                妙盈      -  2022Q2            NaN   hk
46892   HK02361             华测CTI      -  2022Q1            NaN   hk
[46893 rows x 6 columns]
```

#### MSCI

接口: stock_esg_msci_sina

目标地址: <https://finance.sina.com.cn/esg/grade.shtml>

描述: 新浪财经-ESG评级中心-ESG评级-MSCI

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型      | 描述 |
|--------|---------|----|
| 股票代码   | object  | -  |
| ESG评分  | object  | -  |
| 环境总评   | float64 | -  |
| 社会责任总评 | float64 | -  |
| 治理总评   | float64 | -  |
| 评级日期   | object  | -  |
| 交易市场   | object  | -  |

接口示例

```python
import akshare as ak

stock_esg_msci_sina_df = ak.stock_esg_msci_sina()
print(stock_esg_msci_sina_df)
```

数据示例

```
        股票代码 ESG评分 环境总评 社会责任总评 治理总评 评级日期 交易市场
0      00019.HK   AAA   7.0     7.3   6.3  2024-04-24   HK
1     000513.SZ   AAA   6.8     6.4   6.1  2024-06-25   CN
2      00066.HK   AAA   7.2     5.6   6.5  2024-07-11   HK
3      00087.HK   AAA   7.0     7.3   6.3  2024-04-24   HK
4      00992.HK   AAA   5.1     6.2   5.5  2024-07-08   HK
...         ...   ...   ...     ...   ...         ...  ...
4619   UONEK.US   CCC   7.0     3.2   1.0  2024-06-24   US
4620     UVE.US   CCC   1.9     2.0   5.4  2024-07-08   US
4621     VTS.US   CCC   1.1     2.4   6.8  2024-04-24   US
4622    WULF.US   CCC   0.3     1.3   3.9  2024-05-20   US
4623    ZETA.US   CCC   6.7     3.1   2.0  2024-06-24   US
[4624 rows x 7 columns]
```

#### 路孚特

接口: stock_esg_rft_sina

目标地址: <https://finance.sina.com.cn/esg/grade.shtml>

描述: 新浪财经-ESG评级中心-ESG评级-路孚特

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称       | 类型      | 描述 |
|----------|---------|----|
| 股票代码     | object  | -  |
| ESG评分    | object  | -  |
| ESG评分日期  | object  | -  |
| 环境总评     | float64 | -  |
| 环境总评日期   | float64 | -  |
| 社会责任总评   | float64 | -  |
| 社会责任总评日期 | object  | -  |
| 治理总评     | object  | -  |
| 治理总评日期   | object  | -  |
| 争议总评     | object  | -  |
| 争议总评日期   | object  | -  |
| 行业       | object  | -  |
| 交易所      | object  | -  |

接口示例

```python
import akshare as ak

stock_esg_rft_sina_df = ak.stock_esg_rft_sina()
print(stock_esg_rft_sina_df)
```

数据示例

```
           股票代码     ESG评分     ESG评分日期  ...      争议总评日期          行业   交易所
0          MNTX   10.9(D)  2024-03-23  ...  2023-08-26  卡车-建筑-农用机械  纳斯达克
1     600958.SH  52.3(B-)  2024-03-23  ...  2023-08-26         证券Ⅱ   上交所
2     000799.SZ  27.4(C-)  2024-03-23  ...  2023-08-26         白酒Ⅱ   深交所
3     600745.SH  52.5(B-)  2024-03-23  ...  2023-09-09        消费电子   上交所
4         DISCA   59.9(B)  2024-03-23  ...  2024-03-16     有线-卫星电视  纳斯达克
         ...       ...         ...  ...         ...         ...   ...
5418    BILI.US   35.3(C)  2024-03-23  ...  2024-03-23        ????  纳斯达克
5419    TCOM.US  29.0(C-)  2024-03-23  ...  2023-12-16        ????  纳斯达克
5420     HCM.US  52.4(B-)  2024-03-23  ...  2023-08-26     ???????  纳斯达克
5421    XPEV.US   60.4(B)  2024-03-23  ...  2023-08-26          ??   纽交所
5422      LI.US   35.7(C)  2024-03-23  ...  2023-09-23          ??  纳斯达克
[5423 rows x 13 columns]
```

#### 秩鼎

接口: stock_esg_zd_sina

目标地址: <https://finance.sina.com.cn/esg/grade.shtml>

描述: 新浪财经-ESG评级中心-ESG评级-秩鼎

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型     | 描述 |
|--------|--------|----|
| 股票代码   | object | -  |
| ESG评分  | object | -  |
| 环境总评   | object | -  |
| 社会责任总评 | object | -  |
| 治理总评   | object | -  |
| 评分日期   | object | -  |

接口示例

```python
import akshare as ak

stock_esg_zd_sina_df = ak.stock_esg_zd_sina()
print(stock_esg_zd_sina_df)
```

数据示例

```
       股票代码      ESG评分     环境总评   社会责任总评   治理总评    评分日期
0     600775.SH   70.96(AA)    68.36(A)    65.06(A)   78.76(AA)  2024-03-31
1     601717.SH   78.64(AA)  87.28(AAA)  57.09(BBB)  89.15(AAA)  2024-03-31
2     600801.SH   79.78(AA)  85.55(AAA)    68.95(A)  82.06(AAA)  2024-03-31
3     601618.SH   78.31(AA)  86.90(AAA)    64.58(A)  81.37(AAA)  2024-03-31
4     600808.SH   78.17(AA)   78.22(AA)    67.38(A)  87.46(AAA)  2024-03-31
         ...         ...         ...         ...         ...         ...
7670   00247.HK   70.46(AA)   78.32(AA)    63.93(A)    67.50(A)  2024-03-31
7671  301016.SZ   51.54(BB)   36.89(CC)    46.12(B)   73.94(AA)  2024-03-31
7672   03309.HK  56.38(BBB)  56.22(BBB)   35.18(CC)   72.42(AA)  2024-03-31
7673  301166.SZ   51.82(BB)    27.78(C)   39.81(CC)  81.81(AAA)  2024-03-31
7674  837212.BJ    46.57(B)    34.34(C)   51.46(BB)  55.51(BBB)  2024-03-31
[7675 rows x 6 columns]
```

#### 华证指数

接口: stock_esg_hz_sina

目标地址: <https://finance.sina.com.cn/esg/grade.shtml>

描述: 新浪财经-ESG评级中心-ESG评级-华证指数

限量: 单次返回所有数据

输入参数

| 名称  | 类型  | 描述  |
|-----|-----|-----|
| -   | -   | -   |

输出参数

| 名称     | 类型      | 描述 |
|--------|---------|----|
| 日期     | object  | -  |
| 股票代码   | object  | -  |
| 交易市场   | object  | -  |
| 股票名称   | object  | -  |
| ESG评分  | float64 | -  |
| ESG等级  | object  | -  |
| 环境     | float64 | -  |
| 环境等级   | object  | -  |
| 社会     | float64 | -  |
| 社会等级   | object  | -  |
| 公司治理   | float64 | -  |
| 公司治理等级 | object  | -  |

接口示例

```python
import akshare as ak

stock_esg_hz_sina_df = ak.stock_esg_hz_sina()
print(stock_esg_hz_sina_df)
```

数据示例

```
        日期       股票代码 交易市场   股票名称  ESG评分  ... 环境等级     社会 社会等级   公司治理 公司治理等级
0     2023-04-30  300760.SZ   cn   迈瑞医疗  88.85  ...  BBB  92.77   AA  89.90      A
1     2023-04-30  601825.SH   cn   沪农商行  88.09  ...  BBB  88.64    A  89.79      A
2     2023-04-30  601166.SH   cn   兴业银行  88.08  ...   AA  86.00    A  88.78      A
3     2023-04-30  300021.SZ   cn   大禹节水  87.91  ...    A  91.78   AA  85.77      A
4     2023-04-30  600803.SH   cn   新奥股份  87.90  ...    A  90.49   AA  85.99      A
          ...        ...  ...    ...    ...  ...  ...    ...  ...    ...    ...
5159  2023-04-30  000150.SZ   cn  *ST宜康  60.24  ...    C  69.49  CCC  53.14      C
5160  2023-04-30  600242.SH   cn  *ST中昌  59.79  ...    C  68.36  CCC  54.08      C
5161  2023-04-30  000752.SZ   cn  *ST西发  59.55  ...    C  67.36  CCC  56.29      C
5162  2023-04-30  688086.SH   cn  *ST紫晶  57.11  ...   CC  63.37   CC  47.49      C
5163  2023-04-30  000038.SZ   cn  *ST大通  56.95  ...   CC  65.05  CCC  49.79      C
[5164 rows x 12 columns]
```
