import axios from 'axios'
import {ElMessage} from 'element-plus'

// 创建 axios 实例
const request = axios.create({
    baseURL: '/api',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 请求拦截器
request.interceptors.request.use(
    config => {
        // 可以在这里添加认证 token
        // config.headers['Authorization'] = 'Bearer ' + getToken()
        return config
    },
    error => {
        console.error('请求错误:', error)
        return Promise.reject(error)
    }
)

// 响应拦截器
request.interceptors.response.use(
    response => {
        const res = response.data
        return res
    },
    error => {
        // 不要在控制台显示每个错误
        
        let message = '请求失败'
        let showError = true
        
        if (error.response) {
            switch (error.response.status) {
                case 400:
                    message = '请求参数错误'
                    break
                case 401:
                    message = '未授权，请登录'
                    break
                case 403:
                    message = '拒绝访问'
                    break
                case 404:
                    message = '请求地址不存在'
                    break
                case 500:
                    message = '服务器内部错误'
                    break
                case 503:
                    message = '服务不可用'
                    break
                default:
                    message = error.response.data?.detail || error.response.data?.message || '请求失败'
            }
        } else if (error.request) {
            // 网络错误（包括后端未启动）
            message = '无法连接到后端服务，请确保后端已启动'
            // 对于某些周期性请求（如状态轮询），不显示错误
            if (error.config?.url?.includes('/status') ||
                error.config?.url?.includes('/statistics')) {
                showError = false
                console.debug('后端服务未就绪')
            }
        }

        if (showError) {
            ElMessage.error({
                message,
                duration: 3000,
                showClose: true
            })
        }
        
        return Promise.reject(error)
    }
)

export default request