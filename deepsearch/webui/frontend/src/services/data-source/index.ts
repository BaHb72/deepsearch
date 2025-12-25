/**
 * 数据源插槽服务 - 主入口
 */

// 类型导出
export * from './types'
export * from './types/rich-data'

// 适配器导出
export {
    registerAdapter,
    getAdapter,
    getAllAdapters,
    getAdaptersForCapability,
    selectBestAdapter,
    executeRequest
} from './adapters'

// 适配器实现
export { amazingdataAdapter } from './adapters/amazingdata'
export { miniqmtAdapter } from './adapters/miniqmt'
export { akshareAdapter } from './adapters/akshare'

// Hooks 导出
export { useDataSource } from './hooks/useDataSource'
export type { UseDataSourceOptions } from './hooks/useDataSource'
export { useRichDataSource } from './hooks/useRichDataSource'

// 字段映射导出
export { FieldMapper, getFieldMapper, transformToRichData } from './field-mapper'
export { CAPABILITY_MAPPINGS } from './field-mappings'

// 组件导出
export { DataTable, DataCard } from './components'
export type { DataTableProps, DataCardProps } from './components'

// 初始化：注册默认适配器
import { registerAdapter } from './adapters'
import { amazingdataAdapter } from './adapters/amazingdata'
import { miniqmtAdapter } from './adapters/miniqmt'
import { akshareAdapter } from './adapters/akshare'

registerAdapter(amazingdataAdapter)
registerAdapter(miniqmtAdapter)
registerAdapter(akshareAdapter)

