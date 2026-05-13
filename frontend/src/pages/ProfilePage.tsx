import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { authApi } from '../services/api'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try { await authApi.updateMe({ full_name: fullName }) } catch {}
    setSaving(false)
  }

  if (!user) return null

  return (
    <div className="max-w-md mx-auto space-y-4">
      <h1 className="text-sm font-bold">Profile</h1>
      <div className="bg-[#111] border border-[#222] rounded-xl p-5 space-y-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center">
            <span className="text-sm font-bold">{user.full_name.charAt(0)}</span>
          </div>
          <div>
            <div className="text-sm font-medium">{user.full_name}</div>
            <div className="text-[10px] text-gray-500">{user.email} · {user.role}</div>
          </div>
        </div>
        <div>
          <label className="label">Name</label>
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="input-field" />
        </div>
        <div className="flex space-x-2">
          <button onClick={handleSave} className="btn-primary text-[11px]" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
          <button onClick={logout} className="btn-secondary text-[11px]">Sign Out</button>
        </div>
      </div>
      <div className="bg-[#111] border border-[#222] rounded-xl p-4">
        <p className="text-[10px] text-gray-600 leading-relaxed">
          FOR RESEARCH USE ONLY. Not a medical device. Designed protein sequences are computational predictions only and must undergo wet-lab validation.
        </p>
      </div>
    </div>
  )
}
