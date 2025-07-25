<template>
  <div id="element-test-app">
    <h1>{{ message }}</h1>
    <p>计数器: {{ count }}</p>

    <!-- 测试 Element Plus 组件 -->
    <el-button type="primary" @click="increment">Element Plus 按钮</el-button>
    <el-button type="success" @click="showMessage">显示消息</el-button>

    <div style="margin-top: 20px;">
      <el-tag>标签测试</el-tag>
      <el-tag style="margin-left: 10px;" type="success">成功标签</el-tag>
    </div>
  </div>
</template>

<script>
import {ElMessage} from 'element-plus'

export default {
  name: 'ElementTestApp',
  data() {
    return {
      message: 'Vue + Element Plus 正在运行！',
      count: 0
    }
  },
  methods: {
    increment() {
      this.count++
      console.log('Count:', this.count)
    },
    showMessage() {
      ElMessage.success('Element Plus 消息组件正常工作！')
    }
  },
  mounted() {
    console.log('ElementTestApp mounted successfully!')
  }
}
</script>

<style>
#element-test-app {
  font-family: Arial, sans-serif;
  text-align: center;
  margin-top: 50px;
}
</style>