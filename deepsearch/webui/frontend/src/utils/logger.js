const LEVEL_PRIORITY = { debug: 10, info: 20, warn: 30, error: 40 }

function readConfiguredLevel() {
    let envLogLevel = null
    if (typeof import.meta !== 'undefined' && import.meta && import.meta.env && import.meta.env.VITE_LOG_LEVEL) {
        envLogLevel = import.meta.env.VITE_LOG_LEVEL
    }
    if (!envLogLevel && typeof process !== 'undefined' && process && process.env && process.env.VITE_LOG_LEVEL) {
        envLogLevel = process.env.VITE_LOG_LEVEL
    }
    if (envLogLevel) {
        return String(envLogLevel).toLowerCase()
    }
    return 'info'
}

function resolveLevelName(level) {
    return (level && String(level).toLowerCase()) || 'info'
}

function shouldLog(level, configuredLevel) {
    const levelName = resolveLevelName(level)
    const configuredName = resolveLevelName(configuredLevel)
    return (LEVEL_PRIORITY[levelName] || LEVEL_PRIORITY.info) >= (LEVEL_PRIORITY[configuredName] || LEVEL_PRIORITY.info)
}

function formatMessage(scope, message) {
    if (!scope) {
        return message
    }
    return `[${scope}] ${message}`
}

function createWriter(scope, level, configuredLevel) {
    const method = level === 'debug' ? 'debug' : level
    return (message, ...args) => {
        if (!shouldLog(level, configuredLevel)) {
            return
        }
        const formatted = typeof message === 'string' ? formatMessage(scope, message) : message
        console[method](formatted, ...args)
    }
}

export function createLogger(scope = 'APP', level = readConfiguredLevel()) {
    const loggerScope = scope
    const configuredLevel = resolveLevelName(level)
    return {
        debug: createWriter(loggerScope, 'debug', configuredLevel),
        info: createWriter(loggerScope, 'info', configuredLevel),
        warn: createWriter(loggerScope, 'warn', configuredLevel),
        error: createWriter(loggerScope, 'error', configuredLevel),
        child(childScope) {
            const nextScope = childScope ? `${loggerScope}:${childScope}` : loggerScope
            return createLogger(nextScope, configuredLevel)
        }
    }
}

const defaultLogger = createLogger('WEBUI')

export default defaultLogger
