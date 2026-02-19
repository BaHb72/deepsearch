/**
 * FundamentalSection - 基本面数据组件
 * 使用 useRichDataSource 获取数据，支持展示扩展字段
 */
import React, { useState } from 'react'
import { Button, Space, Row, Col, Spin, Empty, Alert } from 'antd'
import { ReloadOutlined, BarChartOutlined, TeamOutlined } from '@ant-design/icons'
import { ProCard, StatisticCard } from '@ant-design/pro-components'
import ReactECharts from 'echarts-for-react'
import type { DataSourceType, CoreFinancialData, CoreShareholderData } from '@/services/data-source'
import { useRichDataSource } from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface FundamentalSectionProps {
    stockCode: string
    preferredSource?: DataSourceType
    onSuggestSourceSwitch?: (source: DataSourceType) => void
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

/** 格式化大数值 */
const formatLargeNumber = (val: number | undefined): string => {
    if (val === undefined || val === null) return '-'
    const absVal = Math.abs(val)
    if (absVal >= 100000000) return (val / 100000000).toFixed(2) + '亿'
    if (absVal >= 10000) return (val / 10000).toFixed(2) + '万'
    return val.toLocaleString()
}

export const FundamentalSection: React.FC<FundamentalSectionProps> = ({
    stockCode,
    preferredSource,
    onSuggestSourceSwitch,
    showExtended = true,
}) => {
    const [activeTab, setActiveTab] = useState('income')

    // 利润表数据
    const incomeResult = useRichDataSource<CoreFinancialData>({
        capability: 'income_statement',
        params: { codes: [stockCode] },
        preferredSource,
        autoFetch: true,
        deps: [stockCode],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'fundamental',
            moduleName: '基本面',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    // 资产负债表数据
    const balanceResult = useRichDataSource<CoreFinancialData>({
        capability: 'balance_sheet',
        params: { codes: [stockCode] },
        preferredSource,
        autoFetch: activeTab === 'balance',
        deps: [stockCode, activeTab],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'fundamental',
            moduleName: '基本面',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    // 股东数据
    const holderResult = useRichDataSource<CoreShareholderData>({
        capability: 'shareholder_num',
        params: { code: stockCode },
        preferredSource,
        autoFetch: activeTab === 'holder',
        deps: [stockCode, activeTab],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'fundamental',
            moduleName: '基本面',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    const loading = incomeResult.loading || balanceResult.loading || holderResult.loading
    const currentMeta = incomeResult.meta || balanceResult.meta || holderResult.meta
    const currentError = incomeResult.error || balanceResult.error || holderResult.error

    // 获取当前 tab 的扩展数据
    const getCurrentExtended = () => {
        switch (activeTab) {
            case 'income': return incomeResult.extended[0]
            case 'balance': return balanceResult.extended[0]
            case 'holder': return holderResult.extended[0]
            default: return undefined
        }
    }

    // 生成利润图表
    const getIncomeChartOption = () => {
        const data = incomeResult.extended || []  // 使用 extended 因为包含原始字段名
        if (data.length === 0) return {}

        const dates = data.slice(0, 8).reverse().map((d: Record<string, unknown>) => {
            const date = (d.REPORT_DATE || d.report_date || d.end_date) as string
            return typeof date === 'string' ? date.slice(0, 10) : date
        })
        const revenues = data.slice(0, 8).reverse().map((d: Record<string, unknown>) =>
            (d.TOTAL_REVENUE || d.total_revenue || 0) as number
        )
        const profits = data.slice(0, 8).reverse().map((d: Record<string, unknown>) =>
            (d.NET_PROFIT || d.net_profit || 0) as number
        )

        return {
            tooltip: { trigger: 'axis' },
            legend: { data: ['营业收入', '净利润'], top: 0 },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
            xAxis: { type: 'category', data: dates },
            yAxis: {
                type: 'value',
                axisLabel: { formatter: (val: number) => formatLargeNumber(val) },
            },
            series: [
                { name: '营业收入', type: 'bar', data: revenues, itemStyle: { color: '#1890ff' } },
                { name: '净利润', type: 'line', data: profits, itemStyle: { color: '#52c41a' } },
            ],
        }
    }

    // 生成股东户数图表
    const getHolderChartOption = () => {
        const data = holderResult.extended || []
        if (data.length === 0) return {}

        const dates = data.slice(0, 12).reverse().map((d: Record<string, unknown>) => {
            const date = (d.ANN_DT || d.END_DATE || d.ann_date) as string
            return typeof date === 'string' ? date.slice(0, 10) : date
        })
        const nums = data.slice(0, 12).reverse().map((d: Record<string, unknown>) =>
            (d.HOLDER_TOTAL_NUM || d.HOLDER_NUM || d.holder_num || 0) as number
        )

        return {
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: { type: 'category', data: dates },
            yAxis: { type: 'value', min: 'dataMin' },
            series: [
                {
                    name: '股东户数',
                    type: 'line',
                    smooth: true,
                    areaStyle: { opacity: 0.3 },
                    data: nums,
                    itemStyle: { color: '#722ed1' },
                },
            ],
        }
    }

    const tabItems = [
        {
            key: 'income',
            label: (
                <Space>
                    <BarChartOutlined />
                    <span>利润营收</span>
                </Space>
            ),
            children: (
                <Spin spinning={incomeResult.loading}>
                    {incomeResult.error && (
                        <Alert message={incomeResult.error} type="warning" showIcon style={{ marginBottom: 16 }} />
                    )}
                    {incomeResult.extended.length > 0 ? (
                        <>
                            <ReactECharts option={getIncomeChartOption()} style={{ height: 350 }} />
                            {showExtended && getCurrentExtended() && (
                                <ExtendedFieldsPanel
                                    extended={getCurrentExtended()}
                                    source={incomeResult.meta?.source}
                                    title="利润表详细数据"
                                />
                            )}
                        </>
                    ) : !incomeResult.loading ? (
                        <Empty description="暂无利润数据" />
                    ) : null}
                </Spin>
            ),
        },
        {
            key: 'balance',
            label: '资产负债',
            children: (
                <Spin spinning={balanceResult.loading}>
                    {balanceResult.error && (
                        <Alert message={balanceResult.error} type="warning" showIcon style={{ marginBottom: 16 }} />
                    )}
                    {balanceResult.extended.length > 0 ? (
                        <>
                            <Row gutter={[16, 16]}>
                                {balanceResult.extended.slice(0, 1).map((item: Record<string, unknown>, idx: number) => (
                                    <React.Fragment key={idx}>
                                        <Col span={8}>
                                            <StatisticCard
                                                statistic={{
                                                    title: '总资产',
                                                    value: formatLargeNumber((item.TOTAL_ASSETS || item.total_assets) as number),
                                                }}
                                            />
                                        </Col>
                                        <Col span={8}>
                                            <StatisticCard
                                                statistic={{
                                                    title: '总负债',
                                                    value: formatLargeNumber((item.TOTAL_LIAB || item.total_liab) as number),
                                                }}
                                            />
                                        </Col>
                                        <Col span={8}>
                                            <StatisticCard
                                                statistic={{
                                                    title: '股东权益',
                                                    value: formatLargeNumber((item.TOTAL_HLDR_EQY_EXC_MIN_INT || item.total_equity) as number),
                                                }}
                                            />
                                        </Col>
                                    </React.Fragment>
                                ))}
                            </Row>
                            {showExtended && getCurrentExtended() && (
                                <ExtendedFieldsPanel
                                    extended={getCurrentExtended()}
                                    source={balanceResult.meta?.source}
                                    title="资产负债表详细数据"
                                />
                            )}
                        </>
                    ) : !balanceResult.loading ? (
                        <Empty description="暂无资产负债数据" />
                    ) : null}
                </Spin>
            ),
        },
        {
            key: 'holder',
            label: (
                <Space>
                    <TeamOutlined />
                    <span>股东分析</span>
                </Space>
            ),
            children: (
                <Spin spinning={holderResult.loading}>
                    {holderResult.error && (
                        <Alert message={holderResult.error} type="warning" showIcon style={{ marginBottom: 16 }} />
                    )}
                    {holderResult.extended.length > 0 ? (
                        <>
                            <ReactECharts option={getHolderChartOption()} style={{ height: 350 }} />
                            {showExtended && getCurrentExtended() && (
                                <ExtendedFieldsPanel
                                    extended={getCurrentExtended()}
                                    source={holderResult.meta?.source}
                                    title="股东数据详情"
                                />
                            )}
                        </>
                    ) : !holderResult.loading ? (
                        <Empty description="暂无股东数据" />
                    ) : null}
                </Spin>
            ),
        },
    ]

    return (
        <ProCard
            title={
                <Space>
                    <span>基本面分析</span>
                    <DataSourceBadge
                        source={currentMeta?.source}
                        latency={currentMeta?.latency}
                        size="small"
                    />
                </Space>
            }
            extra={
                <Button
                    icon={<ReloadOutlined />}
                    onClick={() => {
                        incomeResult.refresh()
                        if (activeTab === 'balance') balanceResult.refresh()
                        if (activeTab === 'holder') holderResult.refresh()
                    }}
                    loading={loading}
                    size="small"
                >
                    刷新
                </Button>
            }
            bordered
            headerBordered
            tabs={{
                activeKey: activeTab,
                onChange: setActiveTab,
                items: tabItems,
            }}
        >
            {currentError && !incomeResult.error && !balanceResult.error && !holderResult.error && (
                <Alert message={currentError} type="warning" showIcon />
            )}
        </ProCard>
    )
}

export default FundamentalSection
