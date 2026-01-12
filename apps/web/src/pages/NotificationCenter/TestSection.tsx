import {useEffect} from 'react'
import {Alert, Button, Card, Form, Input, Select, Space, Switch, Table, Tag, Typography} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import type {NotificationChannel, NotificationConfigResponse} from '@/api/notifications'
import type {NotificationTestInput, NotificationTestRecord} from './useNotificationTest'
import {WECHAT_TITLE_MAX_LENGTH} from './constants'

interface TestSectionProps {
  config: NotificationConfigResponse
  disabled: boolean
  loading: boolean
  history: NotificationTestRecord[]
  onSend: (input: NotificationTestInput) => Promise<NotificationTestRecord>
  onClearHistory: () => void
  onAfterSend?: (record: NotificationTestRecord) => void
}

const CHANNEL_LABEL_MAP: Record<NotificationChannel, string> = {
  wechat: '微信',
  bark: 'Bark',
}

const columns: ColumnsType<NotificationTestRecord> = [
  {
    title: '时间',
    dataIndex: 'createdAt',
    key: 'createdAt',
    render: (value: number) => new Date(value).toLocaleString(),
  },
  {
    title: '标题',
    dataIndex: 'title',
    key: 'title',
    ellipsis: true,
  },
  {
    title: '渠道',
    dataIndex: 'channel',
    key: 'channel',
    render: (value: NotificationChannel | undefined) => {
      if (!value) {
        return '默认渠道'
      }
      return CHANNEL_LABEL_MAP[value]
    },
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    render: (value?: string) => value || 'default',
  },
  {
    title: '状态',
    dataIndex: 'success',
    key: 'success',
    render: (value: boolean) => (
      value ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>
    ),
  },
  {
    title: 'HTTP',
    dataIndex: 'statusCode',
    key: 'statusCode',
    render: (value?: number) => value ?? '-',
  },
  {
    title: '错误信息',
    dataIndex: 'errorMessage',
    key: 'errorMessage',
    ellipsis: true,
    render: (value?: string) => value || '-',
  },
]

const TestSection = ({
  config,
  disabled,
  loading,
  history,
  onSend,
  onClearHistory,
  onAfterSend,
}: TestSectionProps) => {
  const [form] = Form.useForm<NotificationTestInput>()

  useEffect(() => {
    form.setFieldsValue({
      channel: undefined,
      category: 'default',
      bypassQuota: false,
    })
  }, [form])

  const fillFromTemplate = () => {
    form.setFieldsValue({
      title: config.titleTemplate,
      content: config.bodyTemplate,
    })
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const record = await onSend({
        ...values,
        category: values.category || 'default',
      })
      onAfterSend?.(record)
    } catch {
      // 校验错误已由 Form 提示
    }
  }

  return (
    <Card title="发送测试" variant="borderless">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {disabled && (
          <Alert type="warning" showIcon message="通知渠道未启用，无法发起测试" />
        )}

        <Space>
          <Button onClick={fillFromTemplate} disabled={disabled}>填充默认模板</Button>
          <Button onClick={() => form.resetFields()} disabled={disabled}>清空表单</Button>
        </Space>

        <Form
          layout="vertical"
          form={form}
          disabled={disabled}
          onFinish={handleSubmit}
        >
          <Form.Item
            name="title"
            label={`推送标题（最多 ${WECHAT_TITLE_MAX_LENGTH} 字）`}
            rules={[
              { required: true, message: '请输入推送标题' },
              {
                max: WECHAT_TITLE_MAX_LENGTH,
                message: `微信推送标题长度不能超过 ${WECHAT_TITLE_MAX_LENGTH} 个字符`,
              },
            ]}
          >
            <Input placeholder="示例：DeepSearch 风控预警" allowClear />
          </Form.Item>

          <Form.Item
            name="content"
            label="推送正文"
          >
            <Input.TextArea rows={4} placeholder="可选，支持 Markdown" allowClear />
          </Form.Item>

          <Space size={16} style={{ width: '100%' }} wrap>
            <Form.Item name="channel" label="指定渠道" style={{ flex: 1, minWidth: 220 }}>
              <Select
                allowClear
                placeholder="默认使用配置的默认渠道"
                options={[
                  { value: 'wechat', label: '微信' },
                  { value: 'bark', label: 'Bark' },
                ]}
              />
            </Form.Item>
            <Form.Item name="category" label="消息分类" style={{ flex: 1, minWidth: 220 }}>
              <Input placeholder="默认 default" allowClear />
            </Form.Item>
            <Form.Item
              name="bypassQuota"
              label="忽略额度限制"
              valuePropName="checked"
              style={{ minWidth: 220 }}
            >
              <Switch />
            </Form.Item>
          </Space>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} disabled={disabled}>
              发送测试通知
            </Button>
          </Form.Item>
        </Form>

        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Typography.Title level={5} style={{ margin: 0 }}>历史记录</Typography.Title>
          <Button onClick={onClearHistory} disabled={!history.length}>清空历史</Button>
        </Space>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={history}
          pagination={{ pageSize: 5 }}
          size="small"
          locale={{ emptyText: disabled ? '通知渠道未启用' : '暂无测试记录' }}
        />
      </Space>
    </Card>
  )
}

export default TestSection
