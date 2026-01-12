import React from 'react'
import {PageContainer} from '@ant-design/pro-components'
import {Button, Result} from 'antd'
import {BellOutlined} from '@ant-design/icons'

const AlertManager: React.FC = () => {
  return (
      <PageContainer
          header={{
              title: '告警管理',
              ghost: true,
          }}
      >
          <Result
              icon={<BellOutlined/>}
              title="功能开发中"
              subTitle="告警管理功能即将上线，敬请期待。"
              extra={<Button type="primary">返回首页</Button>}
          />
      </PageContainer>
  )
}

export default AlertManager
