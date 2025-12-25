/**
 * K线数据字段映射
 */
import type { FieldMapping } from '../types/rich-data'

export const KLINE_MAPPINGS: FieldMapping[] = [
    {
        core: 'time',
        sources: {
            miniqmt: ['time', 'datetime', 'date'],
            amazingdata: ['TRADE_DATE', 'trade_date', 'datetime'],
            akshare: ['日期', 'date', 'datetime'],
        },
        description: '时间',
    },
    {
        core: 'open',
        sources: {
            miniqmt: ['open'],
            amazingdata: ['OPEN', 'open'],
            akshare: ['开盘', 'open'],
        },
        transform: (v) => Number(v) || 0,
        description: '开盘价',
    },
    {
        core: 'high',
        sources: {
            miniqmt: ['high'],
            amazingdata: ['HIGH', 'high'],
            akshare: ['最高', 'high'],
        },
        transform: (v) => Number(v) || 0,
        description: '最高价',
    },
    {
        core: 'low',
        sources: {
            miniqmt: ['low'],
            amazingdata: ['LOW', 'low'],
            akshare: ['最低', 'low'],
        },
        transform: (v) => Number(v) || 0,
        description: '最低价',
    },
    {
        core: 'close',
        sources: {
            miniqmt: ['close'],
            amazingdata: ['CLOSE', 'close'],
            akshare: ['收盘', 'close'],
        },
        transform: (v) => Number(v) || 0,
        description: '收盘价',
    },
    {
        core: 'volume',
        sources: {
            miniqmt: ['volume', 'vol'],
            amazingdata: ['VOLUME', 'volume'],
            akshare: ['成交量', 'volume'],
        },
        transform: (v) => Number(v) || 0,
        description: '成交量',
    },
    {
        core: 'amount',
        sources: {
            miniqmt: ['amount', 'turnover'],
            amazingdata: ['AMOUNT', 'amount'],
            akshare: ['成交额', 'amount'],
        },
        transform: (v) => Number(v) || undefined,
        description: '成交额',
    },
]
