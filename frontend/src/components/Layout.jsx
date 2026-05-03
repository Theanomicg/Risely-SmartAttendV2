import { useState, useCallback, useRef } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useAlertSocket } from '../hooks/useAlertSocket'
import toast from 'react-hot-toast'
import {
  LayoutDashboard, Users, Camera, CalendarClock,
  Bell, Settings, LogOut, Menu, X, ShieldCheck
} from 'lucide-react'

const BELL_SRC = `data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAA` // placeholder, real bell in prod

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [alertCount, setAlertCount] = useState(0)
  const [ringing, setRinging] = useState(false)
  const audioRef = useRef(null)

  const onAlert = useCallback((alert) => {
    setAlertCount(c => c + 1)
    const isUrgent = alert.severity === 'urgent' || alert.type === 'student_absent_warning'

    if (isUrgent) {
      setRinging(true)
      setTimeout(() => setRinging(false), 5000)
      // Play bell sound
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain); gain.connect(ctx.destination)
        osc.frequency.setValueAtTime(880, ctx.currentTime)
        osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.8)
        gain.gain.setValueAtTime(0.4, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 1)
        osc.start(); osc.stop(ctx.currentTime + 1)
      } catch {}
    }

    toast.custom((t) => (
      <div className="alert-toast" style={{ opacity: t.visible ? 1 : 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: isUrgent ? '#fca5a5' : '#fcd34d' }}>
            {isUrgent ? '🔔 Urgent Alert' : '⚠️ Alert'}
          </span>
          <button onClick={() => toast.dismiss(t.id)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>✕</button>
        </div>
        <p style={{ fontSize: 13, color: '#e2e8f0' }}>{alert.message}</p>
      </div>
    ), { duration: isUrgent ? 15000 : 6000 })
  }, [])

  useAlertSocket(onAlert)

  const nav = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/students',  icon: Users,           label: 'Students' },
    { to: '/cameras',   icon: Camera,          label: 'Cameras' },
    { to: '/sessions',  icon: CalendarClock,   label: 'Sessions' },
    { to: '/alerts',    icon: Bell,            label: 'Alerts', badge: alertCount },
    { to: '/settings',  icon: Settings,        label: 'Settings' },
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-deep)' }}>
      {/* Sidebar */}
      <aside style={{
        width: sidebarOpen ? 240 : 68,
        minHeight: '100vh',
        background: 'var(--bg-card)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        transition: 'width 0.2s ease',
        position: 'fixed', top: 0, left: 0, bottom: 0,
        zIndex: 100,
        overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px', display: 'flex', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--border)', minHeight: 70 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: 'linear-gradient(135deg, var(--accent), var(--accent2))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <ShieldCheck size={18} color="#fff" />
          </div>
          {sidebarOpen && (
            <div>
              <div style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 16, color: 'var(--text-1)', lineHeight: 1 }}>SmartAttend</div>
              <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.08em' }}>by Risely</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {nav.map(({ to, icon: Icon, label, badge }) => (
            <NavLink key={to} to={to} onClick={() => badge && setAlertCount(0)} style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 12px', borderRadius: 8,
              color: isActive ? '#fff' : 'var(--text-3)',
              background: isActive ? 'linear-gradient(135deg, rgba(124,58,237,0.25), rgba(79,70,229,0.15))' : 'transparent',
              fontWeight: isActive ? 600 : 400,
              fontSize: 14, position: 'relative',
              transition: 'all 0.15s',
              border: isActive ? '1px solid rgba(124,58,237,0.3)' : '1px solid transparent',
            })}>
              <Icon size={18} style={{ flexShrink: 0 }} />
              {sidebarOpen && <span style={{ whiteSpace: 'nowrap' }}>{label}</span>}
              {badge > 0 && (
                <span style={{
                  marginLeft: 'auto', background: 'var(--red)', color: '#fff',
                  borderRadius: 10, fontSize: 11, fontWeight: 700,
                  padding: '1px 7px', minWidth: 20, textAlign: 'center',
                  ...(ringing && to === '/alerts' ? { animation: 'bellShake 0.5s ease-in-out infinite' } : {}),
                }}>
                  {badge > 99 ? '99+' : badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User + collapse */}
        <div style={{ padding: '12px 8px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {sidebarOpen && (
            <div style={{ padding: '8px 12px', fontSize: 13, color: 'var(--text-3)' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-2)' }}>{user?.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-4)' }}>{user?.is_admin ? 'Administrator' : 'Teacher'}</div>
            </div>
          )}
          <button onClick={() => setSidebarOpen(o => !o)} className="btn btn-ghost btn-sm" style={{ justifyContent: 'center' }}>
            {sidebarOpen ? <X size={15} /> : <Menu size={15} />}
          </button>
          <button onClick={() => { logout(); navigate('/login') }} className="btn btn-ghost btn-sm" style={{ justifyContent: sidebarOpen ? 'flex-start' : 'center', gap: 8 }}>
            <LogOut size={15} />
            {sidebarOpen && 'Sign out'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{
        flex: 1,
        marginLeft: sidebarOpen ? 240 : 68,
        transition: 'margin-left 0.2s ease',
        padding: '32px',
        maxWidth: 'calc(100vw - ' + (sidebarOpen ? 240 : 68) + 'px)',
      }}>
        <Outlet />
      </main>
    </div>
  )
}
