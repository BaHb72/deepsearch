import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography
} from 'antd'
import { DeleteOutlined, ExperimentOutlined, PlusOutlined, ReloadOutlined, SendOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  fetchNotificationConfig,
  fetchNotificationQuotas,
  NotificationCategoryConfigItem,
  NotificationChannel,
  NotificationConfigUpdatePayload,
  NotificationSendResult,
  resetNotificationQuotas,
  sendNotification,
  updateNotificationConfig
} from '@/api/notifications'

const channelOptions: { label: string; value: NotificationChannel }[] = [
  { label: '微信', value: 'wechat' },
  { label: 'Bark', value: 'bark' }
]

interface NotificationFormValues {
  enabled: boolean
  defaultChannel: NotificationChannel
  wechatToken: string
  barkToken: string
  requestTimeout: number
  retryAttempts: number
  retryDelay: number
  baseUrls: {
    wechat: string
    bark: string
  }
  categories: NotificationCategoryConfigItem[]
}

interface QuotaRow {
  key: string
  category: string
  channel: NotificationChannel
  current: number
  max?: number | null
  remaining?: number | null
  windowSeconds?: number
  resetSeconds?: number
}

interface TestFormValues {
  title: string
  content?: string
  channel?: NotificationChannel
  category?: string
  bypassQuota: boolean
}

const getDefaultCategory = (): NotificationCategoryConfigItem => ({
  name: 'alert',
  enabled: true,
  maxPerWindow: 5,
  windowSeconds: 300,
  channels: ['wechat']
})

const NotificationConfig: React.FC = () => {
  const [form] = Form.useForm<NotificationFormValues>()
  const [testForm] = Form.useForm<TestFormValues>()
  const { message } = AntApp.useApp()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [quotaLoading, setQuotaLoading] = useState(false)
  const [testVisible, setTestVisible] = useState(false)
  const [quotas, setQuotas] = useState<QuotaRow[]>([])
  const [hasWechatToken, setHasWechatToken] = useState(false)
  const [hasBarkToken, setHasBarkToken] = useState(false)
  const [lastTestResult, setLastTestResult] = useState<NotificationSendResult | null>(null)

  const quotaColumns: ColumnsType<QuotaRow> = useMemo(() => [
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category'
    },
    {
      title: '渠道',
      dataIndex: 'channel',
      key: 'channel',
      render: (value: NotificationChannel) => value === 'wechat' ? '微信' : 'Bark'
    },
    {
      title: '已发送',
      dataIndex: 'current',
      key: 'current'
    },
    {
      title: '额度',
      dataIndex: 'max',
      key: 'max',
      render: (value?: number | null) => value ?? '不限'
    },
    {
      title: '剩余',
      dataIndex: 'remaining',
      key: 'remaining',
      render: (value?: number | null) => value ?? '—'
    },
    {
      title: '窗口(秒)',
      dataIndex: 'windowSeconds',
      key: 'windowSeconds'
    },
    {
      title: '重置倒计时',
      dataIndex: 'resetSeconds',
      key: 'resetSeconds',
      render: (value?: number) => {
        if (value === undefined || value === null) {
          return '—'
        }
        if (value <= 0) {
          return <Tag color="blue">可立即发送</Tag>
        }
        return `${value} 秒`
      }
    }
  ], [])

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      const config = await fetchNotificationConfig()
      setHasWechatToken(config.hasWechatToken)
      setHasBarkToken(config.hasBarkToken)
      const categories = (config.categories || []).map(item => ({
        ...item,
        channels: (item.channels || []) as NotificationChannel[]
      }))

      form.setFieldsValue({
        enabled: config.enabled,
        defaultChannel: config.defaultChannel,
        wechatToken: config.hasWechatToken ? (config.wechatToken || '***') : '',
        barkToken: config.hasBarkToken ? (config.barkToken || '***') : '',
        requestTimeout: config.requestTimeout,
        retryAttempts: config.retryAttempts,
        retryDelay: config.retryDelay,
        baseUrls: {
          wechat: config.baseUrls.wechat,
          bark: config.baseUrls.bark
        },
        categories: categories.length > 0 ? categories : [getDefaultCategory()]
      })
    } catch (error) {
      message.error('获取通知配置失败')
      console.error('[NotificationConfig] loadConfig error', error)
    } finally {
      setLoading(false)
    }
  }, [form, message])

  const transformQuotas = useCallback((data: Record<string, Record<string, any>>): QuotaRow[] => {
    const rows: QuotaRow[] = []
    Object.entries(data || {}).forEach(([category, channelMap]) => {
      Object.entries(channelMap || {}).forEach(([channel, info]) => {
        rows.push({
          key: `${category}-${channel}`,
          category,
          channel: channel as NotificationChannel,
          current: info?.current ?? 0,
          max: info?.max_per_window ?? null,
          remaining: info?.remaining ?? null,
          windowSeconds: info?.window_seconds,
          resetSeconds: info?.reset_seconds
        })
      })
    })
    return rows.sort((a, b) => a.category.localeCompare(b.category) || a.channel.localeCompare(b.channel))
  }, [])

  const loadQuotas = useCallback(async () => {
    setQuotaLoading(true)
    try {
      const response = await fetchNotificationQuotas()
      if (response.success) {
        setQuotas(transformQuotas(response.data ?? {}))
      } else {
        setQuotas([])
      }
    } catch (error) {
      console.warn('[NotificationConfig] loadQuotas error', error)
      setQuotas([])
    } finally {
      setQuotaLoading(false)
    }
  }, [transformQuotas])

  useEffect(() => {
    loadConfig()
    loadQuotas()
  }, [loadConfig, loadQuotas])

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const categories = values.categories && values.categories.length > 0 ? values.categories : [getDefaultCategory()]

      const payload: NotificationConfigUpdatePayload = {
        enabled: values.enabled,
        defaultChannel: values.defaultChannel,
        wechatToken: values.wechatToken ?? '',
        barkToken: values.barkToken ?? '',
        requestTimeout: values.requestTimeout,
        retryAttempts: values.retryAttempts,
        retryDelay: values.retryDelay,
        baseUrls: values.baseUrls,
        categories: categories.map(item => ({
          name: item.name,
          enabled: item.enabled,
          maxPerWindow: item.maxPerWindow,
          windowSeconds: item.windowSeconds,
          channels: item.channels && item.channels.length ? item.channels : ['wechat']
        }))
      }

      const updated = await updateNotificationConfig(payload)
      setHasWechatToken(updated.hasWechatToken)
      setHasBarkToken(updated.hasBarkToken)
      form.setFieldsValue({
        enabled: updated.enabled,
        defaultChannel: updated.defaultChannel,
        wechatToken: updated.hasWechatToken ? (updated.wechatToken || '***') : '',
        barkToken: updated.hasBarkToken ? (updated.barkToken || '***') : '',
        requestTimeout: updated.requestTimeout,
        retryAttempts: updated.retryAttempts,
        retryDelay: updated.retryDelay,
        baseUrls: {
          wechat: updated.baseUrls.wechat,
          bark: updated.baseUrls.bark
        },
        categories: updated.categories
      })
      message.success('通知配置已保存')
    } catch (error) {
      if ((error as any)?.errorFields) {
        message.warning('请检查表单填写是否完整')
      } else {
        message.error('保存通知配置失败')
        console.error('[NotificationConfig] handleSave error', error)
      }
    } finally {
      setSaving(false)
    }
  }, [form, message])

  const handleResetQuotas = useCallback(async () => {
    try {
      setQuotaLoading(true)
      await resetNotificationQuotas()
      message.success('额度已重置')
      await loadQuotas()
    } catch (error) {
      message.error('重置额度失败')
      console.error('[NotificationConfig] handleResetQuotas error', error)
    } finally {
      setQuotaLoading(false)
    }
  }, [loadQuotas, message])

  const openTestModal = useCallback(() => {
    const values = form.getFieldsValue()
    testForm.setFieldsValue({
      title: 'DeepSearch 通知测试',
      content: '这是一条测试消息',
      channel: values.defaultChannel,
      category: values.categories?.[0]?.name || 'default',
      bypassQuota: true
    })
    setTestVisible(true)
  }, [form, testForm])

  const handleSendTest = useCallback(async () => {
    try {
      const values = await testForm.validateFields()
      const result = await sendNotification({
        title: values.title,
        content: values.content,
        channel: values.channel,
        category: values.category,
        bypass_quota: values.bypassQuota
      })
      setLastTestResult(result)
      message.success('测试消息已发送')
      setTestVisible(false)
      await loadQuotas()
    } catch (error) {
      if ((error as any)?.errorFields) {
        return
      }
      const detail = (error as any)?.response?.data?.detail
      if (detail && typeof detail === 'object') {
        message.error(detail.message || '发送失败')
      } else {
        message.error('发送测试消息失败')
      }
      console.error('[NotificationConfig] handleSendTest error', error)
    }
  }, [loadQuotas, message, testForm])

  const categoryInitial = useCallback(() => {
    const base = getDefaultCategory()
    return {
      ...base,
      name: `category_${Date.now()}`,
      channels: [...base.channels] as NotificationChannel[]
    }
  }, [])

  return (
    <Spin spinning={loading} tip="加载配置中...">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>

        <Card
          title="基础设置"
          extra={
            <Space size={12} wrap>
              <Tooltip title="重新加载通知配置">
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => loadConfig()}
                  loading={loading}
                />
              </Tooltip>
              <Tooltip title="发送测试消息">
                <Button type="primary" icon={<ExperimentOutlined />} onClick={openTestModal}>
                  发送测试
                </Button>
              </Tooltip>
              <Button type="primary" loading={saving} onClick={handleSave} icon={<SendOutlined />}>
                保存配置
              </Button>
            </Space>
          }
          styles={{ body: { padding: 24 } }}
        >
          <Form form={form} layout="vertical">
            <Space direction="vertical" size={24} style={{ width: '100%' }}>
              <Space size={16} wrap style={{ width: '100%' }}>
                <Form.Item
                  name="enabled"
                  label="启用通知"
                  valuePropName="checked"
                  colon={false}
                  style={{ minWidth: 220 }}
                >
                  <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
                <Form.Item
                  name="defaultChannel"
                  label="默认渠道"
                  rules={[{ required: true, message: '请选择默认渠道' }]}
                  style={{ flex: 1, minWidth: 220 }}
                >
                  <Select options={channelOptions} />
                </Form.Item>
              </Space>

              <Space size={16} wrap style={{ width: '100%' }}>
                <Form.Item
                  name="wechatToken"
                  label="微信推送 Token"
                  extra={hasWechatToken ? '使用 *** 可保留原 token' : undefined}
                  style={{ flex: 1, minWidth: 280 }}
                >
                  <Input placeholder="请输入虾推啥 Token" allowClear />
                </Form.Item>
                <Form.Item
                  name="barkToken"
                  label="Bark 推送 Token"
                  extra={hasBarkToken ? '使用 *** 可保留原 token' : '如与微信共用同一 token 可直接填写'}
                  style={{ flex: 1, minWidth: 280 }}
                >
                  <Input placeholder="请输入 Bark Token" allowClear />
                </Form.Item>
              </Space>

              <div>
                <Typography.Title level={5} style={{ marginBottom: 12 }}>
                  请求与重试
                </Typography.Title>
                <Space size={16} wrap style={{ width: '100%' }}>
                  <Form.Item
                    name="requestTimeout"
                    label="请求超时(秒)"
                    rules={[{ required: true, message: '请设置请求超时' }]}
                    style={{ minWidth: 200, flex: 1 }}
                  >
                    <InputNumber min={1} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item
                    name="retryAttempts"
                    label="重试次数"
                    rules={[{ required: true, message: '请设置重试次数' }]}
                    style={{ minWidth: 200, flex: 1 }}
                  >
                    <InputNumber min={0} style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item
                    name="retryDelay"
                    label="重试间隔(秒)"
                    rules={[{ required: true, message: '请设置重试间隔' }]}
                    style={{ minWidth: 200, flex: 1 }}
                  >
                    <InputNumber min={0} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                </Space>
              </div>

              <div>
                <Typography.Title level={5} style={{ marginBottom: 12 }}>
                  渠道地址
                </Typography.Title>
                <Space size={16} wrap style={{ width: '100%' }}>
                  <Form.Item
                    name={['baseUrls', 'wechat']}
                    label="微信接口地址"
                    rules={[{ required: true, message: '请输入微信接口地址' }]}
                    style={{ flex: 1, minWidth: 280 }}
                  >
                    <Input placeholder="https://wx.xtuis.cn" />
                  </Form.Item>
                  <Form.Item
                    name={['baseUrls', 'bark']}
                    label="Bark 接口地址"
                    rules={[{ required: true, message: '请输入 Bark 接口地址' }]}
                    style={{ flex: 1, minWidth: 280 }}
                  >
                    <Input placeholder="https://bark.xtuis.cn" />
                  </Form.Item>
                </Space>
              </div>

              <div>
                <Typography.Title level={5} style={{ marginBottom: 12 }}>
                  类别额度
                </Typography.Title>
                <Form.List name="categories">
                  {(fields, { add, remove }) => (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      {fields.map((field) => (
                        <Card
                          key={field.key}
                          size="small"
                          title={`类别：${form.getFieldValue(['categories', field.name, 'name']) || '未命名'}`}
                          extra={
                            fields.length > 1 && (
                              <Tooltip title="删除类别">
                                <Button
                                  danger
                                  icon={<DeleteOutlined />}
                                  size="small"
                                  onClick={() => remove(field.name)}
                                />
                              </Tooltip>
                            )
                          }
                        >
                          <Row gutter={16}>
                            <Col span={6}>
                              <Form.Item
                                {...field}
                                name={[field.name, 'name']}
                                label="类别名称"
                                rules={[{ required: true, message: '请输入类别名称' }]}
                              >
                                <Input placeholder="例如 alert" />
                              </Form.Item>
                            </Col>
                            <Col span={4}>
                              <Form.Item
                                {...field}
                                name={[field.name, 'enabled']}
                                label="启用"
                                valuePropName="checked"
                              >
                                <Switch />
                              </Form.Item>
                            </Col>
                            <Col span={6}>
                              <Form.Item
                                {...field}
                                name={[field.name, 'maxPerWindow']}
                                label="窗口内最大条数"
                                rules={[{ required: true, message: '请输入额度' }]}
                              >
                                <InputNumber min={0} style={{ width: '100%' }} />
                              </Form.Item>
                            </Col>
                            <Col span={8}>
                              <Form.Item
                                {...field}
                                name={[field.name, 'windowSeconds']}
                                label="窗口时长(秒)"
                                rules={[{ required: true, message: '请输入窗口时长' }]}
                              >
                                <InputNumber min={30} step={30} style={{ width: '100%' }} />
                              </Form.Item>
                            </Col>
                          </Row>
                          <Row gutter={16}>
                            <Col span={12}>
                              <Form.Item
                                {...field}
                                name={[field.name, 'channels']}
                                label="可用渠道"
                                rules={[{ required: true, message: '请选择渠道' }]}
                              >
                                <Select
                                  mode="multiple"
                                  options={channelOptions}
                                  placeholder="选择可用渠道"
                                />
                              </Form.Item>
                            </Col>
                          </Row>
                        </Card>
                      ))}
                      <Button
                        type="dashed"
                        onClick={() => add(categoryInitial())}
                        icon={<PlusOutlined />}
                        block
                      >
                        新增类别
                      </Button>
                    </Space>
                  )}
                </Form.List>
              </div>
            </Space>
          </Form>
        </Card>

        <Card
          title="额度状态"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} loading={quotaLoading} onClick={loadQuotas}>
                刷新
              </Button>
              <Button danger loading={quotaLoading} onClick={handleResetQuotas}>
                重置额度
              </Button>
            </Space>
          }
        >
          <Table
            rowKey="key"
            loading={quotaLoading}
            columns={quotaColumns}
            dataSource={quotas}
            pagination={false}
          />
        </Card>

        {lastTestResult && (
          <Card title="最近一次测试结果">
            <Space direction="vertical">
              <Typography.Text>
                状态：{lastTestResult.success ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>}
              </Typography.Text>
              <Typography.Text>
                渠道：{lastTestResult.channel === 'wechat' ? '微信' : 'Bark'}
              </Typography.Text>
              <Typography.Text>类别：{lastTestResult.category}</Typography.Text>
              {lastTestResult.status_code && (
                <Typography.Text>HTTP 状态：{lastTestResult.status_code}</Typography.Text>
              )}
            </Space>
          </Card>
        )}
      </Space>

      <Modal
        title="发送测试通知"
        open={testVisible}
        onCancel={() => setTestVisible(false)}
        onOk={handleSendTest}
        okText="发送"
        destroyOnClose
      >
        <Form form={testForm} layout="vertical">
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入测试标题' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="content" label="内容">
            <Input.TextArea rows={3} placeholder="请输入测试内容" />
          </Form.Item>
          <Form.Item name="channel" label="渠道">
            <Select allowClear options={channelOptions} placeholder="默认使用配置的默认渠道" />
          </Form.Item>
          <Form.Item name="category" label="类别">
            <Input placeholder="默认使用 default" />
          </Form.Item>
          <Form.Item name="bypassQuota" label="忽略额度限制" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  )
}

export default NotificationConfig

