import { useState, FormEvent } from 'react'

interface PatientInfo {
  full_name: string
  age: number
  cancer_type: string
  cancer_stage: string
  tumor_markers: string
  previous_treatments: string
  brain_metastasis: boolean
  notes: string
}

interface PatientFormProps {
  onSubmit: (info: PatientInfo) => void
  initial?: PatientInfo
}

export default function PatientForm({ onSubmit, initial }: PatientFormProps) {
  const [form, setForm] = useState<PatientInfo>(
    initial || {
      full_name: '',
      age: 55,
      cancer_type: '',
      cancer_stage: 'IV',
      tumor_markers: '',
      previous_treatments: '',
      brain_metastasis: false,
      notes: '',
    }
  )

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit(form)
  }

  const update = (field: keyof PatientInfo, value: string | boolean | number) =>
    setForm((prev) => ({ ...prev, [field]: value }))

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Full Name</label>
          <input
            type="text" value={form.full_name}
            onChange={(e) => update('full_name', e.target.value)}
            className="input-field" placeholder="Jane Doe" required
          />
        </div>
        <div>
          <label className="label">Age</label>
          <input
            type="number" value={form.age}
            onChange={(e) => update('age', parseInt(e.target.value) || 0)}
            className="input-field" min={0} max={120} required
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Cancer Type</label>
          <input
            type="text" value={form.cancer_type}
            onChange={(e) => update('cancer_type', e.target.value)}
            className="input-field" placeholder="e.g. Glioblastoma" required
          />
        </div>
        <div>
          <label className="label">Stage</label>
          <select value={form.cancer_stage} onChange={(e) => update('cancer_stage', e.target.value)} className="input-field">
            <option value="I">Stage I</option>
            <option value="II">Stage II</option>
            <option value="III">Stage III</option>
            <option value="IV">Stage IV</option>
          </select>
        </div>
      </div>
      <div>
        <label className="label">Tumor Markers / Mutations</label>
        <input
          type="text" value={form.tumor_markers}
          onChange={(e) => update('tumor_markers', e.target.value)}
          className="input-field" placeholder="e.g. EGFRvIII, KRAS G12C, PD-L1+"
        />
      </div>
      <div>
        <label className="label">Previous Treatments</label>
        <input
          type="text" value={form.previous_treatments}
          onChange={(e) => update('previous_treatments', e.target.value)}
          className="input-field" placeholder="e.g. Temozolomide, Radiation"
        />
      </div>
      <div className="flex items-center space-x-2">
        <input
          type="checkbox" id="brain-mets" checked={form.brain_metastasis}
          onChange={(e) => update('brain_metastasis', e.target.checked)}
          className="rounded border-gray-300"
        />
        <label htmlFor="brain-mets" className="text-sm text-gray-700">Brain metastasis (CNS involvement)</label>
      </div>
      <div>
        <label className="label">Additional Notes</label>
        <textarea
          value={form.notes}
          onChange={(e) => update('notes', e.target.value)}
          className="input-field" rows={2} placeholder="Any other clinical context..."
        />
      </div>
      <button type="submit" className="btn-primary w-full">
        Start Design
      </button>
    </form>
  )
}
