/**
 * 龙虎榜数据字段映射
 */
import type { FieldMapping } from '../types/rich-data'

export const DRAGON_TIGER_MAPPINGS: FieldMapping[] = [
    {
        core: 'code',
        sources: {
            amazingdata: ['SECURITY_CODE', 'code'],
            akshare: ['代码', 'code'],
        },
        description: '股票代码',
    },
    {
        core: 'name',
        sources: {
            amazingdata: ['SECURITY_NAME', 'name'],
            akshare: ['名称', 'name'],
        },
        description: '股票名称',
    },
    {
        core: 'tradeDate',
        sources: {
            amazingdata: ['TRADE_DATE', 'trade_date'],
            akshare: ['上榜日', 'trade_date'],
        },
        description: '交易日期',
    },
    {
        core: 'changeRate',
        sources: {
            amazingdata: ['CHANGE_RATE', 'change_rate', 'pct_change'],
            akshare: ['涨跌幅', 'change_rate'],
        },
        transform: (v) => Number(v) || undefined,
        description: '涨跌幅',
    },
    {
        core: 'buyAmount',
        sources: {
            amazingdata: ['BUY_AMOUNT', 'buy_amount'],
            akshare: ['买入额', 'buy_amount'],
        },
        transform: (v) => Number(v) || undefined,
        description: '买入额',
    },
    {
        core: 'sellAmount',
        sources: {
            amazingdata: ['SELL_AMOUNT', 'sell_amount'],
            akshare: ['卖出额', 'sell_amount'],
        },
        transform: (v) => Number(v) || undefined,
        description: '卖出额',
    },
    {
        core: 'netAmount',
        sources: {
            amazingdata: ['NET_AMOUNT', 'net_amount'],
            akshare: ['净买额', 'net_amount'],
        },
        transform: (v) => Number(v) || undefined,
        description: '净买入',
    },
    {
        core: 'reason',
        sources: {
            amazingdata: ['EXPLANATION', 'reason'],
            akshare: ['上榜原因', 'reason'],
        },
        description: '上榜原因',
    },
]
