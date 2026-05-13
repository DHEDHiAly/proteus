import { create } from 'zustand'
import type { User } from '../types'
import { authApi } from '../services/api'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
  clearError: () => void
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('proteus_access_token'),
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const res = await authApi.login({ email, password })
      localStorage.setItem('proteus_access_token', res.data.access_token)
      localStorage.setItem('proteus_refresh_token', res.data.refresh_token)
      set({ user: res.data.user, isAuthenticated: true, isLoading: false })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Login failed'
      set({ error: msg, isLoading: false })
      throw new Error(msg)
    }
  },

  register: async (email, password, fullName) => {
    set({ isLoading: true, error: null })
    try {
      await authApi.register({ email, password, full_name: fullName })
      set({ isAuthenticated: false, isLoading: false })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Registration failed'
      set({ error: msg, isLoading: false })
      throw new Error(msg)
    }
  },

  logout: () => {
    localStorage.removeItem('proteus_access_token')
    localStorage.removeItem('proteus_refresh_token')
    set({ user: null, isAuthenticated: false })
  },

  loadUser: async () => {
    const token = localStorage.getItem('proteus_access_token')
    if (!token) {
      set({ isAuthenticated: false, user: null })
      return
    }
    try {
      const res = await authApi.getMe()
      set({ user: res.data, isAuthenticated: true })
    } catch {
      set({ isAuthenticated: false, user: null })
    }
  },

  clearError: () => set({ error: null }),
}))
