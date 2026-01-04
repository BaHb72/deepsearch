/**
 * 行情数据字段映射
 */
import type { FieldMapping } from '../types/rich-data'

export const QUOTE_MAPPINGS: FieldMapping[] = [
    {
        core: 'code',
        sources: {
            miniqmt: ['stock_code', 'code'],
            amazingdata: ['SECURITY_CODE', 'code'],
            akshare: ['代码', 'code'],
        },
        description: '股票代码',
    },
    {
        core: 'name',
        sources: {
            miniqmt: ['stock_name', 'name'],
            amazingdata: ['SECURITY_NAME', 'name'],
            akshare: ['名称', 'name'],
        },
        description: '股票名称',
    },
    {
        core: 'price',
        sources: {
            miniqmt: ['lastPrice', 'last_price', 'price'],
            amazingdata: ['CLOSE_PRICE', 'close', 'price'],
            akshare: ['最新价', 'price'],
        },
        transform: (v) => (typeof v === 'number' ? v : Number(v) || 0),
        description: '最新价',
    },
    {
        core: 'open',
        sources: {
            miniqmt: ['open', 'openPrice'],
            amazingdata: ['OPEN_PRICE', 'open'],
            akshare: ['开盘价', 'open'],
        },
        transform: (v) => Number(v) || undefined,
        description: '开盘价',
    },
    {
        core: 'high',
        sources: {
            miniqmt: ['high', 'highPrice'],
            amazingdata: ['HIGH_PRICE', 'high'],
            akshare: ['最高价', 'high'],
        },
        transform: (v) => Number(v) || undefined,
        description: '最高价',
    },
    {
        core: 'low',
        sources: {
            miniqmt: ['low', 'lowPrice'],
            amazingdata: ['LOW_PRICE', 'low'],
            akshare: ['最低价', 'low'],
        },
        transform: (v) => Number(v) || undefined,
        description: '最低价',
    },
    {
        core: 'close',
        sources: {
            miniqmt: ['close', 'lastPrice'],
            amazingdata: ['CLOSE_PRICE', 'close'],
            akshare: ['收盘价', 'close'],
        },
        transform: (v) => Number(v) || undefined,
        description: '收盘价',
    },
    {
        core: 'preClose',
        sources: {
            miniqmt: ['preClose', 'pre_close', 'lastClose'],
            amazingdata: ['PRE_CLOSE', 'pre_close'],
            akshare: ['昨收', 'pre_close'],
        },
        transform: (v) => Number(v) || undefined,
        description: '昨收价',
    },
    {
        core: 'change',
        sources: {
            miniqmt: ['change', 'priceChange'],
            amazingdata: ['CHANGE', 'change'],
            akshare: ['涨跌额', 'change'],
        },
        transform: (v) => Number(v) || undefined,
        description: '涨跌额',
    },
    {
        core: 'changePct',
        sources: {
            miniqmt: ['pctChg', 'pct_chg', 'changePct'],
            amazingdata: ['PCT_CHANGE', 'pct_chg'],
            akshare: ['涨跌幅', 'pct_chg'],
        },
        transform: (v) => {
            if (typeof v === 'number') return v
            const str = String(v).replace('%', '')
            return parseFloat(str) || undefined
        },
        description: '涨跌幅 (%)',
    },
    {
        core: 'volume',
        sources: {
            miniqmt: ['volume', 'vol'],
            amazingdata: ['VOLUME', 'volume'],
            akshare: ['成交量', 'volume'],
        },
        transform: (v) => Number(v) || undefined,
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
    {
        core: 'time',
        sources: {
            miniqmt: ['time', 'datetime', 'trade_time'],
            amazingdata: ['TRADE_DATE', 'trade_date'],
            akshare: ['时间', 'datetime'],
        },
        transform: (v) => {
            if (typeof v === 'number') return v
            if (typeof v === 'string') return new Date(v).getTime() || undefined
            return undefined
        },
        description: '时间戳',
    },
]
