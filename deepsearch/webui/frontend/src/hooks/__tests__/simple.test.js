// 简单的测试文件，验证测试环境是否正常工作

describe('测试环境验证', () => {
  it('应该能正常运行基础测试', () => {
    expect(1 + 1).toBe(2)
  })
  
  it('应该能正常使用 Jest matchers', () => {
    expect(true).toBeTruthy()
    expect(false).toBeFalsy()
    expect(null).toBeNull()
    expect(undefined).toBeUndefined()
  })
  
  it('应该能正常测试对象', () => {
    const obj = { name: 'test', value: 123 }
    expect(obj).toEqual({ name: 'test', value: 123 })
    expect(obj).toHaveProperty('name', 'test')
  })
  
  it('应该能正常测试数组', () => {
    const arr = [1, 2, 3, 4, 5]
    expect(arr).toHaveLength(5)
    expect(arr).toContain(3)
  })
})