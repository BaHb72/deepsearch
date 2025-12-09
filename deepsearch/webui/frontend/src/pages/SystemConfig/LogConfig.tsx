// @ts-nocheck
import React from 'react'
import {Button, Card, Col, Divider, Form, Input, InputNumber, message, Row, Space, Spin, Switch, Typography} from 'antd'
import {ApartmentOutlined, FolderOpenOutlined, ReloadOutlined, SaveOutlined} from '@ant-design/icons'

import systemAPI from '@/api/system'
import type {LogSettings} from '@/types/systemConfig'

const {Paragraph} = Typography

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

const normalizePayload = (values: LogSettings): LogSettings => {
    const archive = {
        ...values.archive,
        purge_after_days:
            values.archive?.purge_after_days === undefined ||
            values.archive?.purge_after_days === null ||
            values.archive?.purge_after_days === ''
                ? null
                : values.archive?.purge_after_days
    }

    const modules = {
        ...values.modules,
        rotation: values.modules?.rotation ?? null,
        retention_days:
            values.modules?.retention_days === undefined ||
            values.modules?.retention_days === null ||
            values.modules?.retention_days === ''
                ? null
                : values.modules?.retention_days
    }

    return {
        ...values,
        archive,
        modules
    }
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
            <Card
                title="日志与归档配置"
                bordered={false}
                extra={
                    <Space>
                        <Button
                            icon={<ReloadOutlined/>}
                            onClick={loadConfig}
                            disabled={saving}
                        >
                            重新加载
                        </Button>
                        <Button
                            type="primary"
                            icon={<SaveOutlined/>}
                            onClick={handleSubmit}
                            loading={saving}
                        >
                            保存配置
                        </Button>
                    </Space>
                }
            >
                <Paragraph>
                    配置系统日志的保存策略、归档行为以及按模块拆分的日志输出目录。修改后会实时刷新运行时日志系统，无需重启。
                </Paragraph>

                <Form
                    form={form}
                    layout="vertical"
                    initialValues={DEFAULT_LOG_CONFIG}
                >
                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={8}>
                            <Form.Item
                                label="日志级别"
                                name="level"
                                rules={[{required: true, message: '请选择日志级别'}]}
                            >
                                <Input placeholder="INFO / DEBUG / WARNING / ERROR"/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={8}>
                            <Form.Item
                                label="每日轮转时间 (HH:MM)"
                                name="rotation"
                                tooltip="每天在指定时间切换日志文件"
                                rules={[
                                    {required: true, message: '请输入轮转时间，例如 00:00'}
                                ]}
                            >
                                <Input placeholder="00:00"/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={8}>
                            <Form.Item
                                label="原始日志保留天数"
                                name="retention_days"
                                rules={[{required: true, message: '请输入保留天数'}]}
                            >
                                <InputNumber min={1} precision={0} style={{width: '100%'}}/>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={8}>
                            <Form.Item
                                label="启用 JSON 日志输出"
                                name="enable_json"
                                valuePropName="checked"
                            >
                                <Switch/>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Divider orientation="left">
                        <Space>
                            <FolderOpenOutlined/>
                            归档策略
                        </Space>
                    </Divider>

                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="启用归档"
                                name={['archive', 'enabled']}
                                valuePropName="checked"
                            >
                                <Switch/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="归档目录"
                                name={['archive', 'directory']}
                                rules={[{required: true, message: '请输入归档目录'}]}
                            >
                                <Input disabled={!archiveEnabled} placeholder="archive"/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="压缩格式"
                                name={['archive', 'format']}
                                rules={[{required: true, message: '请输入压缩格式'}]}
                            >
                                <Input disabled placeholder="zip"/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="归档阈值 (天)"
                                name={['archive', 'archive_after_days']}
                                rules={[{required: true, message: '请输入归档天数'}]}
                            >
                                <InputNumber
                                    min={1}
                                    precision={0}
                                    disabled={!archiveEnabled}
                                    style={{width: '100%'}}
                                />
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="归档清理阈值 (天, 可选)"
                                name={['archive', 'purge_after_days']}
                            >
                                <InputNumber
                                    min={1}
                                    precision={0}
                                    disabled={!archiveEnabled}
                                    style={{width: '100%'}}
                                />
                            </Form.Item>
                        </Col>
                    </Row>

                    <Paragraph type="secondary">
                        启用归档后，系统会在日志超出“归档阈值”天数时自动压缩为 ZIP 文件，并根据“归档清理阈值”清理较旧的压缩包。
                    </Paragraph>

                    <Divider orientation="left">
                        <Space>
                            <ApartmentOutlined/>
                            模块化日志
                        </Space>
                    </Divider>

                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="启用按模块拆分"
                                name={['modules', 'enabled']}
                                valuePropName="checked"
                            >
                                <Switch/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="模块日志目录"
                                name={['modules', 'directory']}
                                rules={[{required: true, message: '请输入目录名称'}]}
                            >
                                <Input disabled={!modulesEnabled} placeholder="modules"/>
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="模块层级深度"
                                name={['modules', 'max_depth']}
                                rules={[{required: true, message: '请输入层级深度'}]}
                            >
                                <InputNumber
                                    min={1}
                                    precision={0}
                                    disabled={!modulesEnabled}
                                    style={{width: '100%'}}
                                />
                            </Form.Item>
                        </Col>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="模块日志轮转时间"
                                name={['modules', 'rotation']}
                            >
                                <Input
                                    disabled={!modulesEnabled}
                                    placeholder="继承主配置，例：00:00"
                                />
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={24}>
                        <Col xs={24} sm={12} md={6}>
                            <Form.Item
                                label="模块日志保留天数"
                                name={['modules', 'retention_days']}
                            >
                                <InputNumber
                                    min={1}
                                    precision={0}
                                    disabled={!modulesEnabled}
                                    style={{width: '100%'}}
                                />
                            </Form.Item>
                        </Col>
                    </Row>

                    <Paragraph type="secondary">
                        开启后将根据 Logger 名称自动创建子目录（受“模块层级深度”限制），便于定位不同子系统的日志。
                    </Paragraph>
                </Form>
            </Card>
        </Spin>
    )
}

export default LogConfig

