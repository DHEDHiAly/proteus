import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { runsApi } from '../services/api'
import type { MCMCRun } from '../types'
import { useAuth } from '../hooks/useAuth'
import { savedDesignsService } from '../services/savedDesigns'
import type { SavedDesign } from '../services/savedDesigns'

export default function DashboardPage() {
  const [runs, setRuns] = useState<MCMCRun[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [savedDesigns, setSavedDesigns] = useState<SavedDesign[]>([])
  const { user } = useAuth()

  useEffect(() => {
    runsApi.list({ page_size: 20 }).then((res) => setRuns(res.data.runs)).catch(() => {}).finally(() => setIsLoading(false))
    setSavedDesigns(savedDesignsService.getAll())
  }, [])

  const handleDelete = (id: string) => {
    savedDesignsService.delete(id)
    setSavedDesigns(savedDesignsService.getAll())
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold">Design History</h1>
          <p className="text-[11px] text-gray-500 mt-0.5">{user?.full_name}</p>
        </div>
        <Link to="/agent" className="btn-primary text-[11px]">New Design</Link>
      </div>

      {/* Saved agent designs */}
      {savedDesigns.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">Saved Designs</h2>
            <span className="text-[10px] text-gray-600">{savedDesigns.length} saved</span>
          </div>
          <div className="bg-[#111] border border-[#222] rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#222] text-gray-500">
                  <th className="text-left p-3 font-medium">Name</th>
                  <th className="text-left p-3 font-medium">Sequence</th>
                  <th className="text-right p-3 font-medium">Binding</th>
                  <th className="text-right p-3 font-medium">Kd</th>
                  <th className="text-right p-3 font-medium">Saved</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {savedDesigns.map((d) => (
                  <tr key={d.id} className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a] group">
                    <td className="p-3">
                      <div className="font-medium text-white">{d.name}</div>
                      <div className="text-[10px] text-gray-600">{d.patient ? `${d.patient.cancerType} · ${d.patient.cancerStage}` : d.target}</div>
                    </td>
                    <td className="p-3">
                      <span className="font-mono text-[9px] text-gray-500 truncate block max-w-[180px]">{d.sequence}</span>
                    </td>
                    <td className="p-3 text-right font-mono text-gray-300">
                      {(d.bindingScore * 100).toFixed(0)}%
                    </td>
                    <td className="p-3 text-right font-mono text-gray-400">
                      {d.kd_nM != null ? (d.kd_nM < 1000 ? d.kd_nM.toFixed(0) + ' nM' : (d.kd_nM / 1000).toFixed(1) + ' μM') : '—'}
                    </td>
                    <td className="p-3 text-right text-gray-600">
                      {new Date(d.savedAt).toLocaleDateString()}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center justify-end space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => savedDesignsService.exportFasta(d)}
                          className="text-[8px] px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-400 hover:text-white"
                        >
                          FASTA
                        </button>
                        <button
                          onClick={() => handleDelete(d.id)}
                          className="text-[8px] px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-600 hover:text-red-400"
                        >
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MCMC run history stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total', value: runs.length, color: 'text-white' },
          { label: 'Running', value: runs.filter((r) => r.status === 'running').length, color: 'text-gray-300' },
          { label: 'Completed', value: runs.filter((r) => r.status === 'completed').length, color: 'text-gray-300' },
          { label: 'Failed', value: runs.filter((r) => r.status === 'failed').length, color: 'text-gray-600' },
        ].map((s) => (
          <div key={s.label} className="bg-[#111] border border-[#222] rounded-lg p-3 text-center">
            <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
            <div className="text-[10px] text-gray-600">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-[#111] border border-[#222] rounded-xl">
        {isLoading ? (
          <div className="p-8 text-center text-gray-600 text-xs">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-600 text-xs mb-3">No MCMC run history yet</p>
            <Link to="/agent" className="btn-primary text-[11px]">Start Your First Design</Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#222] text-gray-500">
                  <th className="text-left p-3 font-medium">Target</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-right p-3 font-medium">Score</th>
                  <th className="text-right p-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a]">
                    <td className="p-3">
                      <div className="font-medium">{run.target_name}</div>
                      <div className="text-[10px] text-gray-600">{run.target_pdb_id}</div>
                    </td>
                    <td className="p-3">
                      <span className={`text-[10px] ${run.status === 'completed' ? 'text-gray-300' : run.status === 'running' ? 'text-gray-400' : 'text-gray-600'}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="p-3 text-right text-gray-400">{run.best_score?.toFixed(3) || '-'}</td>
                    <td className="p-3 text-right text-gray-600">{new Date(run.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
