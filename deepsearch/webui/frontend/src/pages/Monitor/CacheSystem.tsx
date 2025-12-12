import React from 'react'
import {PageContainer} from '@ant-design/pro-components'
import {Button, Result} from 'antd'
import {GlobalOutlined} from '@ant-design/icons'

const CacheSystem: React.FC = () => {
  return (
      <PageContainer
          header={{
              title: '缓存系统监控',
              ghost: true,
          }}
      >
          <Result
              icon={<GlobalOutlined/>}
              title="功能开发中"
              subTitle="缓存系统监控功能即将上线，敬请期待。"
              extra={<Button type="primary">返回首页</Button>}
          />
      </PageContainer>
  )
}

export default CacheSystem
