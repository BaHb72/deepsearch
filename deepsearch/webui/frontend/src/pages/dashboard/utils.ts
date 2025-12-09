export const formatDuration = (seconds?: number) => {
    if (!seconds || !Number.isFinite(seconds) || seconds <= 0) {
        return '--'
    }
    const totalMinutes = Math.floor(seconds / 60)
    const days = Math.floor(totalMinutes / (24 * 60))
    const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
    const minutes = totalMinutes % 60

    const parts: string[] = []
    if (days > 0) {
        parts.push(days + '天')
    }
    if (hours > 0) {
        parts.push(hours + '小时')
    }
    if (minutes > 0 && days === 0) {
        parts.push(minutes + '分钟')
    }
    if (parts.length === 0) {
        return '不足1分钟'
    }
    return parts.join(' ')
}

export const formatDateTime = (value?: string | number | Date | null) => {
    if (!value) {
        return '--'
    }

    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) {
        return '--'
    }

    const pad = (num: number) => num.toString().padStart(2, '0')

    return (
        date.getFullYear() +
        '-' +
        pad(date.getMonth() + 1) +
        '-' +
        pad(date.getDate()) +
        ' ' +
        pad(date.getHours()) +
        ':' +
        pad(date.getMinutes()) +
        ':' +
        pad(date.getSeconds())
    )
}

export const formatSuccessRate = (value?: number | null) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return null
    }
    const percent = value <= 1 ? value * 100 : value
    return percent.toFixed(1) + '%'
}

export const getRecommendationByStatus = (status: string) => {
    switch (status) {
        case 'error':
            return '请检查凭据与网络连通性，必要时执行手动重连。'
        case 'offline':
            return '确认数据源是否维护或下线，考虑切换备用线路。'
        case 'degraded':
            return '关注延迟与错误率，适时调整限流或缓存策略。'
        default:
            return '查看运行日志并确认是否需要人工干预。'
    }
}
