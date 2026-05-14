export interface TraceStep {
  step: number
  position: number
  from: string
  to: string
  delta_energy: number
  temperature: number
  narrative: string
}

export interface PatientInfo {
  full_name: string
  age: number
  cancer_type: string
  cancer_stage: string
  tumor_markers: string
  previous_treatments: string
  brain_metastasis: boolean
  notes: string
  modality: string
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
    scores?: Record<string, number | boolean>
    fold?: { plddt: number; ptm: number; predicted_aligned_error: number }
    is_best?: boolean
    rounds?: IterationRound[]
    total_time?: number
    trace?: TraceStep[]
    notes_3d?: string[]
    solubility_tags?: string[]
    fasta?: string
  }
}

export interface IterationRound {
  round: number
  sequence: string
  binding_score: number
  stability_score: number
  solubility_score: number
  total_energy: number
  fold_plddt?: number
  kd_nM?: number
  serum_half_life_min?: number
  selectivity_ratio?: number
  toxicity_flag?: boolean
  delta_g_binding_kcal_mol?: number
  // Triple-Gate Physics Model
  gate1_pass?: boolean
  gate2_pass?: boolean
  gate3_pass?: boolean
  surface_complementarity?: number
  solvation_delta_g?: number
  entropic_penalty?: number
  lab_viability_score?: number
  hbond_count?: number
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
