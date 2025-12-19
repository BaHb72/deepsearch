import {useState} from 'react'
import {Alert, Button, Result, Skeleton, Space, Tabs} from 'antd'
import useNotificationConfig from './useNotificationConfig'
import useNotificationQuota from './useNotificationQuota'
import useNotificationTest from './useNotificationTest'
import OverviewCard from './OverviewCard'
import FormatSection from './FormatSection'
import TestSection from './TestSection'
import QuotaSection from './QuotaSection'
import CredentialsSection from './CredentialsSection'

const NotificationCenter = () => {
  const {
    config,
    loading,
    saving,
    error,
    load,
    save,
    updateTokens,
    toggleEnabled,
  } = useNotificationConfig()
  const quota = useNotificationQuota({ enabled: Boolean(config?.enabled) })
  const tests = useNotificationTest()
  const [activeTab, setActiveTab] = useState('format')

  if (!config) {
    if (loading) {
      return <Skeleton active paragraph={{ rows: 6 }} />
    }
    return (
      <Result
        status="error"
        title="通知中心暂不可用"
        subTitle={error || '无法加载通知中心配置，请确认后端服务已启动'}
        extra={[
          <Button key="reload" type="primary" onClick={() => { void load() }}>
            重新加载
          </Button>,
        ]}
      />
    )
  }

  const disabled = !config.enabled

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {error && !loading && (
        <Alert
          type="error"
          showIcon
          message="通知中心操作异常"
          description={error}
          action={
            <Button size="small" type="link" onClick={() => { void load() }}>
              重试加载
            </Button>
          }
        />
      )}
      <OverviewCard
        config={config}
        loading={loading}
        quotaLoading={quota.loading}
        onToggleEnabled={toggleEnabled}
        onRefreshQuota={quota.refresh}
        onSwitchTab={setActiveTab}
        onReloadConfig={load}
        lastTest={tests.lastRecord}
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'format',
            label: '格式模板',
            children: (
              <FormatSection
                config={config}
                disabled={disabled}
                saving={saving}
                onSave={values => save(values)}
              />
            ),
          },
          {
            key: 'test',
            label: '推送测试',
            children: (
              <TestSection
                config={config}
                disabled={disabled}
                loading={tests.loading}
                history={tests.history}
                onSend={tests.sendTest}
                onClearHistory={tests.clearHistory}
                onAfterSend={() => quota.refresh()}
              />
            ),
          },
          {
            key: 'quota',
            label: '额度监控',
            children: (
              <QuotaSection
                quotas={quota.quotas}
                loading={quota.loading}
                disabled={disabled}
                autoRefresh={quota.autoRefresh}
                lastUpdated={quota.lastUpdated}
                onAutoRefreshChange={quota.setAutoRefresh}
                onRefresh={quota.refresh}
                onReset={quota.reset}
              />
            ),
          },
          {
            key: 'credentials',
            label: '凭据配置',
            children: (
              <CredentialsSection
                config={config}
                saving={saving}
                onSave={save}
                onUpdateTokens={updateTokens}
              />
            ),
          },
        ]}
      />
    </Space>
  )
}

export default NotificationCenter


