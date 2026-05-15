import { useState, useEffect } from 'react'
import { runsApi } from '../services/api'
import type { MCMCRun, RunComparison as RunComparisonType } from '../types'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'

// ── Sequence diff view ────────────────────────────────────────────────────────
function SequenceDiff({ seq1, seq2, label1, label2 }: {
  seq1: string; seq2: string; label1: string; label2: string
}) {
  const maxLen = Math.max(seq1.length, seq2.length)
  const chars1 = seq1.padEnd(maxLen, ' ').split('')
  const chars2 = seq2.padEnd(maxLen, ' ').split('')
  const identityCount = chars1.filter((c, i) => c === chars2[i] && c !== ' ').length
  const validLen = Math.min(seq1.length, seq2.length)
  const identity = validLen > 0 ? ((identityCount / validLen) * 100).toFixed(1) : '0.0'

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>Sequence alignment</span>
        <span className="font-mono">{identity}% identity ({identityCount}/{validLen} positions)</span>
      </div>
      {[{ label: label1, chars: chars1 }, { label: label2, chars: chars2 }].map(({ label, chars }, rowIdx) => (
        <div key={rowIdx} className="flex items-start space-x-2">
          <span className="text-xs text-gray-400 w-16 flex-shrink-0 pt-0.5 font-mono truncate">{label}</span>
          <div className="flex flex-wrap gap-px font-mono text-[10px]">
            {chars.map((ch, i) => {
              const other = rowIdx === 0 ? chars2[i] : chars1[i]
              const mismatch = ch !== other && ch !== ' ' && other !== ' '
              return (
                <span
                  key={i}
                  className={`w-3.5 text-center rounded-sm leading-4 ${
                    mismatch
                      ? 'bg-red-900/50 text-red-300'
                      : ch === ' '
                      ? 'text-gray-800'
                      : 'bg-gray-800 text-gray-300'
                  }`}
                >
                  {ch === ' ' ? '·' : ch}
                </span>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Metric bar row ────────────────────────────────────────────────────────────
function MetricRow({ label, val1, val2, id1, id2, fmt }: {
  label: string
  val1: number | null | undefined
  val2: number | null | undefined
  id1: string
  id2: string
  fmt?: (v: number) => string
}) {
  const f = fmt ?? ((v: number) => (v * 100).toFixed(1) + '%')
  const max = Math.max(Math.abs(val1 ?? 0), Math.abs(val2 ?? 0), 1)
  const bar = (v: number | null | undefined, color: string) => {
    const pct = v != null ? Math.min(100, (Math.abs(v) / max) * 100) : 0
    return (
      <div className="flex items-center space-x-1.5 flex-1">
        <div className="flex-1 bg-gray-800 rounded-sm h-1.5 overflow-hidden">
          <div className={`h-full ${color} rounded-sm`} style={{ width: pct + '%' }} />
        </div>
        <span className="text-[10px] font-mono text-gray-300 w-20 text-right">
          {v != null ? f(v) : '—'}
        </span>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-[100px_1fr_1fr] gap-2 items-center py-0.5">
      <span className="text-[10px] text-gray-500">{label}</span>
      {bar(val1, 'bg-blue-500')}
      {bar(val2, 'bg-emerald-500')}
    </div>
  )
}

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
    if (!runId1 || !runId2) { setError('Please select two runs'); return }
    if (runId1 === runId2) { setError('Please select two different runs'); return }
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

  // Convergence chart: best_score, r-hat, ESS
  const convergenceData = comparison
    ? [
        {
          name: 'Best Score',
          [comparison.run_1.id.slice(0, 8)]: comparison.run_1.best_score || 0,
          [comparison.run_2.id.slice(0, 8)]: comparison.run_2.best_score || 0,
        },
        {
          name: 'R-hat',
          [comparison.run_1.id.slice(0, 8)]: comparison.run_1.convergence_rhat || 0,
          [comparison.run_2.id.slice(0, 8)]: comparison.run_2.convergence_rhat || 0,
        },
        {
          name: 'ESS',
          [comparison.run_1.id.slice(0, 8)]: comparison.run_1.convergence_ess || 0,
          [comparison.run_2.id.slice(0, 8)]: comparison.run_2.convergence_ess || 0,
        },
      ]
    : []

  // Radar chart data — top candidate metrics from each run
  const topCand = (run: any) => run.top_candidates?.[0] ?? {}
  const radarData = comparison
    ? [
        { metric: 'Binding', A: (topCand(comparison.run_1).binding_score ?? 0) * 100, B: (topCand(comparison.run_2).binding_score ?? 0) * 100 },
        { metric: 'Stability', A: (topCand(comparison.run_1).stability_score ?? 0) * 100, B: (topCand(comparison.run_2).stability_score ?? 0) * 100 },
        { metric: 'Solubility', A: (topCand(comparison.run_1).solubility_score ?? 0) * 100, B: (topCand(comparison.run_2).solubility_score ?? 0) * 100 },
        { metric: 'Lab viability', A: topCand(comparison.run_1).lab_viability_score ?? 0, B: topCand(comparison.run_2).lab_viability_score ?? 0 },
        { metric: 'Select.', A: Math.min(100, (topCand(comparison.run_1).selectivity_ratio ?? 0) * 10), B: Math.min(100, (topCand(comparison.run_2).selectivity_ratio ?? 0) * 10) },
      ]
    : []

  const r1id = comparison?.run_1.id.slice(0, 8) ?? 'Run 1'
  const r2id = comparison?.run_2.id.slice(0, 8) ?? 'Run 2'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Compare Designs</h1>
        <p className="text-gray-500 text-sm mt-1">
          Side-by-side comparison of two completed runs
        </p>
      </div>

      {/* Run selector */}
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
          {/* Convergence bar chart */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">Convergence Metrics</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={convergenceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey={r1id} fill="#3b82f6" />
                <Bar dataKey={r2id} fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Radar chart — biophysical metrics */}
          {radarData.some((d) => d.A > 0 || d.B > 0) && (
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Biophysical Profile (Top Candidate)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                  <Radar name={`Run ${r1id}`} dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} />
                  <Radar name={`Run ${r2id}`} dataKey="B" stroke="#10b981" fill="#10b981" fillOpacity={0.25} />
                  <Legend />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Per-metric breakdown */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-3">Per-Metric Breakdown (Top Candidate)</h3>
            <div className="flex items-center space-x-4 mb-3 text-xs">
              <span className="flex items-center space-x-1"><span className="w-3 h-2 rounded-sm bg-blue-500 inline-block" /><span className="text-gray-500">{r1id}</span></span>
              <span className="flex items-center space-x-1"><span className="w-3 h-2 rounded-sm bg-emerald-500 inline-block" /><span className="text-gray-500">{r2id}</span></span>
            </div>
            <div className="space-y-0.5">
              <MetricRow label="Binding" val1={topCand(comparison.run_1).binding_score} val2={topCand(comparison.run_2).binding_score} id1={r1id} id2={r2id} />
              <MetricRow label="Stability" val1={topCand(comparison.run_1).stability_score} val2={topCand(comparison.run_2).stability_score} id1={r1id} id2={r2id} />
              <MetricRow label="Solubility" val1={topCand(comparison.run_1).solubility_score} val2={topCand(comparison.run_2).solubility_score} id1={r1id} id2={r2id} />
              <MetricRow label="Lab viability" val1={topCand(comparison.run_1).lab_viability_score != null ? topCand(comparison.run_1).lab_viability_score / 100 : null} val2={topCand(comparison.run_2).lab_viability_score != null ? topCand(comparison.run_2).lab_viability_score / 100 : null} id1={r1id} id2={r2id} fmt={(v) => (v * 100).toFixed(0) + '/100'} />
              <MetricRow label="Kd" val1={topCand(comparison.run_1).kd_nM != null ? 1 / (topCand(comparison.run_1).kd_nM + 0.001) : null} val2={topCand(comparison.run_2).kd_nM != null ? 1 / (topCand(comparison.run_2).kd_nM + 0.001) : null} id1={r1id} id2={r2id} fmt={(_) => {
                const v1 = topCand(comparison.run_1).kd_nM; const v2 = topCand(comparison.run_2).kd_nM
                return '' // displayed via separate cells
              }} />
            </div>
            {/* Kd raw values */}
            {(topCand(comparison.run_1).kd_nM != null || topCand(comparison.run_2).kd_nM != null) && (
              <div className="grid grid-cols-[100px_1fr_1fr] gap-2 items-center py-0.5">
                <span className="text-[10px] text-gray-500">Kd</span>
                <span className="text-[10px] font-mono text-gray-300">{topCand(comparison.run_1).kd_nM != null ? topCand(comparison.run_1).kd_nM.toFixed(0) + ' nM' : '—'}</span>
                <span className="text-[10px] font-mono text-gray-300">{topCand(comparison.run_2).kd_nM != null ? topCand(comparison.run_2).kd_nM.toFixed(0) + ' nM' : '—'}</span>
              </div>
            )}
          </div>

          {/* Sequence alignment diff */}
          {(comparison.run_1.best_sequence || comparison.run_2.best_sequence) && (
            <div className="card">
              <h3 className="text-lg font-semibold mb-3">Sequence Alignment</h3>
              <SequenceDiff
                seq1={comparison.run_1.best_sequence ?? ''}
                seq2={comparison.run_2.best_sequence ?? ''}
                label1={r1id}
                label2={r2id}
              />
            </div>
          )}

          {/* Side-by-side run summary cards */}
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
                    <span className={runData.convergence_rhat != null && runData.convergence_rhat < 1.05 ? 'text-green-600 font-medium' : ''}>
                      {runData.convergence_rhat?.toFixed(4) || '-'}
                    </span>
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
