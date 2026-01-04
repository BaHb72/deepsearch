import React from 'react'
import {PageContainer} from '@ant-design/pro-components'
import {Button, Result} from 'antd'
import {MonitorOutlined} from '@ant-design/icons'

const ComponentManager: React.FC = () => {
  return (
      <PageContainer
          header={{
              title: '组件管理',
              ghost: true,
          }}
      >
          <Result
              icon={<MonitorOutlined/>}
              title="功能开发中"
              subTitle="组件管理功能即将上线，敬请期待。"
              extra={<Button type="primary">返回首页</Button>}
          />
      </PageContainer>
  )
}

export default ComponentManager
