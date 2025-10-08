/**
 * 数据源状态标签与提示映射
 */

export type DataSourceStatusValue =
  | 'draft'
  | 'pending_test'
  | 'testing'
  | 'ready'
  | 'active'
  | 'degraded'
  | 'error'
  | 'offline'

export type DataSourceStatusBadge = 'success' | 'processing' | 'default' | 'error' | 'warning'

export interface DataSourceStatusMeta {
  /** 原始状态值（规范化后） */
  value: DataSourceStatusValue | 'unknown'
  /** 展示文案 */
  text: string
  /** Tooltip 提示 */
  description: string
  /** Ant Design Badge status */
  badgeStatus: DataSourceStatusBadge
  /** Tag 颜色 */
  tagColor: string
}

const STATUS_META_MAP: Record<DataSourceStatusValue, DataSourceStatusMeta> = {
  draft: {
    value: 'draft',
    text: '未配置',
    description: '配置未完成或尚未保存，无法进行测试',
    badgeStatus: 'default',
    tagColor: '#bfbfbf',
  },
  pending_test: {
    value: 'pending_test',
    text: '待测试',
    description: '配置已保存，等待执行连通性测试',
    badgeStatus: 'default',
    tagColor: '#8c8c8c',
  },
  testing: {
    value: 'testing',
    text: '测试中',
    description: '后端正在执行连通性测试，请稍候',
    badgeStatus: 'processing',
    tagColor: '#1890ff',
  },
  ready: {
    value: 'ready',
    text: '可启用',
    description: '最近一次测试通过但尚未启用，可随时开启',
    badgeStatus: 'processing',
    tagColor: '#13c2c2',
  },
  active: {
    value: 'active',
    text: '已启用',
    description: '数据源已启用且监控健康',
    badgeStatus: 'success',
    tagColor: '#52c41a',
  },
  degraded: {
    value: 'degraded',
    text: '性能异常',
    description: '已启用但监控检测到性能或稳定性异常',
    badgeStatus: 'warning',
    tagColor: '#faad14',
  },
  error: {
    value: 'error',
    text: '错误',
    description: '测试或运行失败，请检查配置和日志',
    badgeStatus: 'error',
    tagColor: '#f5222d',
  },
  offline: {
    value: 'offline',
    text: '已停用',
    description: '数据源已手动停用，重新启用前建议重新测试',
    badgeStatus: 'default',
    tagColor: '#595959',
  },
}

const UNKNOWN_META: DataSourceStatusMeta = {
  value: 'unknown',
  text: '未知状态',
  description: '未识别的数据源状态，请检查后端返回值',
  badgeStatus: 'default',
  tagColor: '#d9d9d9',
}

/**
 * 状态展示顺序，供卡片和图表复用
 */
export const DATA_SOURCE_STATUS_ORDER: ReadonlyArray<Exclude<DataSourceStatusValue, 'draft'>> = [
  'pending_test',
  'testing',
  'ready',
  'active',
  'degraded',
  'error',
  'offline',
]

/**
 * 根据状态值获取展示元数据，自动完成大小写归一化
 */
export const getDataSourceStatusMeta = (status?: string | null): DataSourceStatusMeta => {
  if (!status) {
    return UNKNOWN_META
  }

  const normalized = status.toLowerCase() as DataSourceStatusValue
  if (normalized in STATUS_META_MAP) {
    return STATUS_META_MAP[normalized as DataSourceStatusValue]
  }

  return UNKNOWN_META
}

/**
 * 导出底层映射，供需要遍历全部状态的场景使用
 */

export const normalizeTestSummary = (value: unknown): string | null => {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  if (Array.isArray(value)) {
    const parts = value
      .map(item => normalizeTestSummary(item))
      .filter((item): item is string => typeof item === 'string' && item.length > 0)

    if (parts.length > 0) {
      return parts.join('，')
    }

    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>
    const fragments: string[] = []

    if (typeof record.success === 'boolean') {
      fragments.push(record.success ? '测试成功' : '测试失败')
    }

    const symbolCandidate =
      typeof record.symbol === 'string' && record.symbol.trim().length > 0
        ? record.symbol.trim()
        : typeof record.code === 'string' && record.code.trim().length > 0
          ? record.code.trim()
          : typeof record.target === 'string' && record.target.trim().length > 0
            ? record.target.trim()
            : typeof record.instrument === 'string' && record.instrument.trim().length > 0
              ? record.instrument.trim()
              : null

    if (symbolCandidate) {
      fragments.push('标的: ' + symbolCandidate)
    }

    const latencyCandidate = record.latency_ms ?? record.latencyMs ?? record.latency
    if (latencyCandidate !== undefined && latencyCandidate !== null) {
      const latencyNumber =
        typeof latencyCandidate === 'number'
          ? latencyCandidate
          : Number(latencyCandidate)

      if (Number.isFinite(latencyNumber)) {
        fragments.push('耗时: ' + Math.round(latencyNumber) + 'ms')
      }
    }

    const messageCandidate =
      typeof record.message === 'string' && record.message.trim().length > 0
        ? record.message.trim()
        : typeof record.error === 'string' && record.error.trim().length > 0
          ? record.error.trim()
          : typeof record.note === 'string' && record.note.trim().length > 0
            ? record.note.trim()
            : typeof record.detail === 'string' && record.detail.trim().length > 0
              ? record.detail.trim()
              : typeof record.details === 'string' && record.details.trim().length > 0
                ? record.details.trim()
                : null

    if (messageCandidate) {
      fragments.push(messageCandidate)
    }

    if (fragments.length > 0) {
      return fragments.join(' • ')
    }

    try {
      return JSON.stringify(record)
    } catch {
      return String(record)
    }
  }

  return String(value)
}


export const DATA_SOURCE_STATUS_META = STATUS_META_MAP

export default {
  DATA_SOURCE_STATUS_ORDER,
  DATA_SOURCE_STATUS_META,
  getDataSourceStatusMeta,
  normalizeTestSummary,
}