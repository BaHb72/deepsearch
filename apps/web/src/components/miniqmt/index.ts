/**
 * MiniQMT 数据源组件
 * 包含所有 MiniQMT/xtdata API 数据展示组件
 */

// 通用组件
export { StockSearchSelect } from './StockSearchSelect'
export type { StockOption } from './StockSearchSelect'

// Section 组件
export { SectorCapitalFlowSection } from './SectorCapitalFlowSection'
export { SectorListSection } from './SectorListSection'
export { RealtimeQuoteSection } from './RealtimeQuoteSection'
export { KlineSection } from './KlineSection'
export { StatusSection } from './StatusSection'

// 表格列配置
export {
    capitalFlowColumns,
    quoteColumns,
    klineColumns,
} from './columns'
