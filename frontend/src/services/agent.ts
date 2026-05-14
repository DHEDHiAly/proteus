import api from './api'
import type { PatientInfo, AgentRunResponse } from '../types/agent'

export const agentApi = {
  greet: () => api.post<{ reply: string }>('/agent/greet'),

  design: (patient: PatientInfo, message: string) =>
    api.post<AgentRunResponse>('/agent/design', { patient, message }),
}
