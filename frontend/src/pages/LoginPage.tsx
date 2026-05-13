import { useState, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login, isLoading, error, clearError } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try { await login(email, password); navigate('/agent') }
    catch {}
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 border border-white/20 rounded-xl flex items-center justify-center mx-auto mb-3">
            <span className="text-xl font-bold">P</span>
          </div>
          <h1 className="text-lg font-bold">Proteus</h1>
          <p className="text-gray-500 text-xs mt-1">Sign in to continue</p>
        </div>
        <div className="bg-[#111] border border-[#222] rounded-xl p-6">
          {error && <div className="bg-white/5 border border-white/10 text-white px-3 py-2 rounded-lg mb-4 text-xs">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="label">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="input-field" placeholder="you@example.com" required />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="input-field" placeholder="••••••••" required />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <div className="mt-4 text-center text-xs text-gray-500">
            <span>No account? </span>
            <Link to="/register" className="text-white hover:underline">Register</Link>
          </div>
        </div>
        <p className="text-center text-[10px] text-gray-600 mt-4">FOR RESEARCH USE ONLY</p>
      </div>
    </div>
  )
}
