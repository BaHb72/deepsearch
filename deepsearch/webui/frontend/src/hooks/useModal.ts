import { useState, useCallback } from 'react'

/**
 * Modal 状态管理的通用 Hook
 * @template T 数据类型
 */
export interface ModalState<T = any> {
  visible: boolean
  loading: boolean
  data: T | null
}

export interface UseModalReturn<T = any> {
  visible: boolean
  loading: boolean
  data: T | null
  open: (data?: T) => void
  close: () => void
  setLoading: (loading: boolean) => void
  update: (data: Partial<T>) => void
}

/**
 * 通用的 Modal 状态管理 Hook
 * 用于管理模态框的显示/隐藏、加载状态和数据
 * 
 * @example
 * ```tsx
 * const editModal = useModal<User>()
 * 
 * // 打开模态框并传入数据
 * editModal.open(userData)
 * 
 * // 在模态框中使用
 * <Modal open={editModal.visible} onCancel={editModal.close}>
 *   {editModal.data && <UserForm user={editModal.data} />}
 * </Modal>
 * ```
 */
export const useModal = <T = any>(initialData?: T | null): UseModalReturn<T> => {
  const [state, setState] = useState<ModalState<T>>({
    visible: false,
    loading: false,
    data: initialData || null
  })

  /**
   * 打开模态框
   * @param data 可选的初始数据
   */
  const open = useCallback((data?: T) => {
    setState({
      visible: true,
      loading: false,
      data: data || null
    })
  }, [])

  /**
   * 关闭模态框并清理状态
   */
  const close = useCallback(() => {
    setState({
      visible: false,
      loading: false,
      data: null
    })
  }, [])

  /**
   * 设置加载状态
   */
  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, loading }))
  }, [])

  /**
   * 更新数据（部分更新）
   */
  const update = useCallback((updates: Partial<T>) => {
    setState(prev => ({
      ...prev,
      data: prev.data ? { ...prev.data, ...updates } : null
    }))
  }, [])

  return {
    visible: state.visible,
    loading: state.loading,
    data: state.data,
    open,
    close,
    setLoading,
    update
  }
}

/**
 * 批量管理多个 Modal 的 Hook
 * 
 * @example
 * ```tsx
 * const modals = useModals({
 *   edit: null,
 *   delete: null,
 *   detail: null
 * })
 * 
 * modals.edit.open(userData)
 * modals.delete.open(userId)
 * ```
 */
export const useModals = <T extends Record<string, any>>(
  initialModals: T
): { [K in keyof T]: UseModalReturn<T[K]> } => {
  const result: any = {}
  
  for (const key in initialModals) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    result[key] = useModal(initialModals[key])
  }
  
  return result
}

export default useModal