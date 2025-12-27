# 批次5分析结果：图片41-50

## 概览

图片41-50包含InfoData模块的股东、股权结构相关接口。

---

## 提取的接口信息

### 7. InfoData 模块 - 股东/股权接口

#### 7.1 get_share_holder - 十大股东 (3.5.5.6)

```python
ad.InfoData.get_share_holder(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，十大股东信息

#### 7.2 get_holder_num - 股东人数 (3.5.5.7)

```python
ad.InfoData.get_holder_num(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，股东人数历史数据

#### 7.3 get_equity_structure - 股本结构 (3.5.5.8)

```python
ad.InfoData.get_equity_structure(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，股本结构变化信息

#### 7.4 get_equity_pledge_freeze - 股权质押冻结 (3.5.5.9)

```python
ad.InfoData.get_equity_pledge_freeze(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，股权质押冻结信息

#### 7.5 get_equity_restricted - 限售解禁 (3.5.5.10)

```python
ad.InfoData.get_equity_restricted(
    code_list=["000001.SZ"],
    local_path="./data",
    is_local=True
)
```

**返回**: DataFrame，限售解禁计划

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| get_share_holder | 3.5.5.6 | 是 | 已实现 |
| get_holder_num | 3.5.5.7 | 是 | 已实现 |
| get_equity_structure | 3.5.5.8 | 是 | 已实现 |
| get_equity_pledge_freeze | 3.5.5.9 | 是 | 已实现 |
| get_equity_restricted | 3.5.5.10 | 是 | 已实现 |
