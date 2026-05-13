import { useState, FormEvent } from 'react'
import type { PatientInfo } from '../types/agent'

interface Props {
  onSubmit: (info: PatientInfo) => void
  initial?: PatientInfo
}

export default function PatientForm({ onSubmit, initial }: Props) {
  const [f, setF] = useState<PatientInfo>(
    initial || {
      full_name: '', age: 55, cancer_type: '', cancer_stage: 'IV',
      tumor_markers: '', previous_treatments: '', brain_metastasis: false, notes: '',
    }
  )

  const handleSubmit = (e: FormEvent) => { e.preventDefault(); onSubmit(f) }
  const upd = (field: keyof PatientInfo, v: string | boolean | number) => setF((p) => ({ ...p, [field]: v }))

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Name</label>
          <input type="text" value={f.full_name} onChange={(e) => upd('full_name', e.target.value)}
            className="input-field" placeholder="Patient name" required />
        </div>
        <div>
          <label className="label">Age</label>
          <input type="number" value={f.age} onChange={(e) => upd('age', parseInt(e.target.value) || 0)}
            className="input-field" min={0} max={120} required />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Cancer Type</label>
          <input type="text" value={f.cancer_type} onChange={(e) => upd('cancer_type', e.target.value)}
            className="input-field" placeholder="e.g. Glioblastoma" required />
        </div>
        <div>
          <label className="label">Stage</label>
          <select value={f.cancer_stage} onChange={(e) => upd('cancer_stage', e.target.value)}
            className="input-field">
            {['I', 'II', 'III', 'IV'].map((s) => <option key={s} value={s}>Stage {s}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="label">Genetic Markers</label>
        <input type="text" value={f.tumor_markers} onChange={(e) => upd('tumor_markers', e.target.value)}
          className="input-field" placeholder="EGFRvIII, KRAS G12C, PD-L1+ ..." />
      </div>
      <div>
        <label className="label">Prior Treatments</label>
        <input type="text" value={f.previous_treatments} onChange={(e) => upd('previous_treatments', e.target.value)}
          className="input-field" placeholder="Temozolomide, Radiation ..." />
      </div>
      <label className="flex items-center space-x-2 text-sm text-gray-300 cursor-pointer">
        <input type="checkbox" checked={f.brain_metastasis}
          onChange={(e) => upd('brain_metastasis', e.target.checked)}
          className="rounded border-gray-600 bg-[#1a1a1a]" />
        <span>Brain metastasis (CNS involvement)</span>
      </label>
      <button type="submit" className="btn-primary w-full text-base py-3">
        Launch Autonomous Design
      </button>
    </form>
  )
}
