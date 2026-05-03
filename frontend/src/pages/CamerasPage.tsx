import { useEffect, useState } from 'react'
import { Plus, Camera as CameraIcon, RefreshCw, Trash2, Eye, TestTube } from 'lucide-react'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Camera { id: number; name: string; location: string; rtsp_url: string; status: string; last_seen: string | null; is_active: boolean; notes: string | null }

function AddCameraModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [form, setForm] = useState({ name: '', location: '', rtsp_url: '', notes: '' })
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  const handleTest = async () => {
    if (!form.rtsp_url) return toast.error('Enter RTSP URL first')
    setTesting(true); setTestResult(null)
    try {
      const res = await api.post('/cameras/test-connection', { rtsp_url: form.rtsp_url })
      setTestResult(res.data)
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Test failed') }
    finally { setTesting(false) }
  }

  const handleSave = async () => {
    if (!form.name || !form.location || !form.rtsp_url) return toast.error('Fill all required fields')
    setSaving(true)
    try {
      await api.post('/cameras/', form)
      toast.success('Camera added!')
      onAdded(); onClose()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed to add camera') }
    finally { setSaving(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 520, padding: 28, maxHeight: '90vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 20px' }}>Add New Camera</h3>
        {(['name','location'] as const).map((f) => (
          <div key={f} style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>{f === 'name' ? 'Camera Name *' : 'Location / Room *'}</label>
            <input className="input" placeholder={f === 'name' ? 'e.g. Lab A — Camera 1' : 'e.g. Computer Lab A'} value={form[f]} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
          </div>
        ))}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>RTSP URL *</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="input" placeholder="rtsp://admin:password@192.168.1.100:554/stream" value={form.rtsp_url} onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })} />
            <button className="btn btn-ghost" style={{ flexShrink: 0 }} onClick={handleTest} disabled={testing}>
              {testing ? <span className="spinner" /> : <><TestTube size={14} /> Test</>}
            </button>
          </div>
          {testResult && (
            <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 8, background: testResult.success ? '#14532D20' : '#450A0A', border: `1px solid ${testResult.success ? '#16A34A' : '#DC2626'}40`, fontSize: 12 }}>
              {testResult.success ? (
                <div>
                  <div style={{ color: '#86EFAC', fontWeight: 600 }}>✓ Connection successful — {testResult.resolution}</div>
                  {testResult.preview_b64 && (
                    <img src={`data:image/jpeg;base64,${testResult.preview_b64}`} alt="Preview" style={{ width: '100%', borderRadius: 6, marginTop: 8 }} />
                  )}
                </div>
              ) : <div style={{ color: '#FCA5A5' }}>✗ {testResult.message}</div>}
            </div>
          )}
        </div>
        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 5 }}>Notes (optional)</label>
          <input className="input" placeholder="Any notes about this camera" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? <span className="spinner" /> : 'Add Camera'}</button>
        </div>
      </div>
    </div>
  )
}

function SnapshotModal({ camera, onClose }: { camera: Camera; onClose: () => void }) {
  const [img, setImg] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/cameras/${camera.id}/snapshot`)
      setImg(res.data.image_b64)
    } catch { setImg(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 720, padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0 }}>{camera.name} — Live Snapshot</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost" onClick={load}><RefreshCw size={14} /> Refresh</button>
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
          </div>
        </div>
        {loading ? (
          <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span className="spinner" style={{ width: 40, height: 40 }} /></div>
        ) : img ? (
          <img src={`data:image/jpeg;base64,${img}`} alt="Snapshot" style={{ width: '100%', borderRadius: 8 }} />
        ) : (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>No frame available — camera may be offline</div>
        )}
      </div>
    </div>
  )
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [snapshotCam, setSnapshotCam] = useState<Camera | null>(null)

  const load = async () => {
    try {
      const res = await api.get('/cameras/')
      setCameras(res.data)
    } catch { toast.error('Failed to load cameras') }
    finally { setLoading(false) }
  }

  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i) }, [])

  const deleteCamera = async (cam: Camera) => {
    if (!confirm(`Delete camera "${cam.name}"?`)) return
    await api.delete(`/cameras/${cam.id}`)
    toast.success('Camera removed')
    load()
  }

  const online = cameras.filter((c) => c.status === 'online').length

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Cameras</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>{online}/{cameras.length} cameras online</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}><Plus size={14} /> Add Camera</button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><span className="spinner" style={{ width: 36, height: 36 }} /></div>
      ) : cameras.length === 0 ? (
        <div className="card" style={{ padding: 60, textAlign: 'center' }}>
          <CameraIcon size={48} color="var(--text-dim)" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--text-muted)', margin: '0 0 16px' }}>No cameras configured yet</p>
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}><Plus size={14} /> Add First Camera</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {cameras.map((cam) => (
            <div key={cam.id} className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{cam.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{cam.location}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className={`dot ${cam.status === 'online' ? 'dot-green' : 'dot-red'}`} />
                  <span style={{ fontSize: 12, color: cam.status === 'online' ? 'var(--success)' : 'var(--danger)' }}>
                    {cam.status}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'JetBrains Mono, monospace', background: 'var(--bg-elevated)', padding: '6px 10px', borderRadius: 6, marginBottom: 14, wordBreak: 'break-all' }}>
                {cam.rtsp_url}
              </div>
              {cam.last_seen && (
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 14 }}>
                  Last seen: {new Date(cam.last_seen).toLocaleTimeString()}
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost" style={{ fontSize: 12, padding: '7px 12px' }} onClick={() => setSnapshotCam(cam)}>
                  <Eye size={13} /> Snapshot
                </button>
                <button className="btn btn-danger" style={{ fontSize: 12, padding: '7px 12px', marginLeft: 'auto' }} onClick={() => deleteCamera(cam)}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAdd && <AddCameraModal onClose={() => setShowAdd(false)} onAdded={load} />}
      {snapshotCam && <SnapshotModal camera={snapshotCam} onClose={() => setSnapshotCam(null)} />}
    </div>
  )
}
