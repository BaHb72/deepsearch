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
  Slider,
  App as AntApp
} from 'antd'
import {
  ApiOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  CloudOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'
import { useModal, useAsyncData } from '@/hooks'
import {
  fetchDataSources,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  testDataSource,
  toggleDataSource,
  fetchDataSourceHealth,
  refreshDataSources,
  updateDataSourceConfig
} from '@/api/systemConfig'

const { Option } = Select

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

  const handleTest = async () => {
    try {
      setTesting(true)
      const values = form.getFieldsValue()
      const response = await testDataSource(values)
      if (response?.success) {
        message.success('数据源连接成功！')
        // 调用测试成功回调
        if (onTestSuccess) {
          onTestSuccess(response?.datasource)
        }
      } else {
        message.error(response?.message || '数据源连接失败')
      }
    } catch (error) {
      message.error('测试失败: ' + error.message)
    } finally {
      setTesting(false)
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
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
      onFinish={onSubmit}
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
              <Form.Item
                name={['config', 'password']}
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="请输入密码" />
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
          <Button onClick={handleTest} loading={testing}>
            测试连接
          </Button>
          <Button type="primary" htmlType="submit">
            {initialValues ? '保存' : '创建'}
          </Button>
        </Space>
      </Form.Item>
    </Form>
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

  const handleSave = async () => {
    try {
      // 调用后端API更新速率限制
      await updateDataSourceConfig({ global_rate_limit: tempValue })
      onChange(tempValue)
      setEditing(false)
      message.success('速率限制已更新')
    } catch (error) {
      message.error('更新失败: ' + error.message)
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
  
  // 包装fetch函数以添加日志
  const fetchDataSourcesWithLog = React.useCallback(async () => {
    console.log('\n📡 [DataSourceConfig] 开始获取数据源列表...')
    console.log('API URL: /api/data-sources/list')
    try {
      const result = await fetchDataSources()
      console.log('✅ [DataSourceConfig] 获取数据源成功:', result)
      return result
    } catch (err) {
      console.error('❌ [DataSourceConfig] 获取数据源失败:', err)
      console.error('错误详情:', {
        message: err.message,
        response: err.response,
        stack: err.stack
      })
      throw err
    }
  }, [])
  
  const {
    data: dataSources,
    loading,
    refresh,
    error
  } = useAsyncData(
    fetchDataSourcesWithLog,
    { 
      immediate: true,
      showError: false,
      pollingInterval: 5000, // 5秒自动刷新
      onError: (err) => {
        console.error('🔴 [DataSourceConfig] useAsyncData onError:', err)
      }
    }
  )
  
  // 监控加载状态
  React.useEffect(() => {
    console.log('🔄 [DataSourceConfig] 状态更新:', {
      loading,
      hasData: !!dataSources,
      dataCount: dataSources?.length || 0,
      error: error?.message
    })
  }, [loading, dataSources, error])

  // 包装health fetch函数
  const fetchHealthWithLog = React.useCallback(async () => {
    console.log('🎯 [DataSourceConfig] 获取数据源健康状态...')
    try {
      const result = await fetchDataSourceHealth()
      console.log('✅ [DataSourceConfig] 健康状态:', result)
      return result
    } catch (err) {
      console.error('❌ [DataSourceConfig] 获取健康状态失败:', err)
      throw err
    }
  }, [])
  
  const {
    data: healthData,
    refresh: refreshHealth
  } = useAsyncData(
    fetchHealthWithLog,
    {
      immediate: true,
      showError: false,
      pollingInterval: 5000 // 5秒自动刷新
    }
  )

  const handleCreate = async (values) => {
    try {
      await createDataSource(values)
      message.success('创建成功')
      editModal.close()
      refresh()
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
      refresh()
    } catch (error) {
      message.error('保存失败: ' + error.message)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteDataSource(id)
      message.success('删除成功')
      refresh()
    } catch (error) {
      message.error('删除失败: ' + error.message)
    }
  }

  const handleToggle = async (id, enabled) => {
    // 显示loading状态
    const loadingKey = `toggle-${id}`

    // 设置按钮loading状态
    setToggleLoading(prev => ({ ...prev, [id]: true }))

    if (enabled) {
      message.loading({
        content: '正在测试数据源连接...',
        key: loadingKey,
        duration: 0  // 不自动关闭
      })
    }

    try {
      const response = await toggleDataSource(id, enabled)

      // 检查响应结构
      if (response?.data?.success || response?.success) {
        message.success({
          content: enabled ? '数据源已启用' : '数据源已禁用',
          key: loadingKey
        })
      } else {
        // 处理测试失败的情况
        const errorMsg = response?.data?.message || response?.message || '操作失败'
        const testDetails = response?.data?.data?.test_details || response?.data?.test_details

        // 如果是启用失败，显示详细错误
        if (enabled) {
          message.error({
            content: (
              <div>
                <div>{errorMsg}</div>
                {testDetails && Object.keys(testDetails).length > 0 && (
                  <div style={{ fontSize: '12px', marginTop: '4px', opacity: 0.8 }}>
                    {testDetails.error ? `错误: ${testDetails.error}` : ''}
                    {testDetails.note ? `提示: ${testDetails.note}` : ''}
                  </div>
                )}
              </div>
            ),
            key: loadingKey,
            duration: 8
          })
        } else {
          message.error({
            content: errorMsg,
            key: loadingKey
          })
        }
      }

      // 无论成功失败都刷新列表
      refresh()
    } catch (error) {
      console.error('Toggle datasource error:', error)
      message.error({
        content: '操作失败: ' + (error.response?.data?.message || error.message),
        key: loadingKey
      })
      refresh()
    } finally {
      // 清除loading状态
      setToggleLoading(prev => ({ ...prev, [id]: false }))
    }
  }

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
      render: (priority) => (
        <Tag color={priority === 1 ? 'green' : priority <= 3 ? 'blue' : 'default'}>
          {priority}
        </Tag>
      )
    },
    {
      title: '数据源名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (text, record) => (
        <Space>
          {getTypeIcon(record.type)}
          <span>{text}</span>
          <Tag color="blue" style={{ fontSize: 10 }}>
            {record.type.toUpperCase()}
          </Tag>
        </Space>
      )
    },
    {
      title: '连接地址',
      key: 'address',
      ellipsis: true,
      width: 250,
      render: (_, record) => (
        <Tooltip title={getConnectionAddress(record)}>
          <span style={{ 
            display: 'block',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            {getConnectionAddress(record)}
          </span>
        </Tooltip>
      )
    },
    {
      title: '性能',
      key: 'performance',
      width: 150,
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
      )
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled, record) => (
        <Switch
          checked={enabled}
          loading={toggleLoading[record.id]}
          onChange={(checked) => handleToggle(record.id, checked)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          disabled={toggleLoading[record.id]}
        />
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => {
        const statusMap = {
          online: { status: 'success', text: '已连接' },
          offline: { status: 'error', text: '未连接' },
          error: { status: 'error', text: '错误' },
          degraded: { status: 'warning', text: '降级' },
          unknown: { status: 'default', text: '未知' },
          untested: { status: 'default', text: '未测试' },
          disabled: { status: 'default', text: '已禁用' }
        }
        const config = statusMap[status] || { status: 'default', text: '未知' }
        return <Badge status={config.status} text={config.text} />
      }
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
          <Popconfirm
            title="确定删除此数据源？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  // 实时更新时间显示 - 修复：移除每秒更新，避免频繁重渲染
  const [currentTime, setCurrentTime] = React.useState(new Date())
  useEffect(() => {
    // 只在数据刷新时更新时间
    setCurrentTime(new Date())
  }, [dataSources, healthData])

  // 渲染日志 - 限制日志输出频率
  useEffect(() => {
    console.log('🎨 [DataSourceConfig] 渲染组件:', {
      loading,
      dataSourcesCount: dataSources?.length || 0,
      healthDataCount: healthData?.length || 0,
      error: error?.message
    })
  }, [loading, dataSources, healthData, error])
  
  return (
    <>
      {healthData && healthData.degraded && (
        <Alert
          message="数据源健康提醒"
          description={`有 ${healthData.degraded} 个数据源处于降级状态，可能影响数据获取`}
          type="warning"
          showIcon
          icon={<ExclamationCircleOutlined />}
          closable
          style={{ marginBottom: 16 }}
        />
      )}

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
            <Button onClick={refresh} style={{ marginTop: 16 }}>重试</Button>
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
          onTestSuccess={() => refresh()}
        />
      </Modal>
    </>
  )
}

export default DataSourceConfig