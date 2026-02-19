import { create } from 'zustand'
import type { DataSourceType } from '@/services/data-source'
import type { SlowLoadSwitchEvent } from '@/services/data-source/slow-load/types'

interface SlowLoadSwitchState {
    queue: SlowLoadSwitchEvent[]
    active: SlowLoadSwitchEvent | null
    activeKeys: Record<string, boolean>
    enqueue: (event: SlowLoadSwitchEvent) => void
    dismissCurrent: () => void
    dequeueCurrent: () => void
    switchCurrent: (target: DataSourceType) => Promise<void>
    hasActiveKey: (key: string) => boolean
}

export function buildSlowEventDedupKey(event: SlowLoadSwitchEvent): string {
    return [
        event.pageKey,
        event.moduleKey,
        event.capability,
        event.currentSource || 'auto',
    ].join('|')
}

function shiftState(state: SlowLoadSwitchState): Partial<SlowLoadSwitchState> {
    const current = state.active
    if (!current) {
        return {}
    }

    const nextQueue = [...state.queue]
    const nextActive = nextQueue.shift() || null
    const nextKeys = { ...state.activeKeys }
    delete nextKeys[buildSlowEventDedupKey(current)]

    return {
        active: nextActive,
        queue: nextQueue,
        activeKeys: nextKeys,
    }
}

export const useSlowLoadSwitchStore = create<SlowLoadSwitchState>((set, get) => ({
    queue: [],
    active: null,
    activeKeys: {},

    enqueue: (event) => {
        if (!event.onSwitchSource || event.candidateSources.length === 0) {
            return
        }
        const dedupKey = buildSlowEventDedupKey(event)
        const state = get()
        if (state.activeKeys[dedupKey]) {
            return
        }

        const nextKeys = { ...state.activeKeys, [dedupKey]: true }
        if (!state.active) {
            set({
                active: event,
                queue: state.queue,
                activeKeys: nextKeys,
            })
            return
        }

        set({
            active: state.active,
            queue: [...state.queue, event],
            activeKeys: nextKeys,
        })
    },

    dismissCurrent: () => {
        set((state) => shiftState(state))
    },

    dequeueCurrent: () => {
        set((state) => shiftState(state))
    },

    switchCurrent: async (target) => {
        const current = get().active
        if (!current) {
            return
        }
        if (current.onSwitchSource) {
            await current.onSwitchSource(target)
        }
        get().dequeueCurrent()
    },

    hasActiveKey: (key) => {
        return Boolean(get().activeKeys[key])
    },
}))
