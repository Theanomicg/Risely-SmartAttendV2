import { create } from 'zustand'

export interface LiveAlert {
  id: string
  type: string
  severity: 'info' | 'warning' | 'urgent'
  student_name?: string
  student_id?: string
  session?: string
  minutes?: number
  message?: string
  play_bell?: boolean
  timestamp: Date
}

interface WSState {
  connected: boolean
  alerts: LiveAlert[]
  unreadCount: number
  addAlert: (alert: LiveAlert) => void
  clearAlert: (id: string) => void
  clearAll: () => void
  markAllRead: () => void
}

export const useWSStore = create<WSState>((set) => ({
  connected: false,
  alerts: [],
  unreadCount: 0,

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50),
      unreadCount: state.unreadCount + 1,
    })),

  clearAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    })),

  clearAll: () => set({ alerts: [], unreadCount: 0 }),
  markAllRead: () => set({ unreadCount: 0 }),
}))

// Bell audio using Web Audio API
let audioCtx: AudioContext | null = null

export function playAlertBell() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const ctx = audioCtx

    const playTone = (freq: number, start: number, dur: number, vol: number) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = freq
      osc.type = 'sine'
      gain.gain.setValueAtTime(0, ctx.currentTime + start)
      gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + start + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur)
      osc.start(ctx.currentTime + start)
      osc.stop(ctx.currentTime + start + dur)
    }

    // Double bell chime
    playTone(880, 0,    0.6, 0.4)
    playTone(660, 0.05, 0.6, 0.3)
    playTone(880, 0.8,  0.6, 0.4)
    playTone(660, 0.85, 0.6, 0.3)
  } catch (e) {
    console.warn('Bell audio failed:', e)
  }
}

export function playUrgentBell() {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const ctx = audioCtx

    const playTone = (freq: number, start: number, dur: number, vol: number) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = freq
      osc.type = 'square'
      gain.gain.setValueAtTime(0, ctx.currentTime + start)
      gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + start + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur)
      osc.start(ctx.currentTime + start)
      osc.stop(ctx.currentTime + start + dur)
    }

    // Urgent triple alarm
    for (let i = 0; i < 3; i++) {
      playTone(1200, i * 0.4,        0.25, 0.3)
      playTone(900,  i * 0.4 + 0.25, 0.15, 0.2)
    }
  } catch (e) {
    console.warn('Urgent bell failed:', e)
  }
}
