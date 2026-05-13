import { useState, useEffect } from 'react'
import { adminApi } from '../services/api'
import { useAuth } from '../hooks/useAuth'

export default function AdminPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<'runs' | 'users' | 'audit'>('runs')
  const [allRuns, setAllRuns] = useState<any[]>([])
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [cleanupMsg, setCleanupMsg] = useState('')

  const fetchData = async () => {
    setIsLoading(true)
    try {
      if (activeTab === 'runs') {
        const res = await adminApi.listAllRuns({ page_size: 100 })
        setAllRuns(res.data.runs)
      } else if (activeTab === 'audit') {
        const res = await adminApi.getAuditLogs({ page_size: 100 })
        setAuditLogs(res.data.logs)
      }
    } catch {}
    setIsLoading(false)
  }

  useEffect(() => {
    fetchData()
  }, [activeTab])

  const handleCleanup = async () => {
    if (!confirm('This will delete runs older than 1 year. Continue?')) return
    try {
      const res = await adminApi.cleanup()
      setCleanupMsg(res.data.message)
      setTimeout(() => setCleanupMsg(''), 5000)
    } catch {}
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <p className="text-gray-500 text-sm mt-1">
            {user?.role === 'admin' ? 'Full system administration' : 'Mentor view'}
          </p>
        </div>
        {user?.role === 'admin' && (
          <button onClick={handleCleanup} className="btn-danger text-sm">
            Cleanup Old Runs
          </button>
        )}
      </div>

      {cleanupMsg && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          {cleanupMsg}
        </div>
      )}

      <div className="flex space-x-1 border-b border-gray-200">
        {(['runs', 'users', 'audit'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              activeTab === tab
                ? 'border-proteus-600 text-proteus-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab} {tab === 'audit' ? 'Logs' : ''}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : activeTab === 'runs' ? (
        <div className="card">
          <h3 className="font-semibold mb-4">All Runs ({allRuns.length})</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">User</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Target</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Score</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {allRuns.map((run: any) => (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2">{run.user_id?.slice(0, 8)}</td>
                    <td className="px-3 py-2">{run.target_name}</td>
                    <td className="px-3 py-2">
                      <span className={`capitalize ${run.status === 'completed' ? 'text-green-600' : run.status === 'running' ? 'text-blue-600' : 'text-gray-500'}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">{run.best_score?.toFixed(3) || '-'}</td>
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : activeTab === 'users' ? (
        <div className="card">
          <p className="text-gray-500">User management available for admin role. Visit the admin section in the API.</p>
        </div>
      ) : (
        <div className="card">
          <h3 className="font-semibold mb-4">Audit Logs (Last 100)</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Time</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">User</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Action</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Resource</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {auditLogs.map((log: any) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{log.user_email || log.user_id?.slice(0, 8)}</td>
                    <td className="px-3 py-2">{log.action}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{log.resource_type} {log.resource_id?.slice(0, 8)}</td>
                    <td className="px-3 py-2">
                      <span className={log.success === 'true' ? 'text-green-600' : 'text-red-600'}>
                        {log.success}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
