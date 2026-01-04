/**
 * 字段映射配置索引
 */
import type { DataCapability } from '../types'
import type { FieldMapping } from '../types/rich-data'
import { QUOTE_MAPPINGS } from './quote'
import { KLINE_MAPPINGS } from './kline'
import { DRAGON_TIGER_MAPPINGS } from './dragon-tiger'
import { BLOCK_TRADING_MAPPINGS } from './block-trading'
import { FINANCIAL_MAPPINGS, SHAREHOLDER_MAPPINGS } from './financial'

/** 能力到字段映射的配置表 */
export const CAPABILITY_MAPPINGS: Record<DataCapability, FieldMapping[]> = {
    // 行情类
    realtime_quote: QUOTE_MAPPINGS,
    stock_kline: KLINE_MAPPINGS,
    tick_data: QUOTE_MAPPINGS,  // 复用行情映射

    // 财务类
    income_statement: FINANCIAL_MAPPINGS,
    balance_sheet: FINANCIAL_MAPPINGS,
    cash_flow: FINANCIAL_MAPPINGS,
    stock_basic: FINANCIAL_MAPPINGS,

    // 市场异动类
    dragon_tiger: DRAGON_TIGER_MAPPINGS,
    block_trading: BLOCK_TRADING_MAPPINGS,

    // 融资融券类 (暂用通用映射)
    margin_summary: [],
    margin_detail: [],

    // 股东类
    shareholder_num: SHAREHOLDER_MAPPINGS,
    top_holders: SHAREHOLDER_MAPPINGS,

    // 其他
    stock_list: [],
    index_constituent: [],
    option_chain: [],
    option_quote: QUOTE_MAPPINGS,
}

export { QUOTE_MAPPINGS } from './quote'
export { KLINE_MAPPINGS } from './kline'
export { DRAGON_TIGER_MAPPINGS } from './dragon-tiger'
export { BLOCK_TRADING_MAPPINGS } from './block-trading'
export { FINANCIAL_MAPPINGS, SHAREHOLDER_MAPPINGS } from './financial'
