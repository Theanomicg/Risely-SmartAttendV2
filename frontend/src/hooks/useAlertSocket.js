import { useEffect, useRef, useCallback } from 'react'

const WS_URL = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000') + '/alerts/ws'

export function useAlertSocket(onAlert) {
  const ws = useRef(null)
  const pingRef = useRef(null)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    ws.current = new WebSocket(WS_URL)

    ws.current.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.pong) return
        onAlert(data)
      } catch {}
    }

    ws.current.onopen = () => {
      pingRef.current = setInterval(() => {
        ws.current?.readyState === WebSocket.OPEN &&
          ws.current.send(JSON.stringify({ ping: 1 }))
      }, 30000)
    }

    ws.current.onclose = () => {
      clearInterval(pingRef.current)
      setTimeout(connect, 3000)
    }

    ws.current.onerror = () => {
      ws.current?.close()
    }
  }, [onAlert])

  useEffect(() => {
    connect()
    return () => {
      clearInterval(pingRef.current)
      ws.current?.close()
    }
  }, [connect])
}
