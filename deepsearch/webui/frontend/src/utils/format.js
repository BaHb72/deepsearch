/**
 * 格式化工具函数集合
 */

/**
 * 格式化数字
 * @param {number} value - 数值
 * @param {number} precision - 小数位数
 * @returns {string} 格式化后的字符串
 */
export function formatNumber(value, precision = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '-'
    }
    return parseFloat(value).toFixed(precision)
}

/**
 * 格式化成交量
 * @param {number} volume - 成交量
 * @returns {string} 格式化后的字符串
 */
export function formatVolume(volume) {
    if (!volume || volume === 0) return '0'

    if (volume >= 100000000) {
        return (volume / 100000000).toFixed(2) + '亿'
    } else if (volume >= 10000) {
        return (volume / 10000).toFixed(2) + '万'
    } else {
        return volume.toString()
    }
}

/**
 * 格式化成交额
 * @param {number} amount - 成交额
 * @returns {string} 格式化后的字符串
 */
export function formatAmount(amount) {
    if (!amount || amount === 0) return '0'

    if (amount >= 100000000) {
        return '¥' + (amount / 100000000).toFixed(2) + '亿'
    } else if (amount >= 10000) {
        return '¥' + (amount / 10000).toFixed(2) + '万'
    } else {
        return '¥' + amount.toFixed(2)
    }
}

/**
 * 格式化百分比
 * @param {number} value - 百分比值
 * @param {number} precision - 小数位数
 * @returns {string} 格式化后的字符串
 */
export function formatPercent(value, precision = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0.00'
    }
    return parseFloat(value).toFixed(precision)
}

/**
 * 格式化市值
 * @param {number} marketCap - 市值
 * @returns {string} 格式化后的字符串
 */
export function formatMarketCap(marketCap) {
    if (!marketCap || marketCap === 0) return '-'

    if (marketCap >= 1000000000000) {
        return (marketCap / 1000000000000).toFixed(2) + '万亿'
    } else if (marketCap >= 100000000) {
        return (marketCap / 100000000).toFixed(2) + '亿'
    } else if (marketCap >= 10000) {
        return (marketCap / 10000).toFixed(2) + '万'
    } else {
        return marketCap.toString()
    }
}

/**
 * 格式化时间
 * @param {string|Date} time - 时间
 * @param {string} format - 格式
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(time, format = 'HH:mm:ss') {
    if (!time) return '-'

    const date = time instanceof Date ? time : new Date(time)

    if (format === 'HH:mm:ss') {
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const seconds = date.getSeconds().toString().padStart(2, '0')
        return `${hours}:${minutes}:${seconds}`
    } else if (format === 'YYYY-MM-DD') {
        const year = date.getFullYear()
        const month = (date.getMonth() + 1).toString().padStart(2, '0')
        const day = date.getDate().toString().padStart(2, '0')
        return `${year}-${month}-${day}`
    } else if (format === 'YYYY-MM-DD HH:mm:ss') {
        const year = date.getFullYear()
        const month = (date.getMonth() + 1).toString().padStart(2, '0')
        const day = date.getDate().toString().padStart(2, '0')
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const seconds = date.getSeconds().toString().padStart(2, '0')
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    } else if (format === 'MM-DD HH:mm') {
        const month = (date.getMonth() + 1).toString().padStart(2, '0')
        const day = date.getDate().toString().padStart(2, '0')
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        return `${month}-${day} ${hours}:${minutes}`
    }

    return date.toLocaleString()
}

/**
 * 格式化价格变化
 * @param {number} change - 价格变化
 * @param {number} changePercent - 变化百分比
 * @returns {string} 格式化后的字符串
 */
export function formatPriceChange(change, changePercent) {
    if (change === null || change === undefined) return '-'

    const sign = change > 0 ? '+' : ''
    const changeStr = sign + formatNumber(change)
    const percentStr = sign + formatPercent(changePercent) + '%'

    return `${changeStr} (${percentStr})`
}

/**
 * 格式化大数字（K/M/B）
 * @param {number} num - 数字
 * @returns {string} 格式化后的字符串
 */
export function formatLargeNumber(num) {
    if (!num || num === 0) return '0'

    const abs = Math.abs(num)
    const sign = num < 0 ? '-' : ''

    if (abs >= 1000000000) {
        return sign + (abs / 1000000000).toFixed(2) + 'B'
    } else if (abs >= 1000000) {
        return sign + (abs / 1000000).toFixed(2) + 'M'
    } else if (abs >= 1000) {
        return sign + (abs / 1000).toFixed(2) + 'K'
    } else {
        return sign + abs.toString()
    }
}

/**
 * 格式化指标值
 * @param {any} value - 指标值
 * @returns {string} 格式化后的字符串
 */
export function formatIndicatorValue(value) {
    if (value === null || value === undefined) return '-'

    if (typeof value === 'boolean') {
        return value ? '是' : '否'
    }

    if (typeof value === 'number') {
        if (Math.abs(value) >= 10000) {
            return formatLargeNumber(value)
        }
        return formatNumber(value)
    }

    if (Array.isArray(value)) {
        return value.map(v => formatIndicatorValue(v)).join(', ')
    }

    return String(value)
}

/**
 * 格式化持续时间
 * @param {number} milliseconds - 毫秒数
 * @returns {string} 格式化后的字符串
 */
export function formatDuration(milliseconds) {
    if (!milliseconds || milliseconds < 0) return '0ms'

    if (milliseconds < 1000) {
        return milliseconds + 'ms'
    } else if (milliseconds < 60000) {
        return (milliseconds / 1000).toFixed(1) + 's'
    } else if (milliseconds < 3600000) {
        return (milliseconds / 60000).toFixed(1) + 'm'
    } else {
        return (milliseconds / 3600000).toFixed(1) + 'h'
    }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的字符串
 */
export function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B'

    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let index = 0
    let size = bytes

    while (size >= 1024 && index < units.length - 1) {
        size /= 1024
        index++
    }

    return size.toFixed(2) + ' ' + units[index]
}

/**
 * 获取价格颜色类名
 * @param {number} value - 数值
 * @returns {string} CSS类名
 */
export function getPriceColorClass(value) {
    if (value > 0) return 'price-up'
    if (value < 0) return 'price-down'
    return 'price-flat'
}

/**
 * 获取涨跌颜色
 * @param {number} value - 数值
 * @returns {string} 颜色值
 */
export function getPriceColor(value) {
    if (value > 0) return '#f5222d'  // 红色（涨）- 中国市场标准
    if (value < 0) return '#52c41a'  // 绿色（跌）- 中国市场标准
    return '#8c8c8c'  // 灰色（平）
}

// 导出所有函数
export default {
    formatNumber,
    formatVolume,
    formatAmount,
    formatPercent,
    formatMarketCap,
    formatTime,
    formatPriceChange,
    formatLargeNumber,
    formatIndicatorValue,
    formatDuration,
    formatFileSize,
    getPriceColorClass,
    getPriceColor
}