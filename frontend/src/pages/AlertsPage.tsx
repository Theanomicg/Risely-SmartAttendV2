import { useEffect, useState } from 'react'
import { Bell, CheckCheck, Trash2, Mail, Plus, Send } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'

interface Alert { id: number; type: string; severity: string; message: string; student_name: string | null; session_subject: string | null; email_sent: boolean; is_read: boolean; created_at: string; snapshot_path: string | null }
interface Recipient { id: number; email: string; name: string; is_active: boolean }

const SEVERITY_STYLE: Record<string, { bg: string; border: string; color: string; icon: string }> = {
  urgent:  { bg: '#450A0A', border: '#DC2626', color: '#FCA5A5', icon: '🚨' },
  warning: { bg: '#451A03', border: '#D97706', color: '#FCD34D', icon: '⚠️' },
  info:    { bg: 'var(--bg-elevated)', border: 'var(--border)', color: 'var(--text-muted)', icon: 'ℹ️' },
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [recipients, setRecipients] = useState<Recipient[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'alerts' | 'recipients'>('alerts')
  const [newEmail, setNewEmail] = useState('')
  const [newName, setNewName] = useState('')
  const [sendingTest, setSendingTest] = useState(false)

  const loadAlerts = async () => {
    try {
      const res = await api.get('/alerts/?limit=100')
      setAlerts(res.data)
    } catch { toast.error('Failed to load alerts') }
    finally { setLoading(false) }
  }

  const loadRecipients = async () => {
    try {
      const res = await api.get('/alerts/recipients')
      setRecipients(res.data)
    } catch {}
  }

  useEffect(() => { loadAlerts(); loadRecipients() }, [])

  const markAllRead = async () => {
    await api.post('/alerts/mark-all-read')
    setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
    toast.success('All marked as read')
  }

  const addRecipient = async () => {
    if (!newEmail || !newName) return toast.error('Name and email required')
    try {
      await api.post('/alerts/recipients', { email: newEmail, name: newName })
      toast.success('Recipient added')
      setNewEmail(''); setNewName('')
      loadRecipients()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
  }

  const removeRecipient = async (id: number) => {
    await api.delete(`/alerts/recipients/${id}`)
    toast.success('Removed')
    loadRecipients()
  }

  const sendTest = async () => {
    setSendingTest(true)
    try {
      const res = await api.post('/alerts/test-email')
      if (res.data.ok) toast.success(`Test email sent to ${res.data.sent_to.join(', ')}`)
      else toast.error('Test email failed')
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    finally { setSendingTest(false) }
  }

  const unread = alerts.filter((a) => !a.is_read).length

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Alerts</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>
            {unread > 0 ? <span style={{ color: 'var(--danger)' }}>{unread} unread</span> : 'All caught up'} · {alerts.length} total
          </p>
        </div>
        {unread > 0 && (
          <button className="btn btn-ghost" onClick={markAllRead}><CheckCheck size={14} /> Mark all read</button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        {(['alerts', 'recipients'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: 'none', border: 'none', padding: '10px 20px', cursor: 'pointer',
            color: tab === t ? 'var(--brand-blue)' : 'var(--text-muted)',
            borderBottom: tab === t ? '2px solid var(--brand-blue)' : '2px solid transparent',
            fontSize: 14, fontWeight: 500, fontFamily: 'Inter, sans-serif',
          }}>
            {t === 'alerts' ? <><Bell size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Alert History</> : <><Mail size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />Email Recipients</>}
          </button>
        ))}
      </div>

      {tab === 'alerts' && (
        <div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 60 }}><span className="spinner" style={{ width: 32, height: 32 }} /></div>
          ) : alerts.length === 0 ? (
            <div className="card" style={{ padding: 60, textAlign: 'center' }}>
              <Bell size={40} color="var(--text-dim)" style={{ margin: '0 auto 12px' }} />
              <p style={{ color: 'var(--text-dim)' }}>No alerts yet</p>
            </div>
          ) : (
            <div>
              {alerts.map((a) => {
                const style = SEVERITY_STYLE[a.severity] || SEVERITY_STYLE.info
                return (
                  <div key={a.id} style={{
                    background: style.bg,
                    border: `1px solid ${a.is_read ? 'var(--border)' : style.border}`,
                    borderRadius: 12,
                    padding: '16px 20px',
                    marginBottom: 10,
                    opacity: a.is_read ? 0.6 : 1,
                    transition: 'opacity 0.2s',
                  }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <span style={{ fontSize: 18, lineHeight: 1.2 }}>{style.icon}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                          <div style={{ fontWeight: 600, fontSize: 14, color: style.color }}>{a.message}</div>
                          <div style={{ flexShrink: 0, display: 'flex', gap: 6, alignItems: 'center' }}>
                            {a.email_sent && <span className="badge badge-info" style={{ fontSize: 10 }}>📧 emailed</span>}
                            {!a.is_read && <span style={{ width: 7, height: 7, background: 'var(--brand-blue)', borderRadius: '50%', display: 'inline-block' }} />}
                          </div>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                          {a.student_name && <span>{a.student_name}</span>}
                          {a.session_subject && <span> · {a.session_subject}</span>}
                          <span style={{ marginLeft: 10, color: 'var(--text-dim)' }}>
                            {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {tab === 'recipients' && (
        <div>
          <div className="card" style={{ padding: 20, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15 }}>Add Alert Recipient</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 16px' }}>
              These addresses receive email when a student is absent 20+ minutes. Add up to 3 recipients.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <input className="input" placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} style={{ maxWidth: 200 }} />
              <input className="input" placeholder="Email address" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} type="email" />
              <button className="btn btn-primary" style={{ flexShrink: 0 }} onClick={addRecipient} disabled={recipients.length >= 3}>
                <Plus size={14} /> Add
              </button>
            </div>
            {recipients.length >= 3 && (
              <p style={{ fontSize: 12, color: 'var(--warning)', marginTop: 8 }}>Maximum 3 recipients.</p>
            )}
          </div>

          {recipients.length > 0 && (
            <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 16 }}>
              <table className="table">
                <thead><tr><th>Name</th><th>Email</th><th>Status</th><th></th></tr></thead>
                <tbody>
                  {recipients.map((r) => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 600 }}>{r.name}</td>
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{r.email}</td>
                      <td><span className={`badge ${r.is_active ? 'badge-success' : 'badge-muted'}`}>{r.is_active ? 'Active' : 'Inactive'}</span></td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '5px 10px', color: 'var(--danger)' }} onClick={() => removeRecipient(r.id)}>
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 15 }}>Test Email</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 14px' }}>Send a test email to all active recipients to verify your Zoho SMTP configuration.</p>
            <button className="btn btn-ghost" onClick={sendTest} disabled={sendingTest || recipients.length === 0}>
              {sendingTest ? <span className="spinner" /> : <><Send size={14} /> Send Test Email</>}
            </button>
            {recipients.length === 0 && (
              <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}>Add at least one recipient first.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
