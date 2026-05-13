import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { authApi } from '../services/api'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await authApi.updateMe({ full_name: fullName })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {}
    setIsSaving(false)
  }

  if (!user) return null

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Profile Settings</h1>

      <div className="card space-y-6">
        <div className="flex items-center space-x-4">
          <div className="w-16 h-16 rounded-full bg-proteus-100 flex items-center justify-center">
            <span className="text-2xl text-proteus-700 font-bold">
              {user.full_name.charAt(0)}
            </span>
          </div>
          <div>
            <h2 className="text-xl font-semibold">{user.full_name}</h2>
            <p className="text-gray-500">{user.email}</p>
            <span className="inline-block mt-1 px-2 py-0.5 bg-gray-100 rounded-full text-xs font-medium capitalize">
              {user.role}
            </span>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="label">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input-field"
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" value={user.email} className="input-field" disabled />
          </div>
          <div>
            <label className="label">Role</label>
            <input type="text" value={user.role} className="input-field" disabled />
          </div>
          <div>
            <label className="label">Account Created</label>
            <input
              type="text"
              value={new Date(user.created_at).toLocaleDateString()}
              className="input-field"
              disabled
            />
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <button onClick={handleSave} className="btn-primary" disabled={isSaving}>
            {isSaving ? 'Saving...' : saved ? 'Saved ✓' : 'Save Changes'}
          </button>
          <button onClick={logout} className="btn-secondary">
            Sign Out
          </button>
        </div>
      </div>

      <div className="card bg-gray-50">
        <p className="text-xs text-gray-500">
          FOR RESEARCH USE ONLY. Not a medical device. Designed protein sequences are
          computational predictions only and must undergo wet-lab validation.
        </p>
      </div>
    </div>
  )
}
