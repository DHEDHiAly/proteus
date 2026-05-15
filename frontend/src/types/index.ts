export interface Target {
  name: string
  pdb_id: string
  full_name: string
  binding_site_residues: number[]
  binding_pocket_center: number[]
  native_ligand: string
  known_ic50_nM: number
  cancer_type: string
  cancer_prevalence: string
  clinical_relevance: string
  difficulty_score: number
  notes: string
}

export interface User {
  id: string
  email: string
  full_name: string
  role: 'fellow' | 'mentor' | 'admin'
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface RunConfig {
  num_chains: number
  temperatures: number[]
  steps_per_chain: number
  swap_interval: number
  proposal_distribution: string
  acceptance_criterion: string
  transition_ops: {
    point_substitution: number
    esm_guided_substitution: number
    block_replacement: number
    llm_jump: number
  }
}

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface MCMCRun {
  id: string
  user_id: string
  target_name: string
  target_pdb_id: string
  seed_sequence: string | null
  status: RunStatus
  num_chains: number
  temperatures: number[]
  steps_per_chain: number
  total_steps_completed: number
  best_score: number | null
  best_sequence: string | null
  convergence_rhat: number | null
  convergence_ess: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export interface ChainState {
  chain_index: number
  step: number
  temperature: number
  current_energy: number
  acceptance_rate: number | null
  best_energy: number | null
  best_sequence: string | null
}

export interface Candidate {
  rank: number
  sequence: string
  binding_score: number
  stability_score: number
  solubility_score: number
  hydrophobicity: number | null
  net_charge: number | null
  aggregation_risk: string | null
  num_mutations_from_seed: number
  sequence_entropy: number | null
  homology_to_known: number | null
  // Extended biophysical fields
  kd_nM?: number | null
  delta_g_binding_kcal_mol?: number | null
  total_energy?: number | null
  selectivity_ratio?: number | null
  serum_half_life_min?: number | null
  toxicity_flag?: boolean | null
  lab_viability_score?: number | null
}

export interface MutationStep {
  chain_index: number
  step: number
  position: number
  from_aa: string
  to_aa: string
  mutation_type: string
  energy_before: number
  energy_after: number
  delta_energy: number
  acceptance_probability: number
  accepted: boolean
  temperature: number
}

export interface RunDetail {
  run: MCMCRun
  chain_states: ChainState[]
  candidates: Candidate[]
}

export interface WebSocketMessage {
  type: 'progress' | 'chain_complete' | 'complete' | 'error'
  run_id: string
  chain_index?: number
  step?: number
  total_steps?: number
  current_energy?: number
  best_energy?: number
  acceptance_rate?: number
  temperature?: number
  current_sequence?: string
  best_sequence?: string
  converged?: boolean
  rhat?: number
  ess?: number
  wall_time_seconds?: number
  message?: string
}

export interface RunComparison {
  run_1: RunCompareData
  run_2: RunCompareData
}

interface RunCompareData {
  id: string
  target_name: string
  status: string
  best_score: number | null
  best_sequence: string | null
  num_chains: number
  steps_per_chain: number
  convergence_rhat: number | null
  convergence_ess: number | null
  created_at: string | null
  top_candidates: Candidate[]
}

export interface CreateRunParams {
  target_name: string
  seed_sequence?: string
  num_chains?: number
  temperatures?: number[]
  steps_per_chain?: number
  config_overrides?: Record<string, unknown>
}
