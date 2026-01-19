/**
 * 类型安全的 API 请求包装器
 *
 * 解决问题：
 * - axios 的泛型 request.get<T>() 返回 Promise<AxiosResponse<T>>
 * - 但响应拦截器已经返回 response.data，实际返回 Promise<T>
 * - 这导致类型与实际不符，开发者被迫写错误的 res.data.data
 *
 * 解决方案：
 * - 使用 unknown 绕过 axios 错误的类型声明
 * - 正确断言返回类型为 BackendResponse<T>
 */

import request from '../request'
import type { BackendResponse, DataFrameData } from '../types/response'

/**
 * 类型安全的 GET 请求
 * @param url - API 路径
 * @param params - 查询参数
 * @returns 后端响应（已正确类型化）
 */
export async function apiGet<T>(
    url: string,
    params?: Record<string, unknown>
): Promise<BackendResponse<T>> {
    // 关键：axios 的类型声明是错误的，拦截器返回的是 response.data
    // 使用 unknown 中转来正确断言实际类型
    return request.get(url, { params }) as unknown as Promise<BackendResponse<T>>
}

/**
 * 类型安全的 POST 请求
 * @param url - API 路径
 * @param data - 请求体
 * @param params - 查询参数（可选）
 * @returns 后端响应（已正确类型化）
 */
export async function apiPost<T>(
    url: string,
    data?: unknown,
    params?: Record<string, unknown>
): Promise<BackendResponse<T>> {
    return request.post(url, data, { params }) as unknown as Promise<BackendResponse<T>>
}

/**
 * 类型安全的 PUT 请求
 */
export async function apiPut<T>(
    url: string,
    data?: unknown
): Promise<BackendResponse<T>> {
    return request.put(url, data) as unknown as Promise<BackendResponse<T>>
}

/**
 * 类型安全的 DELETE 请求
 */
export async function apiDelete<T>(
    url: string,
    params?: Record<string, unknown>
): Promise<BackendResponse<T>> {
    return request.delete(url, { params }) as unknown as Promise<BackendResponse<T>>
}

/**
 * 便捷方法：获取数据并自动解包
 * 如果请求失败或 success=false，抛出错误
 *
 * @param url - API 路径
 * @param params - 查询参数
 * @returns 解包后的数据
 * @throws Error 如果请求失败
 *
 * @example
 * // 直接获取数据，失败时抛出异常
 * const stockInfo = await fetchData<DataFrameData>('/amazingdata/basic/stock-basic')
 */
export async function fetchData<T>(
    url: string,
    params?: Record<string, unknown>
): Promise<T> {
    const res = await apiGet<T>(url, params)
    if (!res.success || res.data === undefined) {
        throw new Error(res.error || '请求失败')
    }
    return res.data
}

/**
 * 便捷方法：POST 数据并自动解包
 */
export async function postData<T>(
    url: string,
    data?: unknown,
    params?: Record<string, unknown>
): Promise<T> {
    const res = await apiPost<T>(url, data, params)
    if (!res.success || res.data === undefined) {
        throw new Error(res.error || '请求失败')
    }
    return res.data
}

// 重新导出类型，方便使用
export type { BackendResponse, DataFrameData }
