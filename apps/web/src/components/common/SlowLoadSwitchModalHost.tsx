import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Modal, Select, Space, Tag, Typography } from 'antd'
import type { DataSourceType } from '@/services/data-source'
import { SOURCE_COLORS } from './DataSourceSelect'
import { useSlowLoadSwitchStore } from '@/stores/slowLoadSwitch.store'
import messageManager from '@/utils/messageManager'

const SOURCE_LABELS: Record<DataSourceType, string> = {
    miniqmt: 'MiniQMT',
    amazingdata: 'AmazingData',
    akshare: 'AkShare',
    tushare: 'TuShare',
    eastmoney: '东方财富',
}

function formatSource(source?: DataSourceType): string {
    if (!source) {
        return '自动路由'
    }
    return SOURCE_LABELS[source] || source
}

function formatTrigger(trigger: 'elapsed_timeout' | 'provider_reason', elapsedMs?: number): string {
    if (trigger === 'elapsed_timeout') {
        if (typeof elapsedMs === 'number' && elapsedMs > 0) {
            return `前端等待 ${Math.round(elapsedMs / 1000)} 秒仍未完成`
        }
        return '前端等待超时'
    }
    return '后端返回数据源异常轨迹'
}

const SlowLoadSwitchModalHost: React.FC = () => {
    const active = useSlowLoadSwitchStore((state) => state.active)
    const dismissCurrent = useSlowLoadSwitchStore((state) => state.dismissCurrent)
    const switchCurrent = useSlowLoadSwitchStore((state) => state.switchCurrent)

    const [selectedTarget, setSelectedTarget] = useState<DataSourceType | undefined>()
    const [switching, setSwitching] = useState(false)

    useEffect(() => {
        if (!active || active.candidateSources.length === 0) {
            setSelectedTarget(undefined)
            return
        }
        setSelectedTarget(active.candidateSources[0])
    }, [active])

    const targetOptions = useMemo(() => {
        if (!active) {
            return []
        }
        return active.candidateSources.map((source) => ({
            value: source,
            label: (
                <Space size={6}>
                    <span style={{ color: SOURCE_COLORS[source] || '#999' }}>●</span>
                    <span>{formatSource(source)}</span>
                </Space>
            ),
        }))
    }, [active])
    const canSwitch = Boolean(
        active &&
        active.onSwitchSource &&
        targetOptions.length > 0 &&
        selectedTarget
    )

    const handleSwitch = async () => {
        if (!active || !selectedTarget) {
            return
        }
        setSwitching(true)
        try {
            await switchCurrent(selectedTarget)
            messageManager.success(`已切换到 ${formatSource(selectedTarget)}`)
        } catch (error) {
            const text = error instanceof Error ? error.message : '切换失败，请稍后重试'
            messageManager.error(text)
        } finally {
            setSwitching(false)
        }
    }

    return (
        <Modal
            title="检测到模块加载过慢"
            open={Boolean(active)}
            onCancel={dismissCurrent}
            okText={canSwitch ? '切换数据源' : '我知道了'}
            cancelText="继续等待"
            onOk={canSwitch ? handleSwitch : dismissCurrent}
            confirmLoading={switching}
            cancelButtonProps={canSwitch ? undefined : { style: { display: 'none' } }}
            destroyOnHidden
            maskClosable
        >
            {active && (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <Space wrap size={8}>
                        <Tag color="blue">页面：{active.pageName}</Tag>
                        <Tag color="cyan">模块：{active.moduleName}</Tag>
                        <Tag>能力：{active.capability}</Tag>
                    </Space>

                    <Typography.Text>
                        当前慢数据源：<Typography.Text strong>{formatSource(active.currentSource)}</Typography.Text>
                    </Typography.Text>

                    <Alert
                        type="warning"
                        showIcon
                        message={formatTrigger(active.trigger, active.elapsedMs)}
                        description={active.reasonDetail || active.reasonCode || '暂无详细错误信息'}
                    />

                    {targetOptions.length > 0 ? (
                        <Space direction="vertical" size={6} style={{ width: '100%' }}>
                            <Typography.Text>可切换数据源</Typography.Text>
                            <Select
                                style={{ width: '100%' }}
                                value={selectedTarget}
                                options={targetOptions}
                                onChange={(value) => setSelectedTarget(value)}
                            />
                        </Space>
                    ) : (
                        <Alert
                            type="info"
                            showIcon
                            message="没有可切换的数据源"
                            description="当前能力在可用数据源中没有替代选项，你可以继续等待本次请求。"
                        />
                    )}
                </Space>
            )}
        </Modal>
    )
}

export default SlowLoadSwitchModalHost
