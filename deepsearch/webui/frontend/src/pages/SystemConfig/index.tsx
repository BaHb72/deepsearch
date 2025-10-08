import React, { useState } from 'react'
import { Tabs } from 'antd'
import {
  DatabaseOutlined,
  ApiOutlined,
  AppstoreOutlined,
  BellOutlined
} from '@ant-design/icons'
import DatabaseConfigWithStore from './DatabaseConfigWithStore'
import DataSourceConfig from './DataSourceConfig'
import SystemModules from './SystemModules'
import NotificationConfig from './NotificationConfig'

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
