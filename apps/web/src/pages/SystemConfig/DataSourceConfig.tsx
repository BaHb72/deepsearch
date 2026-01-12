import React, { useEffect, useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import type { SortOrder } from 'antd/es/table/interface'
import {
  Alert,
  App as AntApp,
  Badge,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip
} from 'antd'
import {
  ApiOutlined,
  ClockCircleOutlined,
  CloudOutlined,
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'
import PollingConfig from './PollingConfig'
import { useModal } from '@/hooks'
import {
  createDataSource,
  deleteDataSource,
  testDataSource,
  toggleDataSource,
  updateDataSource,
} from '@/api/config/dataSourceConfig'
import {
  fetchGlobalDataSourceConfig,
  updateDataSourceConfig,
} from '@/api/config/systemImport'
import { DATA_SOURCE_STATUS_ORDER, getDataSourceStatusMeta, normalizeTestSummary } from '@/utils/dataSourceStatus'
import { useDataSourceStatus } from '@/stores'
import type { DataSource } from '@/stores/types'

const { Option } = Select

// ============= 类型定义 =============

interface RateLimitEditorProps {
  value: number
  onChange: (value: number) => void
}

interface DataSourceFormProps {
  initialValues?: DataSourceFormInitialValues
  onSubmit: (values: Record<string, unknown>) => Promise<void>
  onTestSuccess?: (datasource?: unknown) => void
}

interface ConnectionConfig {
  host?: string
  port?: number
  username?: string
  password?: string
  [key: string]: unknown
}


// 初始值类型（支持 snake_case 和 camelCase 双命名）
interface DataSourceFormInitialValues extends Partial<DataSource> {
  login_throttle?: unknown
  pending_login?: boolean
  has_saved_credential?: boolean
  rememberCredential?: boolean
  last_test_time?: string | null
  test_summary?: string | null
}

const padZero = (value: number) => value.toString().padStart(2, '0')

const formatDateTime = (input?: string | number | Date | null) => {
  if (!input) {
    return '未记录'
  }

  const date = input instanceof Date ? input : new Date(input)
  if (Number.isNaN(date.getTime())) {
    return String(input)
  }

  const year = date.getFullYear()
  const month = padZero(date.getMonth() + 1)
  const day = padZero(date.getDate())
  const hours = padZero(date.getHours())
  const minutes = padZero(date.getMinutes())
  const seconds = padZero(date.getSeconds())

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

const normalizeThrottleInfo = (input: any) => {
  if (!input || typeof input !== 'object') {
    return null
  }
  const waitSeconds =
    typeof input.waitSeconds === 'number'
      ? input.waitSeconds
      : typeof input.wait_seconds === 'number'
        ? input.wait_seconds
        : null
  const nextAllowed =
    typeof input.nextAllowedAt === 'string'
      ? input.nextAllowedAt
      : typeof input.next_allowed_at === 'string'
        ? input.next_allowed_at
        : null
  const backoffLevel =
    typeof input.backoffLevel === 'number'
      ? input.backoffLevel
      : typeof input.backoff_level === 'number'
        ? input.backoff_level
        : undefined
  const failureStreak =
    typeof input.failureStreak === 'number'
      ? input.failureStreak
      : typeof input.failure_streak === 'number'
        ? input.failure_streak
        : undefined

  return {
    inProgress: Boolean(input.inProgress ?? input.in_progress),
    waitSeconds,
    nextAllowedAt: nextAllowed ?? null,
    backoffLevel,
    failureStreak,
  }
}

/**
 * @typedef {import('@/types/systemConfig').DataSource} DataSource
 * @typedef {import('@/types/systemConfig').DataSourceFormProps} DataSourceFormProps
 */

/**
 * 数据源表单组件
 * @param {DataSourceFormProps} props
 */
const DataSourceForm = ({ initialValues, onSubmit, onTestSuccess }: DataSourceFormProps) => {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm()
  const [sourceType, setSourceType] = React.useState(initialValues?.type || 'akshare')
  const [testing, setTesting] = React.useState(false)

  const rawThrottleInfo = normalizeThrottleInfo(
    initialValues?.loginThrottle ?? initialValues?.login_throttle ?? null
  )
  const pendingLogin =
    typeof initialValues?.pendingLogin === 'boolean'
      ? initialValues.pendingLogin
      : typeof initialValues?.pending_login === 'boolean'
        ? initialValues.pending_login
        : Boolean(rawThrottleInfo?.inProgress)
  const throttleWaitSeconds = rawThrottleInfo?.waitSeconds ?? null
  const disableTest = pendingLogin || (typeof throttleWaitSeconds === 'number' && throttleWaitSeconds > 0.5)
  const throttleMessage = disableTest
    ? pendingLogin
      ? '当前已有登录任务正在执行，请稍后再试。'
      : `登录退避中，约 ${Math.ceil(throttleWaitSeconds ?? 0)} 秒后可再次尝试。`
    : null
  const throttleNextAllowed = rawThrottleInfo?.nextAllowedAt
    ? formatDateTime(rawThrottleInfo.nextAllowedAt)
    : null

  const throttleDescription = throttleMessage && throttleNextAllowed
    ? `${throttleMessage} 最早可重试: ${throttleNextAllowed}`
    : throttleMessage

  const hasSavedCredential = Boolean(
    initialValues?.hasSavedCredential ?? initialValues?.has_saved_credential
  )
  const [credentialEditable, setCredentialEditable] = React.useState(!hasSavedCredential)
  const initialRememberCredential =
    typeof initialValues?.rememberCredential === 'boolean'
      ? initialValues.rememberCredential
      : true

  const initialConnection = React.useMemo((): ConnectionConfig => {
    const connectionRaw = initialValues?.config?.connection as ConnectionConfig | undefined
    if (connectionRaw && typeof connectionRaw === 'object') {
      return { ...connectionRaw }
    }
    return {}
  }, [initialValues?.config?.connection])

  const formInitialValues = React.useMemo(() => {
    const baseConfig = {
      timeout: 30000,
      retryCount: 3,
      rateLimit: 100,
      ...(initialValues?.config || {}),
    } as Record<string, any>

    if (initialValues?.config?.connection && typeof initialValues.config.connection === 'object') {
      baseConfig.connection = { ...initialValues.config.connection }
    }

    if (initialValues?.type === 'amazingdata') {
      if (initialConnection.host !== undefined && baseConfig.host === undefined) {
        baseConfig.host = initialConnection.host
      }
      if (initialConnection.port !== undefined && baseConfig.port === undefined) {
        baseConfig.port = initialConnection.port
      }
      if (initialConnection.username !== undefined && baseConfig.username === undefined) {
        baseConfig.username = initialConnection.username
      }
    }

    return {
      enabled: false,  // 默认禁用，与 normalizeDataSource 保持一致
      priority: 1,
      ...initialValues,
      rememberCredential: initialRememberCredential,
      config: baseConfig,
    }
  }, [initialConnection, initialRememberCredential, initialValues])

  const lastTestTime = initialValues?.lastTestTime || initialValues?.last_test_time || null
  const testSummary = normalizeTestSummary(
    initialValues?.testSummary ?? initialValues?.test_summary ?? null
  )

  React.useEffect(() => {
    setSourceType(initialValues?.type || 'akshare')
    setCredentialEditable(!hasSavedCredential)
    form.resetFields()
    form.setFieldsValue(formInitialValues)
  }, [form, formInitialValues, initialValues?.type, hasSavedCredential])

  const buildDataSourcePayload = React.useCallback(
    (rawValues: Record<string, any>) => {
      const payload = { ...rawValues }

      if (payload.config) {
        payload.config = { ...payload.config }
        if (!credentialEditable && hasSavedCredential) {
          delete payload.config.password
        } else if (payload.config.password === '' || payload.config.password == null) {
          delete payload.config.password
        }

        if ((payload.type ?? sourceType) === 'amazingdata') {
          const {
            host,
            port,
            username,
            password,
            connection: nestedConnection,
            ...restConfig
          } = payload.config

          const connectionPayload = {
            ...(nestedConnection && typeof nestedConnection === 'object' ? nestedConnection : {}),
          }

          if (
            (!nestedConnection || typeof nestedConnection !== 'object') &&
            Object.keys(connectionPayload).length === 0
          ) {
            Object.assign(connectionPayload, initialConnection)
          } else if (Object.keys(initialConnection).length) {
            for (const [key, value] of Object.entries(initialConnection)) {
              if (!(key in connectionPayload)) {
                connectionPayload[key] = value
              }
            }
          }

          if (host !== undefined) {
            connectionPayload.host = host
          }
          if (port !== undefined) {
            connectionPayload.port = port
          }
          if (username !== undefined) {
            connectionPayload.username = username
          }

          if (credentialEditable || !hasSavedCredential) {
            if (password !== undefined) {
              connectionPayload.password = password
            }
          }

          const cleanedConfig = { ...restConfig }
          if (Object.keys(connectionPayload).length > 0) {
            cleanedConfig.connection = connectionPayload
          }

          payload.config = cleanedConfig
        }
      }

      const rememberCredentialValue = rawValues?.rememberCredential
      if (typeof rememberCredentialValue === 'boolean') {
        payload.rememberCredential = rememberCredentialValue
      } else if (payload.rememberCredential == null) {
        payload.rememberCredential = true
      }

      return payload
    },
    [credentialEditable, hasSavedCredential, initialConnection, sourceType]
  )

  const handleTest = async () => {
    if (disableTest) {
      message.info(throttleDescription || '登录退避中，请稍后再试。')
      return
    }
    try {
      const validatedValues = await form.validateFields()
      setTesting(true)
      const values = form.getFieldsValue(true)
      const mergedValues = {
        ...values,
        ...validatedValues,
        config: {
          ...(values?.config || {}),
          ...(validatedValues?.config || {}),
        },
      }
      const payload = buildDataSourcePayload(mergedValues)
      const response = await testDataSource(payload) as { success?: boolean; message?: string; datasource?: unknown }
      if (response?.success) {
        message.success('数据源连接成功！')
        if (onTestSuccess) {
          onTestSuccess(response?.datasource)
        }
      } else {
        message.error(response?.message || '数据源测试失败')
      }
    } catch (error) {
      const errorInfo = error as { errorFields?: unknown; message?: string }
      if (errorInfo?.errorFields) {
        message.warning('请先完成必填项')
      } else {
        message.error('测试失败: ' + (errorInfo?.message || '未知错误'))
      }
    } finally {
      setTesting(false)
    }
  }

  const handleFinish = (values: Record<string, any>) => {

    const payload = buildDataSourcePayload(values)

    onSubmit(payload)

  }



  const handleEnableCredentialInput = () => {

    setCredentialEditable(true)

    form.setFieldsValue({

      config: {

        ...(form.getFieldValue('config') || {}),

        password: undefined,

      },

    })

  }



  const handleCancelCredentialEdit = () => {

    if (!hasSavedCredential) {

      return

    }

    setCredentialEditable(false)

    form.setFieldsValue({

      config: {

        ...(form.getFieldValue('config') || {}),

        password: undefined,

      },

    })

  }



  const renderTestInfo = () => {

    if (!initialValues || (!lastTestTime && !testSummary)) {

      return null

    }



    return (

      <Alert

        type={initialValues.status === 'error' ? 'error' : 'info'}

        message="最近测试信息"

        description={

          <div style={{ lineHeight: 1.4 }}>

            <div>最近测试: {formatDateTime(lastTestTime)}</div>

            {testSummary && <div style={{ marginTop: 4 }}>{testSummary}</div>}

          </div>

        }

        showIcon

        style={{ marginBottom: 16 }}

      />

    )

  }



  return (
    <>
      {throttleDescription && (
        <Alert
          type={pendingLogin ? 'info' : 'warning'}
          showIcon
          style={{ marginBottom: 16 }}
          message={
            rawThrottleInfo?.failureStreak && rawThrottleInfo.failureStreak > 0
              ? `${throttleDescription}（连续失败 ${rawThrottleInfo.failureStreak} 次）`
              : throttleDescription
          }
        />
      )}
      {renderTestInfo()}
      <Form
        form={form}
        layout="vertical"
        key={initialValues?.id ?? 'create'}
        initialValues={formInitialValues}
        onFinish={handleFinish}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="name"
              label="数据源名称"
              rules={[{ required: true, message: '请输入数据源名称' }]}
            >
              <Input placeholder="例如：主数据源" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="type"
              label="数据源类型"
              rules={[{ required: true, message: '请选择数据源类型' }]}
            >
              <Select onChange={setSourceType}>
                <Option value="akshare">AKShare (直连)</Option>
                <Option value="amazingdata">银河证券星耀数智</Option>
                <Option value="qmt">QMT 实时数据</Option>
                <Option value="cloudflare">CloudFlare 代理</Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="enabled" label="启用状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="priority"
              label="优先级"
              tooltip="数字越小优先级越高"
              rules={[{ required: true, message: '请设置优先级' }]}
            >
              <InputNumber min={1} max={100} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        {/* 根据不同类型显示不同配置 */}
        {sourceType === 'qmt' && (
          <>
            <Row gutter={16}>
              <Col span={16}>
                <Form.Item
                  name={['config', 'host']}
                  label="QMT 主机地址"
                  rules={[{ required: true, message: '请输入主机地址' }]}
                >
                  <Input placeholder="例如：localhost" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item
                  name={['config', 'port']}
                  label="端口"
                  rules={[{ required: true, message: '请输入端口' }]}
                >
                  <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="5556" />
                </Form.Item>
              </Col>
            </Row>
          </>
        )}

        {sourceType === 'amazingdata' && (
          <>
            <Row gutter={16}>
              <Col span={16}>
                <Form.Item
                  name={['config', 'host']}
                  label="服务器地址"
                  rules={[{ required: true, message: '请输入服务器地址' }]}
                >
                  <Input placeholder="120.86.124.106 或 101.230.159.234" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item
                  name={['config', 'port']}
                  label="端口"
                  rules={[{ required: true, message: '请输入端口' }]}
                >
                  <InputNumber placeholder="8600" min={1} max={65535} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name={['config', 'username']}
                  label="用户名"
                  rules={[{ required: true, message: '请输入用户名' }]}
                >
                  <Input placeholder="请输入用户名" />
                </Form.Item>
              </Col>
              <Col span={12}>
                {credentialEditable ? (
                  <>
                    <Form.Item
                      name={['config', 'password']}
                      label="密码"
                      rules={[{ required: true, message: '请输入密码' }]}
                    >
                      <Input.Password placeholder="请输入密码" />
                    </Form.Item>
                    {hasSavedCredential && (
                      <Form.Item
                        colon={false}
                        label=" "
                        style={{ marginTop: -16, marginBottom: 8 }}
                      >
                        <Button
                          type="link"
                          onClick={handleCancelCredentialEdit}
                          style={{ paddingLeft: 0 }}
                        >
                          保留已保存的凭证
                        </Button>
                      </Form.Item>
                    )}
                  </>
                ) : (
                  <Form.Item label="密码">
                    <Space>
                      <Tag color="blue" style={{ margin: 0 }}>已保存</Tag>
                      <span style={{ color: '#8c8c8c' }}>
                        系统已保存凭证，如需修改请点击更新。
                      </span>
                      <Button type="link" onClick={handleEnableCredentialInput}>
                        更新凭证
                      </Button>
                    </Space>
                  </Form.Item>
                )}
                <Form.Item
                  name="rememberCredential"
                  label="记住凭证"
                  valuePropName="checked"
                  tooltip="启用后系统会在配置文件中保留该数据源的登录信息，重启服务后也无需重新填写。"
                  style={{ marginTop: credentialEditable ? 0 : 8 }}
                >
                  <Switch checkedChildren="记住" unCheckedChildren="不保存" />
                </Form.Item>
              </Col>
            </Row>
          </>
        )}

        {sourceType === 'cloudflare' && (
          <Form.Item
            name={['config', 'workerUrl']}
            label="Worker URL"
            rules={[
              { required: true, message: '请输入 Worker URL' },
              { type: 'url', message: '请输入有效的 URL' }
            ]}
          >
            <Input placeholder="https://your-worker.workers.dev" />
          </Form.Item>
        )}

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item
              name={['config', 'timeout']}
              label="超时时间(ms)"
              rules={[{ required: true, message: '请设置超时时间' }]}
            >
              <InputNumber min={1000} max={60000} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              name={['config', 'retryCount']}
              label="重试次数"
              rules={[{ required: true, message: '请设置重试次数' }]}
            >
              <InputNumber min={0} max={10} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              name={['config', 'rateLimit']}
              label="速率限制(req/s)"
              rules={[{ required: true, message: '请设置速率限制' }]}
            >
              <InputNumber min={1} max={1000} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item>
          <Space>
            <Tooltip title={disableTest ? (throttleDescription || "登录退避中，请稍后再试。") : undefined}>
              <span>
                <Button onClick={handleTest} loading={testing} disabled={disableTest}>
                  测试连接
                </Button>
              </span>
            </Tooltip>
            <Button type="primary" htmlType="submit">
              {initialValues ? '保存' : '创建'}
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </>
  )
}

/**
 * 速率限制编辑组件
 * @param {{value: number, onChange: (value: number) => void}} props
 */
const RateLimitEditor: React.FC<RateLimitEditorProps> = ({ value, onChange }) => {
  const { message } = AntApp.useApp()
  const [editing, setEditing] = React.useState(false)
  const [tempValue, setTempValue] = React.useState(value)

  React.useEffect(() => {
    setTempValue(value)
  }, [value])

  const handleSave = async () => {
    try {
      const payload = { global_rate_limit: Number(tempValue) }
      const result = await updateDataSourceConfig(payload)
      const updatedRateLimit = typeof result?.global_rate_limit === 'number'
        ? result.global_rate_limit
        : Number(tempValue)

      onChange(updatedRateLimit)
      setTempValue(updatedRateLimit)
      setEditing(false)
      message.success('速率限制已更新')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误'
      message.error('更新失败: ' + errorMessage)
    }
  }

  if (!editing) {
    return (
      <Space>
        <span>{value} req/s</span>
        <Button type="link" size="small" onClick={() => setEditing(true)}>
          编辑
        </Button>
      </Space>
    )
  }

  return (
    <Space>
      <InputNumber
        min={1}
        max={1000}
        value={tempValue}
        onChange={(val) => val != null && setTempValue(val)}
        style={{ width: 100 }}
      />
      <Button size="small" type="primary" onClick={handleSave}>
        保存
      </Button>
      <Button size="small" onClick={() => setEditing(false)}>
        取消
      </Button>
    </Space>
  )
}

/**
 * 数据源配置管理组件
 */
const DataSourceConfig = () => {
  const { message } = AntApp.useApp()
  const editModal = useModal()
  const [globalRateLimit, setGlobalRateLimit] = React.useState(100)
  const [toggleLoading, setToggleLoading] = React.useState({})

  // 添加调试日志
  React.useEffect(() => {
    console.log('\n========== DataSourceConfig 组件已挂载 ==========');
    console.log('✅ 请打开浏览器开发者工具（F12）查看控制台日志');
    console.log('===============================================\n');
    return () => {
      console.log('[DataSourceConfig] 组件已卸载')
    }
  }, [])

  const {
    dataSources,
    summary,
    health,
    loading,
    error,
    fetchStatus,
    refreshStatus,
  } = useDataSourceStatus()

  React.useEffect(() => {
    fetchStatus().catch(() => undefined)
  }, [fetchStatus])

  React.useEffect(() => {
    let mounted = true

    fetchGlobalDataSourceConfig()
      .then(config => {
        if (!mounted) {
          return
        }
        const rateLimit = Number(config?.global_rate_limit)
        if (!Number.isNaN(rateLimit) && rateLimit > 0) {
          setGlobalRateLimit(rateLimit)
        }
      })
      .catch(error => {
        console.error('加载全局数据源配置失败:', error)
        message.warning('加载全局数据源配置失败，已使用默认值')
      })

    return () => {
      mounted = false
    }
  }, [message])

  // 使用 useRef 保持函数引用稳定，避免 interval 频繁重建
  const refreshStatusRef = React.useRef(refreshStatus)
  React.useEffect(() => {
    refreshStatusRef.current = refreshStatus
  }, [refreshStatus])

  React.useEffect(() => {
    const timer = setInterval(() => {
      refreshStatusRef.current().catch(() => undefined)
    }, 5000)

    return () => {
      clearInterval(timer)
    }
  }, [])  // 空依赖，只在组件挂载/卸载时执行

  const refreshAll = React.useCallback(async () => {
    await refreshStatus()
  }, [refreshStatus])

  const handleTestSuccess = React.useCallback(() => {
    // 状态面板有轮询刷新，这里不立即重载配置，避免清空临时凭证
  }, [])

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await createDataSource(values)
      message.success('创建成功')
      editModal.close()
      await refreshAll()
    } catch (error) {
      message.error('创建失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleUpdate = async (values: Record<string, unknown>) => {
    if (!editModal.data || !editModal.data.id) return
    try {
      await updateDataSource(editModal.data.id, values)
      message.success('保存成功')
      editModal.close()
      await refreshAll()
    } catch (error) {
      message.error('保存失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleDelete = async (id: string | number) => {
    try {
      await deleteDataSource(id)
      message.success('删除成功')
      await refreshAll()
    } catch (error) {
      message.error('删除失败: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  const handleToggle = async (id: string | number, enabled: boolean) => {
    const loadingKey = `toggle-${id}`
    const sourceInfo = dataSources.find(item => item.id === id || item.type === id)

    setToggleLoading(prev => ({ ...prev, [id]: true }))

    if (enabled) {
      message.loading({
        content: '正在尝试启用数据源...',
        key: loadingKey,
        duration: 0,
      })
    }

    let shouldRollback = false
    let rollbackMessage = ''

    try {
      const response = await toggleDataSource(id, enabled) as { success?: boolean; message?: string; data?: Record<string, unknown> }
      const toggleSuccess = response?.success !== false

      if (!toggleSuccess) {
        const errorMsg = response?.message || '操作失败'
        const responseData = response?.data as Record<string, unknown> | undefined
        const testDetails = (responseData?.test_details || responseData?.details) as Record<string, unknown> | undefined

        if (enabled) {
          message.error({
            content: (
              <div>
                <div>{errorMsg}</div>
                {testDetails && Object.keys(testDetails).length > 0 && (
                  <div style={{ fontSize: '12px', marginTop: 4, opacity: 0.8 }}>
                    {testDetails.error ? `错误: ${testDetails.error}` : ''}
                    {testDetails.note ? `提示: ${testDetails.note}` : ''}
                  </div>
                )}
              </div>
            ),
            key: loadingKey,
            duration: 8,
          })
        } else {
          message.error({
            content: errorMsg,
            key: loadingKey,
          })
        }
        return
      }

      if (!enabled) {
        message.success({
          content: '数据源已停用',
          key: loadingKey,
        })
        return
      }

      try {
        const testResult = await testDataSource({
          id: String(id),
          type: sourceInfo?.type ?? String(id),
          config: sourceInfo?.config,
        })

        if (testResult?.success) {
          const latency = typeof testResult.latency_ms === 'number'
            ? `${Math.round(testResult.latency_ms)}ms`
            : '成功'
          message.success({
            content: `数据源已启用，自检通过耗时${latency}。`,
            key: loadingKey,
          })
        } else {
          shouldRollback = true
          rollbackMessage = testResult?.message || '数据源自检失败，已自动恢复为停用状态'
        }
      } catch (testError) {
        console.error('自动自检数据源失败:', testError)
        shouldRollback = true
        rollbackMessage = '数据源启用失败：自检过程发生异常，已恢复为停用状态'
      }
    } catch (error) {
      console.error('Toggle datasource error:', error)
      const err = error as { response?: { data?: { message?: string } }; message?: string }
      message.error({
        content: '操作失败: ' + (err.response?.data?.message || err.message || '未知错误'),
        key: loadingKey,
      })
    } finally {
      if (shouldRollback && enabled) {
        try {
          await toggleDataSource(id, false)
          message.error({
            content: rollbackMessage || '数据源自检失败，已自动恢复为停用状态',
            key: loadingKey,
            duration: 8,
          })
        } catch (rollbackError) {
          console.error('Rollback datasource toggle failed:', rollbackError)
          message.error({
            content: rollbackMessage ? `${rollbackMessage}；尝试恢复为停用状态失败，请手动停用。` : '尝试恢复为停用状态失败，请手动停用。',
            key: loadingKey,
            duration: 8,
          })
        }
      }

      await refreshAll()
      setToggleLoading(prev => ({ ...prev, [id]: false }))
    }
  }

  const statusSummary = React.useMemo(() => {
    const counts = DATA_SOURCE_STATUS_ORDER.reduce((acc, status) => {
      acc[status] = summary?.counts?.[status] ?? 0
      return acc
    }, {} as Record<string, number>)
    let total = summary?.total ?? 0
    let derivedAvailableCount = summary?.availableCount ?? 0

    const accumulate = (entry: any) => {
      const meta = getDataSourceStatusMeta(entry?.status)
      if (Object.prototype.hasOwnProperty.call(counts, meta.value)) {
        counts[meta.value] += 1
      }
      if (typeof entry?.available === 'boolean' && entry.available) {
        derivedAvailableCount += 1
      }
      total += 1
    }

    if (total === 0 && health?.sources && typeof health.sources === 'object') {
      Object.values(health.sources).forEach(accumulate)
    }

    if (total === 0 && Array.isArray(dataSources)) {
      dataSources.forEach(accumulate)
    }

    const availableCountRaw =
      typeof health?.availableCount === 'number'
        ? health.availableCount
        : typeof health?.available_count === 'number'
          ? health.available_count
          : undefined

    return {
      counts,
      total,
      availableCount: availableCountRaw ?? derivedAvailableCount,
    }
  }, [summary, health, dataSources])

  const resolveSourceStatus = React.useCallback(
    (record: any) => {
      if (!record) {
        return {
          statusValue: undefined,
          available: undefined,
          reason: undefined,
          hasSavedCredential: undefined,
          lastTestTime: undefined,
          testSummary: undefined,
          healthEntry: undefined,
        }
      }

      const sourcesMap =
        health?.sources && typeof health.sources === 'object'
          ? (health.sources as Record<string, any>)
          : undefined

      let healthEntry: Record<string, any> | undefined
      if (sourcesMap) {
        const normalizedType = record.type ? String(record.type).toLowerCase() : undefined
        const candidateKeys = Array.from(
          new Set(
            [
              record.id,
              record.name,
              record.key,
              record.identifier,
              record.config?.name,
              record.type,
              normalizedType,
            ]
              .filter(value => value !== undefined && value !== null)
              .map(value => String(value))
          )
        )

        for (const key of candidateKeys) {
          if (Object.prototype.hasOwnProperty.call(sourcesMap, key)) {
            healthEntry = sourcesMap[key]
            break
          }

          const lowerKey = key.toLowerCase()
          if (Object.prototype.hasOwnProperty.call(sourcesMap, lowerKey)) {
            healthEntry = sourcesMap[lowerKey]
            break
          }

          const matched = Object.entries(sourcesMap).find(
            ([mapKey]) => mapKey.toLowerCase() === lowerKey
          )
          if (matched) {
            healthEntry = matched[1]
            break
          }
        }
      }

      const rawStatus =
        (typeof record.status === 'string' && record.status) ||
        (typeof healthEntry?.status === 'string' && healthEntry.status) ||
        undefined
      const statusMeta = getDataSourceStatusMeta(rawStatus)

      const available =
        typeof record.available === 'boolean'
          ? record.available
          : typeof record.is_available === 'boolean'
            ? record.is_available
            : typeof healthEntry?.available === 'boolean'
              ? healthEntry.available
              : undefined

      const reason =
        record.reason ||
        record.degradedReason ||
        healthEntry?.degradedReason ||
        (healthEntry?.reason && healthEntry.reason !== 'from_provider' ? healthEntry.reason : undefined)

      const hasSavedCredential =
        typeof record.hasSavedCredential === 'boolean'
          ? record.hasSavedCredential
          : typeof record.has_saved_credential === 'boolean'
            ? record.has_saved_credential
            : typeof healthEntry?.hasSavedCredential === 'boolean'
              ? healthEntry.hasSavedCredential
              : typeof healthEntry?.has_saved_credential === 'boolean'
                ? healthEntry.has_saved_credential
                : undefined

      const lastTestTime =
        record.lastTestTime ??
        record.last_test_time ??
        healthEntry?.lastTestTime ??
        healthEntry?.last_test_time ??
        null

      const testSummaryRaw =
        record.testSummary ??
        record.test_summary ??
        healthEntry?.testSummary ??
        healthEntry?.test_summary ??
        null
      const testSummary = normalizeTestSummary(testSummaryRaw)

      const rawThrottle =
        record.loginThrottle ??
        record.login_throttle ??
        healthEntry?.loginThrottle ??
        healthEntry?.login_throttle ??
        null
      const loginThrottle = normalizeThrottleInfo(rawThrottle)
      const pendingLogin =
        typeof record.pendingLogin === 'boolean'
          ? record.pendingLogin
          : typeof record.pending_login === 'boolean'
            ? record.pending_login
            : typeof healthEntry?.pendingLogin === 'boolean'
              ? healthEntry.pendingLogin
              : Boolean(loginThrottle?.inProgress)
      const waitSeconds = loginThrottle?.waitSeconds ?? null
      const lastLoginStartedAt =
        record.lastLoginStartedAt ??
        record.last_login_started_at ??
        healthEntry?.lastLoginStartedAt ??
        healthEntry?.last_login_started_at ??
        null
      const lastLoginCompletedAt =
        record.lastLoginCompletedAt ??
        record.last_login_completed_at ??
        healthEntry?.lastLoginCompletedAt ??
        healthEntry?.last_login_completed_at ??
        null
      const lastLoginSuccessAt =
        record.lastLoginSuccessAt ??
        record.last_login_success_at ??
        healthEntry?.lastLoginSuccessAt ??
        healthEntry?.last_login_success_at ??
        null
      const lastLoginErrorAt =
        record.lastLoginErrorAt ??
        record.last_login_error_at ??
        healthEntry?.lastLoginErrorAt ??
        healthEntry?.last_login_error_at ??
        null
      const lastLoginErrorReason =
        record.lastLoginErrorReason ??
        record.last_login_error_reason ??
        healthEntry?.lastLoginErrorReason ??
        healthEntry?.last_login_error_reason ??
        null

      return {
        statusValue: statusMeta.value,
        available,
        reason,
        hasSavedCredential,
        lastTestTime,
        loginThrottle,
        pendingLogin,
        throttleWaitSeconds: waitSeconds,
        lastLoginStartedAt,
        lastLoginCompletedAt,
        lastLoginSuccessAt,
        lastLoginErrorAt,
        lastLoginErrorReason,
        testSummary,
        healthEntry,
      }
    },
    [health]
  )

  const totalSources = statusSummary.total || (Array.isArray(dataSources) ? dataSources.length : 0)
  const availableSources = statusSummary.availableCount ?? 0

  const previousStatusesRef = React.useRef<Record<string, string | undefined>>({})
  const activeAlertsRef = React.useRef<Record<string, { status: string; messageKey: string }>>({})

  React.useEffect(() => {
    if (!Array.isArray(dataSources) || dataSources.length === 0) {
      Object.values(activeAlertsRef.current).forEach(alert => {
        message.destroy(alert.messageKey)
      })
      activeAlertsRef.current = {}
      previousStatusesRef.current = {}
      return
    }

    const seenKeys = new Set<string>()

    dataSources.forEach((record, index) => {
      const { statusValue } = resolveSourceStatus(record)
      const identifier =
        record.id != null
          ? String(record.id)
          : record.name
            ? `name:${record.name}`
            : record.type
              ? `type:${record.type}`
              : `idx:${index}`
      seenKeys.add(identifier)

      const prevStatus = previousStatusesRef.current[identifier]
      const existingAlert = activeAlertsRef.current[identifier]

      if (statusValue) {
        const isDegraded = statusValue === 'degraded'
        const isError = statusValue === 'error'
        const hasAlert = Boolean(existingAlert)
        const readableName = record.name || record.type || record.id || identifier
        const alertKey = existingAlert?.messageKey || `ds-alert-${identifier}`

        if (isDegraded || isError) {
          const shouldNotify =
            (!hasAlert && prevStatus && ['active', 'ready'].includes(prevStatus)) ||
            (hasAlert && existingAlert.status !== statusValue)

          if (shouldNotify) {
            const content = isDegraded
              ? `数据源「${readableName}」状态降级，请重新测试查看诊断`
              : `数据源「${readableName}」出现错误，请检查配置并重新测试`

            message.open({
              key: alertKey,
              type: isError ? 'error' : 'warning',
              content,
              duration: 0,
            })

            activeAlertsRef.current[identifier] = { status: statusValue, messageKey: alertKey }
          } else if (!hasAlert && !prevStatus && (isDegraded || isError)) {
            // 首次检测到异常时也提示，便于首次进入即看到告警
            const content = isDegraded
              ? `数据源「${readableName}」状态降级，请重新测试查看诊断`
              : `数据源「${readableName}」出现错误，请检查配置并重新测试`

            message.open({
              key: alertKey,
              type: isError ? 'error' : 'warning',
              content,
              duration: 0,
            })

            activeAlertsRef.current[identifier] = { status: statusValue, messageKey: alertKey }
          }
        } else if ((statusValue === 'ready' || statusValue === 'active') && hasAlert) {
          message.destroy(existingAlert.messageKey)
          delete activeAlertsRef.current[identifier]
        }
      }

      previousStatusesRef.current[identifier] = statusValue || prevStatus
    })

    Object.keys(previousStatusesRef.current).forEach(key => {
      if (!seenKeys.has(key)) {
        delete previousStatusesRef.current[key]
        const alert = activeAlertsRef.current[key]
        if (alert) {
          message.destroy(alert.messageKey)
          delete activeAlertsRef.current[key]
        }
      }
    })

    // 组件卸载时清理所有持久告警
    return () => {
      Object.values(activeAlertsRef.current).forEach(alert => {
        message.destroy(alert.messageKey)
      })
      activeAlertsRef.current = {}
    }
  }, [dataSources, resolveSourceStatus, message])

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'cloudflare':
        return <CloudOutlined />
      case 'qmt':
        return <ThunderboltOutlined />
      default:
        return <ApiOutlined />
    }
  }

  // 生成连接地址显示
  const getConnectionAddress = (record: DataSource): string => {
    const config = record.config as Record<string, unknown> | undefined
    if (config?.host && config?.port) {
      return `${config.host}:${config.port}`
    }
    if (config?.workerUrl) {
      return String(config.workerUrl)
    }
    if (config?.apiKey) {
      return '***已配置***'
    }
    return '-'
  }

  const columns: ColumnsType<DataSource> = [
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: DataSource, b: DataSource) => a.priority - b.priority,
      defaultSortOrder: 'ascend' as SortOrder,
      render: (priority: number) => (
        <Tag color={priority === 1 ? 'green' : priority <= 3 ? 'blue' : 'default'}>{priority}</Tag>
      ),
    },
    {
      title: '数据源名称',
      dataIndex: 'name',
      key: 'name',
      width: 220,
      render: (text: string, record: DataSource) => (
        <Space>
          {getTypeIcon(record.type)}
          <span>{text}</span>
          <Tag color="blue" style={{ fontSize: 10 }}>{record.type?.toUpperCase()}</Tag>
        </Space>
      ),
    },
    {
      title: '连接地址',
      key: 'address',
      ellipsis: true,
      width: 260,
      render: (_: unknown, record: DataSource) => (
        <Tooltip title={getConnectionAddress(record)}>
          <span
            style={{
              display: 'block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {getConnectionAddress(record)}
          </span>
        </Tooltip>
      ),
    },

    {
      title: '测试信息',
      key: 'test',
      width: 220,
      render: (_: unknown, record: DataSource) => {
        const { lastTestTime, testSummary } = resolveSourceStatus(record)
        const timeText = lastTestTime ? formatDateTime(lastTestTime as string | number | Date) : '未执行测试'
        const summaryNode = testSummary ? (
          <Tooltip title={testSummary}>
            <div
              style={{
                marginTop: 4,
                fontSize: 12,
                color: '#8c8c8c',
                maxWidth: 200,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {testSummary}
            </div>
          </Tooltip>
        ) : (
          <div style={{ marginTop: 4, fontSize: 12, color: '#bfbfbf' }}>暂无摘要</div>
        )

        return (
          <div style={{ lineHeight: 1.4 }}>
            <div style={{ fontSize: 12, color: '#595959' }}>最近: {timeText}</div>
            {summaryNode}
          </div>
        )
      },
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean, record: DataSource) => {
        // 直接使用已被 normalizeDataSource 规范化的 enabled 字段
        // 规范化逻辑: source.enabled > config.enabled > false
        const effectiveEnabled = Boolean(enabled)
        const recordId = record.id
        const idKey = String(recordId)

        return (
          <Switch
            checked={effectiveEnabled}
            loading={recordId != null ? Boolean((toggleLoading as Record<string, boolean>)[idKey]) : false}
            onChange={checked => recordId != null && handleToggle(recordId, checked)}
            checkedChildren="启用"
            unCheckedChildren="禁用"
            disabled={recordId != null ? Boolean((toggleLoading as Record<string, boolean>)[idKey]) : true}
          />
        )
      },
    },

    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 180,
      render: (_: unknown, record: DataSource) => {
        const {
          statusValue,
          available,
          reason,
          hasSavedCredential,
          lastTestTime,
          testSummary,
          loginThrottle,
          pendingLogin,
          throttleWaitSeconds,
          lastLoginErrorReason
        } =
          resolveSourceStatus(record)
        const meta = getDataSourceStatusMeta(statusValue)

        const tooltipLines = [meta.description]
        if (testSummary) {
          tooltipLines.push(`结果: ${testSummary}`)
        }
        if (lastTestTime) {
          tooltipLines.push(`最近测试: ${formatDateTime(lastTestTime as string | number | Date)}`)
        } else if (record.lastTransition) {
          tooltipLines.push(`最近变更: ${formatDateTime(record.lastTransition as string | number | Date)}`)
        }
        if (reason) {
          tooltipLines.push(`原因: ${reason}`)
        }
        if (hasSavedCredential) {
          tooltipLines.push('凭证: 已保存')
        }

        if (pendingLogin) {
          tooltipLines.push('登录任务: 进行中')
        }
        if (typeof throttleWaitSeconds === 'number' && throttleWaitSeconds > 0.5) {
          tooltipLines.push(`退避窗口: 等待 ${Math.ceil(throttleWaitSeconds)} 秒`)
        }
        if (loginThrottle?.nextAllowedAt) {
          tooltipLines.push(`最早可重试: ${formatDateTime(loginThrottle.nextAllowedAt)}`)
        }
        if (lastLoginErrorReason) {
          tooltipLines.push(`最后错误: ${lastLoginErrorReason}`)
        }

        const tooltipContent = (
          <div>
            {tooltipLines.map((line, index) => (
              <div
                key={index}
                style={{ marginTop: index === 0 ? 0 : 4, fontSize: 12, color: '#8c8c8c' }}
              >
                {line}
              </div>
            ))}
          </div>
        )

        return (
          <Space size={6}>
            <Tooltip title={tooltipContent}>
              <Tag color={meta.tagColor} style={{ margin: 0 }}>
                {meta.text}
              </Tag>
            </Tooltip>
            {typeof available === 'boolean' && (
              <Tooltip title={available ? '当前可用' : '当前不可用'}>
                <Badge status={available ? 'success' : 'error'} />
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right' as const,
      render: (_: unknown, record: DataSource) => {
        const recordId = record.id as string | number | undefined
        return (
          <Space size="small">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => editModal.open(record)}
            >
              编辑
            </Button>
            <Popconfirm title="确定删除此数据源？" onConfirm={() => recordId != null && handleDelete(recordId)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )
      },
    },
  ]

  // 实时更新时间显示 - 修复：移除每秒更新，避免频繁重渲染
  const [currentTime, setCurrentTime] = React.useState(new Date())
  useEffect(() => {
    // 只在数据刷新时更新时间
    setCurrentTime(new Date())
  }, [dataSources, health])

  // 渲染日志 - 限制日志输出频率
  useEffect(() => {
    console.log('🎨 [DataSourceConfig] 渲染组件:', {
      loading,
      dataSourcesCount: dataSources?.length || 0,
      healthCount: health?.sources ? Object.keys(health.sources).length : 0,
      error: error?.message
    })
  }, [loading, dataSources, health, error])

  return (
    <Tabs
      defaultActiveKey="datasources"
      items={[
        {
          key: 'datasources',
          label: (
            <span>
              <ThunderboltOutlined />
              数据源管理
            </span>
          ),
          children: (
            <>
              {health && health.degraded && (
                <Alert
                  message="数据源健康提醒"
                  description={`有 ${health.degraded} 个数据源处于降级状态，可能影响数据获取`}
                  type="warning"
                  showIcon
                  icon={<ExclamationCircleOutlined />}
                  closable
                  style={{ marginBottom: 16 }}
                />
              )}

              <Card
                title="状态概览"
                style={{ marginBottom: 16 }}
                extra={
                  <Space size={24}>
                    <span style={{ color: '#595959' }}>
                      总数: <strong style={{ fontSize: 16 }}>{totalSources}</strong>
                    </span>
                    <Tooltip title="标注当前 available=true 的数据源数量">
                      <span style={{ color: '#595959' }}>
                        当前可用: <strong style={{ fontSize: 16 }}>{availableSources}</strong>
                      </span>
                    </Tooltip>
                  </Space>
                }
              >
                <Space size={[16, 16]} wrap>
                  {DATA_SOURCE_STATUS_ORDER.map(statusKey => {
                    const meta = getDataSourceStatusMeta(statusKey)
                    const count = statusSummary.counts?.[statusKey] ?? 0
                    const isZero = count === 0
                    return (
                      <Tooltip title={meta.description} key={statusKey}>
                        <div
                          style={{
                            minWidth: 180,
                            maxWidth: 220,
                            borderRadius: 8,
                            border: `1px solid ${meta.tagColor}`,
                            padding: '12px 16px',
                            background: '#fff',
                            boxShadow: isZero ? 'none' : '0 2px 8px rgba(0,0,0,0.06)',
                            opacity: isZero ? 0.55 : 1,
                            transition: 'all 0.2s ease-in-out',
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              marginBottom: 8,
                            }}
                          >
                            <Tag color={meta.tagColor} style={{ margin: 0 }}>
                              {meta.text}
                            </Tag>
                            <span style={{ fontSize: 24, fontWeight: 600, color: meta.tagColor }}>
                              {count}
                            </span>
                          </div>
                          <div style={{ color: '#8c8c8c', fontSize: 12, lineHeight: 1.4 }}>
                            {meta.description}
                          </div>
                        </div>
                      </Tooltip>
                    )
                  })}
                </Space>
              </Card>

              <Card
                title="数据源管理"
                extra={
                  <Space>
                    <span style={{ fontSize: 12, color: '#999' }}>
                      自动刷新: 5秒 | 最后更新: {currentTime.toLocaleTimeString()}
                    </span>
                    <span style={{ fontSize: 12, color: '#666' }}>
                      全局速率限制:
                    </span>
                    <RateLimitEditor value={globalRateLimit} onChange={setGlobalRateLimit} />
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => editModal.open()}
                    >
                      新建数据源
                    </Button>
                  </Space>
                }
              >
                {error ? (
                  <div style={{ textAlign: 'center', padding: '50px' }}>
                    <p style={{ color: '#ff4d4f' }}>
                      {error.message?.includes('503') || error.message?.includes('系统未初始化')
                        ? '后端服务未就绪'
                        : '加载失败: ' + error.message}
                    </p>
                    {(error.message?.includes('503') || error.message?.includes('系统未初始化')) && (
                      <div style={{ marginTop: '16px', padding: '16px', background: '#f0f0f0', borderRadius: '4px' }}>
                        <p style={{ marginBottom: '8px' }}>请确保后端服务已启动：</p>
                        <code style={{ display: 'block', padding: '8px', background: '#000', color: '#0f0', borderRadius: '4px' }}>
                          python -m deepsearch run --no-frontend
                        </code>
                      </div>
                    )}
                    <Button onClick={refreshAll} style={{ marginTop: 16 }}>重试</Button>
                  </div>
                ) : (
                  <Table
                    columns={columns}
                    dataSource={dataSources || []}
                    loading={loading && !(dataSources && dataSources.length > 0)}
                    rowKey={(record, index) => record.id ?? record.name ?? `${record.type}-${index}`}
                    pagination={{ pageSize: 10 }}
                    scroll={{ x: 1200 }}
                    size="middle"
                  />
                )}
              </Card>

              <Modal
                title={editModal.data ? '编辑数据源' : '新建数据源'}
                open={editModal.visible}
                onCancel={editModal.close}
                footer={null}
                width={700}
              >
                <DataSourceForm
                  initialValues={editModal.data || undefined}
                  onSubmit={editModal.data ? handleUpdate : handleCreate}
                  onTestSuccess={handleTestSuccess}
                />
              </Modal>
            </>
          ),
        },
        {
          key: 'polling',
          label: (
            <span>
              <ClockCircleOutlined />
              轮询配置
            </span>
          ),
          children: <PollingConfig />,
        },
      ]}
    />
  )
}

export default DataSourceConfig
