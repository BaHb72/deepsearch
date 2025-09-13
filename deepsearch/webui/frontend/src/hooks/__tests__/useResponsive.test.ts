import { renderHook, act } from '@testing-library/react'
import { useResponsive } from '../useResponsive'

// Mock Ant Design Grid.useBreakpoint
jest.mock('antd', () => ({
  ...jest.requireActual('antd'),
  Grid: {
    useBreakpoint: jest.fn()
  }
}))

describe('useResponsive Hook', () => {
  let mockUseBreakpoint: jest.Mock
  
  beforeEach(() => {
    // Reset mocks
    mockUseBreakpoint = require('antd').Grid.useBreakpoint
    
    // Mock window dimensions
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 1024
    })
    
    Object.defineProperty(window, 'innerHeight', {
      writable: true,
      configurable: true,
      value: 768
    })
  })
  
  afterEach(() => {
    jest.clearAllMocks()
  })
  
  describe('Device Type Detection', () => {
    it('should detect mobile device correctly', () => {
      mockUseBreakpoint.mockReturnValue({
        xs: true,
        sm: true,
        md: false,
        lg: false,
        xl: false,
        xxl: false
      })
      
      const { result } = renderHook(() => useResponsive())
      
      expect(result.current.isMobile).toBe(true)
      expect(result.current.isTablet).toBe(false)
      expect(result.current.isDesktop).toBe(false)
      expect(result.current.screenSize).toBe('mobile')
    })
    
    it('should detect tablet device correctly', () => {
      mockUseBreakpoint.mockReturnValue({
        xs: false,
        sm: false,
        md: true,
        lg: false,
        xl: false,
        xxl: false
      })
      
      const { result } = renderHook(() => useResponsive())
      
      expect(result.current.isMobile).toBe(false)
      expect(result.current.isTablet).toBe(true)
      expect(result.current.isDesktop).toBe(false)
      expect(result.current.screenSize).toBe('tablet')
    })
    
    it('should detect desktop device correctly', () => {
      mockUseBreakpoint.mockReturnValue({
        xs: false,
        sm: false,
        md: false,
        lg: true,
        xl: false,
        xxl: false
      })
      
      const { result } = renderHook(() => useResponsive())
      
      expect(result.current.isMobile).toBe(false)
      expect(result.current.isTablet).toBe(false)
      expect(result.current.isDesktop).toBe(true)
      expect(result.current.screenSize).toBe('desktop')
    })
    
    it('should detect large screen correctly', () => {
      mockUseBreakpoint.mockReturnValue({
        xs: false,
        sm: false,
        md: false,
        lg: true,
        xl: true,
        xxl: false
      })
      
      const { result } = renderHook(() => useResponsive())
      
      expect(result.current.isLargeScreen).toBe(true)
      expect(result.current.screenSize).toBe('large')
    })
  })
  
  describe('Window Dimensions', () => {
    it('should return current window dimensions', () => {
      mockUseBreakpoint.mockReturnValue({})
      
      const { result } = renderHook(() => useResponsive())
      
      expect(result.current.width).toBe(1024)
      expect(result.current.height).toBe(768)
    })
    
    it('should update dimensions on window resize', async () => {
      mockUseBreakpoint.mockReturnValue({})
      
      const { result } = renderHook(() => useResponsive())
      
      // Initial dimensions
      expect(result.current.width).toBe(1024)
      expect(result.current.height).toBe(768)
      
      // Simulate window resize
      act(() => {
        window.innerWidth = 1920
        window.innerHeight = 1080
        window.dispatchEvent(new Event('resize'))
      })
      
      // Wait for debounce
      await new Promise(resolve => setTimeout(resolve, 200))
      
      // Check updated dimensions
      expect(result.current.width).toBe(1920)
      expect(result.current.height).toBe(1080)
    })
  })
  
  describe('Responsive Utilities', () => {
    it('should clean up event listeners on unmount', () => {
      mockUseBreakpoint.mockReturnValue({})
      
      const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener')
      
      const { unmount } = renderHook(() => useResponsive())
      
      unmount()
      
      expect(removeEventListenerSpy).toHaveBeenCalledWith('resize', expect.any(Function))
      
      removeEventListenerSpy.mockRestore()
    })
  })
})

describe('getResponsiveColumns', () => {
  it('should return default responsive column configuration', () => {
    const { getResponsiveColumns } = require('../useResponsive')
    
    const columns = getResponsiveColumns()
    
    expect(columns).toEqual({
      xs: 24,
      sm: 24,
      md: 12,
      lg: 8,
      xl: 8,
      xxl: 8
    })
  })
  
  it('should return custom responsive column configuration', () => {
    const { getResponsiveColumns } = require('../useResponsive')
    
    const columns = getResponsiveColumns(24, 8, 6)
    
    expect(columns).toEqual({
      xs: 24,
      sm: 24,
      md: 8,
      lg: 6,
      xl: 6,
      xxl: 6
    })
  })
})

describe('getResponsiveTableScroll', () => {
  it('should return mobile scroll configuration', () => {
    const { getResponsiveTableScroll } = require('../useResponsive')
    
    const scroll = getResponsiveTableScroll({
      isMobile: true,
      isTablet: false,
      isDesktop: false,
      isLargeScreen: false,
      screenSize: 'mobile',
      width: 375,
      height: 667,
      screens: {}
    })
    
    expect(scroll).toEqual({ x: 800 })
  })
  
  it('should return tablet scroll configuration', () => {
    const { getResponsiveTableScroll } = require('../useResponsive')
    
    const scroll = getResponsiveTableScroll({
      isMobile: false,
      isTablet: true,
      isDesktop: false,
      isLargeScreen: false,
      screenSize: 'tablet',
      width: 768,
      height: 1024,
      screens: {}
    })
    
    expect(scroll).toEqual({ x: 1000 })
  })
  
  it('should return desktop scroll configuration', () => {
    const { getResponsiveTableScroll } = require('../useResponsive')
    
    const scroll = getResponsiveTableScroll({
      isMobile: false,
      isTablet: false,
      isDesktop: true,
      isLargeScreen: false,
      screenSize: 'desktop',
      width: 1920,
      height: 1080,
      screens: {}
    })
    
    expect(scroll).toEqual({ x: false })
  })
})