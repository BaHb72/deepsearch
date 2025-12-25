/**
 * 财务数据字段映射
 */
import type { FieldMapping } from '../types/rich-data'

export const FINANCIAL_MAPPINGS: FieldMapping[] = [
    {
        core: 'code',
        sources: {
            miniqmt: ['stock_code', 'code'],
            amazingdata: ['SECURITY_CODE', 'code'],
        },
        description: '股票代码',
    },
    {
        core: 'reportDate',
        sources: {
            miniqmt: ['report_date', 'end_date'],
            amazingdata: ['REPORT_DATE', 'report_date', 'END_DATE'],
        },
        description: '报告期',
    },
    {
        core: 'revenue',
        sources: {
            miniqmt: ['total_revenue', 'revenue'],
            amazingdata: ['TOTAL_REVENUE', 'total_revenue'],
        },
        transform: (v) => Number(v) || undefined,
        description: '营业收入',
    },
    {
        core: 'netProfit',
        sources: {
            miniqmt: ['net_profit', 'netProfit'],
            amazingdata: ['NET_PROFIT', 'net_profit'],
        },
        transform: (v) => Number(v) || undefined,
        description: '净利润',
    },
    {
        core: 'totalAssets',
        sources: {
            miniqmt: ['total_assets', 'totalAssets'],
            amazingdata: ['TOTAL_ASSETS', 'total_assets'],
        },
        transform: (v) => Number(v) || undefined,
        description: '总资产',
    },
    {
        core: 'totalLiab',
        sources: {
            miniqmt: ['total_liab', 'totalLiab'],
            amazingdata: ['TOTAL_LIAB', 'total_liab'],
        },
        transform: (v) => Number(v) || undefined,
        description: '总负债',
    },
    {
        core: 'totalEquity',
        sources: {
            miniqmt: ['total_equity', 'totalEquity'],
            amazingdata: ['TOTAL_HLDR_EQY_EXC_MIN_INT', 'total_equity'],
        },
        transform: (v) => Number(v) || undefined,
        description: '股东权益',
    },
]

export const SHAREHOLDER_MAPPINGS: FieldMapping[] = [
    {
        core: 'code',
        sources: {
            amazingdata: ['SECURITY_CODE', 'code'],
        },
        description: '股票代码',
    },
    {
        core: 'annDate',
        sources: {
            amazingdata: ['ANN_DT', 'END_DATE', 'ann_date'],
        },
        description: '公告日期',
    },
    {
        core: 'holderNum',
        sources: {
            amazingdata: ['HOLDER_TOTAL_NUM', 'HOLDER_NUM', 'holder_num'],
        },
        transform: (v) => Number(v) || undefined,
        description: '股东户数',
    },
    {
        core: 'holderNumChange',
        sources: {
            amazingdata: ['HOLDER_NUM_CHANGE', 'holder_num_change'],
        },
        transform: (v) => Number(v) || undefined,
        description: '变化数',
    },
    {
        core: 'holderNumChangePct',
        sources: {
            amazingdata: ['HOLDER_NUM_CHANGE_PCT', 'holder_num_change_pct'],
        },
        transform: (v) => Number(v) || undefined,
        description: '变化比例',
    },
]
