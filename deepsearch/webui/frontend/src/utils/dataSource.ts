/**
 * 数据源名称与列表格式化工具
 */

export const DEFAULT_REALTIME_SOURCES = ['amazingdata', 'akshare'] as const

export const normalizeDataSourceValue = (value?: string | null): string | null => {
  if (!value || typeof value !== 'string') {
    return null
  }
  const normalized = value.trim().toLowerCase()
  return normalized.length ? normalized : null
}

export const normalizeDataSourceList = (
  sources?: Iterable<string | null | undefined>,
  fallback: readonly string[] = DEFAULT_REALTIME_SOURCES
): string[] => {
  const unique: string[] = []

  if (sources) {
    for (const item of sources) {
      const normalized = normalizeDataSourceValue(item)
      if (normalized && !unique.includes(normalized)) {
        unique.push(normalized)
      }
    }
  }

  if (!unique.length) {
    return [...fallback]
  }

  return unique
}

export const formatDataSourceLabel = (value?: string | null): string => {
  const normalized = normalizeDataSourceValue(value)
  if (!normalized) {
    return '未知数据源'
  }
  if (normalized === 'amazingdata') {
    return 'AmazingData'
  }
  if (normalized === 'akshare') {
    return 'AkShare'
  }
  if (normalized === 'cloudflare') {
    return 'AkShare Proxy'
  }
  return value ?? normalized
}
