---
title: 资讯数据
description: AKShare 股票数据 - 资讯数据 接口整理
source: stock.md.txt
updated: 2025-11-17
---

# 资讯数据

#### 财经早餐-东财财富

接口：stock_info_cjzc_em

目标地址：https://stock.eastmoney.com/a/czpnc.html

描述：东方财富-财经早餐

限量：单次返回全部历史数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称   | 类型     | 描述 |
|------|--------|----|
| 标题   | object | -  |
| 摘要   | object | -  |
| 发布时间 | object | -  |
| 链接   | object | -  |

接口示例：

```python
import akshare as ak

stock_info_cjzc_em_df = ak.stock_info_cjzc_em()
print(stock_info_cjzc_em_df)
```

数据示例

```
                                       标题  ...                                                 链接
0                        东方财富财经早餐 3月13日周三  ...  http://finance.eastmoney.com/a/202403133009961...
1                        东方财富财经早餐 3月12日周二  ...  http://finance.eastmoney.com/a/202403113008262...
2                        东方财富财经早餐 3月11日周一  ...  http://finance.eastmoney.com/a/202403103007214...
3                         东方财富财经早餐 3月8日周五  ...  http://finance.eastmoney.com/a/202403073005282...
4                         东方财富财经早餐 3月7日周四  ...  http://finance.eastmoney.com/a/202403073004092...
..                                    ...  ...                                                ...
338                     东方财富财经早餐 10月14日周五  ...  http://finance.eastmoney.com/a/202210142528794...
339                     东方财富早盘内参 10月13日周四  ...  http://finance.eastmoney.com/a/202210132527637...
340                     东方财富早盘内参 10月12日周三  ...  http://finance.eastmoney.com/a/202210122526415...
341  【早盘内参】宁德时代：前三季度净利同比预增112.87%-132.22%  ...  http://finance.eastmoney.com/a/202210112525318...
342           【早盘内参】央行：进一步简化境外投资者进入中国投资流程  ...  http://finance.eastmoney.com/a/202210102524284...
[343 rows x 4 columns]
```

#### 全球财经快讯-东财财富

接口：stock_info_global_em

目标地址：https://kuaixun.eastmoney.com/7_24.html

描述：东方财富-全球财经快讯

限量：单次返回最近 200 条新闻数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称   | 类型     | 描述 |
|------|--------|----|
| 标题   | object | -  |
| 摘要   | object | -  |
| 发布时间 | object | -  |
| 链接   | object | -  |

接口示例：

```python
import akshare as ak

stock_info_global_em_df = ak.stock_info_global_em()
print(stock_info_global_em_df)
```

数据示例

```
                                     标题  ...                                                 链接
0                     法本信息与鸿蒙生态服务公司签约合作  ...  https://finance.eastmoney.com/a/20240313301075...
1    欧洲央行管委维勒鲁瓦：6月降息的可能性高于4月 但仍有可能在春季降息  ...  https://finance.eastmoney.com/a/20240313301075...
2        海马汽车：目前公司氢燃料电池汽车7X-H已开始小批量上线生产  ...  https://finance.eastmoney.com/a/20240313301075...
3     茉酸奶回应被消保委点名：目前配方只有酸奶和水果 后续有官方渠道回应  ...  https://finance.eastmoney.com/a/20240313301075...
4         大众重押合肥：ID.品牌将推U系列车型 计划建独立销售渠道  ...  https://finance.eastmoney.com/a/20240313301075...
..                                  ...  ...                                                ...
195              加速电动化 江淮汽车与大众中国拟增资合资公司  ...  https://finance.eastmoney.com/a/20240313301015...
196                    农业银行普惠贷款余额突破4万亿元  ...  https://finance.eastmoney.com/a/20240313301015...
197            中金公司：AI Agent或开启AI原生应用时代  ...  https://finance.eastmoney.com/a/20240313301015...
198                          日韩股市周三双双高开  ...  https://finance.eastmoney.com/a/20240313301015...
199             委内瑞拉：不允许阿根廷任何形式的飞机使用委领空  ...  https://finance.eastmoney.com/a/20240313301015...
[200 rows x 4 columns]
```

#### 全球财经快讯-新浪财经

接口：stock_info_global_sina

目标地址：https://finance.sina.com.cn/7x24

描述：新浪财经-全球财经快讯

限量：单次返回最近 20 条新闻数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称   | 类型     | 描述 |
|------|--------|----|
| 时间   | object | -  |
| 内容   | object | -  |

接口示例

```python
import akshare as ak

stock_info_global_sina_df = ak.stock_info_global_sina()
print(stock_info_global_sina_df)
```

数据示例

```
                     时间                                                 内容
0   2024-03-13 16:18:40  【Canalys：2023年Q4英特尔CPU出货5000万颗占比78% 是AMD的6倍】根据...
1   2024-03-13 16:18:19  俄罗斯别尔哥罗德市联邦安全局发布消息称，该部门大楼遭到乌军无人机袭击，没有造成人员伤亡，大楼...
2   2024-03-13 16:18:08  日本首相顾问Yata：（当被问及工资提议是否可能会推动在三月结束负利率时）政府不会干涉日本央...
3   2024-03-13 16:16:35  【基金经理：日企大赚而劳动力短缺，加薪5%不足为奇】“与往年相比，日本企业在加薪方面要开放得...
4   2024-03-13 16:15:41  【梅西代言白酒重新上架】多款梅西代言白酒已重新上架。3月13日搜索发现，赤水河白酒电商平台店...
5   2024-03-13 16:15:35         土耳其银行家表示，资产规模超过1000亿里拉的土耳其银行将执行15%的里拉准备金率。
6   2024-03-13 16:15:10                          地区官员表示，俄罗斯梁赞石油精炼厂的火灾已被扑灭。
7   2024-03-13 16:14:46  【九部门：鼓励在有条件的村布放智能快件箱】商务部等9部门发布关于推动农村电商高质量发展的实施...
8   2024-03-13 16:14:23        两名安全消息人士表示，以色列袭击了黎巴嫩南部城市泰尔附近的一辆汽车，导致两名乘客死亡。
9   2024-03-13 16:13:38  【九部门：造县域直播电商基地】商务部等9部门发布关于推动农村电商高质量发展的实施意见。其中提...
10  2024-03-13 16:12:30       土耳其银行家表示，资产规模超过5000亿里拉的土耳其银行将执行25%的里拉存款准备金率。
11  2024-03-13 16:12:25           名创优品美股盘前涨超4%，去年第四季度营收及毛利率双双创新高，拟派特别现金股息。
12  2024-03-13 16:11:08  【商务部等9部门发布关于推动农村电商高质量发展的实施】意见商务部等9部门发布关于推动农村电商...
13  2024-03-13 16:09:50  【乘联会：3月1-10日乘用车市场零售35.5万辆 同比去年同期增长4%】乘联会数据显示，3...
14  2024-03-13 16:08:56  【港股收评：恒指收跌0.07% 科指收涨0.34%】港股收盘，恒指收跌0.07%，科指收涨0...
15  2024-03-13 16:08:01  【韩国总统尹锡悦承诺到2027年将航天产业发展相关预算增至1.5万亿韩元】韩国总统尹锡悦3月...
16  2024-03-13 16:05:34  【恢复两融业务正常平仓措施？业内人士否认】今天盘中，市场突然传出：风险解除，市场秩序恢复正常...
17  2024-03-13 16:05:26  【中欧民航合作项目预先飞行计划研讨会在京召开】日前，中欧民航合作项目（EU-CHINA AP...
18  2024-03-13 16:05:21          英伟达在美股盘前上涨1.8%，报936美元/股。上一交易日，英伟达收盘大涨超7%。
19  2024-03-13 16:04:07  【中国或将调查法国酒业是否与欧盟调查中国电车有关？外交部回应】外交部发言人汪文斌主持例行记者...
```

#### 快讯-富途牛牛

接口：stock_info_global_futu

目标地址：https://news.futunn.com/main/live

描述：富途牛牛-快讯

限量：单次返回最近 50 条新闻数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称   | 类型     | 描述 |
|------|--------|----|
| 标题   | object | -  |
| 内容   | object | -  |
| 发布时间 | object | -  |
| 链接   | object | -  |

接口示例

```python
import akshare as ak

stock_info_global_futu_df = ak.stock_info_global_futu()
print(stock_info_global_futu_df)
```

数据示例

```
                                               标题  ...                                             链接
0                                                  ...  https://news.futunn.com/flash/16697438?src=48
1      Canalys：2023年Q4英特尔CPU出货5000万颗占比78% 是AMD的6倍  ...  https://news.futunn.com/flash/16697433?src=48
2                                                  ...  https://news.futunn.com/flash/16697427?src=48
3                        基金经理：日企大赚而劳动力短缺，加薪5%不足为奇  ...  https://news.futunn.com/flash/16697407?src=48
4                             九部门：鼓励在有条件的村布放智能快件箱  ...  https://news.futunn.com/flash/16697383?src=48
5                                   九部门：造县域直播电商基地  ...  https://news.futunn.com/flash/16697371?src=48
6                                                  ...  https://news.futunn.com/flash/16697361?src=48
7                       商务部等9部门发布关于推动农村电商高质量发展的实施  ...  https://news.futunn.com/flash/16697341?src=48
8                                                  ...  https://news.futunn.com/flash/16697328?src=48
9             乘联会：3月1-10日乘用车市场零售35.5万辆 同比去年同期增长4%  ...  https://news.futunn.com/flash/16697322?src=48
10                            恢复两融业务正常平仓措施？业内人士否认  ...  https://news.futunn.com/flash/16697275?src=48
11                          中欧民航合作项目预先飞行计划研讨会在京召开  ...  https://news.futunn.com/flash/16697270?src=48
12                                                 ...  https://news.futunn.com/flash/16697271?src=48
13                          蔚来推出买车送手机活动，面向2024款车型  ...  https://news.futunn.com/flash/16697255?src=48
14                                                 ...  https://news.futunn.com/flash/16697185?src=48
15                           洛阳钼业：KFM 2月产铜量再创历史新高  ...  https://news.futunn.com/flash/16697158?src=48
16                     策略师：人为压低通胀，日本央行无权继续维持超宽松政策  ...  https://news.futunn.com/flash/16697130?src=48
17                                                 ...  https://news.futunn.com/flash/16697108?src=48
18                                                 ...  https://news.futunn.com/flash/16697090?src=48
19                              法本信息与鸿蒙生态服务公司签约合作  ...  https://news.futunn.com/flash/16697083?src=48
20                            港股医药股尾盘拉升 和黄医药涨超10%  ...  https://news.futunn.com/flash/16697084?src=48
21                   美众议院将就“封禁TikTok”法案进行表决 外交部回应  ...  https://news.futunn.com/flash/16697069?src=48
22                       互金协会：建议将所有涉金融APP纳入备案管理范围  ...  https://news.futunn.com/flash/16697058?src=48
23                           凯投宏观：英国经济在隧道的尽头看到了光明  ...  https://news.futunn.com/flash/16697054?src=48
24                  报告：去年全球艺术品销售额下降4%，中国销售额逆势增长9%  ...  https://news.futunn.com/flash/16697051?src=48
25                          高盛：沟通不足，日本央行会推迟一个月再加息  ...  https://news.futunn.com/flash/16697046?src=48
26                                                 ...  https://news.futunn.com/flash/16697048?src=48
27                                                 ...  https://news.futunn.com/flash/16696995?src=48
28                             天津调整公积金贷款首付比例 首套两成  ...  https://news.futunn.com/flash/16696984?src=48
29                                                 ...  https://news.futunn.com/flash/16696915?src=48
30                                                 ...  https://news.futunn.com/flash/16696860?src=48
31                        小米生态链模式十年来最大调整，提出分级管理策略  ...  https://news.futunn.com/flash/16696189?src=48
32                         《我国支持科技创新主要税费优惠政策指引》发布  ...  https://news.futunn.com/flash/16696803?src=48
33               美国家运输安全委员会将于8月就波音客机“掉门”事故举行调查听证会  ...  https://news.futunn.com/flash/16696764?src=48
34                                                 ...  https://news.futunn.com/flash/16696744?src=48
35                                                 ...  https://news.futunn.com/flash/16696702?src=48
36                                                 ...  https://news.futunn.com/flash/16696682?src=48
37                 香港文旅局：首两个月日均访港人次达13万 旅游业复苏势头强劲  ...  https://news.futunn.com/flash/16696679?src=48
38                                                 ...  https://news.futunn.com/flash/16696632?src=48
39                                                 ...  https://news.futunn.com/flash/16696592?src=48
40                         北向资金净买入15.67亿元，连续4日净买入  ...  https://news.futunn.com/flash/16696597?src=48
41                          财经网站Forexlive评英国GDP数据  ...  https://news.futunn.com/flash/16696577?src=48
42                                                 ...  https://news.futunn.com/flash/16696578?src=48
43  AI研发投资超100亿：荣耀AI PC技术将在荣耀MagicBook Pro 16全面落地  ...  https://news.futunn.com/flash/16696540?src=48
44                    A股收评：沪指缩量调整跌0.4% 传媒、游戏股逆势大涨  ...  https://news.futunn.com/flash/16696512?src=48
45                   二手平台VisionPro租赁每小时199元 需3万押金  ...  https://news.futunn.com/flash/16696336?src=48
46            小米汽车 SU7 新配置申报：宁德时代磷酸铁锂电池，220kW 单电机  ...  https://news.futunn.com/flash/16696331?src=48
47                              大众汽车计划今年推出30多款新产品  ...  https://news.futunn.com/flash/16696328?src=48
48               极氪发布安徽马鞍山极氪 001 过火事件说明：电池无异常、无燃烧  ...  https://news.futunn.com/flash/16696320?src=48
49                 中钢协：3月上旬重点统计钢铁企业共生产钢材1927.62万吨  ...  https://news.futunn.com/flash/16696278?src=48
[50 rows x 4 columns]
```

#### 全球财经直播-同花顺财经

接口：stock_info_global_ths

目标地址：https://news.10jqka.com.cn/realtimenews.html

描述：同花顺财经-全球财经直播

限量：单次返回最近 20 条新闻数据

输入参数

| 名称 | 类型 | 描述 |
|----|----|----|
| -  | -  | -  |

输出参数

| 名称   | 类型     | 描述 |
|------|--------|----|
| 标题   | object | -  |
| 内容   | object | -  |
| 发布时间 | object | -  |
| 链接   | object | -  |

接口示例

```python
import akshare as ak

stock_info_global_ths_df = ak.stock_info_global_ths()
print(stock_info_global_ths_df)
```

数据示例

```
                                            标题  ...                                                 链接
0                       机构论市：指数一波三折 传媒、游戏逆势走强！  ...  https://news.10jqka.com.cn/20240313/c655877020...
1                            日本决定启动与孟加拉国的EPA谈判  ...  https://news.10jqka.com.cn/20240313/c655876966...
2   Canalys：2023年Q4英特尔CPU出货5000万颗占比78% 是AMD的6倍  ...  https://news.10jqka.com.cn/20240313/c655876921...
3                  英伟达美股盘前涨近2% 市值再度升至2.3万亿美元上方  ...  https://news.10jqka.com.cn/20240313/c655876900...
4                          九部门：鼓励在有条件的村布放智能快件箱  ...  https://news.10jqka.com.cn/20240313/c655876856...
5                               九部门：打造县域直播电商基地  ...  https://news.10jqka.com.cn/20240313/c655876844...
6          乘联会：3月1-10日乘用车市场零售35.5万辆 同比去年同期增长4%  ...  https://news.10jqka.com.cn/20240313/c655876794...
7            商务部等9部门：用5年时间在全国培育100个左右农村电商“领跑县”  ...  https://news.10jqka.com.cn/20240313/c655876780...
8                     港股收评：恒指收跌0.07% 科指收涨0.34%  ...  https://news.10jqka.com.cn/20240313/c655876701...
9                        蔚来推出买车送手机活动，面向2024款车型  ...  https://news.10jqka.com.cn/20240313/c655876687...
10         韩国总统尹锡悦承诺到2027年将航天产业发展相关预算增至1.5万亿韩元  ...  https://news.10jqka.com.cn/20240313/c655876677...
11                         恢复两融业务正常平仓措施？业内人士否认  ...  https://news.10jqka.com.cn/20240313/c655876644...
12                       中欧民航合作项目预先飞行计划研讨会在京召开  ...  https://news.10jqka.com.cn/20240313/c655876634...
13                                      欧股多数高开  ...  https://news.10jqka.com.cn/20240313/c655876611...
14                        洛阳钼业：KFM 2月产铜量再创历史新高  ...  https://news.10jqka.com.cn/20240313/c655876547...
15                    第十三届中国数控机床展览会将于4月8日在上海启幕  ...  https://news.10jqka.com.cn/20240313/c655876458...
16                        浙大网新：子公司中标1.28亿元施工项目  ...  https://news.10jqka.com.cn/20240313/c655876449...
17                外交部：不管谁当选下一届美国总统 我们都希望更好造福两国  ...  https://news.10jqka.com.cn/20240313/c655876428...
18                   小米SU7展车已进驻王府井门店，店内仍在装修未开业  ...  https://news.10jqka.com.cn/20240313/c655876412...
19       中证指数有限公司将发布中证港股通人工智能主题指数和中证香港人工智能主题指数  ...  https://news.10jqka.com.cn/20240313/c655876408...
[20 rows x 4 columns]
```

#### 电报-财联社

接口：stock_info_global_cls

目标地址：https://www.cls.cn/telegraph

描述：财联社-电报

限量：单次返回指定 symbol 的最近 20 条财联社-电报的数据

输入参数

| 名称     | 类型  | 描述                                 |
|--------|-----|------------------------------------|
| symbol | str | symbol="全部"；choice of {"全部", "重点"} |

输出参数

| 名称   | 类型     | 描述  |
|------|--------|-----|
| 标题   | object | -   |
| 内容   | object | -   |
| 发布日期 | object | -   |
| 发布时间 | object | -   |

接口示例：

```python
import akshare as ak

stock_info_global_cls_df = ak.stock_info_global_cls(symbol="全部")
print(stock_info_global_cls_df)
```

数据示例

```
                               标题  ...      发布时间
0    华为轮值董事长徐直军谈鸿蒙生态未来目标：拥有10万个应用  ...  14:05:03
1       中国牵头首个冷链物流无接触配送领域国际标准正式发布  ...  14:12:02
2           以军袭击黎巴嫩首都住宅楼 死亡人数升至5人  ...  14:37:34
3            上交所与三大石油石化集团将进一步深化合作  ...  14:50:34
4                                  ...  14:56:22
5    至少19人食用后患病 美国企业紧急召回近76吨牛肉泥产品  ...  15:13:18
6       《加强长江流域生物多样性司法保护倡议书》在武汉发布  ...  15:27:53
7               阿联酋哈伊马角酋长一行到访亿航智能  ...  15:41:35
8           以军称空袭贝鲁特南郊多个真主党武装军事目标  ...  15:43:30
9          以军空袭加沙地带多地 致17名巴勒斯坦人死亡  ...  15:46:34
10             北约秘书长在美国佛州与特朗普举行会谈  ...  15:49:04
11     经济观察报：央国企市值管理更多相关政策在酝酿和推进中  ...  15:56:06
12      华为徐直军：鸿蒙生态就是基于开源鸿蒙共建共享的生态  ...  16:00:29
13  我国牵头的首个工业化建造自动标识与数据采集应用国际标准发布  ...  16:02:03
14     AI辅助诊断首次被列入 国家医保局解读17批价格立项  ...  16:12:22
15            以军袭击贝鲁特中部住宅楼 已致9人死亡  ...  16:32:07
16        俄宣布12月1日起临时禁止废旧贵金属出口6个月  ...  16:36:40
17                                 ...  16:41:55
18          波兰农民在波乌边境抗议 将封锁梅迪卡过境点  ...  16:56:41
19            吉林省将迎大范围明显雨雪及寒潮大风天气  ...  17:17:38
[20 rows x 4 columns]
```
