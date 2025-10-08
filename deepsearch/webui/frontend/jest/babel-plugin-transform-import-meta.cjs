'use strict'

module.exports = function jestTransformImportMeta() {
  return {
    name: 'jest-transform-import-meta',
    visitor: {
      MetaProperty(path) {
        const { node } = path
        if (node.meta && node.meta.name === 'import' && node.property && node.property.name === 'meta') {
          path.replaceWithSourceString('globalThis.__JEST_IMPORT_META__')
        }
      }
    }
  }
}
