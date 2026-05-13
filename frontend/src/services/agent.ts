import axios from 'axios'
import type { PatientInfo, AgentRunResponse, AgentMessage } from '../types/agent'

const API = '/api/v1'

const api = axios.create({
  baseURL: API,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('proteus_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export const agentApi = {
  greet: () => api.post<{ reply: string }>('/agent/greet'),

  design: (patient: PatientInfo, message: string) =>
    api.post<AgentRunResponse>('/agent/design', { patient, message }),
}
