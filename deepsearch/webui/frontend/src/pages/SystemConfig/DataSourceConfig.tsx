import React, { useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Badge,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  InputNumber,
  Popconfirm,
  Tooltip,
  Row,
  Col,
  Alert,
  App as AntApp
} from 'antd'
import {
  ApiOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  CloudOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'
import { useModal } from '@/hooks'
import {
  createDataSource,
  updateDataSource,
  deleteDataSource,
  testDataSource,
  toggleDataSource,
  updateDataSourceConfig,
  fetchGlobalDataSourceConfig
} from '@/api/systemConfig'
import { DATA_SOURCE_STATUS_ORDER, getDataSourceStatusMeta, normalizeTestSummary } from '@/utils/dataSourceStatus'
import { useDataSourceStatus } from '@/stores'

const { Option } = Select

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

/**
 * @typedef {import('@/types/systemConfig').DataSource} DataSource
 * @typedef {import('@/types/systemConfig').DataSourceFormProps} DataSourceFormProps
 */

/**
 * 数据源表单组件
 * @param {DataSourceFormProps} props
 */
const DataSourceForm = ({ initialValues, onSubmit, onTestSuccess }) => {
  const { message } = AntApp.useApp()
  const [form] = Form.useForm()
  const [sourceType, setSourceType] = React.useState(initialValues?.type || 'akshare')
  const [testing, setTesting] = React.useState(false)

  const hasSavedCredential = Boolean(
    initialValues?.hasSavedCredential ?? initialValues?.has_saved_credential
  )
  const [credentialEditable, setCredentialEditable] = React.useState(!hasSavedCredential)

  const lastTestTime = initialValues?.lastTestTime || initialValues?.last_test_time || null
  const testSummary = normalizeTestSummary(
    initialValues?.testSummary ?? initialValues?.test_summary ?? null
  )

  React.useEffect(() => {
    setSourceType(initialValues?.type || 'akshare')
    setCredentialEditable(!hasSavedCredential)
    form.resetFields()
  }, [form, initialValues?.id, initialValues?.type, hasSavedCredential])

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
      }

      return payload
    },
    [credentialEditable, hasSavedCredential]
  )

  const handleTest = async () => {
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
      const response = await testDataSource(payload)
      if (response?.success) {
        message.success('数据源连接成功！')
        if (onTestSuccess) {
          onTestSuccess(response?.datasource)
        }
      } else {
        message.error(response?.message || '数据源测试失败')
      }
    } catch (error) {
      if (error?.errorFields) {
        message.warning('请先完成必填项')
      } else {
        message.error('测试失败: ' + (error?.message || '未知错误'))
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
      {renderTestInfo()}
      <Form
      form={form}
      layout="vertical"
      key={initialValues?.id ?? 'create'}
      initialValues={{
        enabled: true,
        priority: 1,
        ...initialValues,
        config: {
          timeout: 30000,
          retryCount: 3,
          rateLimit: 100,
          ...initialValues?.config
        }
      }}
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

                <Form.Item colon={false} label=" " style={{ marginTop: -16, marginBottom: 8 }}>

                  <Button type="link" onClick={handleCancelCredentialEdit} style={{ paddingLeft: 0 }}>

                    保留已保存的凭证

                  </Button>

                </Form.Item>

              )}

            </>

          ) : (

            <Form.Item label="密码">

              <Space>

                <Tag color="blue" style={{ margin: 0 }}>已保存</Tag>

                <span style={{ color: '#8c8c8c' }}>系统已保存凭证，如需修改请点击更新。</span>

                <Button type="link" onClick={handleEnableCredentialInput}>

                  更新凭证

                </Button>

              </Space>

            </Form.Item>

          )}

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
          <Button onClick={handleTest} loading={testing}>
            测试连接
          </Button>
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
const RateLimitEditor = ({ value, onChange }) => {
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
      const errorMessage = error?.message || '未知错误'
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
        onChange={setTempValue}
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

  React.useEffect(() => {
    const timer = setInterval(() => {
      refreshStatus().catch(() => undefined)
    }, 5000)

    return () => {
      clearInterval(timer)
    }
  }, [refreshStatus])

  const refreshAll = React.useCallback(async () => {
    await refreshStatus()
  }, [refreshStatus])

  const handleCreate = async (values) => {
    try {
      await createDataSource(values)
      message.success('创建成功')
      editModal.close()
      await refreshAll()
    } catch (error) {
      message.error('创建失败: ' + error.message)
    }
  }

  const handleUpdate = async (values) => {
    if (!editModal.data || !editModal.data.id) return
    try {
      await updateDataSource(editModal.data.id, values)
      message.success('保存成功')
      editModal.close()
      await refreshAll()
    } catch (error) {
      message.error('保存失败: ' + error.message)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteDataSource(id)
      message.success('删除成功')
      await refreshAll()
    } catch (error) {
      message.error('删除失败: ' + error.message)
    }
  }

  const handleToggle = async (id, enabled) => {
    const loadingKey = `toggle-${id}`
    const sourceInfo = dataSources.find(item => item.id === id || item.type === id)

    setToggleLoading(prev => ({ ...prev, [id]: true }))

    if (enabled) {
      message.loading({
        content: '正在启用并测试数据源...',
        key: loadingKey,
        duration: 0,
      })
    }

    try {
      const response = await toggleDataSource(id, enabled)
      const toggleSuccess = response?.success !== false

      if (!toggleSuccess) {
        const errorMsg = response?.message || '操作失败'
        const testDetails = response?.data?.test_details || response?.data?.details

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
          content: '数据源已禁用',
          key: loadingKey,
        })
        return
      }

      try {
        const testResult = await testDataSource({
          id,
          type: sourceInfo?.type ?? id,
          config: sourceInfo?.config,
        })

        if (testResult?.success) {
          const latency = typeof testResult.latency_ms === 'number'
            ? `${Math.round(testResult.latency_ms)}ms`
            : '成功'
          message.success({
            content: `数据源已启用，连通性测试通过（${latency}）`,
            key: loadingKey,
          })
        } else {
          const warningMsg = testResult?.message || '数据源已启用，但连通性测试失败'
          message.warning({
            content: warningMsg,
            key: loadingKey,
            duration: 8,
          })
        }
      } catch (testError) {
        console.error('自动测试数据源失败:', testError)
        message.warning({
          content: '数据源已启用，但测试请求失败，请手动测试',
          key: loadingKey,
          duration: 8,
        })
      }
    } catch (error) {
      console.error('Toggle datasource error:', error)
      message.error({
        content: '操作失败: ' + (error.response?.data?.message || error.message),
        key: loadingKey,
      })
    } finally {
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

      return {
        statusValue: statusMeta.value,
        available,
        reason,
        hasSavedCredential,
        lastTestTime,
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
  }, [dataSources, resolveSourceStatus, message])

  const getTypeIcon = (type) => {
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
  const getConnectionAddress = (record) => {
    if (record.config.host && record.config.port) {
      return `${record.config.host}:${record.config.port}`
    }
    if (record.config.workerUrl) {
      return record.config.workerUrl
    }
    if (record.config.apiKey) {
      return '***已配置***'
    }
    return '-'
  }

  const columns = [
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a, b) => a.priority - b.priority,
      defaultSortOrder: 'ascend',
      render: priority => (
        <Tag color={priority === 1 ? 'green' : priority <= 3 ? 'blue' : 'default'}>{priority}</Tag>
      ),
    },
    {
      title: '数据源名称',
      dataIndex: 'name',
      key: 'name',
      width: 220,
      render: (text, record) => (
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
      render: (_, record) => (
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
      title: '性能',
      key: 'performance',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          {record.successRate > 0 && (
            <Tooltip title="成功率">
              <Tag color={record.successRate >= 95 ? 'green' : record.successRate >= 80 ? 'orange' : 'red'}>
                {record.successRate.toFixed(1)}%
              </Tag>
            </Tooltip>
          )}
          {record.avgResponseTime > 0 && (
            <Tooltip title="平均响应时间">
              <Tag>{record.avgResponseTime}ms</Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '测试信息',
      key: 'test',
      width: 220,
      render: (_, record) => {
        const { lastTestTime, testSummary } = resolveSourceStatus(record)
        const timeText = lastTestTime ? formatDateTime(lastTestTime) : '未执行测试'
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
      render: (enabled, record) => {
        // 优先以后端配置(config.enabled)为准，避免旧字段或代理映射导致的误判
        const effectiveEnabled =
          typeof record?.config?.enabled === 'boolean'
            ? record.config.enabled
            : Boolean(enabled)

        return (
          <Switch
            checked={effectiveEnabled}
            loading={toggleLoading[record.id]}
            onChange={checked => handleToggle(record.id, checked)}
            checkedChildren="启用"
            unCheckedChildren="禁用"
            disabled={toggleLoading[record.id]}
          />
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 180,
      render: (_, record) => {
        const { statusValue, available, reason, hasSavedCredential, lastTestTime, testSummary } =
          resolveSourceStatus(record)
        const meta = getDataSourceStatusMeta(statusValue)

        const tooltipLines = [meta.description]
        if (testSummary) {
          tooltipLines.push(`结果: ${testSummary}`)
        }
        if (lastTestTime) {
          tooltipLines.push(`最近测试: ${formatDateTime(lastTestTime)}`)
        } else if (record.lastTransition) {
          tooltipLines.push(`最近变更: ${formatDateTime(record.lastTransition)}`)
        }
        if (reason) {
          tooltipLines.push(`原因: ${reason}`)
        }
        if (hasSavedCredential) {
          tooltipLines.push('凭证: 已保存')
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
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => editModal.open(record)}
          >
            编辑
          </Button>
          <Popconfirm title="确定删除此数据源？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
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
            rowKey="id"
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
          onTestSuccess={refreshAll}
        />
      </Modal>
    </>
  )
}

export default DataSourceConfig
