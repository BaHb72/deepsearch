import React from 'react'
import { Select, Space, Tag } from 'antd'

interface ModuleSourceSelectorProps {
    moduleKey: string
    value: string | null
    options: { label: string; value: string }[]
    fallbackLabel?: string | null
    onChange: (moduleKey: string, value: string) => void
}

const ModuleSourceSelector: React.FC<ModuleSourceSelectorProps> = ({
    moduleKey,
    value,
    options,
    fallbackLabel,
    onChange,
}) => {
    return (
        <Space size="small">
            <Select
                size="small"
                style={{ width: 120 }}
                value={value ?? ''}
                options={options}
                onChange={(val) => onChange(moduleKey, val as string)}
            />
            {fallbackLabel ? <Tag color="orange">{fallbackLabel}</Tag> : null}
        </Space>
    )
}

export default ModuleSourceSelector
