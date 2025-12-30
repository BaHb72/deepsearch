/**
 * 轮询配置组件
 * 用于管理 MiniQMT 和 AmazingData 数据源的轮询时间间隔和轮询时间段
 */
import React, { useCallback, useEffect, useState } from 'react'
import {
    Alert,
    App as AntApp,
    Button,
    Card,
    Col,
    InputNumber,
    Radio,
    Row,
    Select,
    Slider,
    Space,
    Spin,
    Switch,
    Typography,
} from 'antd'
import {
    ClockCircleOutlined,
    ReloadOutlined,
    SaveOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons'
import {
    getPollingConfig,
    updatePollingConfig,
    type PhaseBehavior,
    type PollingConfig as PollingConfigType,
    type PollingConfigUpdate,
    type SessionGuard,
} from '@/api/polling-config'

const { Text, Title } = Typography

// 阶段显示名称和说明
const PHASE_META: Record<string, { label: string; description: string; color: string }> = {
    continuous: {
        label: '连续竞价',
        description: '交易时段（09:30-11:30, 13:00-15:00）',
        color: '#52c41a',
    },
    auction: {
        label: '集合竞价',
        description: '开盘/收盘集合竞价（09:15-09:25, 14:57-15:00）',
        color: '#1890ff',
    },
    no_trade: {
        label: '非交易时段',
        description: '交易日但非交易时间',
        color: '#faad14',
    },
    off_day: {
        label: '休市日',
        description: '周末及节假日',
        color: '#8c8c8c',
    },
}

// 轮询间隔预设值
const INTERVAL_PRESETS = [
    { value: 1, label: '1秒' },
    { value: 2, label: '2秒' },
    { value: 5, label: '5秒' },
    { value: 10, label: '10秒' },
    { value: 30, label: '30秒' },
    { value: 45, label: '45秒' },
    { value: 60, label: '1分钟' },
    { value: 120, label: '2分钟' },
]

// 日历数据源选项
const CALENDAR_SOURCE_OPTIONS = [
    { value: 'amazingdata', label: 'AmazingData', description: '支持更多市场：A股、期货、港股' },
    { value: 'miniqmt', label: 'MiniQMT', description: '本地 QMT 客户端：A股' },
    { value: 'auto', label: '自动选择', description: '优先 AmazingData，回退 MiniQMT' },
]

// 市场代码选项
const MARKET_OPTIONS = [
    { value: 'SH', label: '上交所 (SH)' },
    { value: 'SZ', label: '深交所 (SZ)' },
    { value: 'BJ', label: '北交所 (BJ)' },
    { value: 'HK', label: '港交所 (HK)' },
    { value: 'SHF', label: '上期所 (SHF)' },
    { value: 'CFE', label: '中金所 (CFE)' },
    { value: 'DCE', label: '大商所 (DCE)' },
    { value: 'CZC', label: '郑商所 (CZC)' },
]

interface PhaseConfigCardProps {
    phase: string
    config: PhaseBehavior
    onChange: (phase: string, updates: Partial<PhaseBehavior>) => void
}

/**
 * 阶段配置卡片
 */
const PhaseConfigCard: React.FC<PhaseConfigCardProps> = ({ phase, config, onChange }) => {
    const meta = PHASE_META[phase] || { label: phase, description: '', color: '#1890ff' }

    const handleIntervalChange = (value: number | null) => {
        if (value !== null) {
            onChange(phase, { interval_seconds: value })
        }
    }

    const handleTimeoutChange = (value: number | null) => {
        if (value !== null) {
            onChange(phase, { timeout_seconds: value })
        }
    }

    const handleSkipChange = (checked: boolean) => {
        onChange(phase, { skip_polling: checked })
    }

    return (
        <Card
            size="small"
            title={
                <Space>
                    <span
                        style={{
                            display: 'inline-block',
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            backgroundColor: meta.color,
                        }}
                    />
                    <span>{meta.label}</span>
                    <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
                        {meta.description}
                    </Text>
                </Space>
            }
            extra={
                <Space size="small">
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        跳过轮询
                    </Text>
                    <Switch
                        size="small"
                        checked={config.skip_polling}
                        onChange={handleSkipChange}
                    />
                </Space>
            }
            style={{ marginBottom: 16 }}
        >
            <Row gutter={[16, 12]}>
                {/* 轮询间隔 */}
                <Col span={12}>
                    <div style={{ marginBottom: 4 }}>
                        <Text strong style={{ fontSize: 12 }}>轮询间隔</Text>
                        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                            每隔多久获取一次数据
                        </Text>
                    </div>
                    <Row gutter={8} align="middle">
                        <Col span={16}>
                            <Slider
                                min={1}
                                max={300}
                                value={config.interval_seconds}
                                onChange={handleIntervalChange}
                                disabled={config.skip_polling}
                                marks={{
                                    1: '1s',
                                    60: '1m',
                                    300: '5m',
                                }}
                            />
                        </Col>
                        <Col span={8}>
                            <InputNumber
                                min={1}
                                max={600}
                                value={config.interval_seconds}
                                onChange={handleIntervalChange}
                                disabled={config.skip_polling}
                                addonAfter="秒"
                                size="small"
                                style={{ width: '100%' }}
                            />
                        </Col>
                    </Row>
                </Col>
                {/* 超时时间 */}
                <Col span={12}>
                    <div style={{ marginBottom: 4 }}>
                        <Text strong style={{ fontSize: 12 }}>超时时间</Text>
                        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                            超过此时间视为超时
                        </Text>
                    </div>
                    <Row gutter={8} align="middle">
                        <Col span={16}>
                            <Slider
                                min={1}
                                max={30}
                                value={config.timeout_seconds}
                                onChange={handleTimeoutChange}
                                disabled={config.skip_polling}
                                marks={{
                                    3: '3s',
                                    10: '10s',
                                    30: '30s',
                                }}
                            />
                        </Col>
                        <Col span={8}>
                            <InputNumber
                                min={1}
                                max={60}
                                value={config.timeout_seconds}
                                onChange={handleTimeoutChange}
                                disabled={config.skip_polling}
                                addonAfter="秒"
                                size="small"
                                style={{ width: '100%' }}
                            />
                        </Col>
                    </Row>
                </Col>
            </Row>
        </Card>
    )
}

/**
 * 轮询配置主组件
 */
const PollingConfig: React.FC = () => {
    const { message } = AntApp.useApp()
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [config, setConfig] = useState<PollingConfigType | null>(null)
    const [hasChanges, setHasChanges] = useState(false)

    // 加载配置
    const loadConfig = useCallback(async () => {
        setLoading(true)
        try {
            const response = await getPollingConfig()
            if (response.success) {
                setConfig(response.config)
                setHasChanges(false)
            } else {
                message.error('加载轮询配置失败')
            }
        } catch (error) {
            message.error('加载轮询配置失败: ' + (error instanceof Error ? error.message : String(error)))
        } finally {
            setLoading(false)
        }
    }, [message])

    useEffect(() => {
        loadConfig()
    }, [loadConfig])

    // 更新阶段配置
    const handlePhaseChange = useCallback((phase: string, updates: Partial<PhaseBehavior>) => {
        setConfig(prev => {
            if (!prev) return prev
            const currentPhase = prev.defaults[phase as keyof typeof prev.defaults] || {
                interval_seconds: 1,
                timeout_seconds: 3,
                skip_polling: false,
            }
            return {
                ...prev,
                defaults: {
                    ...prev.defaults,
                    [phase]: {
                        ...currentPhase,
                        ...updates,
                    },
                },
            }
        })
        setHasChanges(true)
    }, [])

    // 保存配置
    const handleSave = useCallback(async () => {
        if (!config) return

        setSaving(true)
        try {
            const payload: PollingConfigUpdate = {
                defaults: {},
                session_guard: config.session_guard ? {
                    enabled: config.session_guard.enabled,
                    calendar_source: config.session_guard.calendar_source,
                    market: config.session_guard.market,
                } : undefined,
            }

            // 构建更新 payload
            for (const phase of Object.keys(PHASE_META)) {
                const phaseConfig = config.defaults[phase as keyof typeof config.defaults]
                if (phaseConfig) {
                    payload.defaults![phase as keyof typeof payload.defaults] = {
                        interval_seconds: phaseConfig.interval_seconds,
                        timeout_seconds: phaseConfig.timeout_seconds,
                        skip_polling: phaseConfig.skip_polling,
                    }
                }
            }

            const response = await updatePollingConfig(payload)
            if (response.success) {
                message.success('轮询配置已保存并热重载')
                setConfig(response.config)
                setHasChanges(false)
            } else {
                message.error('保存失败: ' + (response.message || '未知错误'))
            }
        } catch (error) {
            message.error('保存失败: ' + (error instanceof Error ? error.message : String(error)))
        } finally {
            setSaving(false)
        }
    }, [config, message])

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>加载轮询配置...</div>
            </div>
        )
    }

    if (!config) {
        return (
            <Alert
                type="error"
                message="无法加载轮询配置"
                action={
                    <Button size="small" onClick={loadConfig}>
                        重试
                    </Button>
                }
            />
        )
    }

    return (
        <div>
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space>
                    <ClockCircleOutlined style={{ fontSize: 18 }} />
                    <Title level={5} style={{ margin: 0 }}>轮询时间配置</Title>
                </Space>
                <Space>
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={loadConfig}
                        loading={loading}
                    >
                        刷新
                    </Button>
                    <Button
                        type="primary"
                        icon={<SaveOutlined />}
                        onClick={handleSave}
                        loading={saving}
                        disabled={!hasChanges}
                    >
                        保存并热重载
                    </Button>
                </Space>
            </div>

            {hasChanges && (
                <Alert
                    type="warning"
                    message="配置已修改，请点击保存按钮使更改生效"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
            )}

            <Alert
                type="info"
                message="配置说明"
                description="调整各交易阶段的轮询间隔时间。启用「跳过轮询」后，该阶段将不会获取实时数据。修改后需点击「保存并热重载」按钮使配置生效。"
                showIcon
                style={{ marginBottom: 16 }}
                icon={<ThunderboltOutlined />}
            />

            {/* 交易阶段判断配置 */}
            <Card
                size="small"
                title={
                    <Space>
                        <span
                            style={{
                                display: 'inline-block',
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                backgroundColor: config.session_guard?.enabled ? '#52c41a' : '#8c8c8c',
                            }}
                        />
                        <span>交易阶段判断</span>
                        <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
                            根据交易日历智能调整轮询行为
                        </Text>
                    </Space>
                }
                extra={
                    <Space size="small">
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            启用
                        </Text>
                        <Switch
                            size="small"
                            checked={config.session_guard?.enabled ?? true}
                            onChange={(checked) => {
                                setConfig(prev => {
                                    if (!prev) return prev
                                    return {
                                        ...prev,
                                        session_guard: {
                                            ...prev.session_guard,
                                            enabled: checked,
                                        },
                                    }
                                })
                                setHasChanges(true)
                            }}
                        />
                    </Space>
                }
                style={{ marginBottom: 16 }}
            >
                <Row gutter={[16, 12]}>
                    <Col span={12}>
                        <div style={{ marginBottom: 4 }}>
                            <Text strong style={{ fontSize: 12 }}>日历数据源</Text>
                            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                                获取交易日历的接口
                            </Text>
                        </div>
                        <Radio.Group
                            value={config.session_guard?.calendar_source ?? 'amazingdata'}
                            onChange={(e) => {
                                setConfig(prev => {
                                    if (!prev) return prev
                                    return {
                                        ...prev,
                                        session_guard: {
                                            ...prev.session_guard,
                                            calendar_source: e.target.value,
                                        },
                                    }
                                })
                                setHasChanges(true)
                            }}
                            disabled={!config.session_guard?.enabled}
                        >
                            {CALENDAR_SOURCE_OPTIONS.map(opt => (
                                <Radio key={opt.value} value={opt.value} style={{ display: 'block', marginBottom: 4 }}>
                                    <Space>
                                        <span>{opt.label}</span>
                                        <Text type="secondary" style={{ fontSize: 11 }}>{opt.description}</Text>
                                    </Space>
                                </Radio>
                            ))}
                        </Radio.Group>
                    </Col>
                    <Col span={12}>
                        <div style={{ marginBottom: 4 }}>
                            <Text strong style={{ fontSize: 12 }}>市场代码</Text>
                            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                                选择交易市场
                            </Text>
                        </div>
                        <Select
                            value={config.session_guard?.market ?? 'SH'}
                            onChange={(value) => {
                                setConfig(prev => {
                                    if (!prev) return prev
                                    return {
                                        ...prev,
                                        session_guard: {
                                            ...prev.session_guard,
                                            market: value,
                                        },
                                    }
                                })
                                setHasChanges(true)
                            }}
                            disabled={!config.session_guard?.enabled}
                            style={{ width: '100%' }}
                            options={MARKET_OPTIONS}
                        />
                    </Col>
                </Row>
            </Card>


            {Object.keys(PHASE_META).map(phase => {
                const phaseConfig = config.defaults[phase as keyof typeof config.defaults]
                if (!phaseConfig) return null
                return (
                    <PhaseConfigCard
                        key={phase}
                        phase={phase}
                        config={phaseConfig}
                        onChange={handlePhaseChange}
                    />
                )
            })}
        </div>
    )
}

export default PollingConfig
