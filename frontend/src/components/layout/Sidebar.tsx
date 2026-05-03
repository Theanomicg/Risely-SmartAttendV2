import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Camera, ClipboardList,
  Bell, Settings, LogOut, ChevronRight, Activity,
} from 'lucide-react'
import { useAuthStore } from '../../store/auth'
import { useWSStore } from '../../store/ws'
import clsx from 'clsx'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/sessions',  icon: Activity,        label: 'Live Sessions' },
  { to: '/students',  icon: Users,           label: 'Students' },
  { to: '/cameras',   icon: Camera,          label: 'Cameras' },
  { to: '/attendance',icon: ClipboardList,   label: 'Attendance' },
  { to: '/alerts',    icon: Bell,            label: 'Alerts' },
  { to: '/settings',  icon: Settings,        label: 'Settings' },
]

export default function Sidebar() {
  const { admin, logout } = useAuthStore()
  const { unreadCount, connected } = useWSStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside style={{
      width: 240,
      minWidth: 240,
      background: 'var(--bg-card)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      position: 'sticky',
      top: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '24px 20px 20px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36,
            background: 'linear-gradient(135deg, #4A90D9, #7C5CFC)',
            borderRadius: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'DM Sans, sans-serif',
            fontWeight: 800, color: '#fff', fontSize: 16,
          }}>S</div>
          <div>
            <div style={{ fontFamily: 'DM Sans, sans-serif', fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', lineHeight: 1 }}>SmartAttend</div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>Risely Platform</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 12 }}>
          <span className={clsx('dot', connected ? 'dot-green' : 'dot-red')} />
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {connected ? 'Live monitoring active' : 'Connecting...'}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 10px', overflowY: 'auto' }}>
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 2,
              color: isActive ? 'var(--brand-blue)' : 'var(--text-muted)',
              background: isActive ? 'rgba(74,144,217,0.1)' : 'transparent',
              textDecoration: 'none',
              fontSize: 13,
              fontWeight: 500,
              transition: 'all 0.15s',
              position: 'relative',
            })}
          >
            <Icon size={16} />
            <span style={{ flex: 1 }}>{label}</span>
            {label === 'Alerts' && unreadCount > 0 && (
              <span style={{
                background: '#DC2626',
                color: '#fff',
                borderRadius: 99,
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 6px',
                minWidth: 18,
                textAlign: 'center',
              }}>{unreadCount > 99 ? '99+' : unreadCount}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div style={{ padding: '16px', borderTop: '1px solid var(--border)' }}>
        <div style={{
          background: 'var(--bg-elevated)',
          borderRadius: 10,
          padding: '12px',
          marginBottom: 10,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{admin?.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{admin?.role}</div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 1, wordBreak: 'break-all' }}>{admin?.email}</div>
        </div>
        <button className="btn btn-ghost" style={{ width: '100%', justifyContent: 'center' }} onClick={handleLogout}>
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  )
}
