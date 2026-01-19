import React from 'react'
import {
    Button,
    Card,
    Col,
    Form,
    InputNumber,
    message,
    Row,
    Select,
    Slider,
    Space,
    Spin,
    Switch,
    TimePicker,
    Typography
} from 'antd'
import {
    ApartmentOutlined,
    ClockCircleOutlined,
    FileZipOutlined,
    ReloadOutlined,
    SaveOutlined,
    SettingOutlined
} from '@ant-design/icons'
import dayjs from 'dayjs'

import systemAPI from '@/api/system'
import type { LogSettings } from '@/types/systemConfig'

const { Text, Title } = Typography

const DEFAULT_LOG_CONFIG: LogSettings = {
    level: 'INFO',
    rotation: '00:00',
    retention_days: 7,
    enable_json: false,
    archive: {
        enabled: true,
        format: 'zip',
        directory: 'archive',
        archive_after_days: 7,
        purge_after_days: null
    },
    modules: {
        enabled: false,
        directory: 'modules',
        max_depth: 2,
        rotation: '00:00',
        retention_days: null
    }
}

const LOG_LEVELS = [
    { value: 'DEBUG', label: 'DEBUG', color: '#8c8c8c' },
    { value: 'INFO', label: 'INFO', color: '#1890ff' },
    { value: 'WARNING', label: 'WARNING', color: '#faad14' },
    { value: 'ERROR', label: 'ERROR', color: '#ff4d4f' },
    { value: 'CRITICAL', label: 'CRITICAL', color: '#cf1322' }
]

const RETENTION_MARKS: Record<number, string> = {
    1: '1天',
    7: '7天',
    14: '14天',
    30: '30天',
    60: '60天',
    90: '90天'
}

const normalizePayload = (values: LogSettings): LogSettings => {
    const archive = {
        ...values.archive,
        purge_after_days:
            values.archive?.purge_after_days === undefined ||
                values.archive?.purge_after_days === null
                ? null
                : values.archive?.purge_after_days
    }

    const modules = {
        ...values.modules,
        rotation: values.modules?.rotation ?? null,
        retention_days:
            values.modules?.retention_days === undefined ||
                values.modules?.retention_days === null
                ? null
                : values.modules?.retention_days
    }

    return {
        ...values,
        archive,
        modules
    }
}

const cardStyle: React.CSSProperties = {
    borderRadius: 12,
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
    marginBottom: 16
}

const cardHeadStyle: React.CSSProperties = {
    borderBottom: 'none',
    paddingBottom: 0
}

const LogConfig: React.FC = () => {
    const [form] = Form.useForm<LogSettings>()
    const [loading, setLoading] = React.useState<boolean>(true)
    const [saving, setSaving] = React.useState<boolean>(false)

    const archiveEnabled = Form.useWatch(['archive', 'enabled'], form)
    const modulesEnabled = Form.useWatch(['modules', 'enabled'], form)

    const loadConfig = React.useCallback(async () => {
        setLoading(true)
        try {
            const response = await systemAPI.getLogConfig()
            const payload = {
                ...DEFAULT_LOG_CONFIG,
                ...(response ?? {}),
                archive: {
                    ...DEFAULT_LOG_CONFIG.archive,
                    ...(response?.archive ?? {})
                },
                modules: {
                    ...DEFAULT_LOG_CONFIG.modules,
                    ...(response?.modules ?? {})
                }
            }
            form.setFieldsValue(payload)
        } catch (error: any) {
            console.error('[LogConfig] 获取日志配置失败', error)
            message.error(error?.message ?? '获取日志配置失败')
        } finally {
            setLoading(false)
        }
    }, [form])

    React.useEffect(() => {
        loadConfig()
    }, [loadConfig])

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields()
            const payload = normalizePayload(values)
            setSaving(true)
            const response = await systemAPI.updateLogConfig(payload)
            const msg =
                response?.message ??
                (response?.success ? '日志配置已保存' : undefined) ??
                '日志配置已更新'
            message.success(msg)
            form.setFieldsValue(normalizePayload(payload))
        } catch (error: any) {
            if (error?.errorFields) {
                return
            }
            console.error('[LogConfig] 保存日志配置失败', error)
            message.error(error?.message ?? '保存日志配置失败')
        } finally {
            setSaving(false)
        }
    }

    return (
        <Spin spinning={loading}>
            <div style={{ padding: '0 0 24px 0' }}>
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 24
                }}>
                    <div>
                        <Title level={4} style={{ margin: 0 }}>日志配置</Title>
                        <Text type="secondary">配置系统日志保存策略、归档行为和模块化输出</Text>
                    </div>
                    <Space>
                        <Button
                            icon={<ReloadOutlined />}
                            onClick={loadConfig}
                            disabled={saving}
                        >
                            刷新
                        </Button>
                        <Button
                            type="primary"
                            icon={<SaveOutlined />}
                            onClick={handleSubmit}
                            loading={saving}
                        >
                            保存配置
                        </Button>
                    </Space>
                </div>

                <Form
                    form={form}
                    layout="vertical"
                    initialValues={DEFAULT_LOG_CONFIG}
                >
                    {/* Card 1: 基础配置 */}
                    <Card
                        style={cardStyle}
                        headStyle={cardHeadStyle}
                        title={
                            <Space>
                                <SettingOutlined style={{ color: '#1890ff' }} />
                                <span>基础配置</span>
                            </Space>
                        }
                    >
                        <Row gutter={[24, 16]}>
                            <Col xs={24} sm={12} md={6}>
                                <Form.Item
                                    label="日志级别"
                                    name="level"
                                    rules={[{ required: true, message: '请选择日志级别' }]}
                                >
                                    <Select
                                        options={LOG_LEVELS.map(level => ({
                                            value: level.value,
                                            label: (
                                                <Space>
                                                    <span style={{
                                                        display: 'inline-block',
                                                        width: 8,
                                                        height: 8,
                                                        borderRadius: '50%',
                                                        backgroundColor: level.color
                                                    }} />
                                                    {level.label}
                                                </Space>
                                            )
                                        }))}
                                    />
                                </Form.Item>
                            </Col>
                            <Col xs={24} sm={12} md={6}>
                                <Form.Item
                                    label="每日轮转时间"
                                    name="rotation"
                                    rules={[{ required: true, message: '请选择轮转时间' }]}
                                    getValueProps={(value) => ({
                                        value: value ? dayjs(value, 'HH:mm') : undefined
                                    })}
                                    getValueFromEvent={(time) => time?.format('HH:mm') ?? '00:00'}
                                >
                                    <TimePicker
                                        format="HH:mm"
                                        style={{ width: '100%' }}
                                        placeholder="选择时间"
                                        suffixIcon={<ClockCircleOutlined />}
                                    />
                                </Form.Item>
                            </Col>
                            <Col xs={24} sm={12} md={6}>
                                <Form.Item
                                    label="启用 JSON 格式"
                                    name="enable_json"
                                    valuePropName="checked"
                                >
                                    <Switch checkedChildren="开" unCheckedChildren="关" />
                                </Form.Item>
                            </Col>
                        </Row>

                        <Form.Item
                            label="日志保留天数"
                            name="retention_days"
                            rules={[{ required: true, message: '请选择保留天数' }]}
                            style={{ marginBottom: 0, marginTop: 8 }}
                        >
                            <Slider
                                min={1}
                                max={90}
                                marks={RETENTION_MARKS}
                                tooltip={{ formatter: (value) => `${value} 天` }}
                            />
                        </Form.Item>
                    </Card>

                    {/* Card 2: 归档策略 */}
                    <Card
                        style={{
                            ...cardStyle,
                            opacity: archiveEnabled ? 1 : 0.85,
                            transition: 'opacity 0.3s'
                        }}
                        headStyle={cardHeadStyle}
                        title={
                            <Space>
                                <FileZipOutlined style={{ color: archiveEnabled ? '#52c41a' : '#8c8c8c' }} />
                                <span>归档策略</span>
                            </Space>
                        }
                        extra={
                            <Form.Item
                                name={['archive', 'enabled']}
                                valuePropName="checked"
                                style={{ marginBottom: 0 }}
                            >
                                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                            </Form.Item>
                        }
                    >
                        <div style={{
                            opacity: archiveEnabled ? 1 : 0.5,
                            pointerEvents: archiveEnabled ? 'auto' : 'none',
                            transition: 'opacity 0.3s'
                        }}>
                            <Row gutter={[24, 16]}>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="归档阈值"
                                        name={['archive', 'archive_after_days']}
                                        rules={[{ required: true, message: '请输入归档天数' }]}
                                    >
                                        <InputNumber
                                            min={1}
                                            max={365}
                                            precision={0}
                                            style={{ width: '100%' }}
                                            addonAfter="天后归档"
                                        />
                                    </Form.Item>
                                </Col>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="清理阈值"
                                        name={['archive', 'purge_after_days']}
                                        tooltip="留空则永不自动清理"
                                    >
                                        <InputNumber
                                            min={1}
                                            max={365}
                                            precision={0}
                                            style={{ width: '100%' }}
                                            addonAfter="天后清理"
                                            placeholder="可选"
                                        />
                                    </Form.Item>
                                </Col>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="压缩格式"
                                        name={['archive', 'format']}
                                    >
                                        <Select
                                            options={[
                                                { value: 'zip', label: 'ZIP' },
                                                { value: 'gz', label: 'GZIP' },
                                                { value: 'tar.gz', label: 'TAR.GZ' }
                                            ]}
                                        />
                                    </Form.Item>
                                </Col>
                            </Row>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                日志超出归档阈值后自动压缩，超出清理阈值后删除旧归档文件
                            </Text>
                        </div>
                    </Card>

                    {/* Card 3: 模块化日志 */}
                    <Card
                        style={{
                            ...cardStyle,
                            opacity: modulesEnabled ? 1 : 0.85,
                            transition: 'opacity 0.3s',
                            marginBottom: 0
                        }}
                        headStyle={cardHeadStyle}
                        title={
                            <Space>
                                <ApartmentOutlined style={{ color: modulesEnabled ? '#722ed1' : '#8c8c8c' }} />
                                <span>模块化日志</span>
                            </Space>
                        }
                        extra={
                            <Form.Item
                                name={['modules', 'enabled']}
                                valuePropName="checked"
                                style={{ marginBottom: 0 }}
                            >
                                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                            </Form.Item>
                        }
                    >
                        <div style={{
                            opacity: modulesEnabled ? 1 : 0.5,
                            pointerEvents: modulesEnabled ? 'auto' : 'none',
                            transition: 'opacity 0.3s'
                        }}>
                            <Row gutter={[24, 16]}>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="模块层级深度"
                                        name={['modules', 'max_depth']}
                                        rules={[{ required: true, message: '请输入层级深度' }]}
                                        tooltip="根据 Logger 名称的点号分隔层级"
                                    >
                                        <InputNumber
                                            min={1}
                                            max={5}
                                            precision={0}
                                            style={{ width: '100%' }}
                                        />
                                    </Form.Item>
                                </Col>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="模块日志保留天数"
                                        name={['modules', 'retention_days']}
                                        tooltip="留空则继承主配置"
                                    >
                                        <InputNumber
                                            min={1}
                                            max={365}
                                            precision={0}
                                            style={{ width: '100%' }}
                                            placeholder="继承主配置"
                                        />
                                    </Form.Item>
                                </Col>
                                <Col xs={24} sm={12} md={6}>
                                    <Form.Item
                                        label="模块轮转时间"
                                        name={['modules', 'rotation']}
                                        tooltip="留空则继承主配置"
                                        getValueProps={(value) => ({
                                            value: value ? dayjs(value, 'HH:mm') : undefined
                                        })}
                                        getValueFromEvent={(time) => time?.format('HH:mm') ?? null}
                                    >
                                        <TimePicker
                                            format="HH:mm"
                                            style={{ width: '100%' }}
                                            placeholder="继承主配置"
                                            allowClear
                                        />
                                    </Form.Item>
                                </Col>
                            </Row>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                开启后根据 Logger 名称自动创建子目录，便于定位不同子系统的日志输出
                            </Text>
                        </div>
                    </Card>
                </Form>
            </div>
        </Spin>
    )
}

export default LogConfig
