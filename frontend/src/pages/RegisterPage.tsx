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
    try { await register(email, password, fullName); setSuccess(true); setTimeout(() => navigate('/login'), 2000) }
    catch {}
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="bg-[#111] border border-[#222] rounded-xl p-8 max-w-sm text-center">
          <div className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center mx-auto mb-3">✓</div>
          <h2 className="font-bold mb-1">Registered</h2>
          <p className="text-xs text-gray-500">Redirecting to sign in...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-black">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-lg font-bold">Create Account</h1>
          <p className="text-gray-500 text-xs mt-1">Join Proteus</p>
        </div>
        <div className="bg-[#111] border border-[#222] rounded-xl p-6">
          {error && <div className="bg-white/5 border border-white/10 text-white px-3 py-2 rounded-lg mb-4 text-xs">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div><label className="label">Full Name</label><input type="text" value={fullName} onChange={(e) => { setFullName(e.target.value); clearError() }} className="input-field" required /></div>
            <div><label className="label">Email</label><input type="email" value={email} onChange={(e) => { setEmail(e.target.value); clearError() }} className="input-field" required /></div>
            <div><label className="label">Password</label><input type="password" value={password} onChange={(e) => { setPassword(e.target.value); clearError() }} className="input-field" minLength={8} required /></div>
            <button type="submit" className="btn-primary w-full" disabled={isLoading}>{isLoading ? 'Creating...' : 'Create Account'}</button>
          </form>
          <div className="mt-4 text-center text-xs text-gray-500">
            <span>Already have an account? </span>
            <Link to="/login" className="text-white hover:underline">Sign In</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
