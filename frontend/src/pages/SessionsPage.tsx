import { useEffect, useState } from 'react'
import { Plus, StopCircle, Users, Eye, Clock } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'

interface Session { id: number; subject: string; batch: string; room: string | null; camera_id: number | null; started_at: string; ended_at: string | null; teacher_name: string }
interface Camera  { id: number; name: string; location: string }
interface WatchEntry { id: number; student_id: number; student_name: string; student_code: string; checked_in_at: string; last_seen_at: string | null; warn_15_sent: boolean; email_20_sent: boolean; is_active: boolean }

function WatchListModal({ session, onClose }: { session: Session; onClose: () => void }) {
  const [entries, setEntries] = useState<WatchEntry[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const res = await api.get(`/attendance/sessions/${session.id}/watchlist`)
      setEntries(res.data)
    } catch { toast.error('Failed to load watch list') }
    finally { setLoading(false) }
  }

  useEffect(() => { load(); const i = setInterval(load, 10000); return () => clearInterval(i) }, [])

  const checkout = async (entry: WatchEntry) => {
    try {
      await api.post(`/attendance/sessions/${session.id}/watchlist/${entry.student_id}/checkout`)
      toast.success(`${entry.student_name} checked out`)
      load()
    } catch { toast.error('Checkout failed') }
  }

  const getMissingMinutes = (entry: WatchEntry) => {
    const last = new Date(entry.last_seen_at || entry.checked_in_at)
    return Math.floor((Date.now() - last.getTime()) / 60000)
  }

  const active = entries.filter((e) => e.is_active)
  const left   = entries.filter((e) => !e.is_active)

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 680, maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <div>
            <h3 style={{ margin: 0 }}>Watch List — {session.subject}</h3>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)', fontSize: 13 }}>{session.batch} · {active.length} in class</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={load}>↻ Refresh</button>
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><span className="spinner" style={{ width: 32, height: 32 }} /></div>
          ) : (
            <>
              {active.length > 0 && (
                <>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: 1, marginBottom: 10, textTransform: 'uppercase' }}>In Class ({active.length})</div>
                  {active.map((entry) => {
                    const missing = getMissingMinutes(entry)
                    const statusColor = missing >= 20 ? 'var(--danger)' : missing >= 15 ? 'var(--warning)' : 'var(--success)'
                    const statusBg   = missing >= 20 ? '#450A0A' : missing >= 15 ? '#451A03' : '#14532D'
                    return (
                      <div key={entry.id} style={{ background: 'var(--bg-elevated)', borderRadius: 10, padding: '14px 16px', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 14, border: `1px solid ${missing >= 15 ? statusColor + '40' : 'transparent'}` }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>{entry.student_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>{entry.student_code}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                            Checked in {formatDistanceToNow(new Date(entry.checked_in_at), { addSuffix: true })}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ background: statusBg, color: statusColor, borderRadius: 8, padding: '4px 10px', fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                            {missing >= 20 ? '🚨 ' : missing >= 15 ? '⚠️ ' : '✓ '}{missing}m ago
                          </div>
                          {entry.warn_15_sent  && <div style={{ fontSize: 10, color: 'var(--warning)' }}>⚠ 15m alert sent</div>}
                          {entry.email_20_sent && <div style={{ fontSize: 10, color: 'var(--danger)'  }}>📧 20m email sent</div>}
                          <button className="btn btn-ghost" style={{ marginTop: 8, fontSize: 11, padding: '4px 10px' }} onClick={() => checkout(entry)}>
                            Check Out
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </>
              )}

              {left.length > 0 && (
                <>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: 1, margin: '16px 0 10px', textTransform: 'uppercase' }}>Left ({left.length})</div>
                  {left.map((entry) => (
                    <div key={entry.id} style={{ background: 'var(--bg-elevated)', borderRadius: 10, padding: '12px 16px', marginBottom: 8, opacity: 0.6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{entry.student_name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{entry.student_code}</div>
                      </div>
                      <span className="badge badge-muted">Left</span>
                    </div>
                  ))}
                </>
              )}

              {entries.length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 0' }}>
                  No students checked in yet.<br />
                  <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>Students appear here after kiosk face scan.</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function StartSessionModal({ onClose, onStarted }: { onClose: () => void; onStarted: () => void }) {
  const [form, setForm] = useState({ subject: '', batch: '', room: '', camera_id: '' })
  const [cameras, setCameras] = useState<Camera[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/cameras/').then((r) => setCameras(r.data.filter((c: Camera & { is_active: boolean }) => c.is_active))).catch(() => {})
  }, [])

  const handleSave = async () => {
    if (!form.subject || !form.batch) return toast.error('Subject and batch are required')
    setSaving(true)
    try {
      await api.post('/attendance/sessions', { ...form, camera_id: form.camera_id ? parseInt(form.camera_id) : null })
      toast.success('Session started!')
      onStarted(); onClose()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 440, padding: 28 }}>
        <h3 style={{ margin: '0 0 20px' }}>Start New Session</h3>
        {[
          { key: 'subject', label: 'Subject *',  ph: 'e.g. Mathematics' },
          { key: 'batch',   label: 'Batch *',    ph: 'e.g. CSE-2024-A' },
          { key: 'room',    label: 'Room',       ph: 'e.g. Room 201' },
        ].map(({ key, label, ph }) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>{label}</label>
            <input className="input" placeholder={ph} value={(form as any)[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
          </div>
        ))}
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>Assign Camera</label>
          <select className="input" value={form.camera_id} onChange={(e) => setForm({ ...form, camera_id: e.target.value })}>
            <option value="">— No camera —</option>
            {cameras.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.location})</option>)}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? <span className="spinner" /> : 'Start Session'}</button>
        </div>
      </div>
    </div>
  )
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [showStart, setShowStart] = useState(false)
  const [watchSession, setWatchSession] = useState<Session | null>(null)

  const load = async () => {
    try {
      const res = await api.get('/attendance/sessions?active_only=false')
      setSessions(res.data)
    } catch { toast.error('Failed to load sessions') }
    finally { setLoading(false) }
  }

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i) }, [])

  const endSession = async (s: Session) => {
    if (!confirm(`End session "${s.subject}"?`)) return
    try {
      await api.post(`/attendance/sessions/${s.id}/end`)
      toast.success('Session ended')
      load()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
  }

  const active   = sessions.filter((s) => !s.ended_at)
  const finished = sessions.filter((s) =>  s.ended_at)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Live Sessions</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>{active.length} active · {finished.length} completed today</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowStart(true)}><Plus size={14} /> Start Session</button>
      </div>

      {/* Active sessions */}
      {active.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: 1, marginBottom: 12, textTransform: 'uppercase' }}>Active Now</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
            {active.map((s) => (
              <div key={s.id} className="card" style={{ padding: 20, borderLeft: '3px solid #22C55E' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{s.subject}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>{s.batch}{s.room ? ` · ${s.room}` : ''}</div>
                  </div>
                  <span className="badge badge-success" style={{ flexShrink: 0 }}>
                    <span className="dot dot-green" style={{ width: 6, height: 6 }} /> LIVE
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 14 }}>
                  <Clock size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                  Started {formatDistanceToNow(new Date(s.started_at), { addSuffix: true })} · {s.teacher_name}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-ghost" style={{ fontSize: 12, padding: '7px 12px', flex: 1 }} onClick={() => setWatchSession(s)}>
                    <Eye size={13} /> Watch List
                  </button>
                  <button className="btn btn-danger" style={{ fontSize: 12, padding: '7px 14px' }} onClick={() => endSession(s)}>
                    <StopCircle size={13} /> End
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Past sessions */}
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: 1, marginBottom: 12, textTransform: 'uppercase' }}>History</div>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><span className="spinner" style={{ width: 32, height: 32 }} /></div>
        ) : finished.length === 0 && active.length === 0 ? (
          <div className="card" style={{ padding: 60, textAlign: 'center' }}>
            <p style={{ color: 'var(--text-dim)', margin: '0 0 16px' }}>No sessions yet. Start one to begin monitoring.</p>
            <button className="btn btn-primary" onClick={() => setShowStart(true)}><Plus size={14} /> Start Session</button>
          </div>
        ) : (
          <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
            <table className="table">
              <thead>
                <tr><th>Subject</th><th>Batch</th><th>Teacher</th><th>Started</th><th>Duration</th><th>Status</th></tr>
              </thead>
              <tbody>
                {finished.slice(0, 20).map((s) => {
                  const dur = s.ended_at
                    ? Math.round((new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) / 60000)
                    : null
                  return (
                    <tr key={s.id}>
                      <td><div style={{ fontWeight: 600 }}>{s.subject}</div>{s.room && <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{s.room}</div>}</td>
                      <td>{s.batch}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{s.teacher_name}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{new Date(s.started_at).toLocaleTimeString()}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{dur ? `${dur}m` : '—'}</td>
                      <td><span className="badge badge-muted">Ended</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showStart && <StartSessionModal onClose={() => setShowStart(false)} onStarted={load} />}
      {watchSession && <WatchListModal session={watchSession} onClose={() => setWatchSession(null)} />}
    </div>
  )
}
