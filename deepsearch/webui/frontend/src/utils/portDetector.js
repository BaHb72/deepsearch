/**
 * 后端端口自动探测工具
 * 自动探测后端服务运行在哪个端口
 */

import axios from 'axios'

// 可能的后端端口列表
const POSSIBLE_PORTS = [8000, 8001, 8002, 8080, 3001]  // 移除8888，避免CORS错误

// 缓存探测结果
let detectedPort = null
let lastDetectionTime = 0
const CACHE_DURATION = 60000 // 缓存60秒

/**
 * 检查后端服务是否可用（通过代理）
 * @returns {Promise<boolean>} - 是否可用
 */
async function checkBackend() {
    try {
        // 直接使用代理路径，不需要指定端口
        const response = await axios.get('/api/health', {
            timeout: 1000 // 1秒超时
        })
        return response.status === 200
    } catch (error) {
        return false
    }
}

/**
 * 检查指定端口是否有后端服务运行（保留用于特殊场景）
 * @param {number} port - 端口号
 * @returns {Promise<boolean>} - 是否可用
 */
async function checkPort(port) {
    try {
        const response = await axios.get(`http://localhost:${port}/api/health`, {
            timeout: 1000 // 1秒超时
        })
        return response.status === 200
    } catch (error) {
        // 如果是其他错误（如404），说明端口有服务但不是我们的后端
        if (error.response && error.response.status) {
            return false
        }
        // 连接错误，端口不可用
        return false
    }
}

/**
 * 探测后端服务端口（简化版，使用代理）
 * @param {boolean} forceRefresh - 是否强制刷新（忽略缓存）
 * @returns {Promise<number>} - 后端端口号（现在返回0表示使用代理）
 */
export async function detectBackendPort(forceRefresh = false) {
    console.log('检查后端服务状态...')

    // 新策略：直接通过代理检查后端
    const isAvailable = await checkBackend()

    if (isAvailable) {
        console.log('✓ 后端服务可用（通过Vite代理）')
        return 0 // 返回0表示使用代理，不需要具体端口
    }

    // 如果代理不可用，尝试直接连接（用于开发调试）
    console.log('代理检查失败，尝试直接连接...')

    // 优先检查默认端口8000
    if (await checkPort(8000)) {
        console.log('✓ 后端服务发现在默认端口: 8000')
        detectedPort = 8000
        return 8000
    }

    // 如果默认端口不可用，并发检查其他端口
    const otherPorts = POSSIBLE_PORTS.filter(p => p !== 8000)
    const checkPromises = otherPorts.map(port =>
        checkPort(port).then(isAvailable => ({port, isAvailable}))
    )

    try {
        const results = await Promise.all(checkPromises)

        // 找到第一个可用的端口
        const availablePort = results.find(r => r.isAvailable)

        if (availablePort) {
            detectedPort = availablePort.port
            console.log(`✓ 后端服务发现在端口: ${detectedPort}`)
            return detectedPort
        }

        // 没有找到可用端口
        console.warn('未找到后端服务，将使用代理模式。请确保后端已启动在端口8000')
        return 0 // 返回0，让系统使用代理

    } catch (error) {
        console.error('端口探测失败:', error)
        return 0 // 使用代理
    }
}

/**
 * 获取后端基础URL
 * @param {boolean} forceRefresh - 是否强制刷新端口
 * @returns {Promise<string>} - 后端基础URL
 */
export async function getBackendUrl(forceRefresh = false) {
    const port = await detectBackendPort(forceRefresh)

    // 如果端口为0，表示使用代理，返回空字符串让axios使用相对路径
    if (port === 0) {
        return '' // 使用相对路径，通过Vite代理
    }

    return `http://localhost:${port}`
}

/**
 * 配置axios使用动态后端URL
 * @param {object} axiosInstance - axios实例
 * @returns {Promise<void>}
 */
export async function configureAxiosWithDynamicPort(axiosInstance) {
    const baseURL = await getBackendUrl()
    axiosInstance.defaults.baseURL = baseURL
    console.log(`Axios配置为使用后端: ${baseURL}`)

    // 添加请求拦截器，处理端口变化
    axiosInstance.interceptors.response.use(
        response => response,
        async error => {
            // 如果是连接错误，尝试重新探测端口
            if (!error.response && error.code === 'ECONNREFUSED') {
                console.log('连接被拒绝，重新探测后端端口...')

                // 强制刷新端口
                const newBaseURL = await getBackendUrl(true)
                axiosInstance.defaults.baseURL = newBaseURL

                // 重试原始请求
                error.config.baseURL = newBaseURL
                return axiosInstance.request(error.config)
            }

            return Promise.reject(error)
        }
    )
}

/**
 * 清除缓存的端口信息
 */
export function clearPortCache() {
    detectedPort = null
    lastDetectionTime = 0
    console.log('端口缓存已清除')
}

// 导出默认探测函数
export default detectBackendPort