import dayjs from 'dayjs'

export const CLASSIFICATION_META: Record<string, { label: string; color: string }> = {
    single_core: { label: '单核驱动', color: 'gold' },
    multi_core: { label: '多核扩散', color: 'green' },
    mixed: { label: '混合结构', color: 'blue' },
    unknown: { label: '待识别', color: 'default' },
}

const numberFormatter = new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
})
const percentFormatter = new Intl.NumberFormat('zh-CN', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
})

export const formatAmountBillion = (value?: number | null) => {
    if (value === undefined || value === null) {
        return '--'
    }
    return `${numberFormatter.format(value / 1e8)} 亿`
}

export const formatAmountMillionPerMinute = (value?: number | null) => {
    if (value === undefined || value === null) {
        return '--'
    }
    return `${numberFormatter.format(value / 1e6)} 百万/分钟`
}

export const formatAmountMillionPerMinuteSquared = (value?: number | null) => {
    if (value === undefined || value === null) {
        return '--'
    }
    return `${numberFormatter.format(value / 1e6)} 百万/分钟²`
}

export const formatPercent = (value?: number | null) => {
    if (value === undefined || value === null) {
        return '--'
    }
    return percentFormatter.format(value)
}

export const formatNumber = (value?: number | null, fraction = 2) => {
    if (value === undefined || value === null) {
        return '--'
    }
    const customFormatter = new Intl.NumberFormat('zh-CN', {
        minimumFractionDigits: fraction,
        maximumFractionDigits: fraction,
    })
    return customFormatter.format(value)
}

export const formatTime = (value?: string | null) => {
    if (!value) {
        return '--'
    }
    return dayjs(value).format('HH:mm:ss')
}
