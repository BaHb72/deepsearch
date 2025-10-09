import React from 'react'
import { Badge, Dropdown, Button, Empty, List } from 'antd'
import { BellOutlined, CloseOutlined } from '@ant-design/icons'

const NotificationCenter = ({ notifications = [], onClear }) => {
  const menu = {
    items: notifications.length > 0 ? [
      {
        key: 'notifications',
        label: (
          <List
            dataSource={notifications}
            renderItem={item => (
              <List.Item>
                <List.Item.Meta
                  title={item.title}
                  description={item.description}
                />
              </List.Item>
            )}
          />
        )
      },
      {
        type: 'divider'
      },
      {
        key: 'clear',
        label: '清空所有',
        icon: <CloseOutlined />,
        onClick: onClear
      }
    ] : [
      {
        key: 'empty',
        label: <Empty description="暂无通知" />
      }
    ]
  }

  return (
    <Dropdown menu={menu} placement="bottomRight">
      <Badge count={notifications.length}>
        <Button type="text" icon={<BellOutlined />} />
      </Badge>
    </Dropdown>
  )
}

export default NotificationCenter