import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { runsApi } from '../services/api'
import type { RunDetail, Candidate } from '../types'
import { useRunStatus } from '../hooks/useRunStatus'
import RunStatusBadge from '../components/RunStatusBadge'
import EnergyChart from '../components/EnergyChart'
import AcceptanceChart from '../components/AcceptanceChart'
import CandidateTable from '../components/CandidateTable'
import PDBeViewer from '../components/PDBeViewer'

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null)
  const [activeTab, setActiveTab] = useState<'results' | 'structure' | 'download'>('results')

  const { progress } = useRunStatus(id || null)

  const fetchRun = useCallback(async () => {
    if (!id) return
    try {
      const res = await runsApi.get(id)
      setRunDetail(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load run')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchRun()
    const interval = setInterval(() => {
      if (progress.running) fetchRun()
    }, 3000)
    return () => clearInterval(interval)
  }, [id, progress.running, fetchRun])

  const handleDownload = async () => {
    if (!id) return
    try {
      const res = await runsApi.download(id)
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proteus-run-${id.slice(0, 8)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {}
  }

  if (isLoading) {
    return <div className="text-center py-12 text-gray-500">Loading run details...</div>
  }

  if (error || !runDetail) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error || 'Run not found'}</p>
        <Link to="/dashboard" className="text-proteus-600 mt-4 inline-block">Back to Dashboard</Link>
      </div>
    )
  }

  const { run, chain_states, candidates } = runDetail
  const isRunning = run.status === 'queued' || run.status === 'running'

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold">{run.target_name} Design</h1>
            <RunStatusBadge status={run.status} />
          </div>
          <p className="text-gray-500 text-sm mt-1">
            Run ID: {run.id} | Created: {new Date(run.created_at).toLocaleString()}
            {run.completed_at && ` | Completed: ${new Date(run.completed_at).toLocaleString()}`}
          </p>
        </div>
        <div className="flex space-x-2">
          {run.status === 'running' && (
            <button
              onClick={async () => {
                if (id) await runsApi.cancel(id).then(fetchRun)
              }}
              className="btn-danger text-sm"
            >
              Cancel
            </button>
          )}
          <button onClick={handleDownload} className="btn-secondary text-sm">
            Download JSON
          </button>
        </div>
      </div>

      {isRunning && (
        <div className="card bg-blue-50 border-blue-200">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
            <div>
              <p className="font-medium text-blue-800">MCMC Run in Progress</p>
              <p className="text-sm text-blue-600">
                Step {progress.currentStep}/{progress.totalSteps} |
                Best Energy: {progress.bestEnergy?.toFixed(4) || 'N/A'} |
                Chains: {run.num_chains}
              </p>
            </div>
          </div>
        </div>
      )}

      {progress.chainEnergies.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EnergyChart
            chainEnergies={progress.chainEnergies}
            steps={progress.steps}
            temperatures={run.temperatures}
          />
          <AcceptanceChart
            acceptanceRates={progress.acceptanceRates}
            temperatures={run.temperatures}
          />
        </div>
      )}

      {!isRunning && candidates.length > 0 && (
        <>
          <div className="flex space-x-1 border-b border-gray-200">
            {(['results', 'structure', 'download'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-proteus-600 text-proteus-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab === 'results' ? 'Results' : tab === 'structure' ? '3D Structure' : 'Download'}
              </button>
            ))}
          </div>

          {activeTab === 'results' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="card text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {run.best_score?.toFixed(4) || '-'}
                  </div>
                  <div className="text-sm text-gray-500">Best Energy Score</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {run.convergence_rhat?.toFixed(4) || '-'}
                  </div>
                  <div className="text-sm text-gray-500">R-hat (&lt;1.05 = converged)</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {run.convergence_ess || '-'}
                  </div>
                  <div className="text-sm text-gray-500">Effective Sample Size</div>
                </div>
                <div className="card text-center">
                  <div className="text-2xl font-bold text-gray-700">{candidates.length}</div>
                  <div className="text-sm text-gray-500">Candidates</div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <CandidateTable
                    candidates={candidates}
                    onSelect={setSelectedCandidate}
                    selectedSequence={selectedCandidate?.sequence}
                  />
                </div>
                <div>
                  {selectedCandidate && (
                    <div className="card space-y-3">
                      <h3 className="font-semibold">Selected Candidate</h3>
                      <div className="bg-gray-50 rounded-lg p-3 font-mono text-sm break-all">
                        {selectedCandidate.sequence}
                      </div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Binding Score</span>
                          <span className="font-medium">
                            {(selectedCandidate.binding_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Stability</span>
                          <span className="font-medium">
                            {(selectedCandidate.stability_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Solubility</span>
                          <span className="font-medium">
                            {(selectedCandidate.solubility_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Mutations</span>
                          <span className="font-medium">
                            {selectedCandidate.num_mutations_from_seed}
                          </span>
                        </div>
                        {selectedCandidate.hydrophobicity !== null && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Hydrophobicity</span>
                            <span className="font-medium">
                              {selectedCandidate.hydrophobicity.toFixed(2)}
                            </span>
                          </div>
                        )}
                        {selectedCandidate.net_charge !== null && (
                          <div className="flex justify-between">
                            <span className="text-gray-500">Net Charge</span>
                            <span className="font-medium">
                              {selectedCandidate.net_charge > 0 ? '+' : ''}
                              {selectedCandidate.net_charge.toFixed(1)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === 'structure' && (
            <PDBeViewer
              pdbId={run.target_pdb_id}
              mutations={selectedCandidate
                ? extractMutations(run.seed_sequence || '', selectedCandidate.sequence)
                : undefined
              }
            />
          )}

          {activeTab === 'download' && (
            <div className="card space-y-4">
              <h3 className="font-semibold">Export Options</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button onClick={handleDownload} className="btn-primary">
                  Download Full Run (JSON)
                </button>
                <button
                  onClick={() => {
                    const csv = [
                      ['rank', 'sequence', 'binding_score', 'stability_score', 'solubility_score'],
                      ...candidates.map((c) => [
                        c.rank, c.sequence, c.binding_score, c.stability_score, c.solubility_score,
                      ]),
                    ].map((r) => r.join(',')).join('\n')
                    const blob = new Blob([csv], { type: 'text/csv' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `proteus-candidates-${run.id.slice(0, 8)}.csv`
                    a.click()
                    URL.revokeObjectURL(url)
                  }}
                  className="btn-secondary"
                >
                  Download Candidates (CSV)
                </button>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 text-xs text-gray-500">
                <p className="font-medium mb-1">Reproducibility Information</p>
                <p>Run UUID: {run.id}</p>
                <p>Configuration: {run.num_chains} chains, {run.steps_per_chain} steps each</p>
                <p>Temperatures: {run.temperatures.join(', ')}</p>
                <p>Created: {new Date(run.created_at).toISOString()}</p>
              </div>
            </div>
          )}
        </>
      )}

      {run.status === 'failed' && run.error_message && (
        <div className="card bg-red-50 border-red-200">
          <h3 className="font-semibold text-red-800">Run Failed</h3>
          <p className="text-red-600 text-sm mt-1">{run.error_message}</p>
        </div>
      )}
    </div>
  )
}

function extractMutations(seed: string, candidate: string) {
  const mutations: { position: number; from: string; to: string }[] = []
  const minLen = Math.min(seed.length, candidate.length)
  for (let i = 0; i < minLen; i++) {
    if (seed[i] !== candidate[i]) {
      mutations.push({ position: i + 1, from: seed[i], to: candidate[i] })
    }
  }
  return mutations
}
