# 指标口径白皮书 · V4（AmazingData-only）

> 本白皮书仅基于 AmazingData 手册中**现有**接口字段推导而来，服务于实盘指标计算与统一口径。

## 1. 盘中资金指标

- **强度** `amount_t`：Level‑1 `amount`（成交额，单位：元）。
- **速度** `speed_{Δ}`：`(amount_t – amount_{t-Δ}) / Δ分钟`，默认 Δ=1。
- **加速度** `accel_{Δ}`：`speed_{Δ}(t) – speed_{Δ}(t-Δ)`。
- **分钟曲线**：使用 `query_kline`（1/5/15 分钟）对 `amount/volume` 做平滑展示。

## 2. 盘口质量指标

- **OBI**：`(ΣBid1..5Vol – ΣAsk1..5Vol) / (ΣBid1..5Vol + ΣAsk1..5Vol)`。
- **EIS**：`(Ask1 – Bid1)/Mid × speed_{Δ}`，其中 `Mid=(Ask1+Bid1)/2`。
- **NTM**：`num_trades` 的滚动增速（对数差分/线性差分取其一）。
- **封单金额**：当 `last≈high_limited` 且卖侧无效时，`lock = bid_volume1 × high_limited`。
- **封单稳定度**：`min( lock_{1m_hold}, lock_{3m_hold}, lock_{5m_hold} ) / lock_{t0}`。

## 3. 竞价质量（9:15–9:25）

- **阶段识别**：`trading_phase_code`（上交所 `C`、深交所 `O`）。
- **价稳性**：竞价末 2 分钟参考价序列的方差（以可得快照近似）。

## 4. ETF 指标

- **溢价率**：`premium = last/iopv - 1`（仅基金品种提供 `iopv`）。
- **概念代理**：`S(ETF)=TopK{ corr(stock, ETF) }`（收益或资金速度相关性）。

## 5. 两融（T‑1）

- 直接引用 `get_margin_summary/detail` 字段，统一单位与小数精度。

## 6. 外部资产参考（可选）

- **夜盘对齐**：遵循手册夜盘切分；窗口内对齐分钟序列后再计算 `corr/xcorr/lag`。

## 7. 供给/约束与风格/筹码

- **承载力评分**：`score = EventStrength × Liquidity_{10,20}`（事件强度 × 近端流动性均值/方差）。
- **风格三轴**：盈利质量、成长、负债纪律（由三表与业绩字段经标准化、去极值后合成）。
- **筹码**：股东户数趋势、十大股东集中度、流通盘占比（股本结构）。

## 8. 过滤与复权

- **过滤**：`get_history_stock_status` 的 ST/停牌/除权，剔除不可交易/异常样本。
- **复权**：统一使用 `get_backward_factor/get_adj_factor` 的口径，保证跨期可比。
