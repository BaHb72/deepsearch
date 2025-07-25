<template>
  <div id="simple-app">
    <h1>{{ message }}</h1>
    <p>计数器: {{ count }}</p>
    <button @click="increment">点击增加</button>
  </div>
</template>

<script>
export default {
  name: 'SimpleApp',
  data() {
    return {
      message: 'Vue 应用正在运行！',
      count: 0
    }
  },
  methods: {
    increment() {
      this.count++
      console.log('Count:', this.count)
    }
  },
  mounted() {
    console.log('SimpleApp mounted successfully!')
  }
}
</script>

<style>
#simple-app {
  font-family: Arial, sans-serif;
  text-align: center;
  margin-top: 50px;
}

button {
  margin-top: 20px;
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
}
</style>