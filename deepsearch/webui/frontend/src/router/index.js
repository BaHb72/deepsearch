import {createRouter, createWebHistory} from 'vue-router'

// 调试日志工具
const debugLog = (stage, message, data = null) => {
    const timestamp = new Date().toISOString()
    const logEntry = `[router ${timestamp}] ${stage}: ${message}`
    console.log('%c' + logEntry, 'color: #909399; font-weight: bold;', data)
}

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'dashboard',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Dashboard组件')
                return import('@/views/Dashboard.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Dashboard组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Dashboard组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/events',
            name: 'events',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Events组件')
                return import('@/views/Events.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Events组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Events组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/config',
            name: 'config',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Config组件')
                return import('@/views/Config.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Config组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Config组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/logs',
            name: 'logs',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Logs组件')
                return import('@/views/Logs.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Logs组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Logs组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/trading',
            name: 'trading',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Trading组件')
                return import('@/views/Trading.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Trading组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Trading组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/strategy',
            name: 'strategy',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载StrategyManagement组件')
                return import('@/views/StrategyManagement.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'StrategyManagement组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'StrategyManagement组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/data',
            name: 'data',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载DataManagement组件')
                return import('@/views/DataManagement.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'DataManagement组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'DataManagement组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/data-source',
            name: 'dataSource',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载DataSource组件')
                return import('@/views/DataSource.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'DataSource组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'DataSource组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/workers-proxy',
            name: 'workersProxy',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载WorkersProxy组件')
                return import('@/views/WorkersProxy.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'WorkersProxy组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'WorkersProxy组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/market',
            name: 'market',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载Market组件')
                return import('@/views/Market.vue').then(module => {
                    debugLog('ROUTE_LOAD', 'Market组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', 'Market组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/pro-trading',
            name: 'marketQuote',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载市场行情组件')
                return import('@/views/ProfessionalTradingView.vue').then(module => {
                    debugLog('ROUTE_LOAD', '市场行情组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', '市场行情组件加载失败', {error: err.message})
                    throw err
                })
            }
        },
        {
            path: '/quant-trading',
            name: 'quantTrading',
            component: () => {
                debugLog('ROUTE_LOAD', '开始加载量化交易组件')
                return import('@/views/QuantTradingView.vue').then(module => {
                    debugLog('ROUTE_LOAD', '量化交易组件加载成功')
                    return module
                }).catch(err => {
                    debugLog('ROUTE_ERROR', '量化交易组件加载失败', {error: err.message})
                    throw err
                })
            }
        }
    ]
})

// 路由守卫
router.beforeEach((to, from, next) => {
    debugLog('NAVIGATION', '路由切换开始', {
        from: from.path,
        to: to.path,
        name: to.name
    })
    next()
})

router.afterEach((to, from) => {
    debugLog('NAVIGATION', '路由切换完成', {
        from: from.path,
        to: to.path,
        name: to.name
    })
})

router.onError((error) => {
    debugLog('ROUTER_ERROR', '路由错误', {
        error: error.message,
        stack: error.stack
    })
})

export default router