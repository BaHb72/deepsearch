import { buildSlowEventDedupKey, useSlowLoadSwitchStore } from '../slowLoadSwitch.store'
import type { SlowLoadSwitchEvent } from '@/services/data-source/slow-load/types'

function createEvent(overrides: Partial<SlowLoadSwitchEvent> = {}): SlowLoadSwitchEvent {
    return {
        id: `event-${Date.now()}`,
        pageKey: 'dev/playground',
        pageName: '数据源沙盒',
        moduleKey: 'quote',
        moduleName: '行情数据',
        capability: 'realtime_quote',
        trigger: 'elapsed_timeout',
        candidateSources: ['amazingdata'],
        onSwitchSource: async () => undefined,
        createdAt: Date.now(),
        ...overrides,
    }
}

describe('slowLoadSwitch store', () => {
    beforeEach(() => {
        useSlowLoadSwitchStore.setState({
            queue: [],
            active: null,
            activeKeys: {},
        })
    })

    it('should enqueue first event as active', () => {
        const event = createEvent()
        useSlowLoadSwitchStore.getState().enqueue(event)

        const state = useSlowLoadSwitchStore.getState()
        expect(state.active?.id).toBe(event.id)
        expect(state.queue).toHaveLength(0)
    })

    it('should dedupe events by key', () => {
        const event = createEvent({ id: 'a' })
        const duplicate = createEvent({ id: 'b' })
        const keyA = buildSlowEventDedupKey(event)
        const keyB = buildSlowEventDedupKey(duplicate)

        expect(keyA).toBe(keyB)
        useSlowLoadSwitchStore.getState().enqueue(event)
        useSlowLoadSwitchStore.getState().enqueue(duplicate)

        const state = useSlowLoadSwitchStore.getState()
        expect(state.active?.id).toBe('a')
        expect(state.queue).toHaveLength(0)
    })

    it('should shift queue on dismiss', () => {
        const first = createEvent({ id: 'first', capability: 'realtime_quote' })
        const second = createEvent({ id: 'second', capability: 'stock_kline' })

        const store = useSlowLoadSwitchStore.getState()
        store.enqueue(first)
        store.enqueue(second)
        store.dismissCurrent()

        const state = useSlowLoadSwitchStore.getState()
        expect(state.active?.id).toBe('second')
        expect(state.queue).toHaveLength(0)
    })

    it('should call switch callback then dequeue current', async () => {
        const switchMock = jest.fn().mockResolvedValue(undefined)
        const event = createEvent({
            id: 'switchable',
            onSwitchSource: switchMock,
            candidateSources: ['akshare'],
        })

        const store = useSlowLoadSwitchStore.getState()
        store.enqueue(event)
        await store.switchCurrent('akshare')

        const state = useSlowLoadSwitchStore.getState()
        expect(switchMock).toHaveBeenCalledWith('akshare')
        expect(state.active).toBeNull()
        expect(state.queue).toHaveLength(0)
    })

    it('should ignore non-switchable events', () => {
        const event = createEvent({
            id: 'readonly',
            candidateSources: [],
            onSwitchSource: undefined,
        })

        useSlowLoadSwitchStore.getState().enqueue(event)
        const state = useSlowLoadSwitchStore.getState()
        expect(state.active).toBeNull()
        expect(state.queue).toHaveLength(0)
    })
})
