/**
 * 通用格式化工具函数
 */

/** 金额格式化 (显示万/亿单位) */
export const formatAmount = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-'
    const absValue = Math.abs(value)
    if (absValue >= 100000000) {
        return `${(value / 100000000).toFixed(2)}亿`
    } else if (absValue >= 10000) {
        return `${(value / 10000).toFixed(2)}万`
    }
    return value.toFixed(2)
}

/** 百分比格式化 */
export const formatPercent = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-'
    return `${value.toFixed(2)}%`
}

/** 时间格式化 (时间戳转可读格式) */
export const formatTime = (value: number | string | null | undefined): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'string') return value
    const date = new Date(value)
    if (isNaN(date.getTime())) return String(value)
    return `${date.getFullYear()}年${String(date.getMonth() + 1).padStart(2, '0')}月${String(date.getDate()).padStart(2, '0')}日 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

/** 移除申万行业前缀 (如 SW3 -> 行业名) */
export const removeSectorPrefix = (name: string): string => {
    if (!name) return name
    // 移除 SW1, SW2, SW3 等前缀
    return name.replace(/^SW\d+/, '')
}
