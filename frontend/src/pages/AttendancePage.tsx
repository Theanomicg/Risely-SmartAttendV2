import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Clock, Download } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Session { id: number; subject: string; batch: string; started_at: string; ended_at: string | null; teacher_name: string }
interface AttRecord { id: number; student_id: number; student_name: string; student_code: string; status: string; marked_at: string | null; confidence: number | null; source: string }
interface Summary { total: number; present: number; absent: number; late: number; percentage: number }

const STATUS_OPTIONS = ['present', 'absent', 'late']

function statusBadge(status: string) {
  if (status === 'present') return <span className="badge badge-success"><CheckCircle size={10} /> Present</span>
  if (status === 'absent')  return <span className="badge badge-danger"><XCircle size={10} /> Absent</span>
  return <span className="badge badge-warning"><Clock size={10} /> Late</span>
}

export default function AttendancePage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [records, setRecords] = useState<AttRecord[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/attendance/sessions').then((r) => {
      setSessions(r.data)
      if (r.data.length > 0) setSelectedId(r.data[0].id)
    }).catch(() => toast.error('Failed to load sessions'))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    Promise.all([
      api.get(`/attendance/sessions/${selectedId}/records`),
      api.get(`/attendance/sessions/${selectedId}/summary`),
    ]).then(([rRes, sRes]) => {
      setRecords(rRes.data)
      setSummary(sRes.data)
    }).catch(() => toast.error('Failed to load attendance'))
    .finally(() => setLoading(false))
  }, [selectedId])

  const updateStatus = async (record: AttRecord, newStatus: string) => {
    try {
      await api.patch('/attendance/records/manual', {
        student_id: record.student_id,
        session_id: selectedId,
        status: newStatus,
      })
      setRecords((prev) => prev.map((r) => r.id === record.id ? { ...r, status: newStatus, source: 'manual' } : r))
      // Refresh summary
      api.get(`/attendance/sessions/${selectedId}/summary`).then((r) => setSummary(r.data))
      toast.success('Updated')
    } catch { toast.error('Update failed') }
  }

  const exportCSV = () => {
    if (!records.length) return
    const session = sessions.find((s) => s.id === selectedId)
    const header = 'Student ID,Name,Status,Marked At,Source,Confidence'
    const rows = records.map((r) =>
      `${r.student_code},${r.student_name},${r.status},${r.marked_at || ''},${r.source},${r.confidence ?? ''}`
    )
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `attendance_${session?.subject || selectedId}_${new Date().toLocaleDateString()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const pct = summary?.percentage ?? 0
  const barColor = pct >= 75 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--danger)'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Attendance</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>View and manually override attendance records</p>
        </div>
        <button className="btn btn-ghost" onClick={exportCSV} disabled={!records.length}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Session selector */}
      <div style={{ marginBottom: 20 }}>
        <select
          className="input"
          style={{ maxWidth: 420 }}
          value={selectedId ?? ''}
          onChange={(e) => setSelectedId(Number(e.target.value))}
        >
          <option value="">— Select a session —</option>
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>
              {s.subject} · {s.batch} · {new Date(s.started_at).toLocaleDateString()} {!s.ended_at ? '(LIVE)' : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
          {[
            { label: 'Total',   value: summary.total,   color: '#6B7A99' },
            { label: 'Present', value: summary.present, color: 'var(--success)' },
            { label: 'Absent',  value: summary.absent,  color: 'var(--danger)'  },
            { label: 'Late',    value: summary.late,    color: 'var(--warning)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="stat-card" style={{ padding: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
              <div style={{ fontSize: 26, fontWeight: 700, color, fontFamily: 'DM Sans, sans-serif' }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {summary && (
        <div className="card" style={{ padding: '14px 20px', marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13 }}>
            <span style={{ color: 'var(--text-muted)' }}>Attendance Rate</span>
            <span style={{ fontWeight: 700, color: barColor }}>{pct.toFixed(1)}%</span>
          </div>
          <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 4, transition: 'width 0.4s' }} />
          </div>
        </div>
      )}

      {/* Records table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center' }}><span className="spinner" style={{ width: 32, height: 32 }} /></div>
        ) : records.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-dim)' }}>
            {selectedId ? 'No attendance records for this session.' : 'Select a session to view records.'}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Status</th>
                <th>Time</th>
                <th>Source</th>
                <th>Confidence</th>
                <th>Override</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{r.student_name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>{r.student_code}</div>
                  </td>
                  <td>{statusBadge(r.status)}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                    {r.marked_at ? new Date(r.marked_at).toLocaleTimeString() : '—'}
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ fontSize: 10 }}>{r.source}</span>
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'JetBrains Mono, monospace' }}>
                    {r.confidence != null ? `${(r.confidence * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td>
                    <select
                      className="input"
                      style={{ padding: '5px 8px', fontSize: 12, width: 100 }}
                      value={r.status}
                      onChange={(e) => updateStatus(r, e.target.value)}
                    >
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
