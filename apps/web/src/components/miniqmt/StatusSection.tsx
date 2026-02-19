/**
 * 连接状态组件
 * 展示统一数据查询能力状态
 */
import React, { useState, useEffect } from 'react'
import { Card, Spin, Tag, Button, Space, Typography } from 'antd'
import { ReloadOutlined, StockOutlined } from '@ant-design/icons'
import unifiedDataApi from '@/api/unifiedData'

const { Text } = Typography

export interface StatusSectionProps {
    /** 是否自动加载 */
    autoLoad?: boolean
    /** 是否显示为卡片模式 */
    cardMode?: boolean
}

export const StatusSection: React.FC<StatusSectionProps> = ({
    autoLoad = true,
    cardMode = true,
}) => {
    const [loading, setLoading] = useState(false)
    const [status, setStatus] = useState<Record<string, unknown> | null>(null)

    const fetchStatus = async () => {
        setLoading(true)
        try {
            const res = await unifiedDataApi.getCapabilities()
            if ((res as any).success) {
                setStatus((res as any).data as Record<string, unknown>)
            }
        } catch (err) {
            console.warn('获取状态失败', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (autoLoad) {
            fetchStatus()
        }
    }, [autoLoad])

    const content = (
        <Spin spinning={loading}>
            {status ? (
                <Space direction="vertical" size="small">
                    <div>
                        <Text strong>统一查询: </Text>
                        <Tag color={status.available ? 'green' : 'red'}>
                            {status.available ? '可用' : '不可用'}
                        </Tag>
                    </div>
                    <div>
                        <Text strong>实时行情优先链路: </Text>
                        <Tag color="blue">
                            {Array.isArray((status.capabilities as any)?.realtime_quote)
                                ? ((status.capabilities as any).realtime_quote as string[]).join(' -> ')
                                : '-'}
                        </Tag>
                    </div>
                    <div>
                        <Text strong>K线优先链路: </Text>
                        <Tag color="purple">
                            {Array.isArray((status.capabilities as any)?.stock_kline)
                                ? ((status.capabilities as any).stock_kline as string[]).join(' -> ')
                                : '-'}
                        </Tag>
                    </div>
                    {(status.message as string | undefined) ? (
                        <div>
                            <Text type="secondary">{String(status.message)}</Text>
                        </div>
                    ) : null}
                </Space>
            ) : (
                <Text type="secondary">加载中...</Text>
            )}
        </Spin>
    )

    if (!cardMode) {
        return content
    }

    return (
        <Card
            title={
                <Space>
                    <StockOutlined />
                    <span>连接状态</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchStatus} loading={loading} size="small">
                    刷新
                </Button>
            }
            size="small"
        >
            {content}
        </Card>
    )
}
