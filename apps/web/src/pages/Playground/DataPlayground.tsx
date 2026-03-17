/**
 * DataPlayground - 统一数据源沙盒页面
 * 整合 MiniQMT 和 AmazingData 功能，支持数据源切换
 */
import React, { useState } from 'react'
import { Layout, Space, Row, Col, Divider } from 'antd'
import {
    StockOutlined,
    LineChartOutlined,
    FundOutlined,
    BarChartOutlined,
    ThunderboltOutlined,
    ApiOutlined,
} from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'
import type { DataSourceType } from '@/services/data-source'

// 通用组件
import { UniversalStockSearch } from '@/components/common/UniversalStockSearch'
import { DataSourceSelect } from '@/components/common/DataSourceSelect'
import { StatusSection } from '@/components/miniqmt'

// Playground Section 组件
import {
    QuoteSection,
    KlineSection,
    CapitalFlowSection,
    FundamentalSection,
    TradingAnomalySection,
} from '@/components/playground'

type ModuleKey = 'quote' | 'flow' | 'fundamental' | 'anomaly'

const DataPlayground: React.FC = () => {
    const [stockCode, setStockCode] = useState('000001.SZ')
    const [globalPreferredSource, setGlobalPreferredSource] = useState<DataSourceType | undefined>()
    const [modulePreferredSource, setModulePreferredSource] = useState<
        Partial<Record<ModuleKey, DataSourceType | undefined>>
    >({})

    const resolvePreferredSource = (module: ModuleKey): DataSourceType | undefined =>
        modulePreferredSource[module] ?? globalPreferredSource

    const setModuleSource = (module: ModuleKey, source: DataSourceType) => {
        setModulePreferredSource((prev) => ({
            ...prev,
            [module]: source,
        }))
    }

    const tabItems = [
        {
            key: 'quote',
            label: (
                <Space>
                    <LineChartOutlined />
                    <span>行情数据</span>
                </Space>
            ),
            children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <Row gutter={16}>
                        <Col span={24}>
                            <QuoteSection
                                stockCode={stockCode}
                                preferredSource={resolvePreferredSource('quote')}
                                onSuggestSourceSwitch={(source) => setModuleSource('quote', source)}
                            />
                        </Col>
                    </Row>
                    <Row gutter={16}>
                        <Col span={24}>
                            <KlineSection
                                stockCode={stockCode}
                                preferredSource={resolvePreferredSource('quote')}
                                onSuggestSourceSwitch={(source) => setModuleSource('quote', source)}
                            />
                        </Col>
                    </Row>
                </Space>
            ),
        },
        {
            key: 'flow',
            label: (
                <Space>
                    <FundOutlined />
                    <span>资金流向</span>
                </Space>
            ),
            children: (
                <CapitalFlowSection
                    stockCode={stockCode}
                    preferredSource={resolvePreferredSource('flow')}
                    onSuggestSourceSwitch={(source) => setModuleSource('flow', source)}
                />
            ),
        },
        {
            key: 'fundamental',
            label: (
                <Space>
                    <BarChartOutlined />
                    <span>基本面</span>
                </Space>
            ),
            children: (
                <FundamentalSection
                    stockCode={stockCode}
                    preferredSource={resolvePreferredSource('fundamental')}
                    onSuggestSourceSwitch={(source) => setModuleSource('fundamental', source)}
                />
            ),
        },
        {
            key: 'anomaly',
            label: (
                <Space>
                    <ThunderboltOutlined />
                    <span>市场异动</span>
                </Space>
            ),
            children: (
                <TradingAnomalySection
                    stockCode={stockCode}
                    preferredSource={resolvePreferredSource('anomaly')}
                    onSuggestSourceSwitch={(source) => setModuleSource('anomaly', source)}
                />
            ),
        },
    ]

    return (
        <Layout style={{ height: '100%', background: '#f0f2f5', overflow: 'auto' }}>
            <ProCard
                title={
                    <Space>
                        <StockOutlined />
                        <span>数据源沙盒</span>
                    </Space>
                }
                extra={
                    <Space split={<Divider type="vertical" />}>
                        <Space>
                            <UniversalStockSearch
                                value={stockCode}
                                onChange={(val) => setStockCode(val || '000001.SZ')}
                                style={{ width: 220 }}
                                placeholder="搜索股票..."
                            />
                        </Space>
                        <Space>
                            <ApiOutlined style={{ color: '#1890ff' }} />
                            <DataSourceSelect
                                value={globalPreferredSource}
                                onChange={setGlobalPreferredSource}
                                allowAuto
                                width={140}
                                size="middle"
                            />
                        </Space>
                        <StatusSection />
                    </Space>
                }
                tabs={{
                    type: 'card',
                    items: tabItems,
                }}
                style={{ height: '100%' }}
                bodyStyle={{ padding: 16, overflow: 'auto' }}
            />
        </Layout>
    )
}

export default DataPlayground
