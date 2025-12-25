/**
 * 大宗交易数据字段映射
 */
import type { FieldMapping } from '../types/rich-data'

export const BLOCK_TRADING_MAPPINGS: FieldMapping[] = [
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
            akshare: ['交易日期', 'trade_date'],
        },
        description: '交易日期',
    },
    {
        core: 'price',
        sources: {
            amazingdata: ['PRICE', 'price'],
            akshare: ['成交价', 'price'],
        },
        transform: (v) => Number(v) || undefined,
        description: '成交价',
    },
    {
        core: 'volume',
        sources: {
            amazingdata: ['VOLUME', 'volume'],
            akshare: ['成交量', 'volume'],
        },
        transform: (v) => Number(v) || undefined,
        description: '成交量',
    },
    {
        core: 'amount',
        sources: {
            amazingdata: ['AMOUNT', 'amount'],
            akshare: ['成交额', 'amount'],
        },
        transform: (v) => Number(v) || undefined,
        description: '成交额',
    },
    {
        core: 'buyerName',
        sources: {
            amazingdata: ['BUYER_NAME', 'buyer_name'],
            akshare: ['买方', 'buyer_name'],
        },
        description: '买方营业部',
    },
    {
        core: 'sellerName',
        sources: {
            amazingdata: ['SELLER_NAME', 'seller_name'],
            akshare: ['卖方', 'seller_name'],
        },
        description: '卖方营业部',
    },
]
