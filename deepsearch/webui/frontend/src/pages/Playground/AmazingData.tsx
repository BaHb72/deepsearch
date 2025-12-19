/**
 * AmazingData Playground 页面
 * 用于开发和测试 AmazingData 数据源的各种组件
 */
import React, { useState } from 'react'
import {
    Layout,
    Typography,
    Anchor,
    Card,
    Divider,
    Input,
    Button,
    Space,
    Table,
    Spin,
    Tag,
    Row,
    Col,
    message,
} from 'antd'
import {
    ReloadOutlined,
    SearchOutlined,
    StockOutlined,
    FundOutlined,
    TeamOutlined,
    SwapOutlined,
    AreaChartOutlined,
    PieChartOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
    financialApi,
    marginApi,
    shareholderApi,
    optionApi,
    etfApi,
    DataFrameResult,
} from '@/api/amazingdata'

const { Title, Text, Paragraph } = Typography
const { Content, Sider } = Layout

// ============= 通用工具 =============

/** DataFrame数据转表格数据 */
const dataFrameToTableData = (df: DataFrameResult | null | undefined): Record<string, unknown>[] => {
    if (!df || !df.data || df.data.length === 0) return []
    const columns = df.columns || []
    return df.data.map((row, idx) => {
        const record: Record<string, unknown> = { _key: idx }
        columns.forEach((col, i) => {
            record[col] = row[i]
        })
        return record
    })
}

/** 自动生成表格列 */
const autoColumns = (df: DataFrameResult | null | undefined): ColumnsType<Record<string, unknown>> => {
    if (!df || !df.columns) return []
    return df.columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        width: 120,
    }))
}

// ============= Section 组件 =============

/** Section 1: 财务数据区 */
const FinancialSection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [loading, setLoading] = useState(false)
    const [balanceData, setBalanceData] = useState<DataFrameResult | null>(null)
    const [incomeData, setIncomeData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const [balance, income] = await Promise.all([
                financialApi.getBalanceSheet({ code_list: [stockCode] }),
                financialApi.getIncome({ code_list: [stockCode] }),
            ])
            setBalanceData(balance.data?.data || null)
            setIncomeData(income.data?.data || null)
        } catch (err) {
            message.error('获取财务数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <FundOutlined />
                    <span>财务数据</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                    加载数据
                </Button>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="资产负债表" size="small">
                            <Table
                                dataSource={dataFrameToTableData(balanceData)}
                                columns={autoColumns(balanceData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="利润表" size="small">
                            <Table
                                dataSource={dataFrameToTableData(incomeData)}
                                columns={autoColumns(incomeData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}

/** Section 2: 股东信息区 */
const ShareholderSection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [loading, setLoading] = useState(false)
    const [holderData, setHolderData] = useState<DataFrameResult | null>(null)
    const [holderNumData, setHolderNumData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const [holder, holderNum] = await Promise.all([
                shareholderApi.getShareHolder({ code: stockCode }),
                shareholderApi.getHolderNum({ code: stockCode }),
            ])
            setHolderData(holder.data?.data || null)
            setHolderNumData(holderNum.data?.data || null)
        } catch (err) {
            message.error('获取股东数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <TeamOutlined />
                    <span>股东信息</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                    加载数据
                </Button>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="十大股东" size="small">
                            <Table
                                dataSource={dataFrameToTableData(holderData)}
                                columns={autoColumns(holderData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="股东户数" size="small">
                            <Table
                                dataSource={dataFrameToTableData(holderNumData)}
                                columns={autoColumns(holderNumData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}

/** Section 3: 交易异动区 */
const TradingAnomalySection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [loading, setLoading] = useState(false)
    const [dragonData, setDragonData] = useState<DataFrameResult | null>(null)
    const [blockData, setBlockData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const [dragon, block] = await Promise.all([
                marginApi.getLongHuBang({ code: stockCode, limit: 20 }),
                marginApi.getBlockTrading({ code_list: [stockCode] }),
            ])
            setDragonData(dragon.data?.data || null)
            setBlockData(block.data?.data || null)
        } catch (err) {
            message.error('获取交易异动数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <SwapOutlined />
                    <span>交易异动</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                    加载数据
                </Button>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="龙虎榜" size="small">
                            <Table
                                dataSource={dataFrameToTableData(dragonData)}
                                columns={autoColumns(dragonData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="大宗交易" size="small">
                            <Table
                                dataSource={dataFrameToTableData(blockData)}
                                columns={autoColumns(blockData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}

/** Section 4: 期权数据区 */
const OptionsSection: React.FC = () => {
    const [loading, setLoading] = useState(false)
    const [codeList, setCodeList] = useState<string[]>([])
    const [basicInfo, setBasicInfo] = useState<DataFrameResult | null>(null)

    const fetchCodeList = async () => {
        setLoading(true)
        try {
            const res = await optionApi.getCodeList('EXTRA_ETF_OP')
            setCodeList(res.data?.data || [])
        } catch (err) {
            message.error('获取期权代码列表失败')
        } finally {
            setLoading(false)
        }
    }

    const fetchBasicInfo = async () => {
        if (codeList.length === 0) {
            message.warning('请先获取期权代码列表')
            return
        }
        setLoading(true)
        try {
            // 只取前5个代码测试
            const testCodes = codeList.slice(0, 5)
            const res = await optionApi.getBasicInfo({ code_list: testCodes })
            setBasicInfo(res.data?.data || null)
        } catch (err) {
            message.error('获取期权基本资料失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <AreaChartOutlined />
                    <span>期权数据</span>
                </Space>
            }
            extra={
                <Space>
                    <Button onClick={fetchCodeList} loading={loading}>
                        获取代码列表
                    </Button>
                    <Button onClick={fetchBasicInfo} loading={loading} disabled={codeList.length === 0}>
                        获取基本资料
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={8}>
                        <Card type="inner" title={`期权代码列表 (${codeList.length})`} size="small">
                            <div style={{ maxHeight: 300, overflow: 'auto' }}>
                                {codeList.slice(0, 50).map((code, idx) => (
                                    <Tag key={idx} style={{ margin: 4 }}>
                                        {code}
                                    </Tag>
                                ))}
                                {codeList.length > 50 && <Text type="secondary">...还有 {codeList.length - 50} 个</Text>}
                            </div>
                        </Card>
                    </Col>
                    <Col span={16}>
                        <Card type="inner" title="期权基本资料" size="small">
                            <Table
                                dataSource={dataFrameToTableData(basicInfo)}
                                columns={autoColumns(basicInfo)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 1200, y: 300 }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}

/** Section 5: ETF数据区 */
const EtfSection: React.FC = () => {
    const [loading, setLoading] = useState(false)
    const [etfCode, setEtfCode] = useState('SH.510050')
    const [pcfInfo, setPcfInfo] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        setLoading(true)
        try {
            const res = await etfApi.getPcf([etfCode])
            setPcfInfo(res.data?.data?.etf_pcf_info || null)
        } catch (err) {
            message.error('获取ETF申赎数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <PieChartOutlined />
                    <span>ETF数据</span>
                </Space>
            }
            extra={
                <Space>
                    <Input
                        placeholder="ETF代码"
                        value={etfCode}
                        onChange={(e) => setEtfCode(e.target.value)}
                        style={{ width: 150 }}
                    />
                    <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        加载数据
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Card type="inner" title="ETF申赎信息 (PCF)" size="small">
                    <Table
                        dataSource={dataFrameToTableData(pcfInfo)}
                        columns={autoColumns(pcfInfo)}
                        rowKey="_key"
                        size="small"
                        scroll={{ x: 1200, y: 400 }}
                        pagination={false}
                    />
                </Card>
            </Spin>
        </Card>
    )
}

// ============= 主页面 =============

const AmazingDataPlayground: React.FC = () => {
    const [stockCode, setStockCode] = useState('SH.600519')

    const anchorItems = [
        { key: 'financial', href: '#financial', title: '财务数据' },
        { key: 'shareholder', href: '#shareholder', title: '股东信息' },
        { key: 'trading', href: '#trading', title: '交易异动' },
        { key: 'options', href: '#options', title: '期权数据' },
        { key: 'etf', href: '#etf', title: 'ETF数据' },
    ]

    return (
        <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
            <Sider
                width={160}
                style={{
                    background: '#fff',
                    position: 'fixed',
                    left: 0,
                    top: 64,
                    bottom: 0,
                    overflow: 'auto',
                    zIndex: 100,
                }}
            >
                <div style={{ padding: '16px 8px' }}>
                    <Title level={5} style={{ marginBottom: 16 }}>
                        导航
                    </Title>
                    <Anchor items={anchorItems} offsetTop={80} />
                </div>
            </Sider>

            <Content style={{ marginLeft: 160, padding: 24 }}>
                {/* 页面标题 */}
                <Card style={{ marginBottom: 24 }}>
                    <Title level={3}>
                        <StockOutlined style={{ marginRight: 8 }} />
                        AmazingData Playground
                    </Title>
                    <Paragraph type="secondary">
                        组件开发沙盒 - 在此页面测试各种AmazingData API数据展示组件
                    </Paragraph>
                    <Space>
                        <Text>测试股票代码:</Text>
                        <Input
                            placeholder="如 SH.600519"
                            value={stockCode}
                            onChange={(e) => setStockCode(e.target.value)}
                            style={{ width: 200 }}
                            prefix={<SearchOutlined />}
                        />
                    </Space>
                </Card>

                {/* Section 1: 财务数据 */}
                <div id="financial" style={{ marginBottom: 24 }}>
                    <FinancialSection stockCode={stockCode} />
                </div>

                <Divider />

                {/* Section 2: 股东信息 */}
                <div id="shareholder" style={{ marginBottom: 24 }}>
                    <ShareholderSection stockCode={stockCode} />
                </div>

                <Divider />

                {/* Section 3: 交易异动 */}
                <div id="trading" style={{ marginBottom: 24 }}>
                    <TradingAnomalySection stockCode={stockCode} />
                </div>

                <Divider />

                {/* Section 4: 期权数据 */}
                <div id="options" style={{ marginBottom: 24 }}>
                    <OptionsSection />
                </div>

                <Divider />

                {/* Section 5: ETF数据 */}
                <div id="etf" style={{ marginBottom: 24 }}>
                    <EtfSection />
                </div>
            </Content>
        </Layout>
    )
}

export default AmazingDataPlayground
