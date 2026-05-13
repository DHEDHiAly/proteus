import axios, { AxiosError } from 'axios'
import type {
  Target,
  TokenResponse,
  User,
  MCMCRun,
  RunDetail,
  RunComparison,
  CreateRunParams,
} from '../types'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('proteus_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('proteus_refresh_token')
      if (refreshToken && error.config && !(error.config as any)._retry) {
        (error.config as any)._retry = true
        try {
          const res = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken })
          const data = res.data as TokenResponse
          localStorage.setItem('proteus_access_token', data.access_token)
          localStorage.setItem('proteus_refresh_token', data.refresh_token)
          if (error.config) {
            error.config.headers.Authorization = `Bearer ${data.access_token}`
            return api(error.config)
          }
        } catch {
          localStorage.removeItem('proteus_access_token')
          localStorage.removeItem('proteus_refresh_token')
          window.location.href = '/login'
        }
      } else {
        localStorage.removeItem('proteus_access_token')
        localStorage.removeItem('proteus_refresh_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post<User>('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post<TokenResponse>('/auth/login', data),
  getMe: () => api.get<User>('/auth/me'),
  updateMe: (data: { full_name?: string }) =>
    api.put<User>('/auth/me', data),
}

export const targetsApi = {
  list: () => api.get<{ targets: Target[]; total: number }>('/targets'),
  get: (name: string) => api.get<Target>(`/targets/${name}`),
  getBinders: (name: string) =>
    api.get<{ target: string; binders: Record<string, unknown>[] }>(`/targets/${name}/binders`),
}

export const runsApi = {
  create: (data: CreateRunParams) => api.post<MCMCRun>('/runs', data),
  list: (params?: { page?: number; page_size?: number; status_filter?: string; target_name?: string }) =>
    api.get<{ runs: MCMCRun[]; total: number; page: number; page_size: number }>('/runs', { params }),
  get: (id: string) => api.get<RunDetail>(`/runs/${id}`),
  getMutations: (id: string, params?: { page?: number; page_size?: number; chain_index?: number }) =>
    api.get<{ mutations: any[]; total: number }>(`/runs/${id}/mutations`, { params }),
  download: (id: string) => api.get(`/runs/${id}/download`),
  cancel: (id: string) => api.post(`/runs/${id}/cancel`),
  compare: (runId1: string, runId2: string) =>
    api.post<RunComparison>(`/runs/compare?run_id_1=${runId1}&run_id_2=${runId2}`),
}

export const adminApi = {
  listUsers: (params?: { page?: number; page_size?: number }) =>
    api.get('/admin/users', { params }),
  updateUser: (id: string, data: { full_name?: string; role?: string; is_active?: boolean }) =>
    api.put(`/admin/users/${id}`, data),
  getAuditLogs: (params?: { page?: number; page_size?: number; action?: string; days?: number }) =>
    api.get('/admin/audit-logs', { params }),
  cleanup: () => api.post('/admin/cleanup'),
  listAllRuns: (params?: { page?: number; page_size?: number; status_filter?: string; target_name?: string }) =>
    api.get('/runs/admin', { params }),
}

export default api
