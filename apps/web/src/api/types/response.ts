/**
 * 后端 API 统一响应类型定义
 *
 * 解决问题：
 * - axios 拦截器返回 response.data，实际类型与泛型声明不符
 * - 开发者被迫写 res.data.data 这样的错误二次解包
 *
 * 这些类型准确描述后端实际返回的数据结构
 */

/**
 * 后端统一响应格式
 * 对应后端 FastAPI 返回的标准响应结构
 */
export interface BackendResponse<T = unknown> {
    /** 请求是否成功 */
    success: boolean
    /** 响应时间戳 */
    timestamp: string
    /** 响应数据（成功时存在） */
    data?: T
    /** 错误信息（失败时存在） */
    error?: string
    /** 错误堆栈（调试模式下存在） */
    traceback?: string
}

/**
 * DataFrame 转换后的数据格式
 * 用于 pandas DataFrame 转换为 JSON 后的标准结构
 */
export interface DataFrameData<T = Record<string, unknown>> {
    /** 数据行（records 格式） */
    data: T[]
    /** 列名列表 */
    columns: string[]
    /** 数据行数 */
    count: number
    /** 列数据类型（可选） */
    dtypes?: Record<string, string>
}

/**
 * 分页响应格式
 */
export interface PaginatedData<T = Record<string, unknown>> {
    /** 数据列表 */
    items: T[]
    /** 总数 */
    total: number
    /** 当前页 */
    page: number
    /** 每页大小 */
    page_size: number
}
