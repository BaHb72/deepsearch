/**
 * 表格通用样式配置
 * 解决表格列宽问题：不换行，超长省略号，悬浮提示，可拖拽调整
 */
import type { ColumnsType } from 'antd/es/table'
import { Tooltip } from 'antd'
import { formatAmount, formatPercent } from '@/utils/formatters'

/** 通用列样式：不换行，超长省略+悬浮提示 */
const ellipsisWithTooltip = {
    ellipsis: { showTitle: false },
    render: (text: unknown) => (
        <Tooltip placement="topLeft" title={String(text ?? '-')}>
            <span style={{ whiteSpace: 'nowrap' }}>{String(text ?? '-')}</span>
        </Tooltip>
    ),
}

/** 数值列：不换行，保留精度 */
const numericColumn = (precision: number = 2) => ({
    ellipsis: { showTitle: false },
    render: (v: number) => {
        const text = v?.toFixed(precision) ?? '-'
        return (
            <Tooltip placement="topLeft" title={text}>
                <span style={{ whiteSpace: 'nowrap' }}>{text}</span>
            </Tooltip>
        )
    },
})

/** 金额列：不换行，格式化显示 */
const amountColumn = (colorize: boolean = false) => ({
    ellipsis: { showTitle: false },
    render: (v: number) => {
        const text = formatAmount(v)
        const color = colorize ? (v >= 0 ? '#cf1322' : '#3f8600') : undefined
        return (
            <Tooltip placement="topLeft" title={text}>
                <span style={{ whiteSpace: 'nowrap', color }}>{text}</span>
            </Tooltip>
        )
    },
})

/** 百分比列：不换行，格式化显示 */
const percentColumn = (colorize: boolean = false) => ({
    ellipsis: { showTitle: false },
    render: (v: number) => {
        const text = formatPercent(v)
        const color = colorize ? (v >= 0 ? '#cf1322' : '#3f8600') : undefined
        return (
            <Tooltip placement="topLeft" title={text}>
                <span style={{ whiteSpace: 'nowrap', color }}>{text}</span>
            </Tooltip>
        )
    },
})

/** 板块资金流向列配置 */
export const capitalFlowColumns: ColumnsType<Record<string, unknown>> = [
    { title: '序号', dataIndex: '序号', key: '序号', width: 50, fixed: 'left' },
    { title: '名称', dataIndex: '名称', key: '名称', width: 90, fixed: 'left', ...ellipsisWithTooltip },
    {
        title: '涨跌幅', dataIndex: '今日涨跌幅', key: '今日涨跌幅', width: 75,
        ...percentColumn(true),
        sorter: (a, b) => (a['今日涨跌幅'] as number || 0) - (b['今日涨跌幅'] as number || 0),
    },
    {
        title: '主力净额', dataIndex: '今日主力净流入-净额', key: '今日主力净流入-净额', width: 90,
        ...amountColumn(true),
        sorter: (a, b) => (a['今日主力净流入-净额'] as number || 0) - (b['今日主力净流入-净额'] as number || 0),
        defaultSortOrder: 'descend',
    },
    {
        title: '主力占比', dataIndex: '今日主力净流入-净占比', key: '今日主力净流入-净占比', width: 80,
        ...percentColumn(),
        sorter: (a, b) => (a['今日主力净流入-净占比'] as number || 0) - (b['今日主力净流入-净占比'] as number || 0),
    },
    {
        title: '超大单净额', dataIndex: '今日超大单净流入-净额', key: '今日超大单净流入-净额', width: 95,
        ...amountColumn(),
        sorter: (a, b) => (a['今日超大单净流入-净额'] as number || 0) - (b['今日超大单净流入-净额'] as number || 0),
    },
    {
        title: '超大单占比', dataIndex: '今日超大单净流入-净占比', key: '今日超大单净流入-净占比', width: 90,
        ...percentColumn(),
        sorter: (a, b) => (a['今日超大单净流入-净占比'] as number || 0) - (b['今日超大单净流入-净占比'] as number || 0),
    },
    {
        title: '大单净额', dataIndex: '今日大单净流入-净额', key: '今日大单净流入-净额', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a['今日大单净流入-净额'] as number || 0) - (b['今日大单净流入-净额'] as number || 0),
    },
    {
        title: '中单净额', dataIndex: '今日中单净流入-净额', key: '今日中单净流入-净额', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a['今日中单净流入-净额'] as number || 0) - (b['今日中单净流入-净额'] as number || 0),
    },
    {
        title: '小单净额', dataIndex: '今日小单净流入-净额', key: '今日小单净流入-净额', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a['今日小单净流入-净额'] as number || 0) - (b['今日小单净流入-净额'] as number || 0),
    },
    { title: '主力最大股', dataIndex: '今日主力净流入最大股', key: '今日主力净流入最大股', width: 95, ...ellipsisWithTooltip },
]

/** 实时行情列配置 */
export const quoteColumns: ColumnsType<Record<string, unknown>> = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 90, ...ellipsisWithTooltip },
    { title: '名称', dataIndex: 'name', key: 'name', width: 85, ...ellipsisWithTooltip },
    {
        title: '最新价', dataIndex: 'lastPrice', key: 'lastPrice', width: 75,
        ...numericColumn(2),
        sorter: (a, b) => (a.lastPrice as number || 0) - (b.lastPrice as number || 0),
    },
    {
        title: '涨跌', dataIndex: 'change', key: 'change', width: 70,
        ...amountColumn(true),
        sorter: (a, b) => (a.change as number || 0) - (b.change as number || 0),
    },
    {
        title: '涨跌幅', dataIndex: 'changePct', key: 'changePct', width: 75,
        ...percentColumn(true),
        sorter: (a, b) => (a.changePct as number || 0) - (b.changePct as number || 0),
    },
    {
        title: '开盘', dataIndex: 'open', key: 'open', width: 70,
        ...numericColumn(2),
        sorter: (a, b) => (a.open as number || 0) - (b.open as number || 0),
    },
    {
        title: '最高', dataIndex: 'high', key: 'high', width: 70,
        ...numericColumn(2),
        sorter: (a, b) => (a.high as number || 0) - (b.high as number || 0),
    },
    {
        title: '最低', dataIndex: 'low', key: 'low', width: 70,
        ...numericColumn(2),
        sorter: (a, b) => (a.low as number || 0) - (b.low as number || 0),
    },
    {
        title: '成交量', dataIndex: 'volume', key: 'volume', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a.volume as number || 0) - (b.volume as number || 0),
    },
    {
        title: '成交额', dataIndex: 'amount', key: 'amount', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a.amount as number || 0) - (b.amount as number || 0),
    },
]

/** K线数据列配置 */
export const klineColumns: ColumnsType<Record<string, unknown>> = [
    {
        title: '时间', dataIndex: 'time', key: 'time', width: 150,
        ...ellipsisWithTooltip,
        render: (v: number, record) => {
            const text = (record.time_str as string) || new Date(v).toLocaleString('zh-CN')
            return (
                <Tooltip placement="topLeft" title={text}>
                    <span style={{ whiteSpace: 'nowrap' }}>{text}</span>
                </Tooltip>
            )
        },
    },
    {
        title: '开盘', dataIndex: 'open', key: 'open', width: 75,
        ...numericColumn(2),
        sorter: (a, b) => (a.open as number || 0) - (b.open as number || 0),
    },
    {
        title: '最高', dataIndex: 'high', key: 'high', width: 75,
        ...numericColumn(2),
        sorter: (a, b) => (a.high as number || 0) - (b.high as number || 0),
    },
    {
        title: '最低', dataIndex: 'low', key: 'low', width: 75,
        ...numericColumn(2),
        sorter: (a, b) => (a.low as number || 0) - (b.low as number || 0),
    },
    {
        title: '收盘', dataIndex: 'close', key: 'close', width: 75,
        ...numericColumn(2),
        sorter: (a, b) => (a.close as number || 0) - (b.close as number || 0),
    },
    {
        title: '成交量', dataIndex: 'volume', key: 'volume', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a.volume as number || 0) - (b.volume as number || 0),
    },
    {
        title: '成交额', dataIndex: 'amount', key: 'amount', width: 90,
        ...amountColumn(),
        sorter: (a, b) => (a.amount as number || 0) - (b.amount as number || 0),
    },
]
