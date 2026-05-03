import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sa_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('sa_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const kioskApi = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

kioskApi.interceptors.request.use((config) => {
  const key = import.meta.env.VITE_KIOSK_API_KEY || ''
  if (key) config.headers['x-kiosk-key'] = key
  return config
})

export default api
