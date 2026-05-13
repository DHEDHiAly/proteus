import { useState, useEffect } from 'react'
import { runsApi } from '../services/api'
import type { MCMCRun, RunComparison as RunComparisonType } from '../types'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

export default function ComparePage() {
  const [runs, setRuns] = useState<MCMCRun[]>([])
  const [runId1, setRunId1] = useState('')
  const [runId2, setRunId2] = useState('')
  const [comparison, setComparison] = useState<RunComparisonType | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    runsApi.list({ page_size: 50 }).then((res) => {
      setRuns(res.data.runs.filter((r) => r.status === 'completed'))
    }).catch(() => {})
  }, [])

  const handleCompare = async () => {
    if (!runId1 || !runId2) {
      setError('Please select two runs')
      return
    }
    if (runId1 === runId2) {
      setError('Please select two different runs')
      return
    }
    setError('')
    setIsLoading(true)
    try {
      const res = await runsApi.compare(runId1, runId2)
      setComparison(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to compare runs')
    } finally {
      setIsLoading(false)
    }
  }

  const selectedIds = runs.filter(
    (r) => r.id === runId1 || r.id === runId2
  )

  const chartData = comparison
    ? [
        {
          name: 'Best Score',
          [`${comparison.run_1.id.slice(0, 8)}`]: comparison.run_1.best_score || 0,
          [`${comparison.run_2.id.slice(0, 8)}`]: comparison.run_2.best_score || 0,
        },
        {
          name: 'R-hat',
          [`${comparison.run_1.id.slice(0, 8)}`]: comparison.run_1.convergence_rhat || 0,
          [`${comparison.run_2.id.slice(0, 8)}`]: comparison.run_2.convergence_rhat || 0,
        },
        {
          name: 'ESS',
          [`${comparison.run_1.id.slice(0, 8)}`]: comparison.run_1.convergence_ess || 0,
          [`${comparison.run_2.id.slice(0, 8)}`]: comparison.run_2.convergence_ess || 0,
        },
      ]
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Compare Designs</h1>
        <p className="text-gray-500 text-sm mt-1">
          Side-by-side comparison of two completed runs for the same target
        </p>
      </div>

      <div className="card">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Run 1</label>
            <select value={runId1} onChange={(e) => setRunId1(e.target.value)} className="input-field">
              <option value="">Select a run...</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.target_name} - {new Date(r.created_at).toLocaleDateString()} - Score: {r.best_score?.toFixed(3) || 'N/A'}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Run 2</label>
            <select value={runId2} onChange={(e) => setRunId2(e.target.value)} className="input-field">
              <option value="">Select a run...</option>
              {runs.filter((r) => r.id !== runId1).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.target_name} - {new Date(r.created_at).toLocaleDateString()} - Score: {r.best_score?.toFixed(3) || 'N/A'}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
        <button
          onClick={handleCompare}
          className="btn-primary mt-4"
          disabled={isLoading || !runId1 || !runId2}
        >
          {isLoading ? 'Comparing...' : 'Compare Runs'}
        </button>
      </div>

      {comparison && (
        <>
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">Convergence Metrics Comparison</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey={`${comparison.run_1.id.slice(0, 8)}`} fill="#3b82f6" />
                <Bar dataKey={`${comparison.run_2.id.slice(0, 8)}`} fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[comparison.run_1, comparison.run_2].map((runData, idx) => (
              <div key={idx} className="card">
                <h3 className="font-semibold mb-2">
                  Run {idx + 1}: {runData.target_name}
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Best Score</span>
                    <span className="font-medium">{runData.best_score?.toFixed(4) || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Best Sequence</span>
                    <span className="font-mono text-xs max-w-[200px] truncate">{runData.best_sequence}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">R-hat</span>
                    <span>{runData.convergence_rhat?.toFixed(4) || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">ESS</span>
                    <span>{runData.convergence_ess || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Chains</span>
                    <span>{runData.num_chains}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Steps/Chain</span>
                    <span>{runData.steps_per_chain}</span>
                  </div>
                </div>
                <h4 className="font-medium text-sm mt-4 mb-2">Top Candidates</h4>
                <div className="space-y-2">
                  {runData.top_candidates.map((c) => (
                    <div key={c.rank} className="flex justify-between text-xs bg-gray-50 rounded p-2">
                      <span className="font-mono truncate max-w-[150px]">{c.sequence}</span>
                      <span className="text-gray-500">
                        {(c.binding_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
