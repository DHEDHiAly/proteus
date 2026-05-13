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
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch {}
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-proteus-700">Proteus</h1>
          <p className="text-gray-500 mt-2">MCMC Protein Design Platform</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
          <h2 className="text-2xl font-semibold mb-6">Sign In</h2>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); clearError() }}
                className="input-field"
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); clearError() }}
                className="input-field"
                placeholder="••••••••"
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <div className="mt-6 text-center text-sm text-gray-500">
            <span>Don't have an account? </span>
            <Link to="/register" className="text-proteus-600 hover:text-proteus-700 font-medium">
              Register
            </Link>
          </div>
          <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500">
            <p className="font-medium mb-1">Demo Accounts:</p>
            <p>Fellow: fellow@proteus.dev / password123</p>
            <p>Admin: admin@proteus.dev / password123</p>
          </div>
        </div>
        <p className="text-center text-xs text-gray-400 mt-6">
          FOR RESEARCH USE ONLY. Not a medical device.
        </p>
      </div>
    </div>
  )
}
