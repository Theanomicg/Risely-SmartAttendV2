import { useState } from 'react'
import { Settings, Bell, Clock, Mail, Shield, ExternalLink } from 'lucide-react'

export default function SettingsPage() {
  const [tab, setTab] = useState<'general' | 'email' | 'monitoring' | 'security'>('general')

  const TABS = [
    { id: 'general',    icon: Settings, label: 'General' },
    { id: 'email',      icon: Mail,     label: 'Email / SMTP' },
    { id: 'monitoring', icon: Clock,    label: 'Monitoring' },
    { id: 'security',   icon: Shield,   label: 'Security' },
  ] as const

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: '-0.5px' }}>Settings</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>Configure SmartAttend system settings</p>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 24 }}>
        {TABS.map(({ id, icon: Icon, label }) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: 'none', border: 'none', padding: '10px 20px', cursor: 'pointer',
            color: tab === id ? 'var(--brand-blue)' : 'var(--text-muted)',
            borderBottom: tab === id ? '2px solid var(--brand-blue)' : '2px solid transparent',
            fontSize: 14, fontWeight: 500, fontFamily: 'Inter, sans-serif',
            display: 'flex', alignItems: 'center', gap: 7,
          }}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <div>
          <div className="card" style={{ padding: 24, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>About SmartAttend</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 20px' }}>System information and version details.</p>
            {[
              ['Version',        'SmartAttend v2.0.0'],
              ['Face Model',     'InsightFace Buffalo_L (ArcFace 512-d)'],
              ['Database',       'SQLite (upgradeable to PostgreSQL)'],
              ['Framework',      'FastAPI + React + Vite'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{k}</span>
                <span style={{ fontSize: 13, fontFamily: 'JetBrains Mono, monospace', color: 'var(--brand-blue)' }}>{v}</span>
              </div>
            ))}
          </div>
          <div className="card" style={{ padding: 24 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>API Documentation</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 14px' }}>Interactive API docs powered by FastAPI.</p>
            <a href="/api/docs" target="_blank" rel="noreferrer" className="btn btn-ghost" style={{ textDecoration: 'none', display: 'inline-flex' }}>
              <ExternalLink size={14} /> Open API Docs
            </a>
          </div>
        </div>
      )}

      {tab === 'email' && (
        <div>
          <div className="card" style={{ padding: 24, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>Zoho SMTP Configuration</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 20px' }}>
              These values are set in your <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>.env</code> file.
              Restart the server after changing them.
            </p>
            {[
              ['SMTP_HOST',     'smtp.zoho.in'],
              ['SMTP_PORT',     '587 (STARTTLS)'],
              ['SMTP_USER',     'alerts@yourdomain.com'],
              ['SMTP_PASSWORD', 'Your Zoho App Password'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 13, fontFamily: 'JetBrains Mono, monospace' }}>{k}</span>
                <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{v}</span>
              </div>
            ))}
          </div>
          <div className="card" style={{ padding: 24 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>How to get a Zoho App Password</h3>
            <ol style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 2, paddingLeft: 20, margin: 0 }}>
              <li>Log in to <strong style={{ color: 'var(--text-primary)' }}>mail.zoho.in</strong> (or .com)</li>
              <li>Go to <strong style={{ color: 'var(--text-primary)' }}>Settings → Security → App Passwords</strong></li>
              <li>Click <strong style={{ color: 'var(--text-primary)' }}>Generate New Password</strong>, name it "SmartAttend"</li>
              <li>Copy the generated password into your <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>.env</code> file as <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>SMTP_PASSWORD</code></li>
            </ol>
          </div>
        </div>
      )}

      {tab === 'monitoring' && (
        <div>
          <div className="card" style={{ padding: 24, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>Monitoring Thresholds</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 20px' }}>
              Set in your <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>.env</code> file.
            </p>
            {[
              ['MONITORING_INTERVAL_SECONDS', '300', 'How often the camera checks for students (default: every 5 min)'],
              ['ABSENT_WARN_MINUTES',         '15',  'Minutes before a panel bell alert is triggered'],
              ['ABSENT_EMAIL_MINUTES',        '20',  'Minutes before an email alert is sent to recipients'],
              ['FACE_THRESHOLD',              '0.45','Face recognition confidence threshold (0–1, higher = stricter)'],
              ['FACE_ENROLLMENT_SAMPLES',     '5',   'Photos required per student for enrollment'],
            ].map(([k, v, desc]) => (
              <div key={k} style={{ padding: '14px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: 'var(--brand-blue)' }}>{k}</span>
                  <span style={{ background: 'var(--bg-elevated)', padding: '2px 10px', borderRadius: 6, fontSize: 12, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>{v}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'security' && (
        <div>
          <div className="card" style={{ padding: 24, marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px', fontSize: 15 }}>Authentication</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: '0 0 20px' }}>JWT-based authentication with configurable expiry.</p>
            {[
              ['SECRET_KEY',                    'Random 32-byte hex string (generate with openssl rand -hex 32)'],
              ['ACCESS_TOKEN_EXPIRE_MINUTES',   '480 (8 hours)'],
              ['KIOSK_API_KEY',                 'Shared secret for kiosk devices'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 20, padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: 'var(--brand-blue)', flexShrink: 0 }}>{k}</span>
                <span style={{ fontSize: 12, color: 'var(--text-dim)', textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </div>
          <div className="card" style={{ padding: 24, borderLeft: '3px solid var(--warning)' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 15, color: 'var(--warning)' }}>⚠ Production Checklist</h3>
            <ul style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 2, paddingLeft: 20, margin: 0 }}>
              <li>Change <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>SECRET_KEY</code> from default</li>
              <li>Change <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>KIOSK_API_KEY</code> from default</li>
              <li>Set <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>ALLOWED_ORIGINS</code> to your actual domain</li>
              <li>Use HTTPS with an SSL certificate (Nginx + Let's Encrypt)</li>
              <li>Set <code style={{ background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>DEBUG=false</code></li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
