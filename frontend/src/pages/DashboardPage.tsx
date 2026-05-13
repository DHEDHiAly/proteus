import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { runsApi } from '../services/api'
import type { MCMCRun } from '../types'
import RunStatusBadge from '../components/RunStatusBadge'
import { useAuth } from '../hooks/useAuth'

export default function DashboardPage() {
  const [runs, setRuns] = useState<MCMCRun[]>([])
  const [totalRuns, setTotalRuns] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const { user } = useAuth()

  const fetchRuns = async () => {
    try {
      const params: Record<string, unknown> = { page: 1, page_size: 20 }
      if (statusFilter) params.status_filter = statusFilter
      const res = await runsApi.list(params)
      setRuns(res.data.runs)
      setTotalRuns(res.data.total)
    } catch {
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
    const interval = setInterval(fetchRuns, 5000)
    return () => clearInterval(interval)
  }, [statusFilter])

  const stats = {
    total: totalRuns,
    running: runs.filter((r) => r.status === 'running').length,
    completed: runs.filter((r) => r.status === 'completed').length,
    failed: runs.filter((r) => r.status === 'failed').length,
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Welcome back, {user?.full_name}
          </p>
        </div>
        <Link to="/runs/new" className="btn-primary">
          + New Design Run
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card text-center">
          <div className="text-3xl font-bold text-gray-800">{stats.total}</div>
          <div className="text-sm text-gray-500">Total Runs</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-blue-600">{stats.running}</div>
          <div className="text-sm text-gray-500">Running</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-green-600">{stats.completed}</div>
          <div className="text-sm text-gray-500">Completed</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-red-600">{stats.failed}</div>
          <div className="text-sm text-gray-500">Failed</div>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Recent Runs</h2>
          <div className="flex space-x-2">
            {['', 'running', 'completed', 'failed'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? 'bg-proteus-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s || 'All'}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="text-center py-12 text-gray-500">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-4">No design runs yet</p>
            <Link to="/runs/new" className="btn-primary">
              Start Your First Run
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Target</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Best Score</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Steps</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div>
                        <div className="font-medium text-sm">{run.target_name}</div>
                        <div className="text-xs text-gray-500">PDB: {run.target_pdb_id}</div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {run.best_score !== null ? run.best_score.toFixed(4) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {run.total_steps_completed}/{run.steps_per_chain * run.num_chains}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/runs/${run.id}`}
                        className="text-proteus-600 hover:text-proteus-700 text-sm font-medium"
                      >
                        View →
</Link>
                    </td>
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
