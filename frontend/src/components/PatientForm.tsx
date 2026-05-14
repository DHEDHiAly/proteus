import { useState, FormEvent } from 'react'
import type { PatientInfo } from '../types/agent'

interface Props {
  onSubmit: (info: PatientInfo) => void
  initial?: PatientInfo
}

export default function PatientForm({ onSubmit, initial }: Props) {
  const [f, setF] = useState<PatientInfo>(
    initial || {
      full_name: '', age: 0, cancer_type: '', cancer_stage: '',
      tumor_markers: '', previous_treatments: '', brain_metastasis: false,
      notes: '', modality: '',
    }
  )
  const [step, setStep] = useState(0)

  const upd = (field: keyof PatientInfo, v: string | boolean | number) => setF((p) => ({ ...p, [field]: v }))

  const handleSubmit = (e: FormEvent) => { e.preventDefault(); onSubmit(f) }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {step === 0 && (
        <div className="animate-fade-in space-y-3">
          <p className="text-[11px] text-gray-500 font-medium">Step 1 — Describe the clinical presentation</p>
          <div>
            <label className="label">What illness is the patient presenting with?</label>
            <input type="text" value={f.cancer_type}
              onChange={(e) => upd('cancer_type', e.target.value)}
              className="input-field" placeholder="e.g. Metastatic glioblastoma, recurrent after resection"
              required />
          </div>
          <div>
            <label className="label">Patient name (optional)</label>
            <input type="text" value={f.full_name}
              onChange={(e) => upd('full_name', e.target.value)}
              className="input-field" placeholder="e.g. Jane Doe" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Age</label>
              <input type="number" value={f.age || ''}
                onChange={(e) => upd('age', parseInt(e.target.value) || 0)}
                className="input-field" min={0} max={120} />
            </div>
            <div>
              <label className="label">Stage / severity</label>
              <input type="text" value={f.cancer_stage}
                onChange={(e) => upd('cancer_stage', e.target.value)}
                className="input-field" placeholder="e.g. Stage IV, recurrent" />
            </div>
          </div>
          <button type="button" onClick={() => setStep(1)}
            className="btn-primary w-full flex items-center justify-center space-x-2">
            <span>Next — Genetic Details</span>
            <span className="text-[11px] opacity-60">→</span>
          </button>
        </div>
      )}

      {step === 1 && (
        <div className="animate-fade-in space-y-3">
          <p className="text-[11px] text-gray-500 font-medium">Step 2 — Genetic & molecular context</p>
          <div>
            <label className="label">Known genetic markers or mutations</label>
            <input type="text" value={f.tumor_markers}
              onChange={(e) => upd('tumor_markers', e.target.value)}
              className="input-field" placeholder="e.g. EGFRvIII, KRAS G12C, HER2+ ..." />
            <p className="text-[9px] text-gray-600 mt-1">If unknown, leave blank — Proteus will research likely targets.</p>
          </div>
          <div>
            <label className="label">Previous treatments</label>
            <input type="text" value={f.previous_treatments}
              onChange={(e) => upd('previous_treatments', e.target.value)}
              className="input-field" placeholder="e.g. Temozolomide, checkpoint inhibitors" />
          </div>
          <label className="flex items-center space-x-2 text-sm text-gray-300 cursor-pointer">
            <input type="checkbox" checked={f.brain_metastasis}
              onChange={(e) => upd('brain_metastasis', e.target.checked)}
              className="rounded border-gray-600 bg-[#1a1a1a]" />
            <span className="text-xs">CNS involvement (brain metastasis)</span>
          </label>
          <div>
            <label className="label">Therapeutic modality</label>
            <select value={f.modality}
              onChange={(e) => upd('modality', e.target.value)}
              className="input-field">
              <option value="">Auto (let Proteus decide)</option>
              <option value="peptide">Peptide (8–30 AA)</option>
              <option value="miniprotein">Miniprotein (30–100 AA)</option>
              <option value="nanobody">Nanobody / VHH (110–130 AA)</option>
              <option value="cyclic_peptide">Cyclic peptide (cell-penetrating)</option>
              <option value="antimicrobial">Antimicrobial peptide (AMP)</option>
            </select>
            <p className="text-[9px] text-gray-600 mt-1">Sets seed length and oracle weight presets.</p>
          </div>
          <div>
            <label className="label">Additional notes</label>
            <textarea value={f.notes}
              onChange={(e) => upd('notes', e.target.value)}
              className="input-field" rows={2} placeholder="Any other relevant clinical context..." />
          </div>
          <div className="flex space-x-2">
            <button type="button" onClick={() => setStep(0)}
              className="btn-secondary text-xs flex-1">← Back</button>
            <button type="submit" className="btn-primary text-xs flex-1">Start Design</button>
          </div>
        </div>
      )}
    </form>
  )
}
