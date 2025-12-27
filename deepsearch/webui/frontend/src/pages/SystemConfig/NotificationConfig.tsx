import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  App as AntApp,
  Button,
  Card,
  Checkbox,
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
  Tabs,
  Tag,
  Tooltip,
  Typography
} from 'antd'
import { DeleteOutlined, ExperimentOutlined, PlusOutlined, ReloadOutlined, SendOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  BarkMessageTemplate,
  BarkServer,
  fetchNotificationConfig,
  fetchNotificationQuotas,
  MessageTemplates,
  NotificationCategoryConfigItem,
  NotificationChannel,
  NotificationConfigUpdatePayload,
  NotificationSendResult,
  resetNotificationQuotas,
  sendNotification,
  updateNotificationConfig,
  WechatMessageTemplate,
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
  titleTemplate: string
  bodyTemplate: string
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
  const [barkServers, setBarkServers] = useState<BarkServer[]>([])
  const [selectedBarkServers, setSelectedBarkServers] = useState<string[]>([])  // 测试时选中的 Bark 服务器 (by name)
  const [lastTestResult, setLastTestResult] = useState<NotificationSendResult | null>(null)
  // 消息模板状态
  const [templates, setTemplates] = useState<MessageTemplates>({ wechat: [], bark: [], defaultWechat: undefined, defaultBark: undefined })
  const [barkTemplateModalVisible, setBarkTemplateModalVisible] = useState(false)
  const [editingBarkTemplate, setEditingBarkTemplate] = useState<BarkMessageTemplate | null>(null)
  const [barkTemplateForm] = Form.useForm()

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
        titleTemplate: config.titleTemplate || '',
        bodyTemplate: config.bodyTemplate || '',
        baseUrls: {
          wechat: config.baseUrls.wechat,
          bark: config.baseUrls.bark
        },
        categories: categories.length > 0 ? categories : [getDefaultCategory()]
      })
      // 设置 Bark 服务器列表
      setBarkServers(config.barkServers || [])
      // 设置消息模板
      setTemplates(config.templates || { wechat: [], bark: [], defaultWechat: undefined, defaultBark: undefined })
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
        enabled: values.enabled ?? false,
        defaultChannel: values.defaultChannel,
        wechatToken: values.wechatToken ?? '',
        barkToken: values.wechatToken ?? '',  // 虾推啥只需一个 Token，复用微信 Token
        barkServers: barkServers,  // 包含 Bark 服务器列表
        requestTimeout: values.requestTimeout ?? 5,
        retryAttempts: values.retryAttempts ?? 3,
        retryDelay: values.retryDelay ?? 1,
        titleTemplate: values.titleTemplate || 'DeepSearch: {title}',
        bodyTemplate: values.bodyTemplate || '{content}',
        baseUrls: {
          wechat: values.baseUrls?.wechat ?? 'https://wx.xtuis.cn',
          bark: values.baseUrls?.bark ?? 'https://bark.xtuis.cn'
        },
        categories: categories.map(item => ({
          name: item.name,
          enabled: item.enabled ?? true,
          maxPerWindow: item.maxPerWindow,
          windowSeconds: item.windowSeconds,
          channels: item.channels && item.channels.length ? item.channels : ['wechat']
        })),
        templates: templates,  // 保存消息模板
      }

      const updated = await updateNotificationConfig(payload)
      setHasWechatToken(updated.hasWechatToken)
      setHasBarkToken(updated.hasBarkToken)
      setBarkServers(updated.barkServers || [])  // 同步更新 Bark 服务器列表
      setTemplates(updated.templates || { wechat: [], bark: [], defaultWechat: undefined, defaultBark: undefined })  // 同步更新模板
      form.setFieldsValue({
        enabled: updated.enabled,
        defaultChannel: updated.defaultChannel,
        wechatToken: updated.hasWechatToken ? (updated.wechatToken || '***') : '',
        barkToken: updated.hasBarkToken ? (updated.barkToken || '***') : '',
        requestTimeout: updated.requestTimeout,
        retryAttempts: updated.retryAttempts,
        retryDelay: updated.retryDelay,
        titleTemplate: updated.titleTemplate || '',
        bodyTemplate: updated.bodyTemplate || '',
        baseUrls: {
          wechat: updated.baseUrls?.wechat || 'https://wx.xtuis.cn',
          bark: updated.baseUrls?.bark || 'https://bark.xtuis.cn'
        },
        categories: updated.categories || []
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
  }, [form, message, barkServers])

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
      // 支持多渠道：遍历发送
      const channels = values.channel && values.channel.length > 0 ? values.channel : [undefined]
      let lastResult: NotificationSendResult | null = null
      let successCount = 0
      let failCount = 0

      for (const ch of channels) {
        try {
          const result = await sendNotification({
            title: values.title,
            content: values.content,
            channel: ch,
            category: values.category,
            bypass_quota: values.bypassQuota,
            // 当渠道是 Bark 且有选中服务器时，传递服务器名称列表
            ...(ch === 'bark' && selectedBarkServers.length > 0 ? { barkServerNames: selectedBarkServers } : {}),
            // 当渠道是 Bark 且选择了模板时，传递模板名称
            ...(ch === 'bark' && values.barkTemplateName ? { barkTemplateName: values.barkTemplateName } : {}),
          })
          lastResult = result
          successCount++
        } catch (err) {
          failCount++
          console.error(`[NotificationConfig] 发送到渠道 ${ch} 失败`, err)
        }
      }

      if (lastResult) {
        setLastTestResult(lastResult)
      }

      if (successCount > 0 && failCount === 0) {
        message.success(`测试消息已发送 (${successCount} 个渠道)`)
      } else if (successCount > 0) {
        message.warning(`部分发送成功: ${successCount} 成功, ${failCount} 失败`)
      } else {
        message.error('所有渠道发送失败')
      }

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
      <Form form={form} layout="vertical">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>

          {/* 页面顶部操作区 */}
          <Row justify="end">
            <Space size={12} wrap>
              <Tooltip title="重新加载配置">
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
          </Row>

          <Card title="基础设置" styles={{ body: { padding: 24 } }}>
            <Space direction="vertical" size={24} style={{ width: '100%' }}>

              <Row gutter={24}>
                <Col xs={24} md={8}>
                  <Form.Item
                    name="enabled"
                    label="启用通知"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="已开启" unCheckedChildren="已关闭" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={16}>
                  <Form.Item
                    name="defaultChannel"
                    label="默认渠道"
                    rules={[{ required: true, message: '请选择默认渠道' }]}
                  >
                    <Select mode="multiple" options={channelOptions} placeholder="可多选" />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={24}>
                <Col xs={24} md={24}>
                  <Form.Item
                    name="wechatToken"
                    label="虾推啥 Token"
                    extra={hasWechatToken ? '已配置 (使用 *** 保留原值)。一个 Token 同时支持微信和 Bark 推送' : '一个 Token 同时支持微信和 Bark 推送'}
                  >
                    <Input
                      placeholder="请输入虾推啥 Token"
                      allowClear
                      autoComplete="off"
                    />
                  </Form.Item>

                </Col>
                {/* Bark Token 复用微信 Token，hidden */}
                <Form.Item name="barkToken" hidden>
                  <Input />
                </Form.Item>
              </Row>

              {/* Bark 服务器地址已移至 Bark 服务器卡片，保留 hidden 字段用于向后兼容 */}
              <Form.Item name={['baseUrls', 'bark']} hidden initialValue="https://bark.xtuis.cn">
                <Input />
              </Form.Item>

              <Form.Item name="requestTimeout" hidden initialValue={5.0} />
              <Form.Item name="retryAttempts" hidden initialValue={3} />
              <Form.Item name="retryDelay" hidden initialValue={1.0} />
              <Form.Item name={['baseUrls', 'wechat']} hidden initialValue="https://wx.xtuis.cn" />
            </Space>
          </Card>

          {/* Bark 服务器列表 */}
          <Card
            title="Bark 服务器"
            styles={{ body: { padding: 24 } }}
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                size="small"
                onClick={() => {
                  const newServer: BarkServer = {
                    name: `Bark ${barkServers.length + 1}`,
                    baseUrl: 'https://api.day.app',
                    token: '',
                    enabled: true
                  }
                  setBarkServers([...barkServers, newServer])
                  message.info('已添加新服务器，请填写配置后保存')
                }}
              >
                添加服务器
              </Button>
            }
          >
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Typography.Text type="secondary">
                支持配置多个 Bark 服务器同时推送。每个服务器需配置地址和设备 Key。
              </Typography.Text>
              {barkServers.length === 0 ? (
                <Typography.Text type="secondary" style={{ fontStyle: 'italic' }}>
                  暂无 Bark 服务器配置，点击"添加服务器"开始配置
                </Typography.Text>
              ) : (
                <Table
                  dataSource={barkServers.map((s, i) => ({ ...s, key: i }))}
                  pagination={false}
                  size="small"
                  columns={[
                    {
                      title: '名称',
                      dataIndex: 'name',
                      width: 120,
                      render: (value, _, index) => (
                        <Input
                          size="small"
                          value={value}
                          onChange={(e) => {
                            const updated = [...barkServers]
                            updated[index] = { ...updated[index], name: e.target.value }
                            setBarkServers(updated)
                          }}
                          placeholder="服务器名称"
                        />
                      )
                    },
                    {
                      title: '服务器地址',
                      dataIndex: 'baseUrl',
                      render: (value, _, index) => (
                        <Input
                          size="small"
                          value={value}
                          onChange={(e) => {
                            const updated = [...barkServers]
                            updated[index] = { ...updated[index], baseUrl: e.target.value }
                            setBarkServers(updated)
                          }}
                          placeholder="https://api.day.app"
                        />
                      )
                    },
                    {
                      title: '设备 Key',
                      dataIndex: 'token',
                      render: (value, _, index) => (
                        <Input
                          size="small"
                          value={value}
                          onChange={(e) => {
                            const updated = [...barkServers]
                            updated[index] = { ...updated[index], token: e.target.value }
                            setBarkServers(updated)
                          }}
                          placeholder="设备 Key（官方 Bark 如已在 URL 中可留空）"
                        />
                      )
                    },
                    {
                      title: '启用',
                      dataIndex: 'enabled',
                      width: 70,
                      render: (value, _, index) => (
                        <Switch
                          size="small"
                          checked={value}
                          onChange={(checked) => {
                            const updated = [...barkServers]
                            updated[index] = { ...updated[index], enabled: checked }
                            setBarkServers(updated)
                          }}
                        />
                      )
                    },
                    {
                      title: '操作',
                      width: 60,
                      render: (_, __, index) => (
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => {
                            const updated = barkServers.filter((_, i) => i !== index)
                            setBarkServers(updated)
                            message.info('已删除，请保存以生效')
                          }}
                        />
                      )
                    }
                  ]}
                />
              )}
            </Space>
          </Card>

          <Card title="消息模板" styles={{ body: { padding: 24 } }}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Typography.Text type="secondary">
                支持变量: <Tag>{'{title}'}</Tag> <Tag>{'{content}'}</Tag> <Tag>{'{symbol}'}</Tag> <Tag>{'{price}'}</Tag> <Tag>{'{timestamp}'}</Tag>
              </Typography.Text>

              {/* 向后兼容：默认模板 */}
              <Row gutter={24}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="titleTemplate"
                    label="默认标题模板"
                    style={{ marginBottom: 0 }}
                  >
                    <Input placeholder="DeepSearch 通知: {title}" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="bodyTemplate"
                    label="默认正文模板"
                    style={{ marginBottom: 0 }}
                  >
                    <Input.TextArea
                      rows={1}
                      placeholder="{content}"
                      style={{ resize: 'none' }}
                      autoSize={{ minRows: 1, maxRows: 3 }}
                    />
                  </Form.Item>
                </Col>
              </Row>

              {/* 分渠道模板管理 */}
              <Tabs
                items={[
                  {
                    key: 'bark',
                    label: `Bark 模板 (${templates.bark.length})`,
                    children: (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Button
                          type="dashed"
                          icon={<PlusOutlined />}
                          onClick={() => {
                            setEditingBarkTemplate(null)
                            barkTemplateForm.resetFields()
                            setBarkTemplateModalVisible(true)
                          }}
                        >
                          添加 Bark 模板
                        </Button>
                        {templates.bark.length > 0 && (
                          <Table
                            size="small"
                            rowKey="name"
                            dataSource={templates.bark}
                            pagination={false}
                            columns={[
                              { title: '模板名称', dataIndex: 'name', width: 120 },
                              { title: '标题模板', dataIndex: 'titleTemplate', ellipsis: true },
                              {
                                title: '级别',
                                dataIndex: 'level',
                                width: 100,
                                render: (v) => v ? <Tag>{v}</Tag> : <Tag color="default">active</Tag>
                              },
                              {
                                title: '声音',
                                dataIndex: 'sound',
                                width: 100,
                                render: (v) => v || '-'
                              },
                              {
                                title: '默认',
                                width: 60,
                                render: (_, record) => (
                                  record.name === templates.defaultBark ? <Tag color="green">默认</Tag> : null
                                )
                              },
                              {
                                title: '操作',
                                width: 120,
                                render: (_, record, index) => (
                                  <Space size="small">
                                    <Button
                                      type="link"
                                      size="small"
                                      onClick={() => {
                                        setEditingBarkTemplate(record)
                                        barkTemplateForm.setFieldsValue(record)
                                        setBarkTemplateModalVisible(true)
                                      }}
                                    >
                                      编辑
                                    </Button>
                                    <Button
                                      type="link"
                                      size="small"
                                      onClick={() => {
                                        setTemplates(prev => ({ ...prev, defaultBark: record.name }))
                                        message.success('已设为默认')
                                      }}
                                    >
                                      设默认
                                    </Button>
                                    <Button
                                      type="link"
                                      size="small"
                                      danger
                                      onClick={() => {
                                        setTemplates(prev => ({
                                          ...prev,
                                          bark: prev.bark.filter((_, i) => i !== index)
                                        }))
                                        message.info('已删除，请保存以生效')
                                      }}
                                    >
                                      删除
                                    </Button>
                                  </Space>
                                )
                              }
                            ]}
                          />
                        )}
                      </Space>
                    )
                  },
                  {
                    key: 'wechat',
                    label: `微信模板 (${templates.wechat.length})`,
                    children: (
                      <Typography.Text type="secondary">
                        微信模板使用默认标题/正文模板，暂不支持自定义样式。
                      </Typography.Text>
                    )
                  }
                ]}
              />
            </Space>
          </Card>

          <Card
            title="类别额度"
            styles={{ body: { padding: 24 } }}
          >
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
      </Form>

      <Modal
        title="发送测试通知"
        open={testVisible}
        onCancel={() => {
          testForm.resetFields()
          setTestVisible(false)
        }}
        onOk={handleSendTest}
        okText="发送"
        forceRender
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
            <Select
              mode="multiple"
              options={channelOptions}
              placeholder="可多选，留空使用默认渠道"
              onChange={(values: NotificationChannel[]) => {
                // 当选择 Bark 时，默认全选所有启用的服务器
                if (values?.includes('bark') && selectedBarkServers.length === 0) {
                  setSelectedBarkServers(
                    barkServers.filter(s => s.enabled).map(s => s.name)
                  )
                }
              }}
            />
          </Form.Item>
          {/* 当选择了 Bark 渠道时，显示 Bark 服务器选择器 */}
          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.channel !== curr.channel}>
            {({ getFieldValue }) => {
              const channels = getFieldValue('channel') as NotificationChannel[] | undefined
              if (!channels?.includes('bark')) return null

              const enabledServers = barkServers.filter(s => s.enabled)
              if (enabledServers.length === 0) {
                return (
                  <Form.Item label="Bark 服务器">
                    <Typography.Text type="secondary">暂无已启用的 Bark 服务器</Typography.Text>
                  </Form.Item>
                )
              }

              const allNames = enabledServers.map(s => s.name)
              const isAllSelected = selectedBarkServers.length === allNames.length

              return (
                <Form.Item label="Bark 服务器">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Checkbox
                      checked={isAllSelected}
                      indeterminate={selectedBarkServers.length > 0 && !isAllSelected}
                      onChange={e => {
                        setSelectedBarkServers(e.target.checked ? allNames : [])
                      }}
                    >
                      全选所有服务器
                    </Checkbox>
                    <Checkbox.Group
                      value={selectedBarkServers}
                      onChange={values => setSelectedBarkServers(values as string[])}
                      style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
                    >
                      {enabledServers.map(server => (
                        <Checkbox key={server.name} value={server.name}>
                          {server.name} ({server.baseUrl})
                        </Checkbox>
                      ))}
                    </Checkbox.Group>
                  </Space>
                </Form.Item>
              )
            }}
          </Form.Item>
          {/* 当选择了 Bark 渠道时，显示模板选择器 */}
          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.channel !== curr.channel}>
            {({ getFieldValue }) => {
              const channels = getFieldValue('channel') as NotificationChannel[] | undefined
              if (!channels?.includes('bark')) return null

              return (
                <Form.Item name="barkTemplateName" label="Bark 模板">
                  <Select
                    allowClear
                    placeholder={templates.bark.length === 0 ? '暂无模板' : '使用默认模板'}
                    disabled={templates.bark.length === 0}
                    options={templates.bark.length > 0 ? [
                      { label: `默认模板${templates.defaultBark ? ` (${templates.defaultBark})` : ''}`, value: '' },
                      ...templates.bark.map(t => ({
                        label: `${t.name}${t.name === templates.defaultBark ? ' (默认)' : ''}`,
                        value: t.name,
                      }))
                    ] : []}
                  />
                </Form.Item>
              )
            }}
          </Form.Item>
          <Form.Item name="category" label="类别">
            <Input placeholder="默认使用 default" />
          </Form.Item>
          <Form.Item name="bypassQuota" label="忽略额度限制" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* Bark 模板编辑 Modal */}
      <Modal
        title={editingBarkTemplate ? `编辑 Bark 模板: ${editingBarkTemplate.name}` : '添加 Bark 模板'}
        open={barkTemplateModalVisible}
        onCancel={() => setBarkTemplateModalVisible(false)}
        width={720}
        onOk={async () => {
          try {
            const values = await barkTemplateForm.validateFields()
            const newTemplate: BarkMessageTemplate = {
              name: values.name,
              titleTemplate: values.titleTemplate || '{title}',
              bodyTemplate: values.bodyTemplate || '{content}',
              subtitleTemplate: values.subtitleTemplate || undefined,
              useMarkdown: values.useMarkdown || false,
              level: values.level || undefined,
              sound: values.sound || undefined,
              icon: values.icon || undefined,
              image: values.image || undefined,
              group: values.group || undefined,
              url: values.url || undefined,
              copy: values.copy || undefined,
              autoCopy: values.autoCopy || false,
              isArchive: values.isArchive,
              call: values.call || false,
              badge: values.badge !== undefined && values.badge !== null ? values.badge : undefined,
            }

            if (editingBarkTemplate) {
              // 编辑模式：替换
              setTemplates(prev => ({
                ...prev,
                bark: prev.bark.map(t => t.name === editingBarkTemplate.name ? newTemplate : t)
              }))
              message.success('模板已更新，请保存配置')
            } else {
              // 新增模式：检查名称重复
              if (templates.bark.some(t => t.name === newTemplate.name)) {
                message.error('模板名称已存在')
                return
              }
              setTemplates(prev => ({
                ...prev,
                bark: [...prev.bark, newTemplate]
              }))
              message.success('模板已添加，请保存配置')
            }
            setBarkTemplateModalVisible(false)
          } catch (error) {
            console.error('[NotificationConfig] Bark template form error', error)
          }
        }}
      >
        <Form form={barkTemplateForm} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
                <Input placeholder="例如: 股票提醒" disabled={!!editingBarkTemplate} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="level" label="中断级别">
                <Select
                  allowClear
                  placeholder="默认 active"
                  options={[
                    { label: 'Active (默认)', value: 'active' },
                    { label: 'Time Sensitive (时效)', value: 'timeSensitive' },
                    { label: 'Passive (静默)', value: 'passive' },
                    { label: 'Critical (紧急)', value: 'critical' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="titleTemplate" label="标题模板">
            <Input placeholder="{title}" />
          </Form.Item>

          <Form.Item name="bodyTemplate" label="正文模板">
            <Input.TextArea rows={2} placeholder="{content}" autoSize={{ minRows: 2, maxRows: 5 }} />
          </Form.Item>

          <Form.Item name="subtitleTemplate" label="副标题模板">
            <Input placeholder="可选，如: {symbol} - {price}" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="sound" label="通知声音">
                <Select
                  allowClear
                  showSearch
                  placeholder="系统默认"
                  options={[
                    { label: 'alarm', value: 'alarm' },
                    { label: 'anticipate', value: 'anticipate' },
                    { label: 'bell', value: 'bell' },
                    { label: 'birdsong', value: 'birdsong' },
                    { label: 'bloom', value: 'bloom' },
                    { label: 'calypso', value: 'calypso' },
                    { label: 'chime', value: 'chime' },
                    { label: 'electronic', value: 'electronic' },
                    { label: 'fanfare', value: 'fanfare' },
                    { label: 'glass', value: 'glass' },
                    { label: 'horn', value: 'horn' },
                    { label: 'minuet', value: 'minuet' },
                    { label: 'newsflash', value: 'newsflash' },
                    { label: 'noir', value: 'noir' },
                    { label: 'paymentsuccess', value: 'paymentsuccess' },
                    { label: 'shake', value: 'shake' },
                    { label: 'silence (静音)', value: 'silence' },
                    { label: 'spell', value: 'spell' },
                    { label: 'suspense', value: 'suspense' },
                    { label: 'telegraph', value: 'telegraph' },
                    { label: 'update', value: 'update' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="group" label="通知分组">
                <Input placeholder="例如: 股票提醒" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="icon" label="图标 URL">
                <Input placeholder="https://example.com/icon.png" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="image" label="配图 URL">
                <Input placeholder="https://example.com/image.png" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="url" label="点击跳转 URL">
                <Input placeholder="https://example.com 或 app://..." />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="badge" label="角标数字">
                <InputNumber min={0} style={{ width: '100%' }} placeholder="0" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="copy" label="复制内容">
            <Input placeholder="用户点击复制时复制的内容" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="useMarkdown" label="Markdown" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="autoCopy" label="自动复制" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="isArchive" label="归档历史" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="call" label="持续响铃" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </Spin>
  )
}

export default NotificationConfig
