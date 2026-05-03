import { useEffect, useRef, useState } from 'react'
import { Bell, X, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { useWSStore, type LiveAlert } from '../../store/ws'
import { formatDistanceToNow } from 'date-fns'

function AlertToast({ alert, onDismiss }: { alert: LiveAlert; onDismiss: () => void }) {
  const isUrgent = alert.severity === 'urgent'
  const isWarning = alert.severity === 'warning'

  const bg = isUrgent ? '#450A0A' : isWarning ? '#451A03' : 'var(--bg-elevated)'
  const border = isUrgent ? '#DC2626' : isWarning ? '#D97706' : 'var(--border)'
  const Icon = isUrgent ? AlertCircle : isWarning ? AlertTriangle : Info
  const iconColor = isUrgent ? '#EF4444' : isWarning ? '#F59E0B' : 'var(--brand-blue)'

  return (
    <div className="slide-in" style={{
      background: bg,
      border: `1px solid ${border}`,
      borderRadius: 12,
      padding: '14px 16px',
      marginBottom: 10,
      maxWidth: 360,
      boxShadow: `0 4px 24px rgba(0,0,0,0.4)`,
      position: 'relative',
    }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <Icon size={18} color={iconColor} style={{ marginTop: 2, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {isUrgent ? '🚨 URGENT: ' : isWarning ? '⚠️ Warning: ' : ''}
            {alert.student_name || alert.message}
          </div>
          {alert.session && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Session: {alert.session}
              {alert.minutes && ` · ${alert.minutes} min absent`}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
            {formatDistanceToNow(alert.timestamp, { addSuffix: true })}
          </div>
        </div>
        <button
          onClick={onDismiss}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: 0, marginTop: -2 }}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}

export default function AlertPanel() {
  const { alerts, unreadCount, clearAlert, markAllRead } = useWSStore()
  const [open, setOpen] = useState(false)
  const bellRef = useRef<HTMLButtonElement>(null)

  // Shake bell on new alert
  useEffect(() => {
    if (unreadCount > 0 && bellRef.current) {
      bellRef.current.classList.remove('bell-shake')
      void bellRef.current.offsetWidth
      bellRef.current.classList.add('bell-shake')
    }
  }, [unreadCount])

  return (
    <div style={{ position: 'relative' }}>
      <button
        ref={bellRef}
        onClick={() => { setOpen((v) => !v); markAllRead() }}
        style={{
          background: unreadCount > 0 ? 'rgba(220,38,38,0.15)' : 'var(--bg-elevated)',
          border: `1px solid ${unreadCount > 0 ? '#DC262640' : 'var(--border)'}`,
          borderRadius: 8,
          padding: '8px 10px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          color: unreadCount > 0 ? '#EF4444' : 'var(--text-muted)',
          position: 'relative',
        }}
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: -4, right: -4,
            background: '#DC2626',
            color: '#fff',
            borderRadius: 99,
            fontSize: 9,
            fontWeight: 700,
            padding: '1px 5px',
            minWidth: 16,
            textAlign: 'center',
          }}>{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 40 }}
            onClick={() => setOpen(false)}
          />
          <div style={{
            position: 'absolute',
            top: '110%',
            right: 0,
            zIndex: 50,
            width: 380,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 14,
            boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '14px 16px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <span style={{ fontWeight: 700, fontSize: 14, fontFamily: 'DM Sans, sans-serif' }}>
                Live Alerts
              </span>
              {alerts.length > 0 && (
                <button
                  onClick={() => useWSStore.getState().clearAll()}
                  style={{ fontSize: 11, color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  Clear all
                </button>
              )}
            </div>
            <div style={{ maxHeight: 420, overflowY: 'auto', padding: 12 }}>
              {alerts.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', fontSize: 13, padding: '24px 0' }}>
                  No alerts
                </div>
              ) : (
                alerts.map((a) => (
                  <AlertToast key={a.id} alert={a} onDismiss={() => clearAlert(a.id)} />
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
