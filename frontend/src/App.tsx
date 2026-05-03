import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import Sidebar from './components/layout/Sidebar'
import AlertPanel from './components/ui/AlertPanel'
import { useAuthStore } from './store/auth'
import { useWebSocket } from './hooks/useWebSocket'

// Pages (lazy would be better for prod, but fine for now)
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import StudentsPage from './pages/StudentsPage'
import CamerasPage from './pages/CamerasPage'
import SessionsPage from './pages/SessionsPage'
import AttendancePage from './pages/AttendancePage'
import AlertsPage from './pages/AlertsPage'
import SettingsPage from './pages/SettingsPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { admin } = useAuthStore()
  const location = useLocation()
  if (!admin) return <Navigate to="/login" state={{ from: location }} replace />
  return <>{children}</>
}

function AppShell() {
  useWebSocket()

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Top bar */}
        <header style={{
          height: 56,
          background: 'var(--bg-card)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 20px',
          gap: 10,
          flexShrink: 0,
        }}>
          <AlertPanel />
        </header>
        {/* Page content */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          <Routes>
            <Route path="/"           element={<DashboardPage />} />
            <Route path="/sessions"   element={<SessionsPage />} />
            <Route path="/students"   element={<StudentsPage />} />
            <Route path="/cameras"    element={<CamerasPage />} />
            <Route path="/attendance" element={<AttendancePage />} />
            <Route path="/alerts"     element={<AlertsPage />} />
            <Route path="/settings"   element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const { restoreSession } = useAuthStore()

  useEffect(() => {
    restoreSession()
  }, [])

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            fontSize: 13,
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        />
      </Routes>
    </>
  )
}
