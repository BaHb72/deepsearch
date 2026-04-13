import '@testing-library/jest-dom'

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}))

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}))

// Mock scrollTo
window.scrollTo = jest.fn()

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
global.localStorage = localStorageMock as any

// Mock sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
global.sessionStorage = sessionStorageMock as any

// jsdom does not implement pseudo-element getComputedStyle; rc-table may call it.
const originalGetComputedStyle = window.getComputedStyle.bind(window)
Object.defineProperty(window, 'getComputedStyle', {
  writable: true,
  value: (element: Element, pseudoElement?: string | null) => {
    if (pseudoElement) {
      return originalGetComputedStyle(element)
    }
    return originalGetComputedStyle(element, pseudoElement)
  },
})

// Suppress console errors in tests
const originalError = console.error
const ignoredConsoleErrorMessages = [
  'Warning: ReactDOM.render',
  'Warning: useLayoutEffect',
  'Not implemented: HTMLFormElement.submit',
  'Not implemented: window.getComputedStyle(elt, pseudoElt)',
]

const toConsoleMessage = (value: unknown): string => {
  if (value instanceof Error) {
    return value.message
  }
  if (typeof value === 'string') {
    return value
  }
  return ''
}

beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const firstMessage = toConsoleMessage(args[0])
    if (ignoredConsoleErrorMessages.some(message => firstMessage.includes(message))) {
      return
    }
    originalError.call(console, ...args)
  }
})

afterAll(() => {
  console.error = originalError
})
