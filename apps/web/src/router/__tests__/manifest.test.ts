import {
  APP_PATHS,
  APP_ROUTE_DEFINITIONS,
  DEFAULT_HOME_PATH,
  PAGE_ROUTE_DEFINITIONS,
  REDIRECT_ROUTE_DEFINITIONS,
  buildMenuRouteTree,
} from '../manifest'

function flattenMenuNodes(nodes: Array<{ path: string; routes?: Array<{ path: string; routes?: any[] }> }>): string[] {
  return nodes.flatMap((node) => {
    const children = node.routes ? flattenMenuNodes(node.routes) : []
    return [node.path, ...children]
  })
}

describe('router manifest consistency', () => {
  it('all route paths should be unique', () => {
    const paths = APP_ROUTE_DEFINITIONS.map((route) => route.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('default home path should map to a page route', () => {
    const hasDefaultHomeRoute = PAGE_ROUTE_DEFINITIONS.some((route) => route.path === DEFAULT_HOME_PATH)
    expect(hasDefaultHomeRoute).toBe(true)
  })

  it('redirect targets should reference existing routes', () => {
    const knownPaths = new Set(APP_ROUTE_DEFINITIONS.map((route) => route.path))
    REDIRECT_ROUTE_DEFINITIONS.forEach((route) => {
      expect(knownPaths.has(route.redirectTo)).toBe(true)
    })
  })

  it('menu should not expose legacy alias routes', () => {
    const legacyPaths = new Set<string>([
      APP_PATHS.aliasMarket,
      APP_PATHS.aliasScreener,
      APP_PATHS.devAmazingDataLegacy,
      APP_PATHS.devMiniQmtLegacy,
    ])
    const menuTree = buildMenuRouteTree()
    const allMenuPaths = flattenMenuNodes(menuTree.routes)

    allMenuPaths.forEach((path) => {
      expect(legacyPaths.has(path)).toBe(false)
    })
  })

  it('menu children should always resolve to page routes', () => {
    const pagePaths = new Set(PAGE_ROUTE_DEFINITIONS.map((route) => route.path))
    const menuTree = buildMenuRouteTree()

    menuTree.routes.forEach((groupNode) => {
      if (!groupNode.routes?.length) {
        expect(pagePaths.has(groupNode.path)).toBe(true)
        return
      }

      groupNode.routes.forEach((childNode) => {
        expect(pagePaths.has(childNode.path)).toBe(true)
      })
    })
  })
})
