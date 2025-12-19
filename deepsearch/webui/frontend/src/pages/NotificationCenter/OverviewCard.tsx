import {useMemo, useState} from 'react'
import {Alert, Button, Card, Descriptions, Space, Switch, Tag, Tooltip, Typography} from 'antd'
import {ExperimentOutlined, EyeOutlined, ReloadOutlined} from '@ant-design/icons'
import {useNavigate} from 'react-router-dom'
import type {NotificationConfigResponse} from '@/api/notifications'
import type {NotificationTestRecord} from './useNotificationTest'

const CHANNEL_LABEL_MAP: Record<string, string> = {
  wechat: '微信',
  bark: 'Bark',
}

interface OverviewCardProps {
  config: NotificationConfigResponse
  loading: boolean
  quotaLoading: boolean
  onToggleEnabled: (enabled: boolean) => Promise<void>
  onRefreshQuota: () => void
  onSwitchTab: (key: string) => void
  onReloadConfig: () => void
  lastTest?: NotificationTestRecord | null
}

const OverviewCard = ({
  config,
  loading,
  quotaLoading,
  onToggleEnabled,
  onRefreshQuota,
  onSwitchTab,
  onReloadConfig,
  lastTest,
}: OverviewCardProps) => {
  const navigate = useNavigate()
  const [switching, setSwitching] = useState(false)

  const handleToggle = async (checked: boolean) => {
    setSwitching(true)
    try {
      await onToggleEnabled(checked)
    } finally {
      setSwitching(false)
    }
  }

  const statusTag = useMemo(() => {
    if (!config.enabled) {
      return <Tag color="red">未启用</Tag>
    }
    if (config.hasWechatToken || config.hasBarkToken) {
      return <Tag color="green">凭证正常</Tag>
    }
    return <Tag color="orange">凭证未配置</Tag>
  }, [config])

  const credentialSummary = useMemo(() => {
    const items: string[] = []
    items.push(config.hasWechatToken ? '微信凭证完整' : '微信凭证缺失')
    items.push(config.hasBarkToken ? 'Bark 凭证完整' : 'Bark 凭证缺失')
    return items.join(' / ')
  }, [config.hasWechatToken, config.hasBarkToken])

  const retrySummary = useMemo(
    () => `${config.retryAttempts} 次 / 间隔 ${config.retryDelay}s`,
    [config.retryAttempts, config.retryDelay]
  )

  const defaultChannelLabel = CHANNEL_LABEL_MAP[config.defaultChannel] || config.defaultChannel

  return (
    <Card
      title="渠道概览"
      variant="borderless"
      extra={
        <Space>
          <Button onClick={onReloadConfig} loading={loading}>刷新配置</Button>
          <Button icon={<ReloadOutlined />} onClick={onRefreshQuota} loading={quotaLoading}>
            刷新额度
          </Button>
          <Button
            icon={<ExperimentOutlined />}
            type="primary"
            onClick={() => onSwitchTab('test')}
          >
            前往测试
          </Button>
          <Tooltip title="跳转系统日志查看通知相关记录">
            <Button icon={<EyeOutlined />} onClick={() => navigate('/system/logs')}>
              查看日志
            </Button>
          </Tooltip>
        </Space>
      }
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space size="large" align="center">
          <Typography.Text strong>通知渠道</Typography.Text>
          <Switch
            checked={config.enabled}
            onChange={handleToggle}
            loading={loading || switching}
            checkedChildren="启用"
            unCheckedChildren="停用"
          />
          {statusTag}
          <Typography.Text type="secondary">
            默认渠道：{defaultChannelLabel}
          </Typography.Text>
        </Space>

        <Descriptions column={2} size="small" labelStyle={{ minWidth: 120 }}>
          <Descriptions.Item label="凭证状态">{credentialSummary}</Descriptions.Item>
          <Descriptions.Item label="请求超时">{config.requestTimeout}s</Descriptions.Item>
          <Descriptions.Item label="重试策略">{retrySummary}</Descriptions.Item>
          <Descriptions.Item label="服务地址">
            <Space direction="vertical" size={4}>
              <span>微信：{config.baseUrls?.wechat || '未配置'}</span>
              <span>Bark：{config.baseUrls?.bark || '未配置'}</span>
            </Space>
          </Descriptions.Item>
        </Descriptions>

        {lastTest && (
          <Alert
            type={lastTest.success ? 'success' : 'error'}
            showIcon
            message={lastTest.success ? '最近一次推送成功' : '最近一次推送失败'}
            description={
              <Space direction="vertical" size={2}>
                <span>标题：{lastTest.title}</span>
                <span>渠道：{CHANNEL_LABEL_MAP[lastTest.channel || config.defaultChannel] || lastTest.channel}</span>
                <span>分类：{lastTest.category || 'default'}</span>
                {lastTest.statusCode && <span>状态码：{lastTest.statusCode}</span>}
                {lastTest.errorMessage && <span>错误：{lastTest.errorMessage}</span>}
                <Typography.Link onClick={() => onSwitchTab('test')}>查看测试详情</Typography.Link>
              </Space>
            }
          />
        )}
      </Space>
    </Card>
  )
}

export default OverviewCard

