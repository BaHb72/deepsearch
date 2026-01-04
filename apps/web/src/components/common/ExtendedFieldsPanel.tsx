/**
 * ExtendedFieldsPanel - 扩展字段展示面板
 * 以可折叠表格形式展示数据源特有的扩展字段
 */
import React, { useMemo } from 'react'
import { Collapse, Table, Typography, Tag } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import type { DataSourceType } from '@/services/data-source'

const { Text } = Typography
const { Panel } = Collapse

export interface ExtendedFieldsPanelProps {
    /** 扩展字段数据 */
    extended?: Record<string, unknown>
    /** 数据来源 */
    source?: DataSourceType
    /** 面板标题 */
    title?: string
    /** 默认是否展开 */
    defaultExpanded?: boolean
    /** 字段名中文映射 */
    fieldLabels?: Record<string, string>
    /** 最大显示字段数 */
    maxFields?: number
}

/** 数据源显示名称 */
const SOURCE_LABELS: Record<DataSourceType, string> = {
    miniqmt: 'MiniQMT',
    amazingdata: 'AmazingData',
    akshare: 'AkShare',
    tushare: 'TuShare',
    eastmoney: 'EastMoney',
}

/** 常用字段中文映射 */
const DEFAULT_FIELD_LABELS: Record<string, string> = {
    // 买卖盘
    bidPrice1: '买一价',
    bidPrice2: '买二价',
    bidPrice3: '买三价',
    bidPrice4: '买四价',
    bidPrice5: '买五价',
    bidVol1: '买一量',
    bidVol2: '买二量',
    bidVol3: '买三量',
    bidVol4: '买四量',
    bidVol5: '买五量',
    askPrice1: '卖一价',
    askPrice2: '卖二价',
    askPrice3: '卖三价',
    askPrice4: '卖四价',
    askPrice5: '卖五价',
    askVol1: '卖一量',
    askVol2: '卖二量',
    askVol3: '卖三量',
    askVol4: '卖四量',
    askVol5: '卖五量',
    // 行情
    turnoverRate: '换手率',
    amplitude: '振幅',
    averagePrice: '均价',
    pe: '市盈率',
    pb: '市净率',
    totalValue: '总市值',
    circValue: '流通市值',
    // 财务
    eps: '每股收益',
    bvps: '每股净资产',
    roe: '净资产收益率',
    debtRatio: '资产负债率',
}

/**
 * 格式化字段值
 */
function formatValue(value: unknown): string {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'number') {
        // 大数值格式化
        if (Math.abs(value) >= 1e8) {
            return (value / 1e8).toFixed(2) + '亿'
        }
        if (Math.abs(value) >= 1e4) {
            return (value / 1e4).toFixed(2) + '万'
        }
        // 小数保留4位
        if (!Number.isInteger(value)) {
            return value.toFixed(4).replace(/\.?0+$/, '')
        }
        return value.toLocaleString()
    }
    if (typeof value === 'boolean') {
        return value ? '是' : '否'
    }
    if (typeof value === 'object') {
        return JSON.stringify(value)
    }
    return String(value)
}

export const ExtendedFieldsPanel: React.FC<ExtendedFieldsPanelProps> = ({
    extended,
    source,
    title = '扩展字段',
    defaultExpanded = false,
    fieldLabels = {},
    maxFields = 50,
}) => {
    // 合并字段标签
    const allLabels = useMemo(
        () => ({ ...DEFAULT_FIELD_LABELS, ...fieldLabels }),
        [fieldLabels]
    )

    // 处理字段数据
    const tableData = useMemo(() => {
        if (!extended || typeof extended !== 'object') return []

        return Object.entries(extended)
            .filter(([key]) => !key.startsWith('_')) // 过滤内部字段
            .slice(0, maxFields)
            .map(([key, value], index) => ({
                key: index,
                fieldName: key,
                fieldLabel: allLabels[key] || key,
                value: formatValue(value),
                rawValue: value,
            }))
            .sort((a, b) => a.fieldLabel.localeCompare(b.fieldLabel))
    }, [extended, allLabels, maxFields])

    // 空数据处理
    if (!extended || tableData.length === 0) {
        return null
    }

    const columns = [
        {
            title: '字段',
            dataIndex: 'fieldLabel',
            key: 'fieldLabel',
            width: 120,
            render: (text: string, record: { fieldName: string }) => (
                <Text
                    style={{ fontSize: 12 }}
                    title={record.fieldName}
                >
                    {text}
                </Text>
            ),
        },
        {
            title: '值',
            dataIndex: 'value',
            key: 'value',
            render: (text: string) => (
                <Text
                    style={{ fontSize: 12 }}
                    copyable={text !== '-' ? { text } : false}
                >
                    {text}
                </Text>
            ),
        },
    ]

    const sourceLabel = source ? SOURCE_LABELS[source] : undefined
    const panelHeader = (
        <span style={{ fontSize: 12 }}>
            <InfoCircleOutlined style={{ marginRight: 6 }} />
            {title}
            {sourceLabel && (
                <Tag color="blue" style={{ marginLeft: 8, fontSize: 10 }}>
                    {sourceLabel}
                </Tag>
            )}
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 10 }}>
                ({tableData.length}项)
            </Text>
        </span>
    )

    return (
        <Collapse
            ghost
            defaultActiveKey={defaultExpanded ? ['extended'] : []}
            style={{ marginTop: 8 }}
        >
            <Panel header={panelHeader} key="extended">
                <Table
                    dataSource={tableData}
                    columns={columns}
                    size="small"
                    pagination={false}
                    showHeader={false}
                    scroll={{ y: 200 }}
                    style={{ fontSize: 12 }}
                />
            </Panel>
        </Collapse>
    )
}

export default ExtendedFieldsPanel
