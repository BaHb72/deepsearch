import { useEffect, useState } from 'react'
import { App, Button, Card, Form, Input, InputNumber, Modal, Select, Space, Tag, Typography } from 'antd'
import type { NotificationChannel, NotificationConfigResponse } from '@/api/notifications'

interface CredentialsSectionProps {
  config: NotificationConfigResponse
  saving: boolean
  onSave: (values: Partial<NotificationConfigResponse>) => Promise<unknown>
  onUpdateTokens: (
    tokens: { wechatToken?: string | null; barkToken?: string | null },
    options?: { successMessage?: string | false; silent?: boolean },
  ) => Promise<unknown>
}

const CHANNEL_LABEL_MAP: Record<NotificationChannel, string> = {
  wechat: '微信',
  bark: 'Bark',
}

const CredentialsSection = ({ config, saving, onSave, onUpdateTokens }: CredentialsSectionProps) => {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const [tokenModalChannel, setTokenModalChannel] = useState<NotificationChannel | null>(null)
  const [tokenValue, setTokenValue] = useState('')
  const [tokenSubmitting, setTokenSubmitting] = useState(false)

  useEffect(() => {
    form.setFieldsValue({
      defaultChannel: config.defaultChannel,
      requestTimeout: config.requestTimeout,
      retryAttempts: config.retryAttempts,
      retryDelay: config.retryDelay,
      baseUrls: {
        wechat: config.baseUrls.wechat,
        bark: config.baseUrls.bark,
      },
    })
  }, [config, form])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      await onSave({
        defaultChannel: values.defaultChannel,
        requestTimeout: values.requestTimeout,
        retryAttempts: values.retryAttempts,
        retryDelay: values.retryDelay,
        baseUrls: values.baseUrls,
      })
    } catch {
      // 校验错误已提示
    }
  }

  const openTokenModal = (channel: NotificationChannel) => {
    setTokenModalChannel(channel)
    setTokenValue('')
  }

  const handleConfirmToken = async () => {
    if (!tokenModalChannel) {
      return
    }
    if (!tokenValue.trim()) {
      message.warning('请输入有效的 Token')
      return
    }
    setTokenSubmitting(true)
    try {
      const payload = tokenModalChannel === 'wechat'
        ? { wechatToken: tokenValue.trim() }
        : { barkToken: tokenValue.trim() }
      await onUpdateTokens(payload, { silent: true })
      message.success(`${CHANNEL_LABEL_MAP[tokenModalChannel]} Token 已更新`)
      setTokenModalChannel(null)
      setTokenValue('')
    } finally {
      setTokenSubmitting(false)
    }
  }

  const handleClearToken = async (channel: NotificationChannel) => {
    const payload = channel === 'wechat' ? { wechatToken: null } : { barkToken: null }
    await onUpdateTokens(payload, { silent: true, successMessage: false })
    message.success(`${CHANNEL_LABEL_MAP[channel]} Token 已清除`)
  }

  return (
    <Card title="凭证与基础配置" variant="borderless">
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Space>
            <Typography.Text>微信凭证：</Typography.Text>
            {config.hasWechatToken ? <Tag color="green">已配置</Tag> : <Tag color="red">未配置</Tag>}
            <Space>
              <Button size="small" onClick={() => openTokenModal('wechat')}>更新</Button>
              {config.hasWechatToken && (
                <Button size="small" danger onClick={() => handleClearToken('wechat')}>
                  清除
                </Button>
              )}
            </Space>
          </Space>

          <Space>
            <Typography.Text>Bark 凭证：</Typography.Text>
            {config.hasBarkToken ? <Tag color="green">已配置</Tag> : <Tag color="red">未配置</Tag>}
            <Space>
              <Button size="small" onClick={() => openTokenModal('bark')}>更新</Button>
              {config.hasBarkToken && (
                <Button size="small" danger onClick={() => handleClearToken('bark')}>
                  清除
                </Button>
              )}
            </Space>
          </Space>

          <Form.Item
            name="defaultChannel"
            label="默认发送渠道"
            rules={[{ required: true, message: '请选择默认渠道' }]}
          >
            <Select
              options={Object.entries(CHANNEL_LABEL_MAP).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>

          <Space size={16} style={{ width: '100%' }} wrap>
            <Form.Item
              name="requestTimeout"
              label="请求超时（秒）"
              style={{ flex: 1, minWidth: 200 }}
              rules={[{ required: true, message: '请输入请求超时' }]}
            >
              <InputNumber min={1} step={0.5} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="retryAttempts"
              label="重试次数"
              style={{ flex: 1, minWidth: 200 }}
              rules={[{ required: true, message: '请输入重试次数' }]}
            >
              <InputNumber min={0} max={5} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="retryDelay"
              label="重试间隔（秒）"
              style={{ flex: 1, minWidth: 200 }}
              rules={[{ required: true, message: '请输入重试间隔' }]}
            >
              <InputNumber min={0} step={0.5} style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Typography.Title level={5}>服务端地址</Typography.Title>
          <Space size={16} style={{ width: '100%' }} wrap>
            <Form.Item
              name={['baseUrls', 'wechat']}
              label="微信服务地址"
              style={{ flex: 1, minWidth: 240 }}
            >
              <Input placeholder="示例：https://api.your-domain.com/wechat" allowClear />
            </Form.Item>
            <Form.Item
              name={['baseUrls', 'bark']}
              label="Bark 服务地址"
              style={{ flex: 1, minWidth: 240 }}
            >
              <Input placeholder="示例：https://api.your-domain.com/bark" allowClear />
            </Form.Item>
          </Space>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存配置
              </Button>
              <Button onClick={() => form.resetFields()} disabled={saving}>
                恢复当前值
              </Button>
            </Space>
          </Form.Item>
        </Space>
      </Form>

      <Modal
        open={Boolean(tokenModalChannel)}
        title={tokenModalChannel ? `${CHANNEL_LABEL_MAP[tokenModalChannel]} Token 配置` : ''}
        onCancel={() => setTokenModalChannel(null)}
        onOk={handleConfirmToken}
        confirmLoading={tokenSubmitting}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Typography.Paragraph type="secondary">
          系统不会存储明文凭证，仅在内存中用于加密后保存。
        </Typography.Paragraph>
        <Input.TextArea
          rows={3}
          placeholder="请输入对应渠道的 Token"
          value={tokenValue}
          onChange={event => setTokenValue(event.target.value)}
        />
      </Modal>
    </Card>
  )
}

export default CredentialsSection
