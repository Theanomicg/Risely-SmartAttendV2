import { create } from 'zustand'
import api from '../lib/api'

interface Admin {
  id: number
  name: string
  email: string
  role: string
}

interface AuthState {
  admin: Admin | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  restoreSession: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  admin: null,
  token: null,
  loading: false,

  login: async (email, password) => {
    set({ loading: true })
    const res = await api.post('/auth/login', { email, password })
    const { access_token, admin_id, name, role } = res.data
    localStorage.setItem('sa_token', access_token)
    localStorage.setItem('sa_admin', JSON.stringify({ id: admin_id, name, email, role }))
    set({ token: access_token, admin: { id: admin_id, name, email, role }, loading: false })
  },

  logout: () => {
    localStorage.removeItem('sa_token')
    localStorage.removeItem('sa_admin')
    set({ token: null, admin: null })
  },

  restoreSession: () => {
    const token = localStorage.getItem('sa_token')
    const adminStr = localStorage.getItem('sa_admin')
    if (token && adminStr) {
      try {
        const admin = JSON.parse(adminStr)
        set({ token, admin })
      } catch {
        localStorage.removeItem('sa_token')
        localStorage.removeItem('sa_admin')
      }
    }
  },
}))
