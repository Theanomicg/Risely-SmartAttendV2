import { useEffect, useState } from 'react'
import { Users, Camera, Activity, Bell, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react'
import api from '../lib/api'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface Stats {
  total_students: number
  total_cameras: number
  active_sessions: number
  unread_alerts: number
  present_today: number
  absent_today: number
  cameras_online: number
}

interface Session {
  id: number
  subject: string
  batch: string
  started_at: string
  teacher_name: string
}

const MOCK_TREND = [
  { day: 'Mon', present: 88, absent: 12 },
  { day: 'Tue', present: 91, absent: 9 },
  { day: 'Wed', present: 85, absent: 15 },
  { day: 'Thu', present: 93, absent: 7 },
  { day: 'Fri', present: 78, absent: 22 },
  { day: 'Sat', present: 82, absent: 18 },
  { day: 'Today', present: 87, absent: 13 },
]

function StatCard({ icon: Icon, label, value, sub, color }: any) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'DM Sans, sans-serif', color: 'var(--text-primary)', lineHeight: 1 }}>
            {value ?? <span className="spinner" style={{ width: 24, height: 24 }} />}
          </div>
          {sub && <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>{sub}</div>}
        </div>
        <div style={{
          width: 40, height: 40,
          background: `${color}20`,
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} color={color} />
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Partial<Stats>>({})
  const [sessions, setSessions] = useState<Session[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const [studRes, camRes, sessRes, alertRes] = await Promise.all([
          api.get('/students/'),
          api.get('/cameras/'),
          api.get('/attendance/sessions?active_only=true'),
          api.get('/alerts/unread-count'),
        ])
        const cams = camRes.data as any[]
        setStats({
          total_students: studRes.data.length,
          total_cameras: cams.length,
          cameras_online: cams.filter((c: any) => c.status === 'online').length,
          active_sessions: sessRes.data.length,
          unread_alerts: alertRes.data.count,
        })
        setSessions(sessRes.data.slice(0, 5))
      } catch (e) {
        console.error(e)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Dashboard</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>
          {new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatCard icon={Users}    label="Total Students"   value={stats.total_students}   color="#4A90D9" sub="Enrolled" />
        <StatCard icon={Camera}   label="Cameras"          value={stats.total_cameras != null ? `${stats.cameras_online}/${stats.total_cameras}` : undefined} color="#22C55E" sub="Online" />
        <StatCard icon={Activity} label="Active Sessions"  value={stats.active_sessions}  color="#7C5CFC" sub="Right now" />
        <StatCard icon={Bell}     label="Unread Alerts"    value={stats.unread_alerts}    color={stats.unread_alerts ? '#EF4444' : '#6B7A99'} sub="Pending" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20 }}>
        {/* Attendance trend */}
        <div className="card" style={{ padding: 24 }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15 }}>Weekly Attendance Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={MOCK_TREND}>
              <defs>
                <linearGradient id="gPresent" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#4A90D9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gAbsent" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#EF4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2A45" />
              <XAxis dataKey="day" tick={{ fill: '#6B7A99', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6B7A99', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#1A2138', border: '1px solid #1E2A45', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#E2E8F0' }}
              />
              <Area type="monotone" dataKey="present" stroke="#4A90D9" fill="url(#gPresent)" name="Present" />
              <Area type="monotone" dataKey="absent"  stroke="#EF4444" fill="url(#gAbsent)"  name="Absent" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Active sessions */}
        <div className="card" style={{ padding: 24 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Active Sessions</h3>
          {sessions.length === 0 ? (
            <div style={{ color: 'var(--text-dim)', fontSize: 13, textAlign: 'center', padding: '32px 0' }}>
              No active sessions right now
            </div>
          ) : (
            sessions.map((s) => (
              <div key={s.id} style={{
                background: 'var(--bg-elevated)',
                borderRadius: 10,
                padding: '12px 14px',
                marginBottom: 10,
                borderLeft: '3px solid #4A90D9',
              }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{s.subject}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  {s.batch} · {s.teacher_name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                  Started {new Date(s.started_at).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
