import api from './api'
import type { PatientInfo, AgentRunResponse, DesignSessionContext } from '../types/agent'

export const agentApi = {
  greet: () => api.post<{ reply: string }>('/agent/greet'),

  design: (patient: PatientInfo, message: string, session?: DesignSessionContext) =>
    api.post<AgentRunResponse>('/agent/design', { patient, message, ...(session ? { session } : {}) }),
}
