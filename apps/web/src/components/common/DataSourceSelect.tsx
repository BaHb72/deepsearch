/**
 * DataSourceSelect - 数据源选择器
 * 允许用户切换首选数据源
 */
import React, { useEffect, useMemo, useState } from 'react'
import { Select, Space } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import type { DataSourceType, DataCapability } from '@/services/data-source'
import { getAdaptersForCapability, getAllAdapters } from '@/services/data-source'
import {
    getAllCapabilitySources,
    getSourcesForCapability,
    normalizeSources,
} from '@/services/data-source/capability-resolver'

export interface DataSourceSelectProps {
    /** 当前选中的数据源 */
    value?: DataSourceType
    /** 数据源变更回调 */
    onChange?: (source: DataSourceType | undefined) => void
    /** 限定能力，只显示支持该能力的数据源 */
    capability?: DataCapability
    /** 是否允许自动选择 */
    allowAuto?: boolean
    /** 宽度 */
    width?: number
    /** 大小 */
    size?: 'small' | 'middle' | 'large'
}

/** 数据源显示名称映射 */
const SOURCE_LABELS: Record<DataSourceType, string> = {
    miniqmt: 'MiniQMT',
    amazingdata: 'AmazingData',
    akshare: 'AkShare',
    tushare: 'TuShare',
    eastmoney: '东方财富',
}

/** 数据源颜色映射 */
export const SOURCE_COLORS: Record<DataSourceType, string> = {
    miniqmt: '#1890ff',
    amazingdata: '#52c41a',
    akshare: '#faad14',
    tushare: '#722ed1',
    eastmoney: '#eb2f96',
}

export const DataSourceSelect: React.FC<DataSourceSelectProps> = ({
    value,
    onChange,
    capability,
    allowAuto = true,
    width = 150,
    size = 'middle',
}) => {
    const localSources = useMemo<DataSourceType[]>(() => {
        const adapters = capability
            ? getAdaptersForCapability(capability)
            : getAllAdapters()
        return normalizeSources(adapters.map((adapter) => adapter.name))
    }, [capability])
    const [availableSources, setAvailableSources] = useState<DataSourceType[]>(localSources)

    useEffect(() => {
        let cancelled = false
        setAvailableSources(localSources)

        const loadAsync = async () => {
            const remoteSources = capability
                ? await getSourcesForCapability(capability)
                : await getAllCapabilitySources()
            if (cancelled || remoteSources.length === 0) {
                return
            }
            setAvailableSources(remoteSources)
        }
        void loadAsync()

        return () => {
            cancelled = true
        }
    }, [capability, localSources])

    const uniqueSources = useMemo(() => {
        const seen = new Set<string>()
        return availableSources.filter((source) => {
            if (seen.has(source)) {
                return false
            }
            seen.add(source)
            return true
        })
    }, [availableSources])

    const options = [
        ...(allowAuto ? [{ value: undefined, label: '自动选择' }] : []),
        ...uniqueSources.map((source) => ({
            value: source,
            label: (
                <Space size={4}>
                    <span style={{ color: SOURCE_COLORS[source] }}>●</span>
                    <span>{SOURCE_LABELS[source] || source}</span>
                </Space>
            ),
        })),
    ]

    const selectedValue =
        value && uniqueSources.includes(value) ? value : undefined

    const handleChange = (nextValue: DataSourceType | undefined) => {
        onChange?.(nextValue)
    }

    return (
        <Select
            value={selectedValue}
            onChange={handleChange}
            options={options}
            style={{ width }}
            size={size}
            placeholder="选择数据源"
            allowClear={allowAuto}
            suffixIcon={<DatabaseOutlined />}
        />
    )
}

export default DataSourceSelect
