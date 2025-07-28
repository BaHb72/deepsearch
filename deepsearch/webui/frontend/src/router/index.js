import {createRouter, createWebHistory} from 'vue-router'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'dashboard',
            component: () => import('@/views/Dashboard.vue')
        },
        {
            path: '/events',
            name: 'events',
            component: () => import('@/views/Events.vue')
        },
        {
            path: '/config',
            name: 'config',
            component: () => import('@/views/Config.vue')
        },
        {
            path: '/logs',
            name: 'logs',
            component: () => import('@/views/Logs.vue')
        },
        {
            path: '/trading',
            name: 'trading',
            component: () => import('@/views/Trading.vue')
        },
        {
            path: '/data',
            name: 'data',
            component: () => import('@/views/DataManagement.vue')
        }
    ]
})

export default router