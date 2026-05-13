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
    status?: 'running' | 'round_complete' | 'complete' | 'error'
    phase?: 'research' | 'generate' | 'fold' | 'evaluate'
    round?: number
    target?: string
    sequence?: string
    seed?: string
    pdb_id?: string
    mutations?: { position: number; from: string; to: string }[]
    scores?: Record<string, number>
    fold?: { plddt: number; ptm: number; predicted_aligned_error: number }
    is_best?: boolean
    rounds?: IterationRound[]
    total_time?: number
  }
}

export interface IterationRound {
  round: number
  sequence: string
  binding_score: number
  stability_score: number
  solubility_score: number
  total_energy: number
  fold_plddt: number
  is_best: boolean
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
  rounds?: number[]
  total_time?: number
  disclaimer: string
}
