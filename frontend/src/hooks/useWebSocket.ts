import { useEffect, useRef } from 'react'
import { useWSStore, playAlertBell, playUrgentBell, type LiveAlert } from '../store/ws'
import { useAuthStore } from '../store/auth'

const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws`

export function useWebSocket() {
  const { admin } = useAuthStore()
  const { addAlert } = useWSStore()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!admin) return

    const connect = () => {
      try {
        const ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
          useWSStore.setState({ connected: true })
          console.log('WS connected')
        }

        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data)
            if (msg.type === 'alert') {
              const alert: LiveAlert = {
                id: `${Date.now()}-${Math.random()}`,
                type: msg.alert_type,
                severity: msg.severity,
                student_name: msg.student_name,
                student_id: msg.student_id,
                session: msg.session,
                minutes: msg.minutes,
                message: msg.message,
                play_bell: msg.play_bell,
                timestamp: new Date(),
              }
              addAlert(alert)

              if (msg.play_bell) {
                if (msg.severity === 'urgent') {
                  playUrgentBell()
                } else {
                  playAlertBell()
                }
              }
            }
          } catch (e) {
            console.warn('WS parse error:', e)
          }
        }

        ws.onclose = () => {
          useWSStore.setState({ connected: false })
          reconnectRef.current = setTimeout(connect, 5000)
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch (e) {
        reconnectRef.current = setTimeout(connect, 5000)
      }
    }

    connect()

    // Ping keepalive
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      clearTimeout(reconnectRef.current)
      clearInterval(pingInterval)
      wsRef.current?.close()
    }
  }, [admin])
}
