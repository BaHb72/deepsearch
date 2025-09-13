/**
 * API调试工具
 * 用于追踪为什么请求会发送到错误的地址
 */

// 拦截所有的 XMLHttpRequest
const originalXHROpen = XMLHttpRequest.prototype.open;
const originalXHRSend = XMLHttpRequest.prototype.send;

XMLHttpRequest.prototype.open = function(method, url, ...args) {
    // 记录所有请求
    if (url && url.includes('database')) {
        console.error('🚨 [XHR拦截] 发现database请求:', {
            method,
            url,
            fullUrl: new URL(url, window.location.href).href,
            stack: new Error().stack
        });
    }
    
    // 调用原始方法
    return originalXHROpen.call(this, method, url, ...args);
};

// 拦截 fetch API
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    if (url && url.toString().includes('database')) {
        console.error('🚨 [Fetch拦截] 发现database请求:', {
            url: url.toString(),
            fullUrl: new URL(url, window.location.href).href,
            method: options.method || 'GET',
            stack: new Error().stack
        });
    }
    
    return originalFetch.call(this, url, options);
};

// 监控 axios 实例
export function debugAxiosInstance(axiosInstance) {
    console.log('📊 [Axios调试] 当前配置:', {
        baseURL: axiosInstance.defaults.baseURL,
        timeout: axiosInstance.defaults.timeout,
        headers: axiosInstance.defaults.headers
    });
    
    // 添加请求拦截器
    axiosInstance.interceptors.request.use(
        config => {
            if (config.url && config.url.includes('database')) {
                const fullUrl = config.baseURL ? 
                    config.baseURL + config.url : 
                    config.url;
                    
                console.error('🚨 [Axios拦截] database请求配置:', {
                    url: config.url,
                    baseURL: config.baseURL,
                    fullUrl,
                    actualUrl: new URL(fullUrl, window.location.href).href
                });
            }
            return config;
        },
        error => {
            console.error('❌ [Axios请求错误]:', error);
            return Promise.reject(error);
        }
    );
}

console.log('✅ API调试工具已加载');

export default {
    debugAxiosInstance
};