export interface PatientInfo {
  full_name: string
  age: number
  cancer_type: string
  cancer_stage: string
  tumor_markers: string
  previous_treatments: string
  brain_metastasis: boolean
  notes: string
}

export interface AgentMessage {
  role: 'user' | 'agent'
  content: string
  timestamp?: string
  data?: {
    status?: 'running' | 'complete' | 'error'
    target?: string
    sequence?: string
    pdb_id?: string
    mutations?: { position: number; from: string; to: string }[]
    scores?: Record<string, number>
  }
}

export interface AgentRunRequest {
  patient: PatientInfo
  message: string
}

export interface AgentRunResponse {
  reply: string
  messages: AgentMessage[]
  run_id?: string
  candidate_sequence?: string
  candidate_scores?: Record<string, number>
  pdb_id?: string
  mutations?: { position: number; from: string; to: string }[]
  disclaimer: string
}
