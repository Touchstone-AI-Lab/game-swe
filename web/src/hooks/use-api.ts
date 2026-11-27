import { useCallback, useEffect, useState } from 'react'

import { api } from '@/lib/api'

export function useApi<T>(path: string, interval = 0) {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setData(await api<T>(path))
      setError(undefined)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    void refresh()
    if (!interval) return
    const timer = window.setInterval(() => void refresh(), interval)
    return () => window.clearInterval(timer)
  }, [interval, refresh])

  return { data, error, loading, refresh }
}

