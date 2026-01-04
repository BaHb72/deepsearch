import React, { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Space,
  Tabs,
  InputNumber,
  message,
  Spin,
  Divider,
  Alert,
  Row,
  Col,
  Typography
} from 'antd'
import {
  SettingOutlined,
  SaveOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ApiOutlined,
  SecurityScanOutlined,
  ThunderboltOutlined
} from '@ant-design/icons'
import systemService from '../services/system'

const { Option } = Select
const { TabPane } = Tabs
const { Title, Text, Paragraph } = Typography

// 配置页面组件
const Config = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('basic')
  const [config, setConfig] = useState({
    basic: {
      appName: 'DeepSearch',
      env: 'dev',
      debug: false,
      timezone: 'Asia/Shanghai'
    },
    server: {
      host: 'localhost',
      port: 8000,
      workers: 4,
      timeout: 30
    },
    database: {
      type: 'postgresql',
      host: 'localhost',
      port: 5432,
      name: 'deepsearch',
      pool_size: 10
    },
    cache: {
      enabled: true,
      type: 'redis',
      ttl: 3600,
      maxSize: 1000
    },
    api: {
      rate_limit: 100,
      timeout: 30000,
      retry: 3,
      batch_size: 100
    },
    monitoring: {
      enabled: true,
      interval: 60,
      alert_threshold: 80,
      log_level: 'info'
    }
  })

  // 获取配置
  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await systemService.getConfig()
      const configData = res.data || config
      setConfig(configData)
      form.setFieldsValue(configData)
      message.success('配置加载成功')
    } catch (error) {
      message.error('加载配置失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 保存配置
  const saveConfig = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      // 合并配置
      const updatedConfig = {
        ...config,
        ...values
      }

      await systemService.updateConfig(updatedConfig)
      setConfig(updatedConfig)
      message.success('配置保存成功')
    } catch (error) {
      if (error.errorFields) {
        message.error('请检查表单填写是否正确')
      } else {
        message.error('保存配置失败')
      }
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  // 重置配置
  const resetConfig = () => {
    form.setFieldsValue(config)
    message.info('配置已重置')
  }

  // 初始加载
  useEffect(() => {
    fetchConfig()
  }, [])

  return (
    <div>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <SettingOutlined /> 系统配置
        </Title>
        <Paragraph type="secondary">
          管理系统各项参数配置，优化系统性能和行为
        </Paragraph>
      </div>

      {/* 操作按钮 */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={saveConfig}
            loading={saving}
          >
            保存配置
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={resetConfig}
          >
            重置
          </Button>
          <Button
            onClick={fetchConfig}
            loading={loading}
          >
            刷新
          </Button>
        </Space>
      </Card>

      {/* 配置表单 */}
      <Spin spinning={loading}>
        <Form
          form={form}
          layout="vertical"
          initialValues={config}
          autoComplete="off"
        >
          <Tabs activeKey={activeTab} onChange={setActiveTab}>
            {/* 基础配置 */}
            <TabPane tab={<span><SettingOutlined /> 基础配置</span>} key="basic">
              <Card>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['basic', 'appName']}
                      label="应用名称"
                      rules={[{ required: true, message: '请输入应用名称' }]}
                    >
                      <Input placeholder="输入应用名称" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['basic', 'env']}
                      label="运行环境"
                      rules={[{ required: true }]}
                    >
                      <Select placeholder="选择运行环境">
                        <Option value="dev">开发环境</Option>
                        <Option value="test">测试环境</Option>
                        <Option value="prod">生产环境</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['basic', 'timezone']}
                      label="时区设置"
                    >
                      <Select placeholder="选择时区">
                        <Option value="Asia/Shanghai">亚洲/上海</Option>
                        <Option value="Asia/Hong_Kong">亚洲/香港</Option>
                        <Option value="America/New_York">美国/纽约</Option>
                        <Option value="Europe/London">欧洲/伦敦</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['basic', 'debug']}
                      label="调试模式"
                      valuePropName="checked"
                    >
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Col>
                </Row>
                <Alert
                  message="注意"
                  description="生产环境请关闭调试模式，以免泄露敏感信息"
                  type="warning"
                  showIcon
                />
              </Card>
            </TabPane>

            {/* 服务器配置 */}
            <TabPane tab={<span><CloudServerOutlined /> 服务器配置</span>} key="server">
              <Card>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['server', 'host']}
                      label="服务器地址"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: localhost" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['server', 'port']}
                      label="服务端口"
                      rules={[{ required: true, type: 'number', min: 1, max: 65535 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        placeholder="例如: 8000"
                        min={1}
                        max={65535}
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['server', 'workers']}
                      label="工作进程数"
                      rules={[{ type: 'number', min: 1, max: 16 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={1}
                        max={16}
                        placeholder="建议为CPU核心数"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['server', 'timeout']}
                      label="请求超时(秒)"
                      rules={[{ type: 'number', min: 1 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={1}
                        placeholder="默认30秒"
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>
            </TabPane>

            {/* 数据库配置 */}
            <TabPane tab={<span><DatabaseOutlined /> 数据库配置</span>} key="database">
              <Card>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['database', 'type']}
                      label="数据库类型"
                      rules={[{ required: true }]}
                    >
                      <Select placeholder="选择数据库类型">
                        <Option value="postgresql">PostgreSQL</Option>
                        <Option value="mysql">MySQL</Option>
                        <Option value="sqlite">SQLite</Option>
                        <Option value="duckdb">DuckDB</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['database', 'host']}
                      label="数据库地址"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: localhost" />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['database', 'port']}
                      label="数据库端口"
                      rules={[{ type: 'number', min: 1, max: 65535 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        placeholder="例如: 5432"
                        min={1}
                        max={65535}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['database', 'name']}
                      label="数据库名称"
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="例如: deepsearch" />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item
                  name={['database', 'pool_size']}
                  label="连接池大小"
                  rules={[{ type: 'number', min: 1, max: 100 }]}
                >
                  <InputNumber
                    style={{ width: '100%' }}
                    min={1}
                    max={100}
                    placeholder="建议10-20"
                  />
                </Form.Item>
              </Card>
            </TabPane>

            {/* 缓存配置 */}
            <TabPane tab={<span><ThunderboltOutlined /> 缓存配置</span>} key="cache">
              <Card>
                <Form.Item
                  name={['cache', 'enabled']}
                  label="启用缓存"
                  valuePropName="checked"
                >
                  <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['cache', 'type']}
                      label="缓存类型"
                    >
                      <Select placeholder="选择缓存类型">
                        <Option value="redis">Redis</Option>
                        <Option value="memory">内存缓存</Option>
                        <Option value="file">文件缓存</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['cache', 'ttl']}
                      label="缓存时间(秒)"
                      rules={[{ type: 'number', min: 0 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={0}
                        placeholder="默认3600秒"
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item
                  name={['cache', 'maxSize']}
                  label="最大缓存数"
                  rules={[{ type: 'number', min: 1 }]}
                >
                  <InputNumber
                    style={{ width: '100%' }}
                    min={1}
                    placeholder="默认1000"
                  />
                </Form.Item>
              </Card>
            </TabPane>

            {/* API配置 */}
            <TabPane tab={<span><ApiOutlined /> API配置</span>} key="api">
              <Card>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['api', 'rate_limit']}
                      label="速率限制(次/分钟)"
                      rules={[{ type: 'number', min: 0 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={0}
                        placeholder="0表示不限制"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['api', 'timeout']}
                      label="请求超时(毫秒)"
                      rules={[{ type: 'number', min: 1000 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={1000}
                        placeholder="默认30000"
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['api', 'retry']}
                      label="重试次数"
                      rules={[{ type: 'number', min: 0, max: 10 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={0}
                        max={10}
                        placeholder="默认3次"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['api', 'batch_size']}
                      label="批处理大小"
                      rules={[{ type: 'number', min: 1, max: 1000 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={1}
                        max={1000}
                        placeholder="默认100"
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>
            </TabPane>

            {/* 监控配置 */}
            <TabPane tab={<span><SecurityScanOutlined /> 监控配置</span>} key="monitoring">
              <Card>
                <Form.Item
                  name={['monitoring', 'enabled']}
                  label="启用监控"
                  valuePropName="checked"
                >
                  <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                </Form.Item>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name={['monitoring', 'interval']}
                      label="监控间隔(秒)"
                      rules={[{ type: 'number', min: 1 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={1}
                        placeholder="默认60秒"
                      />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['monitoring', 'alert_threshold']}
                      label="告警阈值(%)"
                      rules={[{ type: 'number', min: 0, max: 100 }]}
                    >
                      <InputNumber
                        style={{ width: '100%' }}
                        min={0}
                        max={100}
                        placeholder="默认80%"
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item
                  name={['monitoring', 'log_level']}
                  label="日志级别"
                >
                  <Select placeholder="选择日志级别">
                    <Option value="debug">DEBUG</Option>
                    <Option value="info">INFO</Option>
                    <Option value="warning">WARNING</Option>
                    <Option value="error">ERROR</Option>
                  </Select>
                </Form.Item>
              </Card>
            </TabPane>
          </Tabs>
        </Form>
      </Spin>
    </div>
  )
}

export default Config
