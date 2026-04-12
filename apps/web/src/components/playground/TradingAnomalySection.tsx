/**
 * TradingAnomalySection - 市场异动组件
 * 使用 useRichDataSource 获取数据，支持展示扩展字段
 */
import React, { useState } from 'react'
import { Button, Space, Table, DatePicker, Tag, Alert } from 'antd'
import { ReloadOutlined, ThunderboltOutlined, SwapOutlined } from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import {
    type CoreBlockTradingData,
    type CoreDragonTigerData,
    type DataSourceType,
    useRichDataSource,
} from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface TradingAnomalySectionProps {
    stockCode?: string
    preferredSource?: DataSourceType
    onSuggestSourceSwitch?: (source: DataSourceType) => void
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

const { RangePicker } = DatePicker

/** 格式化金额 */
const formatAmount = (val: number | undefined): string => {
    if (val === undefined || val === null) return '-'
    const absVal = Math.abs(val)
    if (absVal >= 100000000) return (val / 100000000).toFixed(2) + '亿'
    if (absVal >= 10000) return (val / 10000).toFixed(2) + '万'
    return val.toFixed(2)
}

/** 龙虎榜列配置 */
const dragonTigerColumns: ColumnsType<CoreDragonTigerData & { _key: number }> = [
    { title: '证券代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '证券名称', dataIndex: 'name', key: 'name', width: 100 },
    {
        title: '上榜日期',
        dataIndex: 'tradeDate',
        key: 'tradeDate',
        width: 110,
        render: (val) => val?.slice?.(0, 10) || val,
    },
    {
        title: '涨跌幅',
        dataIndex: 'changeRate',
        key: 'changeRate',
        width: 90,
        render: (val) => (
            <span style={{ color: val > 0 ? '#f5222d' : val < 0 ? '#52c41a' : undefined }}>
                {val?.toFixed?.(2) || val}%
            </span>
        ),
    },
    {
        title: '上榜原因',
        dataIndex: 'reason',
        key: 'reason',
        width: 200,
        ellipsis: true,
    },
    {
        title: '买入额',
        dataIndex: 'buyAmount',
        key: 'buyAmount',
        width: 100,
        render: (val) => <span style={{ color: '#f5222d' }}>{formatAmount(val)}</span>,
    },
    {
        title: '卖出额',
        dataIndex: 'sellAmount',
        key: 'sellAmount',
        width: 100,
        render: (val) => <span style={{ color: '#52c41a' }}>{formatAmount(val)}</span>,
    },
    {
        title: '净买入',
        dataIndex: 'netAmount',
        key: 'netAmount',
        width: 100,
        render: (val) => (
            <span style={{ color: val > 0 ? '#f5222d' : '#52c41a' }}>
                {formatAmount(val)}
            </span>
        ),
    },
]

/** 大宗交易列配置 */
const blockTradingColumns: ColumnsType<CoreBlockTradingData & { _key: number }> = [
    { title: '证券代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '证券名称', dataIndex: 'name', key: 'name', width: 100 },
    {
        title: '交易日期',
        dataIndex: 'tradeDate',
        key: 'tradeDate',
        width: 110,
        render: (val) => val?.slice?.(0, 10) || val,
    },
    { title: '成交价', dataIndex: 'price', key: 'price', width: 90 },
    {
        title: '成交量',
        dataIndex: 'volume',
        key: 'volume',
        width: 100,
        render: (val) => formatAmount(val),
    },
    {
        title: '成交额',
        dataIndex: 'amount',
        key: 'amount',
        width: 100,
        render: (val) => formatAmount(val),
    },
    { title: '买方营业部', dataIndex: 'buyerName', key: 'buyerName', width: 150, ellipsis: true },
    { title: '卖方营业部', dataIndex: 'sellerName', key: 'sellerName', width: 150, ellipsis: true },
]

export const TradingAnomalySection: React.FC<TradingAnomalySectionProps> = ({
    stockCode,
    preferredSource,
    onSuggestSourceSwitch,
    showExtended = true,
}) => {
    const [activeTab, setActiveTab] = useState('dragon')
    const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
        dayjs().subtract(30, 'day'),
        dayjs(),
    ])

    const dateParams = {
        startDate: dateRange[0].format('YYYYMMDD'),
        endDate: dateRange[1].format('YYYYMMDD'),
    }

    // 龙虎榜数据
    const dragonResult = useRichDataSource<CoreDragonTigerData>({
        capability: 'dragon_tiger',
        params: { code: stockCode, limit: 100, ...dateParams },
        preferredSource,
        autoFetch: true,
        deps: [stockCode, dateParams.startDate, dateParams.endDate],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'anomaly',
            moduleName: '市场异动',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    // 大宗交易数据
    const blockResult = useRichDataSource<CoreBlockTradingData>({
        capability: 'block_trading',
        params: { codes: stockCode ? [stockCode] : [], ...dateParams },
        preferredSource,
        autoFetch: activeTab === 'block',
        deps: [stockCode, activeTab, dateParams.startDate, dateParams.endDate],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'anomaly',
            moduleName: '市场异动',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    const loading = dragonResult.loading || blockResult.loading
    const currentMeta = activeTab === 'dragon' ? dragonResult.meta : blockResult.meta

    const tabItems = [
        {
            key: 'dragon',
            label: (
                <Space>
                    <ThunderboltOutlined />
                    <span>龙虎榜</span>
                    {dragonResult.data.length > 0 && <Tag>{dragonResult.data.length}</Tag>}
                </Space>
            ),
            children: (
                <>
                    {dragonResult.error && (
                        <Alert message={dragonResult.error} type="warning" showIcon style={{ marginBottom: 16 }} />
                    )}
                    <Table
                        dataSource={dragonResult.data.map((item, idx) => ({ ...item, _key: idx }))}
                        columns={dragonTigerColumns}
                        rowKey="_key"
                        size="small"
                        scroll={{ x: 900, y: 350 }}
                        loading={dragonResult.loading}
                        pagination={{ pageSize: 15, showSizeChanger: true }}
                    />
                    {showExtended && dragonResult.extended[0] && Object.keys(dragonResult.extended[0]).length > 0 && (
                        <ExtendedFieldsPanel
                            extended={dragonResult.extended[0]}
                            source={dragonResult.meta?.source}
                            title="龙虎榜扩展数据"
                        />
                    )}
                </>
            ),
        },
        {
            key: 'block',
            label: (
                <Space>
                    <SwapOutlined />
                    <span>大宗交易</span>
                    {blockResult.data.length > 0 && <Tag>{blockResult.data.length}</Tag>}
                </Space>
            ),
            children: (
                <>
                    {blockResult.error && (
                        <Alert message={blockResult.error} type="warning" showIcon style={{ marginBottom: 16 }} />
                    )}
                    <Table
                        dataSource={blockResult.data.map((item, idx) => ({ ...item, _key: idx }))}
                        columns={blockTradingColumns}
                        rowKey="_key"
                        size="small"
                        scroll={{ x: 900, y: 350 }}
                        loading={blockResult.loading}
                        pagination={{ pageSize: 15, showSizeChanger: true }}
                    />
                    {showExtended && blockResult.extended[0] && Object.keys(blockResult.extended[0]).length > 0 && (
                        <ExtendedFieldsPanel
                            extended={blockResult.extended[0]}
                            source={blockResult.meta?.source}
                            title="大宗交易扩展数据"
                        />
                    )}
                </>
            ),
        },
    ]

    return (
        <ProCard
            title={
                <Space>
                    <span>市场异动</span>
                    <DataSourceBadge
                        source={currentMeta?.source}
                        latency={currentMeta?.latency}
                        size="small"
                    />
                </Space>
            }
            extra={
                <Space>
                    <RangePicker
                        value={dateRange}
                        onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
                        size="small"
                    />
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={() => {
                            dragonResult.refresh()
                            blockResult.refresh()
                        }}
                        loading={loading}
                        size="small"
                    >
                        刷新
                    </Button>
                </Space>
            }
            bordered
            headerBordered
            tabs={{
                activeKey: activeTab,
                onChange: setActiveTab,
                items: tabItems,
            }}
        />
    )
}

export default TradingAnomalySection
