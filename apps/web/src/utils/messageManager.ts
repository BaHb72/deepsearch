import type {MessageInstance, MessageType} from 'antd/es/message/interface'

import logger from '@/utils/logger'

type MessageMethod = 'success' | 'error' | 'warning' | 'info'

type MessageArgs<T extends MessageMethod> = Parameters<MessageInstance[T]>
type LoadingArgs = Parameters<MessageInstance['loading']>

const messageManagerLogger = logger.child('utils:message-manager')

const createFallbackMessage = (): MessageType => {
    const handler = (() => undefined) as MessageType
    handler.then = (onfulfilled, onrejected) =>
        Promise.resolve(false).then(onfulfilled, onrejected)
    return handler
}

class MessageManager {
    private messageApi: MessageInstance | null = null

    setMessageApi(api: MessageInstance | null) {
        this.messageApi = api
    }

    success(...args: MessageArgs<'success'>) {
        if (this.messageApi) {
            this.messageApi.success(...args)
            return
        }
        messageManagerLogger.info?.('[Success]:', args[0])
    }

    error(...args: MessageArgs<'error'>) {
        if (this.messageApi) {
            this.messageApi.error(...args)
            return
        }
        messageManagerLogger.error?.('[Error]:', args[0])
    }

    warning(...args: MessageArgs<'warning'>) {
        if (this.messageApi) {
            this.messageApi.warning(...args)
            return
        }
        messageManagerLogger.warn?.('[Warning]:', args[0])
    }

    info(...args: MessageArgs<'info'>) {
        if (this.messageApi) {
            this.messageApi.info(...args)
            return
        }
        messageManagerLogger.info?.('[Info]:', args[0])
    }

    loading(...args: LoadingArgs): MessageType {
        if (this.messageApi) {
            return this.messageApi.loading(...args)
        }
        messageManagerLogger.info?.('[Loading]:', args[0])
        return createFallbackMessage()
    }
}

const messageManager = new MessageManager()

export default messageManager
