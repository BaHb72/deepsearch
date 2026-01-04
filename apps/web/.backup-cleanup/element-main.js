// 测试 Vue + Element Plus
import {createApp} from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import ElementTestApp from './ElementTestApp.vue'

console.log('element-main.js loaded')

// 创建应用
const app = createApp(ElementTestApp)

// 使用 Element Plus
app.use(ElementPlus, {
    locale: zhCn,
})

// 添加全局错误处理
app.config.errorHandler = (err, instance, info) => {
    console.error('Vue error:', err, info)
}

// 挂载应用
console.log('About to mount app with Element Plus')
app.mount('#app')
console.log('App with Element Plus mounted')
