import { useState } from 'react'
import { Tabs } from 'antd'
import {
  ApiOutlined,
  AppstoreOutlined,
  BellOutlined,
  DatabaseOutlined,
  FileZipOutlined,
  NodeIndexOutlined
} from '@ant-design/icons'
import DatabaseConfigWithStore from './DatabaseConfigWithStore'
import DataSourceConfig from './DataSourceConfig'
import ModuleSourceConfig from './ModuleSourceConfig'
import SystemModules from './SystemModules'
import NotificationConfig from './NotificationConfig'
import LogConfig from './LogConfig'

/**
 * 系统配置主页面
 * 集成数据库配置、数据源管理和系统模块管理
 */
const SystemConfig = () => {
  const [activeTab, setActiveTab] = useState('database')

  const tabItems = [
    {
      key: 'database',
      label: (
        <span>
          <DatabaseOutlined />
          数据库配置
        </span>
      ),
      children: <DatabaseConfigWithStore />
    },
    {
      key: 'datasource',
      label: (
        <span>
          <ApiOutlined />
          数据源管理
        </span>
      ),
      children: <DataSourceConfig />
    },
    {
      key: 'module-sources',
      label: (
        <span>
          <NodeIndexOutlined />
          模块数据源
        </span>
      ),
      children: <ModuleSourceConfig />
    },
    {
      key: 'log',
      label: (
        <span>
          <FileZipOutlined />
          日志配置
        </span>
      ),
      children: <LogConfig />
    },
    {
      key: 'notification',
      label: (
        <span>
          <BellOutlined />
          通知配置
        </span>
      ),
      children: <NotificationConfig />
    },
    {
      key: 'modules',
      label: (
        <span>
          <AppstoreOutlined />
          系统模块
        </span>
      ),
      children: <SystemModules />
    }
  ]

  return (
    <div style={{ padding: '24px' }}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="large"
        tabBarStyle={{ marginBottom: 24 }}
        items={tabItems}
      />
    </div>
  )
}

export default SystemConfig

