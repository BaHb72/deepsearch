import React, {useMemo} from 'react'
import {Segmented, Spin, Switch, Tooltip} from 'antd'

import {
  DEFAULT_REALTIME_SOURCES,
  formatDataSourceLabel,
  normalizeDataSourceList,
  normalizeDataSourceValue,
} from '@/utils/dataSource'

export interface DataSourceSwitchProps {
  sources?: string[]
  value?: string | null
  size?: 'small' | 'middle' | 'large'
  loading?: boolean
  disabled?: boolean
  tooltip?: React.ReactNode
  onChange?: (value: string) => void
}

const DataSourceSwitch: React.FC<DataSourceSwitchProps> = ({
  sources,
  value,
  size = 'middle',
  loading = false,
  disabled = false,
  tooltip = '切换行情数据源',
  onChange,
}) => {
  const normalizedSources = useMemo(() => normalizeDataSourceList(sources), [sources])
  const fallback = normalizedSources[0] ?? DEFAULT_REALTIME_SOURCES[0]
  const active = normalizeDataSourceValue(value) ?? fallback
  const switchDisabled = disabled || loading || normalizedSources.length <= 1

  const emitChange = (next: string) => {
    if (!next || next === active || switchDisabled) {
      return
    }
    onChange?.(next)
  }

  if (normalizedSources.length <= 1) {
    return (
      <Tooltip title="当前仅启用了一个行情数据源">
        <span>{formatDataSourceLabel(active)}</span>
      </Tooltip>
    )
  }

  if (normalizedSources.length === 2) {
    const [primary, secondary] = normalizedSources
    const checked = active === secondary
    return (
      <Tooltip title={tooltip}>
        <Switch
          checked={checked}
          onChange={(checkedValue) => emitChange(checkedValue ? secondary : primary)}
          checkedChildren={formatDataSourceLabel(secondary)}
          unCheckedChildren={formatDataSourceLabel(primary)}
          loading={loading}
          disabled={disabled || loading}
        />
      </Tooltip>
    )
  }

  return (
    <Tooltip title={tooltip}>
      <Spin spinning={loading} size="small">
        <Segmented
          value={active}
          onChange={(val) => emitChange(String(val))}
          size={size}
          disabled={disabled || loading}
          options={normalizedSources.map((source) => ({
            value: source,
            label: formatDataSourceLabel(source),
          }))}
        />
      </Spin>
    </Tooltip>
  )
}

export default DataSourceSwitch
