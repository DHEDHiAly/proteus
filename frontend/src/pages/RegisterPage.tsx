import { useState, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [success, setSuccess] = useState(false)
  const { register, isLoading, error, clearError } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await register(email, password, fullName)
      setSuccess(true)
      setTimeout(() => navigate('/login'), 3000)
    } catch {}
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-blue-50">
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8 max-w-md text-center">
          <div className="text-4xl mb-4">✓</div>
          <h2 className="text-2xl font-semibold mb-2">Registration Successful</h2>
          <p className="text-gray-500">You can now sign in with your credentials.</p>
          <Link to="/login" className="btn-primary inline-block mt-6">Go to Sign In</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-proteus-700">Proteus</h1>
          <p className="text-gray-500 mt-2">Create your account</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl border border-gray-200 p-8">
          <h2 className="text-2xl font-semibold mb-6">Register</h2>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => { setFullName(e.target.value); clearError() }}
                className="input-field"
                placeholder="Jane Doe"
                required
              />
            </div>
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
                placeholder="Min. 8 characters"
                minLength={8}
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={isLoading}>
              {isLoading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>
          <div className="mt-6 text-center text-sm text-gray-500">
            <span>Already have an account? </span>
            <Link to="/login" className="text-proteus-600 hover:text-proteus-700 font-medium">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
