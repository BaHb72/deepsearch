import { renderHook, act } from '@testing-library/react'
import { useModal, useModals } from '../useModal'

describe('useModal Hook', () => {
  interface TestData {
    id: number
    name: string
    description: string
  }

  describe('Basic Functionality', () => {
    it('should initialize with default state', () => {
      const { result } = renderHook(() => useModal<TestData>())

      expect(result.current.visible).toBe(false)
      expect(result.current.loading).toBe(false)
      expect(result.current.data).toBe(null)
    })

    it('should initialize with provided data', () => {
      const initialData: TestData = { id: 1, name: 'Test', description: 'Test item' }
      const { result } = renderHook(() => useModal<TestData>(initialData))

      expect(result.current.data).toEqual(initialData)
    })
  })

  describe('open()', () => {
    it('should open modal without data', () => {
      const { result } = renderHook(() => useModal<TestData>())

      act(() => {
        result.current.open()
      })

      expect(result.current.visible).toBe(true)
      expect(result.current.loading).toBe(false)
      expect(result.current.data).toBe(null)
    })

    it('should open modal with data', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const testData: TestData = { id: 1, name: 'Test', description: 'Test item' }

      act(() => {
        result.current.open(testData)
      })

      expect(result.current.visible).toBe(true)
      expect(result.current.data).toEqual(testData)
    })

    it('should replace existing data when opening', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const data1: TestData = { id: 1, name: 'Test1', description: 'First item' }
      const data2: TestData = { id: 2, name: 'Test2', description: 'Second item' }

      act(() => {
        result.current.open(data1)
      })

      expect(result.current.data).toEqual(data1)

      act(() => {
        result.current.open(data2)
      })

      expect(result.current.data).toEqual(data2)
    })
  })

  describe('close()', () => {
    it('should close modal and clear data', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const testData: TestData = { id: 1, name: 'Test', description: 'Test item' }

      // Open modal with data
      act(() => {
        result.current.open(testData)
      })

      expect(result.current.visible).toBe(true)
      expect(result.current.data).toEqual(testData)

      // Close modal
      act(() => {
        result.current.close()
      })

      expect(result.current.visible).toBe(false)
      expect(result.current.loading).toBe(false)
      expect(result.current.data).toBe(null)
    })
  })

  describe('setLoading()', () => {
    it('should set loading state', () => {
      const { result } = renderHook(() => useModal<TestData>())

      expect(result.current.loading).toBe(false)

      act(() => {
        result.current.setLoading(true)
      })

      expect(result.current.loading).toBe(true)

      act(() => {
        result.current.setLoading(false)
      })

      expect(result.current.loading).toBe(false)
    })

    it('should preserve other state when setting loading', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const testData: TestData = { id: 1, name: 'Test', description: 'Test item' }

      act(() => {
        result.current.open(testData)
      })

      act(() => {
        result.current.setLoading(true)
      })

      expect(result.current.visible).toBe(true)
      expect(result.current.data).toEqual(testData)
      expect(result.current.loading).toBe(true)
    })
  })

  describe('update()', () => {
    it('should update existing data partially', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const initialData: TestData = { id: 1, name: 'Test', description: 'Initial' }

      act(() => {
        result.current.open(initialData)
      })

      act(() => {
        result.current.update({ description: 'Updated' })
      })

      expect(result.current.data).toEqual({
        id: 1,
        name: 'Test',
        description: 'Updated'
      })
    })

    it('should not update when data is null', () => {
      const { result } = renderHook(() => useModal<TestData>())

      act(() => {
        result.current.update({ name: 'Test' })
      })

      expect(result.current.data).toBe(null)
    })

    it('should handle multiple updates', () => {
      const { result } = renderHook(() => useModal<TestData>())
      const initialData: TestData = { id: 1, name: 'Test', description: 'Initial' }

      act(() => {
        result.current.open(initialData)
      })

      act(() => {
        result.current.update({ name: 'Updated Name' })
      })

      act(() => {
        result.current.update({ description: 'Updated Description' })
      })

      expect(result.current.data).toEqual({
        id: 1,
        name: 'Updated Name',
        description: 'Updated Description'
      })
    })
  })

  describe('Function Stability', () => {
    it('should have stable function references', () => {
      const { result, rerender } = renderHook(() => useModal<TestData>())

      const firstOpen = result.current.open
      const firstClose = result.current.close
      const firstSetLoading = result.current.setLoading
      const firstUpdate = result.current.update

      rerender()

      expect(result.current.open).toBe(firstOpen)
      expect(result.current.close).toBe(firstClose)
      expect(result.current.setLoading).toBe(firstSetLoading)
      expect(result.current.update).toBe(firstUpdate)
    })
  })
})

describe('useModals Hook', () => {
  interface User {
    id: number
    name: string
  }

  interface Product {
    id: number
    title: string
    price: number
  }

  it('should create multiple modal instances', () => {
    const { result } = renderHook(() => useModals({
      user: null as User | null,
      product: null as Product | null,
      confirm: null
    }))

    expect(result.current.user).toBeDefined()
    expect(result.current.product).toBeDefined()
    expect(result.current.confirm).toBeDefined()

    expect(result.current.user.visible).toBe(false)
    expect(result.current.product.visible).toBe(false)
    expect(result.current.confirm.visible).toBe(false)
  })

  it('should manage multiple modals independently', () => {
    const { result } = renderHook(() => useModals({
      user: null as User | null,
      product: null as Product | null
    }))

    const userData: User = { id: 1, name: 'John' }
    const productData: Product = { id: 1, title: 'Product', price: 99.99 }

    // Open user modal
    act(() => {
      result.current.user.open(userData)
    })

    expect(result.current.user.visible).toBe(true)
    expect(result.current.user.data).toEqual(userData)
    expect(result.current.product.visible).toBe(false)

    // Open product modal
    act(() => {
      result.current.product.open(productData)
    })

    expect(result.current.user.visible).toBe(true)
    expect(result.current.product.visible).toBe(true)
    expect(result.current.product.data).toEqual(productData)

    // Close user modal
    act(() => {
      result.current.user.close()
    })

    expect(result.current.user.visible).toBe(false)
    expect(result.current.user.data).toBe(null)
    expect(result.current.product.visible).toBe(true)
    expect(result.current.product.data).toEqual(productData)
  })

  it('should handle initial values for multiple modals', () => {
    const userData: User = { id: 1, name: 'John' }
    const productData: Product = { id: 1, title: 'Product', price: 99.99 }

    const { result } = renderHook(() => useModals({
      user: userData,
      product: productData,
      empty: null
    }))

    expect(result.current.user.data).toEqual(userData)
    expect(result.current.product.data).toEqual(productData)
    expect(result.current.empty.data).toBe(null)
  })
})
