import { useState, useEffect } from 'react'

export const useSystemStatus = () => {
  const [systemStatus, setSystemStatus] = useState({
    status: 'running',
    cpu: 0,
    memory: 0,
    uptime: 0
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // 模拟获取系统状态
    const fetchStatus = () => {
      setSystemStatus({
        status: 'running',
        cpu: Math.random() * 100,
        memory: Math.random() * 100,
        uptime: Date.now()
      })
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    
    return () => clearInterval(interval)
  }, [])

  return { systemStatus, loading }
}