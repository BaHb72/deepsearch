/**
 * 时间格式化工具函数
 *
 * 专门处理 A 股交易时间的格式化，确保使用北京时区 (Asia/Shanghai)
 */

/**
 * 将时间戳转换为北京时间的 HH:MM 格式字符串
 *
 * 根据 TradingView Lightweight Charts 官方文档，图表库不支持原生时区，
 * 需要在传入数据前手动进行时区转换。
 *
 * @param timestamp 毫秒级时间戳
 * @returns 格式化后的时间字符串，如 "09:30"
 */
export function timestampToBeijingTime(timestamp: number): string {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}

/**
 * 将时间戳转换为北京时间的完整日期时间格式
 *
 * @param timestamp 毫秒级时间戳
 * @returns 格式化后的日期时间字符串，如 "2024-12-29 09:30"
 */
export function timestampToBeijingDateTime(timestamp: number): string {
    return new Date(timestamp).toLocaleString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}

/**
 * 将 Date 对象转换为北京时间的 HH:MM 格式字符串
 *
 * @param date Date 对象
 * @returns 格式化后的时间字符串
 */
export function dateToBeijingTime(date: Date): string {
    return date.toLocaleTimeString('zh-CN', {
        timeZone: 'Asia/Shanghai',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}
