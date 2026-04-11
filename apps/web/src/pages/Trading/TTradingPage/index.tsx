/**
 * T-Trading 日内做T操盘页面
 * 用于设置日内对用户选中标的做T买卖点和仓位提醒
 */

import React, { useMemo, useState } from 'react'
import {
    Alert,
    Card,
    Button,
    Table,
    Space,
    Tag,
    Modal,
    Form,
    Input,
    InputNumber,
    Select,
    Switch,
    Popconfirm,
    message,
    Row,
    Col,
    Typography,
    Empty,
    Statistic,
    Badge,
    Segmented,
    theme,
    Descriptions,
    Progress,
} from 'antd'
import {
    PlusOutlined,
    DeleteOutlined,
    EditOutlined,
    PlayCircleOutlined,
    PauseCircleOutlined,
    BellOutlined,
    SwapOutlined,
    ReloadOutlined,
    SearchOutlined,
} from '@ant-design/icons'
import { useRequest } from 'ahooks'
import { StockSearchSelect } from '@/components/miniqmt'
import ttradingAPI from './api'
import type { TTradingStrategy, TradingSignal, CreateStrategyRequest, CreateSignalRequest } from './types'

const { Text } = Typography
const { Option } = Select

const TTradingPage: React.FC = () => {
    const { token } = theme.useToken()

    // 状态管理
    const [strategies, setStrategies] = useState<TTradingStrategy[]>([])
    const [selectedStrategy, setSelectedStrategy] = useState<TTradingStrategy | null>(null)
    const [strategyModalVisible, setStrategyModalVisible] = useState(false)
    const [signalModalVisible, setSignalModalVisible] = useState(false)
    const [editingSignal, setEditingSignal] = useState<TradingSignal | null>(null)
    const [strategyFilter, setStrategyFilter] = useState<'all' | 'active' | 'paused' | 'completed'>('all')
    const [strategyKeyword, setStrategyKeyword] = useState('')

    // 表单实例
    const [strategyForm] = Form.useForm()
    const [signalForm] = Form.useForm()

    // 获取策略列表
    const { loading: loadingStrategies, run: fetchStrategies } = useRequest(
        async () => {
            const res = await ttradingAPI.listStrategies()
            if ((res as any).success && (res as any).data) {
                setStrategies((res as any).data)
                // 如果有选中的策略，更新它
                if (selectedStrategy) {
                    const updated = (res as any).data.find((s: TTradingStrategy) => s.id === selectedStrategy.id)
                    if (updated) {
                        setSelectedStrategy(updated)
                    }
                }
            }
            return res
        },
        { manual: false }
    )

    // 创建策略
    const handleCreateStrategy = async (values: CreateStrategyRequest) => {
        try {
            const res = await ttradingAPI.createStrategy(values)
            if ((res as any).success) {
                message.success('策略创建成功')
                setStrategyModalVisible(false)
                strategyForm.resetFields()
                fetchStrategies()
            } else {
                message.error((res as any).message || '创建失败')
            }
        } catch {
            message.error('创建策略失败')
        }
    }

    // 删除策略
    const handleDeleteStrategy = async (strategyId: string) => {
        try {
            const res = await ttradingAPI.deleteStrategy(strategyId)
            if ((res as any).success) {
                message.success('策略已删除')
                if (selectedStrategy?.id === strategyId) {
                    setSelectedStrategy(null)
                }
                fetchStrategies()
            }
        } catch {
            message.error('删除策略失败')
        }
    }

    // 切换策略状态
    const handleToggleStrategy = async (strategyId: string) => {
        try {
            const res = await ttradingAPI.toggleStrategy(strategyId)
            if ((res as any).success) {
                message.success((res as any).message)
                fetchStrategies()
            }
        } catch {
            message.error('切换状态失败')
        }
    }

    // 添加/更新信号
    const handleSaveSignal = async (values: CreateSignalRequest) => {
        if (!selectedStrategy) return

        try {
            let res
            if (editingSignal) {
                res = await ttradingAPI.updateSignal(selectedStrategy.id, editingSignal.id, values)
            } else {
                res = await ttradingAPI.addSignal(selectedStrategy.id, values)
            }

            if ((res as any).success) {
                message.success(editingSignal ? '信号已更新' : '信号已添加')
                setSignalModalVisible(false)
                setEditingSignal(null)
                signalForm.resetFields()
                fetchStrategies()
            }
        } catch {
            message.error('保存信号失败')
        }
    }

    // 删除信号
    const handleDeleteSignal = async (signalId: string) => {
        if (!selectedStrategy) return

        try {
            const res = await ttradingAPI.removeSignal(selectedStrategy.id, signalId)
            if ((res as any).success) {
                message.success('信号已删除')
                fetchStrategies()
            }
        } catch {
            message.error('删除信号失败')
        }
    }

    // 测试通知
    const handleTestNotify = async () => {
        try {
            const res = await ttradingAPI.testNotify(selectedStrategy?.symbol)
            if ((res as any).success) {
                message.success('测试通知已发送')
            } else {
                message.warning((res as any).message || '发送失败，请检查通知配置')
            }
        } catch {
            message.error('发送测试通知失败')
        }
    }

    // 打开编辑信号弹窗
    const openEditSignal = (signal: TradingSignal) => {
        setEditingSignal(signal)
        signalForm.setFieldsValue(signal)
        setSignalModalVisible(true)
    }

    const overviewStats = useMemo(() => {
        const activeCount = strategies.filter((item) => item.status === 'active').length
        const pausedCount = strategies.filter((item) => item.status === 'paused').length
        const completedCount = strategies.filter((item) => item.status === 'completed').length
        const totalSignals = strategies.reduce((sum, item) => sum + item.signals.length, 0)
        const triggeredSignals = strategies.reduce(
            (sum, item) => sum + item.signals.filter((signal) => signal.triggered).length,
            0
        )
        return {
            total: strategies.length,
            active: activeCount,
            paused: pausedCount,
            completed: completedCount,
            totalSignals,
            triggeredSignals,
        }
    }, [strategies])

    const filteredStrategies = useMemo(() => {
        const keyword = strategyKeyword.trim().toLowerCase()

        return strategies.filter((item) => {
            const matchStatus = strategyFilter === 'all' || item.status === strategyFilter
            if (!matchStatus) {
                return false
            }
            if (!keyword) {
                return true
            }
            return (
                item.name.toLowerCase().includes(keyword)
                || item.symbol.toLowerCase().includes(keyword)
            )
        })
    }, [strategies, strategyFilter, strategyKeyword])

    const selectedSignalsOverview = useMemo(() => {
        if (!selectedStrategy) {
            return {
                buyCount: 0,
                sellCount: 0,
                triggeredCount: 0,
                pendingCount: 0,
                completionPercent: 0,
            }
        }

        const buyCount = selectedStrategy.signals.filter((signal) => signal.signal_type === 'buy').length
        const sellCount = selectedStrategy.signals.filter((signal) => signal.signal_type === 'sell').length
        const triggeredCount = selectedStrategy.signals.filter((signal) => signal.triggered).length
        const pendingCount = selectedStrategy.signals.filter((signal) => !signal.triggered && signal.enabled).length
        const completionPercent = selectedStrategy.signals.length
            ? Math.round((triggeredCount / selectedStrategy.signals.length) * 100)
            : 0

        return {
            buyCount,
            sellCount,
            triggeredCount,
            pendingCount,
            completionPercent,
        }
    }, [selectedStrategy])

    const statusMetaMap: Record<TTradingStrategy['status'], { badge: 'processing' | 'warning' | 'default'; text: string }> = {
        active: { badge: 'processing', text: '运行中' },
        paused: { badge: 'warning', text: '已暂停' },
        completed: { badge: 'default', text: '已完成' },
    }

    const getStatusMeta = (status: string) => {
        const known = statusMetaMap[status as TTradingStrategy['status']]
        if (known) {
            return known
        }
        return {
            badge: 'default' as const,
            text: status || '未知状态',
        }
    }

    const strategyFilterOptions = useMemo(
        () => [
            { label: `全部 (${overviewStats.total})`, value: 'all' },
            { label: `活跃 (${overviewStats.active})`, value: 'active' },
            { label: `暂停 (${overviewStats.paused})`, value: 'paused' },
            { label: `完成 (${overviewStats.completed})`, value: 'completed' },
        ],
        [overviewStats]
    )

    const formatDateTime = (value: string) => {
        if (!value) {
            return '-'
        }
        const parsed = new Date(value)
        if (Number.isNaN(parsed.getTime())) {
            return value
        }
        return parsed.toLocaleString('zh-CN', { hour12: false })
    }

    // 策略列表表格列
    const strategyColumns = [
        {
            title: '策略名称',
            dataIndex: 'name',
            key: 'name',
            render: (text: string, record: TTradingStrategy) => (
                <a onClick={() => setSelectedStrategy(record)}>{text}</a>
            ),
        },
        {
            title: '股票代码',
            dataIndex: 'symbol',
            key: 'symbol',
            render: (symbol: string) => <Tag color="blue">{symbol}</Tag>,
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => {
                const meta = getStatusMeta(status)
                return <Badge status={meta.badge} text={meta.text} />
            },
        },
        {
            title: '信号数',
            key: 'signals',
            render: (_: any, record: TTradingStrategy) => (
                <Space>
                    <Tag color="red">{record.signals.filter(s => s.signal_type === 'buy').length} 买</Tag>
                    <Tag color="green">{record.signals.filter(s => s.signal_type === 'sell').length} 卖</Tag>
                </Space>
            ),
        },
        {
            title: '通知',
            dataIndex: 'notify_enabled',
            key: 'notify',
            render: (enabled: boolean) => (
                enabled ? <Tag color="blue">已开启</Tag> : <Tag>已关闭</Tag>
            ),
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: TTradingStrategy) => (
                <Space size="small">
                    <Button
                        type="text"
                        size="small"
                        icon={record.status === 'active' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                        onClick={() => handleToggleStrategy(record.id)}
                    />
                    <Popconfirm
                        title="确定删除此策略？"
                        onConfirm={() => handleDeleteStrategy(record.id)}
                    >
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            ),
        },
    ]

    // 信号列表表格列
    const signalColumns = [
        {
            title: '类型',
            dataIndex: 'signal_type',
            key: 'type',
            render: (type: string) => (
                <Tag color={type === 'buy' ? 'red' : 'green'}>
                    {type === 'buy' ? '买入' : '卖出'}
                </Tag>
            ),
        },
        {
            title: '触发价格',
            dataIndex: 'trigger_price',
            key: 'price',
            render: (price: number) => <Text strong>{price.toFixed(2)}</Text>,
        },
        {
            title: '仓位比例',
            dataIndex: 'position_ratio',
            key: 'ratio',
            render: (ratio: number) => `${ratio}%`,
        },
        {
            title: '状态',
            key: 'status',
            render: (_: any, record: TradingSignal) => (
                <Space>
                    {!record.enabled && <Tag color="default">已禁用</Tag>}
                    {record.triggered ? (
                        <Tag color="purple">已触发</Tag>
                    ) : (
                        <Tag color="blue">待触发</Tag>
                    )}
                </Space>
            ),
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: TradingSignal) => (
                <Space size="small">
                    <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => openEditSignal(record)}
                    />
                    <Popconfirm
                        title="确定删除此信号？"
                        onConfirm={() => handleDeleteSignal(record.id)}
                    >
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            ),
        },
    ]

    return (
        <div style={{ padding: 0 }}>
            <Card
                style={{
                    marginBottom: 16,
                    borderRadius: 16,
                    border: 'none',
                    background: `linear-gradient(135deg, ${token.colorPrimaryBg} 0%, ${token.colorBgContainer} 65%)`,
                    boxShadow: '0 12px 28px rgba(0,0,0,0.08)',
                }}
            >
                <Row gutter={[16, 16]} align="middle">
                    <Col xs={24} md={14}>
                        <Space direction="vertical" size={4}>
                            <Space size={8}>
                                <SwapOutlined style={{ color: token.colorPrimary, fontSize: 18 }} />
                                <Text strong style={{ fontSize: 20, color: token.colorTextHeading }}>
                                    日内做T策略中心
                                </Text>
                            </Space>
                            <Text type="secondary">
                                统一管理监控标的、买卖点与提醒状态，支持策略级快速切换与信号执行追踪。
                            </Text>
                        </Space>
                    </Col>
                    <Col xs={24} md={10}>
                        <Space style={{ width: '100%', justifyContent: 'flex-end' }} wrap>
                            <Button icon={<ReloadOutlined />} onClick={fetchStrategies} loading={loadingStrategies}>
                                刷新
                            </Button>
                            <Button
                                type="primary"
                                icon={<PlusOutlined />}
                                onClick={() => setStrategyModalVisible(true)}
                            >
                                新建策略
                            </Button>
                        </Space>
                    </Col>
                </Row>
                <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
                    <Col xs={12} md={6}>
                        <Card size="small" style={{ borderRadius: 12 }}>
                            <Statistic title="策略总数" value={overviewStats.total} />
                        </Card>
                    </Col>
                    <Col xs={12} md={6}>
                        <Card size="small" style={{ borderRadius: 12 }}>
                            <Statistic
                                title="活跃策略"
                                value={overviewStats.active}
                                valueStyle={{ color: token.colorSuccess }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} md={6}>
                        <Card size="small" style={{ borderRadius: 12 }}>
                            <Statistic
                                title="信号总数"
                                value={overviewStats.totalSignals}
                                valueStyle={{ color: token.colorPrimary }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} md={6}>
                        <Card size="small" style={{ borderRadius: 12 }}>
                            <Statistic
                                title="已触发信号"
                                value={overviewStats.triggeredSignals}
                                valueStyle={{ color: token.colorWarning }}
                            />
                        </Card>
                    </Col>
                </Row>
            </Card>

            <Row gutter={[16, 16]}>
                {/* 左侧：策略列表 */}
                <Col xs={24} lg={10}>
                    <Card
                        title={
                            <Space>
                                <SwapOutlined />
                                <span>做T策略</span>
                            </Space>
                        }
                        extra={
                            <Segmented
                                size="small"
                                value={strategyFilter}
                                onChange={(value) =>
                                    setStrategyFilter(value as 'all' | 'active' | 'paused' | 'completed')
                                }
                                options={strategyFilterOptions}
                            />
                        }
                    >
                        <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
                            <Col span={24}>
                                <Input
                                    allowClear
                                    value={strategyKeyword}
                                    onChange={(event) => setStrategyKeyword(event.target.value)}
                                    placeholder="搜索策略名称或股票代码"
                                    prefix={<SearchOutlined />}
                                />
                            </Col>
                        </Row>
                        <Table
                            dataSource={filteredStrategies}
                            columns={strategyColumns}
                            rowKey="id"
                            loading={loadingStrategies}
                            size="small"
                            pagination={false}
                            rowClassName={(record) =>
                                record.id === selectedStrategy?.id ? 'ant-table-row-selected' : ''
                            }
                            onRow={(record) => ({
                                onClick: () => setSelectedStrategy(record),
                                style: { cursor: 'pointer' },
                            })}
                            locale={{
                                emptyText: (
                                    <Empty
                                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                                        description="暂无匹配策略，调整筛选条件后重试"
                                    />
                                ),
                            }}
                        />
                    </Card>
                </Col>

                {/* 右侧：策略详情和信号管理 */}
                <Col xs={24} lg={14}>
                    {selectedStrategy ? (
                        <Space direction="vertical" size={16} style={{ width: '100%' }}>
                            <Card
                                title={
                                    <Space>
                                        <Tag color="blue">{selectedStrategy.symbol}</Tag>
                                        <Text strong>{selectedStrategy.name}</Text>
                                        <Badge
                                            status={getStatusMeta(selectedStrategy.status).badge}
                                            text={getStatusMeta(selectedStrategy.status).text}
                                        />
                                    </Space>
                                }
                                extra={
                                    <Space>
                                        <Button
                                            icon={selectedStrategy.status === 'active' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                                            onClick={() => handleToggleStrategy(selectedStrategy.id)}
                                        >
                                            {selectedStrategy.status === 'active'
                                                ? '暂停策略'
                                                : selectedStrategy.status === 'paused'
                                                    ? '启动策略'
                                                    : '重新激活'}
                                        </Button>
                                        <Button icon={<BellOutlined />} onClick={handleTestNotify}>
                                            测试通知
                                        </Button>
                                        <Button
                                            type="primary"
                                            icon={<PlusOutlined />}
                                            onClick={() => {
                                                setEditingSignal(null)
                                                signalForm.resetFields()
                                                setSignalModalVisible(true)
                                            }}
                                        >
                                            添加买卖点
                                        </Button>
                                    </Space>
                                }
                            >
                                {selectedStrategy.status !== 'active' && (
                                    <Alert
                                        type="info"
                                        showIcon
                                        style={{ marginBottom: 12 }}
                                        message={
                                            selectedStrategy.status === 'completed'
                                                ? '当前策略已完成，如需继续跟踪请重新激活。'
                                                : '当前策略处于暂停状态，信号不会触发提醒。'
                                        }
                                    />
                                )}
                                <Descriptions
                                    size="small"
                                    column={{ xs: 1, sm: 2, md: 2, lg: 2 }}
                                    style={{ marginBottom: 16 }}
                                    items={[
                                        {
                                            key: 'notify',
                                            label: '通知状态',
                                            children: selectedStrategy.notify_enabled ? '已开启' : '已关闭',
                                        },
                                        {
                                            key: 'signal-total',
                                            label: '信号总数',
                                            children: `${selectedStrategy.signals.length} 个`,
                                        },
                                        {
                                            key: 'created',
                                            label: '创建时间',
                                            children: formatDateTime(selectedStrategy.created_at),
                                        },
                                        {
                                            key: 'updated',
                                            label: '最近更新',
                                            children: formatDateTime(selectedStrategy.updated_at),
                                        },
                                    ]}
                                />
                                <Row style={{ marginBottom: 16 }}>
                                    <Col span={24}>
                                        <Card size="small" style={{ borderRadius: 12 }}>
                                            <Space
                                                direction="vertical"
                                                size={6}
                                                style={{ width: '100%' }}
                                            >
                                                <Text type="secondary">信号执行进度</Text>
                                                <Progress
                                                    percent={selectedSignalsOverview.completionPercent}
                                                    size="small"
                                                    status={selectedSignalsOverview.completionPercent === 100 ? 'success' : 'active'}
                                                />
                                            </Space>
                                        </Card>
                                    </Col>
                                </Row>
                                <Row gutter={[12, 12]}>
                                    <Col xs={12} md={6}>
                                        <Card size="small" style={{ borderRadius: 12 }}>
                                            <Statistic
                                                title="买入信号"
                                                value={selectedSignalsOverview.buyCount}
                                                valueStyle={{ color: token.colorError }}
                                            />
                                        </Card>
                                    </Col>
                                    <Col xs={12} md={6}>
                                        <Card size="small" style={{ borderRadius: 12 }}>
                                            <Statistic
                                                title="卖出信号"
                                                value={selectedSignalsOverview.sellCount}
                                                valueStyle={{ color: token.colorSuccess }}
                                            />
                                        </Card>
                                    </Col>
                                    <Col xs={12} md={6}>
                                        <Card size="small" style={{ borderRadius: 12 }}>
                                            <Statistic
                                                title="已触发"
                                                value={selectedSignalsOverview.triggeredCount}
                                                valueStyle={{ color: token.colorWarning }}
                                            />
                                        </Card>
                                    </Col>
                                    <Col xs={12} md={6}>
                                        <Card size="small" style={{ borderRadius: 12 }}>
                                            <Statistic
                                                title="待触发"
                                                value={selectedSignalsOverview.pendingCount}
                                                valueStyle={{ color: token.colorPrimary }}
                                            />
                                        </Card>
                                    </Col>
                                </Row>
                            </Card>

                            <Card title="买卖点列表">
                                <Table
                                    dataSource={selectedStrategy.signals}
                                    columns={signalColumns}
                                    rowKey="id"
                                    size="small"
                                    pagination={false}
                                    locale={{ emptyText: <Empty description="暂无买卖点，点击上方添加" /> }}
                                />
                            </Card>
                        </Space>
                    ) : (
                        <Card style={{ height: '100%', minHeight: 400 }}>
                            <Empty
                                description="请选择左侧策略查看详情，或点击上方新建策略开始配置。"
                                style={{ marginTop: 100 }}
                            />
                        </Card>
                    )}
                </Col>
            </Row>

            {/* 新建策略弹窗 */}
            <Modal
                title="新建做T策略"
                open={strategyModalVisible}
                onCancel={() => {
                    setStrategyModalVisible(false)
                    strategyForm.resetFields()
                }}
                onOk={() => strategyForm.submit()}
                okText="创建"
                cancelText="取消"
            >
                <Form
                    form={strategyForm}
                    layout="vertical"
                    onFinish={handleCreateStrategy}
                    initialValues={{ notify_enabled: true }}
                >
                    <Form.Item
                        name="symbol"
                        label="股票代码"
                        rules={[{ required: true, message: '请选择股票' }]}
                    >
                        <StockSearchSelect
                            value={strategyForm.getFieldValue('symbol')}
                            onChange={(value) => strategyForm.setFieldsValue({ symbol: value })}
                            placeholder="输入代码或搜索股票"
                            style={{ width: '100%' }}
                        />
                    </Form.Item>
                    <Form.Item
                        name="name"
                        label="策略名称"
                        rules={[{ required: true, message: '请输入策略名称' }]}
                    >
                        <Input placeholder="例如：银行股做T" />
                    </Form.Item>
                    <Form.Item
                        name="notify_enabled"
                        label="开启通知提醒"
                        valuePropName="checked"
                    >
                        <Switch />
                    </Form.Item>
                </Form>
            </Modal>

            {/* 添加/编辑信号弹窗 */}
            <Modal
                title={editingSignal ? '编辑买卖点' : '添加买卖点'}
                open={signalModalVisible}
                onCancel={() => {
                    setSignalModalVisible(false)
                    setEditingSignal(null)
                    signalForm.resetFields()
                }}
                onOk={() => signalForm.submit()}
                okText={editingSignal ? '保存' : '添加'}
                cancelText="取消"
            >
                <Form
                    form={signalForm}
                    layout="vertical"
                    onFinish={handleSaveSignal}
                    initialValues={{ signal_type: 'buy', position_ratio: 30, enabled: true }}
                >
                    <Form.Item
                        name="signal_type"
                        label="信号类型"
                        rules={[{ required: true }]}
                    >
                        <Select>
                            <Option value="buy">
                                <Tag color="red">买入</Tag> 当价格跌至目标价时提醒
                            </Option>
                            <Option value="sell">
                                <Tag color="green">卖出</Tag> 当价格涨至目标价时提醒
                            </Option>
                        </Select>
                    </Form.Item>
                    <Form.Item
                        name="trigger_price"
                        label="触发价格"
                        rules={[{ required: true, message: '请输入触发价格' }]}
                    >
                        <InputNumber
                            style={{ width: '100%' }}
                            min={0}
                            step={0.01}
                            precision={2}
                            placeholder="例如：10.50"
                        />
                    </Form.Item>
                    <Form.Item
                        name="position_ratio"
                        label="仓位比例 (%)"
                        rules={[{ required: true, message: '请输入仓位比例' }]}
                    >
                        <InputNumber
                            style={{ width: '100%' }}
                            min={0}
                            max={100}
                            step={5}
                            placeholder="例如：30"
                            addonAfter="%"
                        />
                    </Form.Item>
                    <Form.Item
                        name="enabled"
                        label="启用此信号"
                        valuePropName="checked"
                    >
                        <Switch />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    )
}

export default TTradingPage
