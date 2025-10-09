// 最简单的 Vue 应用入口
import {createApp} from 'vue'
import SimpleApp from './SimpleApp.vue'

console.log('simple-main.js loaded')

// 创建并挂载应用
const app = createApp(SimpleApp)

// 添加全局错误处理
app.config.errorHandler = (err, instance, info) => {
    console.error('Vue error:', err, info)
}

// 挂载前的日志
console.log('About to mount app to #app')

// 挂载应用
app.mount('#app')

console.log('App mounted')