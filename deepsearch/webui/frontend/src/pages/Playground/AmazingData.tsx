/**
 * AmazingData Playground 页面
 * 用于开发和测试 AmazingData 数据源的各种组件
 * 
 * Update: 2025-12-24 UI Refactor with ProComponents
 */
import React, { useState, useEffect } from 'react'
import {
    Layout,
    Typography,
    Card,
    Button,
    Space,
    Table,
    Spin,
    Tag,
    Row,
    Col,
    message,
    DatePicker,
    Empty,
} from 'antd'
import {
    ReloadOutlined,
    AreaChartOutlined,
    TableOutlined,
    BarChartOutlined,
    LineChartOutlined,
    StockOutlined,
    FundOutlined,
    TeamOutlined,
    SwapOutlined,
    PieChartOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { ProCard } from '@ant-design/pro-components'

import { UniversalStockSearch } from '@/components/common/UniversalStockSearch'
import dayjs from 'dayjs'
import { useDataSource } from '@/services/data-source'

import {
    financialApi,
    shareholderApi,
    optionApi,
    etfApi,
    DataFrameResult,
    basicApi
} from '@/api/amazingdata'
import ReactECharts from 'echarts-for-react'

const { Text } = Typography

// ============= 通用工具 (保持不变) =============

const flattenDataFrameResult = (df: DataFrameResult | null | undefined): DataFrameResult | null => {
    if (!df) return null
    if (df.data && Array.isArray(df.data) && df.data.length > 0) {
        const firstItem = df.data[0]
        if (typeof firstItem === 'object' && !Array.isArray(firstItem)) {
            const keys = Object.keys(firstItem)
            if (keys.length > 0) {
                const firstKey = keys[0]
                const nestedData = firstItem[firstKey]
                if (nestedData && typeof nestedData === 'object' && 'data' in nestedData) {
                    const allRecords: Record<string, unknown>[] = []
                    df.data.forEach((item: Record<string, unknown>) => {
                        Object.entries(item).forEach(([code, nested]) => {
                            if (nested && typeof nested === 'object' && 'data' in nested) {
                                const nestedDf = nested as DataFrameResult
                                if (Array.isArray(nestedDf.data)) {
                                    nestedDf.data.forEach((record: unknown) => {
                                        if (typeof record === 'object' && record !== null) {
                                            allRecords.push(record as Record<string, unknown>)
                                        }
                                    })
                                }
                            }
                        })
                    })
                    if (allRecords.length > 0) {
                        return {
                            data: allRecords,
                            columns: Object.keys(allRecords[0]),
                            count: allRecords.length,
                        }
                    }
                }
            }
        }
    }
    return df
}

/** DataFrame数据转表格数据 */
const dataFrameToTableData = (df: DataFrameResult | null | undefined): Record<string, unknown>[] => {
    const flatDf = flattenDataFrameResult(df)
    if (!flatDf || !flatDf.data || flatDf.data.length === 0) return []

    // 如果data已经是对象数组（records格式），直接使用
    if (flatDf.data.every((item: unknown) => typeof item === 'object' && !Array.isArray(item))) {
        return flatDf.data.map((row: Record<string, unknown>, idx: number) => ({
            _key: idx,
            ...row,
        }))
    }

    // 兼容二维数组格式（旧格式）
    const columns = flatDf.columns || []
    return flatDf.data.map((row: unknown, idx: number) => {
        const record: Record<string, unknown> = { _key: idx }
        if (Array.isArray(row)) {
            columns.forEach((col: string, i: number) => {
                record[col] = row[i]
            })
        }
        return record
    })
}

/** 列名中英文映射 */
const COLUMN_NAME_MAP: Record<string, string> = {
    // 股东信息相关
    'SHAREHOLDER_NAME': '股东名称',
    'HOLDER_NAME': '股东名称',
    'SHAREHOLDER_RANK': '股东排名',
    'HOLD_NUM': '持股数量',
    'QTY_NUM': '持股量序号',
    'HOLDER_QUANTITY': '持股数(股)',
    'HOLDER_PCT': '持股比例(%)',
    'CHANGE_NUM': '变动数量',
    'CHANGE_RATIO': '变动比例',
    'HOLDER_TYPE': '股东类别',
    'HOLDER_HOLDER_CATEGORY': '股东性质',
    'HOLDER_SHARECATEGORYNAME': '股份类型',
    'FLOAT_QTY': '流通股数量',
    'END_DATE': '截止日期',
    'HOLDER_ENDDATE': '到期日期',
    'MARKET_CODE': '证券代码',
    'REPORT_DATE': '报告日期',
    'ANN_DATE': '公告日期',
    'HOLDER_NUM': '股东户数',
    'HOLDER_TOTAL_NUM': '股东总户数',
    'AVG_HOLD': '户均持股',
    'TOTAL_NUM_RATIO': '户数变动',
    // 财务数据相关
    'SECURITY_CODE': '证券代码',
    'SECURITY_NAME': '证券名称',
    'TRADE_DATE': '交易日期',
    'STATEMENT_TYPE': '报表类型',
    'REPORT_TYPE': '报告类型',
    'REPORTING_PERIOD': '报告期',
    'TYPE': '类型',
    'NOTICE_DATE': '公告/预告日期',
    'ANN_DT': '公告日期',
    'PAY_DATE': '支付日期',
    'PLAN_DATE': '预案日期',
    'DIVIDEND_RATIO': '分红比例',
    'TRANSFER_RATIO': '转增比例',
    'AT_BONUS_RATIO': '送股比例',

    // 期权相关
    'CONTRACT_FULL_NAME': '合约全称',
    'CONTRACT_TYPE': '合约类型',
    'EXERCISE_PRICE': '行权价',
    'EXPIRY_DATE': '到期日',
    'CONTRACT_UNIT': '合约单位',
    'EXERCISE_DATE': '行权日',
    'LAST_TRADING_DATE': '最后交易日',
    'POSITION_LIMIT': '持仓限额',
    'DELIST_DATE': '退市日期',
    'EXERCISE_METHOD': '行权方式',
    'DELIVERY_METHOD': '交割方式',
    'EXCHANGE_NAME': '交易所',
    'CONTRACT_VALUE': '合约价值',
    'IS_SIMULATION': '是否仿真',
    'OPTION_STRIKE_PRICE': '期权行权价',
    'LISTED_DATE': '上市日期',
    'OPTION_NAME': '期权名称',
    'OPTION_TYPE': '期权类型',
    'CONTRACT_MULTIPLIER': '合约乘数',
    'CODE_OLD': '原代码',
    'CHANGE_DATE': '调整日期',
    'NAME_NEW': '新简称',
    'EXERCISE_PRICE_NEW': '新行权价',
    'NAME_OLD': '原简称',
    'CODE_NEW': '新代码',
    'EXERCISE_PRICE_OLD': '原行权价',
    'UNIT_OLD': '原单位',
    'UNIT_NEW': '新单位',
    'CHANGE_REASON': '调整原因',

    // 龙虎榜相关
    'EXPLANATION': '上榜原因',
    'CLOSE_PRICE': '收盘价',
    'CHANGE_RATE': '涨跌幅',
    'TOTAL_NET_AMOUNT': '净买入额',
    'BUY_AMOUNT': '买入额',
    'SELL_AMOUNT': '卖出额',
    'NET_AMOUNT': '净额',
    'TURNOVER_RATE': '换手率',
    'TOTAL_BUY_AMOUNT': '总买入额',
    'TOTAL_SELL_AMOUNT': '总卖出额',
    'SALES_DEPT_NAME': '营业部名称',
    'RANK': '排名',

    // 大宗交易相关
    'PRICE': '成交价',
    'VOLUME': '成交量',
    'AMOUNT': '成交额',
    'BUYER_NAME': '买方营业部',
    'SELLER_NAME': '卖方营业部',
    'REL_PRICE': '成交价/收盘价',

    // ETF相关
    'ETF_CODE': 'ETF代码',
    'ETF_NAME': 'ETF名称',
    'CASH_COMPONENT': '现金替代标志',
    'REDEMPTION_STATUS': '赎回状态',
    'SUBSCRIPTION_STATUS': '申购状态',
    'PRE_CASH_COMPONENT': '预估现金部分',
    'TRADING_DAY': '交易日',
    'TOTAL_CASH_COMPONENT': '现金差额',
    'NAV_PER_CU': '最小申赎单位净值',
    'NAV': '基金净值',
    'ESTIMATED_CASH_COMPONENT': '预估现金',
    'MAX_CASH_RATIO': '现金替代比例上限',

    // 通用
    'code': '代码',
    'name': '名称',
    'date': '日期',
}

/** 格式化日期值 */
const formatDateValue = (value: unknown): string => {
    if (!value) return '-'
    const str = String(value)
    if (/^\d{8}$/.test(str)) {
        return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
    }
    if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
        return str.slice(0, 10)
    }
    return str
}

/** 自动生成表格列 (优化版) */
const autoColumns = (df: DataFrameResult | null | undefined): ColumnsType<Record<string, unknown>> => {
    const flatDf = flattenDataFrameResult(df)
    if (!flatDf) return []

    const isDateColumn = (col: string) =>
        /date|_date|DATE/i.test(col) || ['END_DATE', 'REPORT_DATE', 'ANN_DATE', 'TRADE_DATE'].includes(col)

    const createColumn = (col: string) => ({
        title: COLUMN_NAME_MAP[col] || COLUMN_NAME_MAP[col.toUpperCase()] || col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        width: 120, // 默认宽度
        render: isDateColumn(col) ? (val: unknown) => formatDateValue(val) :
            (val: unknown) => (typeof val === 'number' && Math.abs(val) > 1000000) ? val.toLocaleString() : val // 简单的大数格式化
    })

    if (flatDf.columns && flatDf.columns.length > 0) {
        return flatDf.columns.map(createColumn)
    }

    if (flatDf.data && flatDf.data.length > 0 && typeof flatDf.data[0] === 'object') {
        const firstRow = flatDf.data[0] as Record<string, unknown>
        return Object.keys(firstRow).filter(k => k !== '_key').map(createColumn)
    }

    return []
}

// ============= 组件定义 =============

/** 通用数据视图组件 */
const DataView: React.FC<{
    title?: React.ReactNode
    data: DataFrameResult | null
    loading: boolean
    chartOption?: any
    columns?: ColumnsType<any>
    height?: number
}> = ({ title, data, loading, chartOption, columns, height = 350 }) => {
    const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart')
    const hasData = data && data.data && data.data.length > 0

    return (
        <ProCard
            title={title}
            extra={
                chartOption && hasData ? (
                    <Space size={2}>
                        <Button
                            type={viewMode === 'chart' ? 'text' : 'text'}
                            size="small"
                            onClick={() => setViewMode('chart')}
                            icon={<BarChartOutlined style={{ color: viewMode === 'chart' ? '#1890ff' : undefined }} />}
                        />
                        <Button
                            type={viewMode === 'table' ? 'text' : 'text'}
                            size="small"
                            onClick={() => setViewMode('table')}
                            icon={<TableOutlined style={{ color: viewMode === 'table' ? '#1890ff' : undefined }} />}
                        />
                    </Space>
                ) : null
            }
            bordered
            headerBordered
            style={{ height: '100%' }}
            bodyStyle={{ padding: viewMode === 'chart' ? 10 : 0, height: height, overflow: 'hidden' }}
        >
            <Spin spinning={loading}>
                {!hasData && !loading ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
                ) : viewMode === 'chart' && chartOption ? (
                    <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                ) : (
                    <Table
                        dataSource={dataFrameToTableData(data)}
                        columns={columns || autoColumns(data)}
                        rowKey="_key"
                        size="small"
                        scroll={{ x: 'max-content', y: height - 80 }}
                        pagination={{ defaultPageSize: 10, showSizeChanger: true, size: 'small' }}
                    />
                )}
            </Spin>
        </ProCard>
    )
}

/** 概览页签 */
const OverviewSection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [info, setInfo] = useState<any>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (stockCode) {
            setLoading(true)
            basicApi.getStockBasic([stockCode]).then(res => {
                const df = flattenDataFrameResult(res.data)
                if (df && df.data && df.data.length > 0) {
                    setInfo(df.data[0])
                }
            }).finally(() => setLoading(false))
        }
    }, [stockCode])

    return (
        <ProCard title="证券信息" headerBordered bordered loading={loading}>
            {info ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                    <Row gutter={[24, 12]}>
                        <Col span={8}><Text type="secondary">代码：</Text><Text strong>{info.symbol || info.code || stockCode}</Text></Col>
                        <Col span={8}><Text type="secondary">名称：</Text><Text strong>{info.name || info.sec_name}</Text></Col>
                        <Col span={8}><Text type="secondary">市场：</Text><Text>{info.market}</Text></Col>
                        <Col span={8}><Text type="secondary">上市日期：</Text><Text>{formatDateValue(info.list_date)}</Text></Col>
                        {/* 这里展示更多基础字段 */}
                    </Row>
                </Space>
            ) : <Empty description="请搜索股票查看详情" />}
        </ProCard>
    )
}

/** 基本面页签 */
const FundamentalSection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [loading, setLoading] = useState(false)
    const [balanceData, setBalanceData] = useState<DataFrameResult | null>(null)
    const [incomeData, setIncomeData] = useState<DataFrameResult | null>(null)
    const [cashFlowData, setCashFlowData] = useState<DataFrameResult | null>(null)

    // 股东数据
    const [holderData, setHolderData] = useState<DataFrameResult | null>(null)
    const [holderNumData, setHolderNumData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) return
        setLoading(true)
        try {
            const results = await Promise.allSettled([
                financialApi.getBalanceSheet({ code_list: [stockCode] }),
                financialApi.getIncome({ code_list: [stockCode] }),
                financialApi.getCashFlow({ code_list: [stockCode] }),
                shareholderApi.getShareHolder({ code: stockCode }),
                shareholderApi.getHolderNum({ code: stockCode }),
            ])

            const getResult = (res: PromiseSettledResult<any>, apiName: string) => {
                if (res.status === 'rejected') {
                    console.error(`${apiName} 请求失败:`, res.reason)
                    message.error(`${apiName} 请求失败: ${res.reason}`)
                    return null
                }
                const response = res.value
                if (!response.success) {
                    console.error(`${apiName} 返回错误:`, response.error, response.traceback)
                    message.error(`${apiName} 失败: ${response.error}`)
                    return null
                }
                return response.data
            }

            console.log('Fetch Results:', results)

            setBalanceData(getResult(results[0], '资产负债表'))
            setIncomeData(getResult(results[1], '利润表'))
            setCashFlowData(getResult(results[2], '现金流表'))
            setHolderData(getResult(results[3], '股东信息'))
            setHolderNumData(getResult(results[4], '股东数量'))

            // Check if all failed
            const allFailed = results.every(r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.success))
            if (allFailed) {
                message.error('所有数据获取失败，请检查后端服务日志')
            }
        } catch (err) {
            console.error('Unexpected Fetch Error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchData() }, [stockCode])

    // 图表生成器
    const getCommonOption = (title: string, xData: string[], series: any[]) => ({
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '10%', top: '15%', containLabel: true },
        xAxis: { type: 'category', data: xData },
        yAxis: { type: 'value', axisLabel: { formatter: (val: number) => (val / 100000000).toFixed(1) + '亿' } },
        series: series.map(s => ({ ...s, smooth: true })),
        color: ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
    })

    const getBalanceOption = () => {
        const data = dataFrameToTableData(balanceData).reverse()
        if (data.length === 0) return null
        const dates = data.map(d => formatDateValue(d.REPORT_DATE || d.report_date))
        return getCommonOption('', dates, [
            { name: '总资产', type: 'bar', stack: 'total', data: data.map(d => d.TOTAL_ASSETS || d.total_assets) },
            { name: '总负债', type: 'bar', stack: 'total', data: data.map(d => d.TOTAL_LIAB || d.total_liab) },
            { name: '股东权益', type: 'line', yAxisIndex: 0, data: data.map(d => d.TOTAL_HLDR_EQY_EXC_MIN_INT || d.total_hldr_eqy_exc_min_int) },
        ])
    }

    const getIncomeOption = () => {
        const data = dataFrameToTableData(incomeData).reverse()
        if (data.length === 0) return null
        const dates = data.map(d => formatDateValue(d.REPORT_DATE || d.report_date))
        return getCommonOption('', dates, [
            { name: '营业总收入', type: 'bar', data: data.map(d => d.TOTAL_REVENUE || d.total_revenue) },
            { name: '净利润', type: 'line', data: data.map(d => d.NET_PROFIT || d.net_profit) },
        ])
    }

    const getCashFlowOption = () => {
        const data = dataFrameToTableData(cashFlowData).reverse()
        if (data.length === 0) return null
        const dates = data.map(d => formatDateValue(d.REPORT_DATE || d.report_date))
        return getCommonOption('', dates, [
            { name: '经营现金流', type: 'line', data: data.map(d => d.N_CASHFLOW_ACT || d.n_cashflow_act) },
            { name: '投资现金流', type: 'line', data: data.map(d => d.N_CASHFLOW_INV || d.n_cashflow_inv) },
        ])
    }

    // 股东户数图表
    const getHolderNumOption = () => {
        const data = dataFrameToTableData(holderNumData).reverse()
        if (data.length === 0) return null
        const dates = data.map(d => formatDateValue(d.ANN_DT || d.END_DATE))
        return {
            tooltip: { trigger: 'axis' },
            grid: { left: 50, right: 20, top: 20, bottom: 20 },
            xAxis: { type: 'category', data: dates },
            yAxis: { type: 'value', min: 'dataMin' },
            series: [{ name: '股东户数', type: 'line', smooth: true, areaStyle: {}, data: data.map(d => d.HOLDER_TOTAL_NUM || d.HOLDER_NUM) }]
        }
    }

    // 十大股东自定义列
    const holderColumns: ColumnsType<Record<string, unknown>> = [
        { title: '公告日期', dataIndex: 'ANN_DATE', width: 110, render: (val) => formatDateValue(val) },
        { title: '到期日期', dataIndex: 'HOLDER_ENDDATE', width: 110, render: (val) => formatDateValue(val) },
        { title: '股东类别', dataIndex: 'HOLDER_TYPE', width: 140, render: (val) => ({ '10': '十大股东', '20': '流通股前十大股东' }[String(val)] || val) },
        { title: '股东名称', dataIndex: 'HOLDER_NAME', width: 200, ellipsis: true },
        { title: '持股数', dataIndex: 'HOLDER_QUANTITY', width: 120, align: 'right', render: (val) => Number(val).toLocaleString() },
        { title: '比例(%)', dataIndex: 'HOLDER_PCT', width: 90, align: 'right', render: (val) => (val ? Number(val).toFixed(2) : '-') },
        { title: '性质', dataIndex: 'HOLDER_HOLDER_CATEGORY', width: 80, render: (val) => ({ '1': '个人', '2': '公司' }[String(val)] || val) },
    ]

    return (
        <ProCard split="vertical" bordered headerBordered>
            <ProCard colSpan="20%" title="财务指标" direction="column" ghost gutter={[0, 16]}>
                <ProCard><DataView title="资产负债" data={balanceData} loading={loading} chartOption={getBalanceOption()} height={250} /></ProCard>
                <ProCard><DataView title="利润营收" data={incomeData} loading={loading} chartOption={getIncomeOption()} height={250} /></ProCard>
                <ProCard><DataView title="现金流量" data={cashFlowData} loading={loading} chartOption={getCashFlowOption()} height={250} /></ProCard>
            </ProCard>
            <ProCard title="股东分析" direction="column" headerBordered>
                <ProCard split="horizontal">
                    <ProCard height={300} title="股东户数趋势">
                        <DataView data={holderNumData} loading={loading} chartOption={getHolderNumOption()} height={250} />
                    </ProCard>
                    <ProCard title="十大股东">
                        <DataView data={holderData} loading={loading} columns={holderColumns} height={400} />
                    </ProCard>
                </ProCard>
            </ProCard>
        </ProCard>
    )
}

/** 衍生品页签 */
const DerivativesSection: React.FC = () => {
    const [codeList, setCodeList] = useState<string[]>([])
    const [basicInfo, setBasicInfo] = useState<DataFrameResult | null>(null)
    const [pcfInfo, setPcfInfo] = useState<DataFrameResult | null>(null)
    const [loading, setLoading] = useState(false)
    const [etfCode] = useState('510050.SH') // 默认示例

    useEffect(() => {
        setLoading(true)
        Promise.all([
            optionApi.getCodeList('EXTRA_ETF_OP').catch(() => ({ data: { data: [] } })),
            etfApi.getPcf([etfCode]).catch(() => ({ data: { etf_pcf_info: null } }))
        ]).then(([optRes, etfRes]) => {
            const codes = optRes.data?.data || []
            setCodeList(codes)
            if (codes.length > 0) {
                optionApi.getBasicInfo({ code_list: codes.slice(0, 10) }).then(res => setBasicInfo(res.data || null))
            }
            setPcfInfo(etfRes.data?.etf_pcf_info || null)
        }).finally(() => setLoading(false))
    }, [])

    return (
        <ProCard split="vertical" bordered>
            <ProCard colSpan="50%" title="期权数据" headerBordered>
                <DataView
                    title={`代码列表 (${codeList.length})`}
                    data={basicInfo}
                    loading={loading}
                    height={600}
                />
            </ProCard>
            <ProCard title="ETF申赎 (510050.SH)" headerBordered>
                <DataView data={pcfInfo} loading={loading} height={600} />
            </ProCard>
        </ProCard>
    )
}

/** 市场分析页签 */
const { RangePicker } = DatePicker
const MarketSection: React.FC<{ stockCode: string }> = ({ stockCode }) => {
    const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>([dayjs().subtract(1, 'month'), dayjs()])

    const dateParams = dateRange ? {
        startDate: dateRange[0].format('YYYYMMDD'),
        endDate: dateRange[1].format('YYYYMMDD'),
    } : {}

    const dragonData = useDataSource({
        capability: 'dragon_tiger',
        params: { code: stockCode, limit: 100, ...dateParams },
        preferredSource: 'amazingdata',
    })
    const blockData = useDataSource({
        capability: 'block_trading',
        params: { codes: stockCode ? [stockCode] : [], ...dateParams },
        preferredSource: 'amazingdata',
    })

    const loading = dragonData.loading || blockData.loading

    return (
        <ProCard
            title="异动分析"
            extra={
                <Space>
                    <RangePicker value={dateRange} onChange={(d) => setDateRange(d as any)} />
                    <Button icon={<ReloadOutlined />} onClick={() => { dragonData.refresh(); blockData.refresh() }} loading={loading}>刷新</Button>
                </Space>
            }
            direction="column"
            gutter={[0, 16]}
            ghost
        >
            <ProCard split="vertical" bordered headerBordered>
                <ProCard title="龙虎榜" colSpan="50%">
                    <DataView data={{ data: dragonData.data, columns: dragonData.columns?.map(c => c.dataIndex) || [], count: 0 }} loading={loading} height={500} />
                </ProCard>
                <ProCard title="大宗交易">
                    <DataView data={{ data: blockData.data, columns: blockData.columns?.map(c => c.dataIndex) || [], count: 0 }} loading={loading} height={500} />
                </ProCard>
            </ProCard>
        </ProCard>
    )
}

// ============= 全局页面 =============

const AmazingDataPage: React.FC = () => {
    const [stockCode, setStockCode] = useState('600519.SH')
    const [tab, setTab] = useState('fundamental') // 默认看基本面

    return (
        <Layout style={{ height: '100vh', background: '#f0f2f5' }}>
            <ProCard
                title={<Space><StockOutlined /><span>AmazingData 深度数据</span></Space>}
                extra={
                    <Space>
                        <UniversalStockSearch
                            value={stockCode}
                            onChange={(val) => setStockCode(val || '600519.SH')}
                            style={{ width: 250 }}
                            placeholder="搜索股票代码..."
                        />
                    </Space>
                }
                tabs={{
                    activeKey: tab,
                    onChange: setTab,
                    type: 'card',
                    items: [
                        { label: '概览', key: 'overview', children: <OverviewSection stockCode={stockCode} />, icon: <TableOutlined /> },
                        { label: '基本面', key: 'fundamental', children: <FundamentalSection stockCode={stockCode} />, icon: <BarChartOutlined /> },
                        { label: '衍生品', key: 'derivatives', children: <DerivativesSection />, icon: <LineChartOutlined /> },
                        { label: '市场异动', key: 'market', children: <MarketSection stockCode={stockCode} />, icon: <AreaChartOutlined /> },
                    ]
                }}
                style={{ height: '100%', overflow: 'hidden' }}
                bodyStyle={{ padding: 0 }}
            />
        </Layout>
    )
}

export default AmazingDataPage
