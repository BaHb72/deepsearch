# Web 应用中存在未使用的变量声明

> 发现日期: 2026-01-16
> 发现位置: apps/web/src (多个文件)
> 类型: code-quality
> 严重程度: low
> 状态: resolved

---

## 问题描述

Web 前端代码中存在多个未使用的变量声明（以 `_` 前缀命名），导致 TypeScript 产生 TS6133 警告。这些变量可能是重构过程中遗留的，或者是预留但未实现的功能。

### 现象

运行 `npx tsc --noEmit` 时出现以下警告：

```text
src/App.tsx(25,7): error TS6133: '_TTradingPage' is declared but its value is never read.
src/components/strategy/StrategySelector.tsx(108,11): error TS6133: '_categories' is declared but its value is never read.
src/components/strategy/TradingViewIntradayChart.tsx(81,10): error TS6133: '_timeToMinuteIndex' is declared but its value is never read.
src/components/strategy/TradingViewIntradayChart.tsx(115,11): error TS6133: '_dayOffset' is declared but its value is never read.
src/components/strategy/TradingViewIntradayChart.tsx(548,15): error TS6133: '_toolTipWidth' is declared but its value is never read.
src/components/strategy/TradingViewIntradayChart.tsx(549,15): error TS6133: '_toolTipHeight' is declared but its value is never read.
src/components/strategy/TradingViewIntradayChart.tsx(661,19): error TS6133: '_coordinate' is declared but its value is never read.
src/pages/SystemConfig/DatabaseConfigWithStore.tsx(56,7): error TS6133: '_formatTimestamp' is declared but its value is never read.
src/pages/SystemConfig/LogConfig.tsx(170,11): error TS6133: '_levelColor' is declared but its value is never read.
```text

### 影响

- 代码质量降低，存在无用代码
- TypeScript 检查输出中存在噪音，可能掩盖真正的问题
- 增加维护负担

---

## 发现上下文

> 在执行"API 响应统一解包方案"实施时发现此问题

在运行 TypeScript 类型检查验证修改是否正确时，发现这些预存的警告。

---

## 相关文件

| 文件 | 行号 | 变量名 |
|------|------|--------|
| `src/App.tsx` | 25 | `_TTradingPage` |
| `src/components/strategy/StrategySelector.tsx` | 108 | `_categories` |
| `src/components/strategy/TradingViewIntradayChart.tsx` | 81 | `_timeToMinuteIndex` |
| `src/components/strategy/TradingViewIntradayChart.tsx` | 115 | `_dayOffset` |
| `src/components/strategy/TradingViewIntradayChart.tsx` | 548 | `_toolTipWidth` |
| `src/components/strategy/TradingViewIntradayChart.tsx` | 549 | `_toolTipHeight` |
| `src/components/strategy/TradingViewIntradayChart.tsx` | 661 | `_coordinate` |
| `src/pages/SystemConfig/DatabaseConfigWithStore.tsx` | 56 | `_formatTimestamp` |
| `src/pages/SystemConfig/LogConfig.tsx` | 170 | `_levelColor` |

---

## 建议修复方案

### 方案 1: 删除未使用变量

直接删除这些未使用的变量声明。需要确认：

- 这些变量是否真的不需要
- 是否有计划在未来使用

### 方案 2: 启用使用

如果这些变量有实际用途但被遗忘实现，需要补全相关逻辑。

### 预估工作量

- [x] 小（< 30 分钟）
- [ ] 中（30分钟 - 2小时）
- [ ] 大（> 2小时）

---

## 备注

- `_` 前缀通常用于表示"已知未使用"的变量，可能是解构时故意忽略的
- 需要逐个检查确认是否可以安全删除
- 特别注意 `TradingViewIntradayChart.tsx` 文件，有5个未使用变量，可能是重构不完整

---

## 解决记录

> 解决日期: 2026-01-16
> 解决方式: 删除所有未使用的变量和函数
> 相关提交: (待提交)

### 修复详情

| 文件 | 删除内容 |
|------|----------|
| `App.tsx` | 删除 `_TTradingPage` 懒加载组件 |
| `StrategySelector.tsx` | 删除 `_categories` 变量及注释 |
| `TradingViewIntradayChart.tsx` | 删除 `_timeToMinuteIndex` 函数（28行） |
| `TradingViewIntradayChart.tsx` | 删除 `_dayOffset` 变量 |
| `TradingViewIntradayChart.tsx` | 删除 `_toolTipWidth`, `_toolTipHeight` 常量 |
| `TradingViewIntradayChart.tsx` | 删除 `_coordinate` 变量 |
| `DatabaseConfigWithStore.tsx` | 删除 `_formatTimestamp` 函数（12行） |
| `LogConfig.tsx` | 删除 `_levelColor` 变量及其依赖的 `currentLevel` |

### 验证结果

运行 `npx tsc --noEmit` 检查通过，无任何警告或错误。
