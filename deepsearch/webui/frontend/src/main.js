import {createApp} from 'vue'
import {createPinia} from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
// import TestApp from './TestApp.vue'
import router from './router'

// 导入全局样式
import './assets/styles/global.scss'

// 导入错误追踪器
import {errorTracker} from './utils/errorTracker'

// 创建应用
const app = createApp(App)
// const app = createApp(TestApp)

// 使用 Pinia
app.use(createPinia())

// 使用路由
app.use(router)

// 使用 Element Plus
app.use(ElementPlus, {
    locale: zhCn,
})

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

// 初始化错误追踪器
errorTracker.init(app)

// 挂载应用
app.mount('#app')