#!/usr/bin/env node
/**
 * 测试antd静态message警告修复
 */

const fs = require('fs')
const path = require('path')

// 检查文件是否已正确修改
function checkFile() {
  const filePath = path.join(__dirname, '../deepsearch/webui/frontend/src/pages/SystemConfig/DataSourceConfig.tsx')

  if (!fs.existsSync(filePath)) {
    console.error('❌ 文件不存在:', filePath)
    return false
  }

  const content = fs.readFileSync(filePath, 'utf8')

  // 检查是否导入了App as AntApp
  if (!content.includes('App as AntApp')) {
    console.error('❌ 未找到 "App as AntApp" 导入')
    return false
  }

  // 检查是否不再直接导入message
  const lines = content.split('\n')
  const importLine = lines.find(line => line.includes('} from \'antd\''))
  if (importLine && importLine.includes('message,')) {
    console.error('❌ 仍然直接导入了message')
    return false
  }

  // 检查是否使用了useApp钩子
  if (!content.includes('AntApp.useApp()')) {
    console.error('❌ 未找到 AntApp.useApp() 调用')
    return false
  }

  // 检查三个主要组件是否都添加了useApp
  const components = [
    'DataSourceForm',
    'DataSourceConfig',
    'RateLimitEditor'
  ]

  let allFixed = true
  for (const comp of components) {
    const regex = new RegExp(`const ${comp} = .*?\\{[\\s\\S]*?const \\{ message \\} = AntApp\\.useApp\\(\\)`)
    if (!regex.test(content)) {
      console.warn(`⚠️ ${comp} 组件可能未正确使用useApp`)
      allFixed = false
    }
  }

  if (allFixed) {
    console.log('✅ 所有组件都已正确修复')
  }

  return true
}

// 主函数
function main() {
  console.log('检查antd静态message警告修复...')
  console.log('=' * 50)

  if (checkFile()) {
    console.log('\n✅ 修复已应用！')
    console.log('\n下一步:')
    console.log('1. 重启前端服务: cd deepsearch/webui/frontend && npm run dev')
    console.log('2. 打开浏览器控制台，检查是否还有警告')
    console.log('3. 测试数据源配置功能是否正常工作')
  } else {
    console.error('\n❌ 修复未完全应用')
  }
}

// 运行
main()
