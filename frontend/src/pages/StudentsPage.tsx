import { useEffect, useState, useRef, useCallback } from 'react'
import { Plus, Camera, CheckCircle, XCircle, Search, Trash2, Upload } from 'lucide-react'
import Webcam from 'react-webcam'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Student { id: number; student_id: string; name: string; batch: string; email: string; face_samples_count: number; is_face_enrolled: boolean }

function EnrollModal({ student, onClose, onDone }: { student: Student; onClose: () => void; onDone: () => void }) {
  const webcamRef = useRef<Webcam>(null)
  const [count, setCount] = useState(student.face_samples_count)
  const required = 5
  const [capturing, setCapturing] = useState(false)
  const [uploading, setUploading] = useState(false)

  const capture = useCallback(async () => {
    const img = webcamRef.current?.getScreenshot()
    if (!img) return toast.error('Could not capture image')
    setCapturing(true)
    try {
      const formData = new FormData()
      formData.append('image_b64', img)
      const res = await api.post(`/students/${student.student_id}/enroll-face`, formData)
      setCount(res.data.samples_stored)
      toast.success(res.data.message)
      if (res.data.is_complete) { toast.success('Enrollment complete!'); onDone(); onClose() }
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Capture failed') }
    finally { setCapturing(false) }
  }, [student.student_id])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    for (const file of files.slice(0, required - count)) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await api.post(`/students/${student.student_id}/enroll-face/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
        setCount(res.data.samples_stored)
        if (res.data.is_complete) { toast.success('Enrollment complete!'); setUploading(false); onDone(); onClose(); return }
      } catch (e: any) { toast.error(e.response?.data?.detail || 'Upload failed') }
    }
    setUploading(false)
    toast.success('Photos uploaded!')
  }

  const resetSamples = async () => {
    if (!confirm('Delete all face samples for this student?')) return
    await api.delete(`/students/${student.student_id}/face-samples`)
    setCount(0)
    toast.success('Samples reset')
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 560, padding: 28 }}>
        <h3 style={{ margin: '0 0 4px' }}>Enroll Face — {student.name}</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 20px' }}>Capture {required} clear photos. Ask student to look directly at camera.</p>
        
        {/* Progress */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            <span>Samples captured</span><span style={{ color: 'var(--brand-blue)' }}>{count}/{required}</span>
          </div>
          <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${(count / required) * 100}%`, background: count >= required ? 'var(--success)' : 'var(--brand-blue)', borderRadius: 3, transition: 'width 0.3s' }} />
          </div>
        </div>

        <Webcam
          ref={webcamRef}
          screenshotFormat="image/jpeg"
          style={{ width: '100%', borderRadius: 10, marginBottom: 16, background: '#000' }}
          videoConstraints={{ width: 640, height: 480, facingMode: 'user' }}
        />

        <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={capture} disabled={capturing || count >= required}>
            {capturing ? <span className="spinner" /> : <><Camera size={14} /> Capture Photo</>}
          </button>
          <label className="btn btn-ghost" style={{ cursor: 'pointer' }}>
            <Upload size={14} /> Upload
            <input type="file" multiple accept="image/*" style={{ display: 'none' }} onChange={handleFileUpload} disabled={uploading} />
          </label>
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between' }}>
          <button className="btn btn-ghost" style={{ color: 'var(--danger)', borderColor: '#450A0A' }} onClick={resetSamples}>Reset Samples</button>
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

function AddStudentModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [form, setForm] = useState({ student_id: '', name: '', batch: '', email: '', phone: '' })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!form.student_id || !form.name || !form.batch) return toast.error('ID, name and batch are required')
    setSaving(true)
    try {
      await api.post('/students/', form)
      toast.success('Student added!')
      onAdded(); onClose()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    finally { setSaving(false) }
  }

  const fields = [
    { key: 'student_id', label: 'Student ID *', placeholder: 'e.g. STU001' },
    { key: 'name',       label: 'Full Name *',  placeholder: 'e.g. Rahul Sharma' },
    { key: 'batch',      label: 'Batch *',      placeholder: 'e.g. CSE-2024-A' },
    { key: 'email',      label: 'Email',        placeholder: 'student@school.com' },
    { key: 'phone',      label: 'Phone',        placeholder: '+91 99999 99999' },
  ]

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 460, padding: 28 }}>
        <h3 style={{ margin: '0 0 20px' }}>Add Student</h3>
        {fields.map(({ key, label, placeholder }) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>{label}</label>
            <input className="input" placeholder={placeholder} value={(form as any)[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
          </div>
        ))}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? <span className="spinner" /> : 'Add Student'}</button>
        </div>
      </div>
    </div>
  )
}

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [enrollStudent, setEnrollStudent] = useState<Student | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const res = await api.get('/students/', { params: { search: search || undefined } })
      setStudents(res.data)
    } catch { toast.error('Failed to load students') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [search])

  const deleteStudent = async (s: Student) => {
    if (!confirm(`Deactivate student "${s.name}"?`)) return
    await api.delete(`/students/${s.student_id}`)
    toast.success('Student deactivated')
    load()
  }

  const enrolled = students.filter((s) => s.is_face_enrolled).length

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Students</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>{students.length} students · {enrolled} face-enrolled</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}><Plus size={14} /> Add Student</button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ position: 'relative', maxWidth: 320 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
            <input className="input" style={{ paddingLeft: 36 }} placeholder="Search students..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center' }}><span className="spinner" style={{ width: 32, height: 32 }} /></div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Student</th><th>Batch</th><th>Face Enrollment</th><th>Samples</th><th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace' }}>{s.student_id}</div>
                  </td>
                  <td><span className="badge badge-info">{s.batch}</span></td>
                  <td>
                    {s.is_face_enrolled
                      ? <span className="badge badge-success"><CheckCircle size={10} /> Enrolled</span>
                      : <span className="badge badge-warning"><XCircle size={10} /> Pending</span>}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 13 }}>{s.face_samples_count}/5</td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 12px' }} onClick={() => setEnrollStudent(s)}>
                        <Camera size={13} /> Enroll
                      </button>
                      <button className="btn btn-ghost" style={{ fontSize: 12, padding: '6px 10px', color: 'var(--danger)' }} onClick={() => deleteStudent(s)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAdd && <AddStudentModal onClose={() => setShowAdd(false)} onAdded={load} />}
      {enrollStudent && <EnrollModal student={enrollStudent} onClose={() => setEnrollStudent(null)} onDone={load} />}
    </div>
  )
}
