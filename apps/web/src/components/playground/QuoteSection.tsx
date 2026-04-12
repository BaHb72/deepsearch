/**
 * QuoteSection - 实时行情组件
 * 使用 useRichDataSource 获取数据，支持展示扩展字段
 */
import React from 'react'
import { Button, Space, Statistic, Row, Col, Empty, Spin, Alert } from 'antd'
import { ReloadOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'
import {
    type CoreQuoteData,
    type DataSourceType,
    useRichDataSource,
} from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface QuoteSectionProps {
    stockCode: string
    preferredSource?: DataSourceType
    onSuggestSourceSwitch?: (source: DataSourceType) => void
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

export const QuoteSection: React.FC<QuoteSectionProps> = ({
    stockCode,
    preferredSource,
    onSuggestSourceSwitch,
    showExtended = true,
}) => {
    const { data, extended, meta, loading, error, refresh } = useRichDataSource<CoreQuoteData>({
        capability: 'realtime_quote',
        params: { code: stockCode },
        preferredSource,
        autoFetch: true,
        deps: [stockCode],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'quote',
            moduleName: '行情数据',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    const quote = data[0]
    const extendedData = extended[0]

    // 价格变动颜色
    const priceColor = quote?.changePct
        ? quote.changePct > 0 ? '#f5222d' : quote.changePct < 0 ? '#52c41a' : undefined
        : undefined

    return (
        <ProCard
            title={
                <Space>
                    <span>实时行情</span>
                    <DataSourceBadge
                        source={meta?.source}
                        latency={meta?.latency}
                        size="small"
                    />
                </Space>
            }
            extra={
                <Button
                    icon={<ReloadOutlined />}
                    onClick={refresh}
                    loading={loading}
                    size="small"
                >
                    刷新
                </Button>
            }
            bordered
            headerBordered
        >
            <Spin spinning={loading}>
                {error && (
                    <Alert
                        message="获取行情失败"
                        description={error}
                        type="warning"
                        showIcon
                        style={{ marginBottom: 16 }}
                    />
                )}
                {quote ? (
                    <>
                        <Row gutter={[16, 16]}>
                            <Col span={6}>
                                <Statistic
                                    title="最新价"
                                    value={quote.price ?? '-'}
                                    precision={2}
                                    valueStyle={{ color: priceColor, fontSize: 24 }}
                                    prefix={quote.changePct && quote.changePct > 0 ? <RiseOutlined /> : quote.changePct && quote.changePct < 0 ? <FallOutlined /> : null}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="涨跌幅"
                                    value={quote.changePct ?? 0}
                                    precision={2}
                                    suffix="%"
                                    valueStyle={{ color: priceColor }}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="成交量"
                                    value={quote.volume ?? 0}
                                    formatter={(val) => {
                                        const num = Number(val)
                                        if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿'
                                        if (num >= 10000) return (num / 10000).toFixed(2) + '万'
                                        return num.toLocaleString()
                                    }}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="成交额"
                                    value={quote.amount ?? 0}
                                    formatter={(val) => {
                                        const num = Number(val)
                                        if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿'
                                        if (num >= 10000) return (num / 10000).toFixed(2) + '万'
                                        return num.toLocaleString()
                                    }}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic title="开盘价" value={quote.open ?? '-'} precision={2} />
                            </Col>
                            <Col span={6}>
                                <Statistic title="最高价" value={quote.high ?? '-'} precision={2} />
                            </Col>
                            <Col span={6}>
                                <Statistic title="最低价" value={quote.low ?? '-'} precision={2} />
                            </Col>
                            <Col span={6}>
                                <Statistic title="昨收价" value={quote.preClose ?? '-'} precision={2} />
                            </Col>
                        </Row>

                        {/* 扩展字段面板 */}
                        {showExtended && extendedData && Object.keys(extendedData).length > 0 && (
                            <ExtendedFieldsPanel
                                extended={extendedData}
                                source={meta?.source}
                                title="更多行情数据"
                            />
                        )}
                    </>
                ) : !loading && !error ? (
                    <Empty description="暂无行情数据" />
                ) : null}
            </Spin>
        </ProCard>
    )
}

export default QuoteSection
