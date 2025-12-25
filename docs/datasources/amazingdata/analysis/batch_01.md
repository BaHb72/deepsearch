# 批次1分析结果：图片01-10

## 概览
图片01-10主要包含SDK安装配置、登录接口和BaseData模块基础接口。

---

## 提取的接口信息

### 1. SDK 安装与登录 (图片01-04)
```python
# 安装
pip install tgw-1.7.1-py3-none-any.whl
pip install AmazingData-1.0.0-cp312-none-any.whl

# 登录
import AmazingData as ad
ad.login(
    username="xxx",
    password="xxx", 
    host="xxx.xxx.xxx.xxx",
    port=xxxx
)
```

### 2. BaseData 模块接口 (图片05-10)

#### 2.1 get_code_list - 每日最新代码列表
```python
ad.BaseData.get_code_list(security_type="EXTRA_STOCK_A")
```
**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| security_type | str | 代码类型，默认EXTRA_STOCK_A |

**返回**: 代码列表 List[str]

#### 2.2 get_code_info - 每日最新证券信息
```python
ad.BaseData.get_code_info(security_type="EXTRA_STOCK_A")
```
**参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| security_type | str | 代码类型 |

**返回**: DataFrame，包含symbol、pre_close、high_limited、low_limited等

#### 2.3 get_future_code_list - 期货代码列表
```python
ad.BaseData.get_future_code_list(security_type="EXTRA__FUTURE")
```

#### 2.4 get_option_code_list - 期权代码列表
```python
ad.BaseData.get_option_code_list(security_type="EXTRA_ETF_OP")
```

---

## security_type 枚举值 (图片08-10)

### 股票类型
- `EXTRA_STOCK_A` - 沪深北A股
- `SH_A` - 上海A股
- `SZ_A` - 深圳A股  
- `BJ_A` - 北京A股
- `EXTRA_STOCK_A_SH_SZ` - 沪深A股

### 指数类型
- `EXTRA_INDEX_A` - 沪深北指数
- `SH_INDEX` - 上海指数
- `SZ_INDEX` - 深圳指数
- `BJ_INDEX` - 北京指数

### ETF类型
- `EXTRA_ETF` - 沪深ETF
- `SH_ETF` - 上海ETF
- `SZ_ETF` - 深圳ETF

### 可转债
- `EXTRA_KZZ` - 沪深可转债
- `SH_KZZ` - 上海可转债
- `SZ_KZZ` - 深圳可转债

### 港股通
- `EXTRA_HKT` - 沪深港股通
- `SH_HKT` - 上海港股通
- `SZ_HKT` - 深圳港股通

### 期货类型
- `EXTRA_FUTURE` - 全部期货
- `ZJ_FUTURE` - 中金所期货
- `SQ_FUTURE` - 上期所期货
- `DS_FUTURE` - 大商所期货
- `ZS_FUTURE` - 郑商所期货
- `SN_FUTURE` - 上能源期货

### 期权类型
- `EXTRA_ETF_OP` - ETF期权
- `SH_OPTION` - 上海期权
- `SZ_OPTION` - 深圳期权

---

## 实现状态对比

| 接口 | 文档 | 现有实现 | 状态 |
|------|------|----------|------|
| login | 是 | 是 | 已实现 |
| get_code_list | 是 | 是 | 已实现 |
| get_code_info | 是 | 是 | 已实现 |
| get_future_code_list | 是 | 是 | 已实现 |
| get_option_code_list | 是 | 是 | 已实现 |
