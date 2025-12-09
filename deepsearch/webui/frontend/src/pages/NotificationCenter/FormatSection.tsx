// @ts-nocheck
import {useEffect, useMemo} from 'react'
import {Alert, App, Button, Card, Form, Input, Space, Tag, Typography} from 'antd'
import type {NotificationConfigResponse} from '@/api/notifications'
import {DEFAULT_BODY_TEMPLATE, DEFAULT_TITLE_TEMPLATE, WECHAT_TITLE_MAX_LENGTH,} from './constants'

interface FormatSectionProps {
  config: NotificationConfigResponse
  disabled: boolean
  saving: boolean
  onSave: (values: { titleTemplate: string; bodyTemplate: string }) => Promise<unknown>
}

const PLACEHOLDER_TAGS = ['{symbol}', '{price}', '{change}', '{time}']

const FormatSection = ({ config, disabled, saving, onSave }: FormatSectionProps) => {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const watchedTitle = Form.useWatch('titleTemplate', form)
  const watchedBody = Form.useWatch('bodyTemplate', form)

  useEffect(() => {
    form.setFieldsValue({
      titleTemplate: config.titleTemplate || DEFAULT_TITLE_TEMPLATE,
      bodyTemplate: config.bodyTemplate || DEFAULT_BODY_TEMPLATE,
    })
  }, [config.bodyTemplate, config.titleTemplate, form])

  const titleLabel = useMemo(
    () => `标题模板（最多 ${WECHAT_TITLE_MAX_LENGTH} 字）`,
    []
  )

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      await onSave(values)
    } catch {
      // 已由表单校验反馈，无需额外处理
    }
  }

  const handleRestoreDefault = async () => {
    form.setFieldsValue({
      titleTemplate: DEFAULT_TITLE_TEMPLATE,
      bodyTemplate: DEFAULT_BODY_TEMPLATE,
    })
    await handleSubmit()
  }

  const handleCopy = async (field: 'titleTemplate' | 'bodyTemplate') => {
    const value = form.getFieldValue(field)
    if (!value) {
      message.warning('暂无可复制的内容')
      return
    }

    try {
      await navigator.clipboard.writeText(value)
      message.success('模板内容已复制到剪贴板')
    } catch {
      console.error('[NotificationCenter] 复制模板失败', error)
      message.error('复制失败，请手动选择文本复制')
    }
  }

  const handleResetToCurrent = () => {
    form.setFieldsValue({
      titleTemplate: config.titleTemplate || DEFAULT_TITLE_TEMPLATE,
      bodyTemplate: config.bodyTemplate || DEFAULT_BODY_TEMPLATE,
    })
  }

  return (
    <Card title="格式与模板" variant="borderless">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {disabled && (
          <Alert
            type="warning"
            showIcon
            message="通知渠道未启用，启用后方可编辑模板"
          />
        )}

        <Space wrap>
          <Button onClick={() => handleCopy('titleTemplate')}>复制标题模板</Button>
          <Button onClick={() => handleCopy('bodyTemplate')}>复制正文模板</Button>
          <Button onClick={handleRestoreDefault}>恢复默认模板</Button>
        </Space>

        <Form
          form={form}
          layout="vertical"
          disabled={disabled}
          onFinish={handleSubmit}
        >
          <Form.Item
            name="titleTemplate"
            label={titleLabel}
            rules={[
              { required: true, message: '请输入标题模板' },
              {
                max: WECHAT_TITLE_MAX_LENGTH,
                message: `微信推送标题长度不能超过 ${WECHAT_TITLE_MAX_LENGTH} 个字符`,
              },
            ]}
          >
            <Input placeholder="示例：DeepSearch 通知提醒：{title}" allowClear />
          </Form.Item>

          <Typography.Paragraph type="secondary" style={{ marginTop: -12 }}>
            模板支持占位符：
            {PLACEHOLDER_TAGS.map(tag => (
              <Tag key={tag} color="blue">{tag}</Tag>
            ))}
          </Typography.Paragraph>

          <Form.Item
            name="bodyTemplate"
            label="正文模板"
            rules={[{ required: true, message: '请输入正文模板' }]}
          >
            <Input.TextArea
              rows={4}
              placeholder="示例：{symbol} 最新价格 {price}，涨跌幅 {change}"
              allowClear
            />
          </Form.Item>

          <Card type="inner" title="实时预览" size="small">
            <Space direction="vertical" size={4}>
              <Typography.Text strong>{watchedTitle || '标题示例'}</Typography.Text>
              <Typography.Paragraph style={{ marginBottom: 0 }}>
                {(watchedBody || '正文示例').split('\n').map((line, index) => (
                  <span key={index}>
                    {line}
                    <br />
                  </span>
                ))}
              </Typography.Paragraph>
            </Space>
          </Card>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving} disabled={disabled}>
                保存模板
              </Button>
              <Button onClick={handleResetToCurrent} disabled={disabled}>
                恢复当前配置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Space>
    </Card>
  )
}

export default FormatSection

