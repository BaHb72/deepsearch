/**
 * 导出工具函数
 */

/**
 * 导出数据到Excel
 * @param {Array} data - 要导出的数据数组
 * @param {String} filename - 文件名
 */
export function exportToExcel(data, filename = 'export.xlsx') {
  // 简单的CSV导出实现（如果需要真正的Excel格式，可以使用xlsx库）
  exportToCSV(data, filename.replace('.xlsx', '.csv'))
}

/**
 * 导出数据到CSV
 * @param {Array} data - 要导出的数据数组
 * @param {String} filename - 文件名
 */
export function exportToCSV(data, filename = 'export.csv') {
  if (!data || data.length === 0) {
    console.warn('No data to export')
    return
  }
  
  // 获取表头
  const headers = Object.keys(data[0])
  
  // 构建CSV内容
  let csvContent = '\uFEFF' // BOM for UTF-8
  
  // 添加表头
  csvContent += headers.map(h => `"${h}"`).join(',') + '\n'
  
  // 添加数据行
  data.forEach(row => {
    const values = headers.map(h => {
      const value = row[h]
      if (value === null || value === undefined) {
        return ''
      }
      // 处理包含逗号或引号的值
      const strValue = String(value)
      if (strValue.includes(',') || strValue.includes('"') || strValue.includes('\n')) {
        return `"${strValue.replace(/"/g, '""')}"`
      }
      return strValue
    })
    csvContent += values.join(',') + '\n'
  })
  
  // 创建Blob并下载
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
  downloadBlob(blob, filename)
}

/**
 * 导出数据到JSON
 * @param {Any} data - 要导出的数据
 * @param {String} filename - 文件名
 */
export function exportToJSON(data, filename = 'export.json') {
  const json = JSON.stringify(data, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  downloadBlob(blob, filename)
}

/**
 * 下载Blob对象
 * @param {Blob} blob - Blob对象
 * @param {String} filename - 文件名
 */
function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  
  // 触发下载
  document.body.appendChild(link)
  link.click()
  
  // 清理
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

/**
 * 格式化文件大小
 * @param {Number} bytes - 字节数
 * @returns {String} 格式化后的大小
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 将表格数据转换为Markdown格式
 * @param {Array} data - 表格数据
 * @param {Array} headers - 表头（可选）
 * @returns {String} Markdown格式的表格
 */
export function tableToMarkdown(data, headers = null) {
  if (!data || data.length === 0) return ''
  
  // 获取表头
  const cols = headers || Object.keys(data[0])
  
  // 构建Markdown表格
  let markdown = '| ' + cols.join(' | ') + ' |\n'
  markdown += '| ' + cols.map(() => '---').join(' | ') + ' |\n'
  
  // 添加数据行
  data.forEach(row => {
    const values = cols.map(col => {
      const value = row[col]
      return value === null || value === undefined ? '' : String(value)
    })
    markdown += '| ' + values.join(' | ') + ' |\n'
  })
  
  return markdown
}

/**
 * 复制文本到剪贴板
 * @param {String} text - 要复制的文本
 * @returns {Promise<Boolean>} 是否复制成功
 */
export async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      // 使用新API
      await navigator.clipboard.writeText(text)
      return true
    } else {
      // 降级方案
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      const success = document.execCommand('copy')
      document.body.removeChild(textarea)
      return success
    }
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    return false
  }
}

/**
 * 导出能力对比报告
 * @param {Object} comparisonData - 对比数据
 * @param {String} format - 导出格式 (csv, json, markdown)
 * @param {String} filename - 文件名
 */
export function exportCapabilityReport(comparisonData, format = 'csv', filename = null) {
  const timestamp = new Date().toISOString().split('T')[0]
  const defaultFilename = `capability_comparison_${timestamp}`
  
  switch (format) {
    case 'csv':
      exportToCSV(comparisonData, filename || `${defaultFilename}.csv`)
      break
    case 'json':
      exportToJSON(comparisonData, filename || `${defaultFilename}.json`)
      break
    case 'markdown':
      const markdown = tableToMarkdown(comparisonData)
      const blob = new Blob([markdown], { type: 'text/markdown' })
      downloadBlob(blob, filename || `${defaultFilename}.md`)
      break
    default:
      console.warn(`Unsupported export format: ${format}`)
  }
}