import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { targetsApi, runsApi } from '../services/api'
import type { Target } from '../types'

export default function NewRunPage() {
  const [targets, setTargets] = useState<Target[]>([])
  const [selectedTarget, setSelectedTarget] = useState('')
  const [seedSequence, setSeedSequence] = useState('')
  const [numChains, setNumChains] = useState(5)
  const [stepsPerChain, setStepsPerChain] = useState(1000)
  const [temperatures, setTemperatures] = useState('0.5, 1.0, 2.0, 5.0, 10.0')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    targetsApi.list().then((res) => {
      setTargets(res.data.targets)
    }).catch(() => {})
  }, [])

  const target = targets.find((t) => t.name === selectedTarget)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!selectedTarget) {
      setError('Please select a target protein')
      return
    }
    setError('')
    setIsSubmitting(true)

    try {
      const tempArray = temperatures.split(',').map((s) => parseFloat(s.trim())).filter((n) => !isNaN(n))
      const res = await runsApi.create({
        target_name: selectedTarget,
        seed_sequence: seedSequence || undefined,
        num_chains: numChains,
        steps_per_chain: stepsPerChain,
        temperatures: tempArray.length > 0 ? tempArray : undefined,
      })
      navigate(`/runs/${res.data.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create run')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">New Protein Design Run</h1>
        <p className="text-gray-500 text-sm mt-1">
          Configure and launch an MCMC protein design experiment
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">Target Selection</h2>
          <div>
            <label className="label">Target Protein</label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="input-field"
              required
            >
              <option value="">Select a target...</option>
              {targets.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name} - {t.full_name.split('(')[0].trim()} (Difficulty: {t.difficulty_score}/10)
                </option>
              ))}
            </select>
          </div>

          {target && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">PDB ID</span>
                <span className="font-mono">{target.pdb_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Cancer Type</span>
                <span>{target.cancer_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Known IC50</span>
                <span>{target.known_ic50_nM} nM</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Difficulty</span>
                <span>{target.difficulty_score}/10</span>
              </div>
              <p className="text-gray-600 mt-2">{target.clinical_relevance.slice(0, 200)}...</p>
            </div>
          )}

          <div>
            <label className="label">Seed Sequence (optional)</label>
            <input
              type="text"
              value={seedSequence}
              onChange={(e) => setSeedSequence(e.target.value)}
              className="input-field font-mono"
              placeholder="Leave empty to use known binder as seed"
            />
          </div>
        </div>

        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">MCMC Parameters</h2>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-proteus-600 hover:text-proteus-700"
            >
              {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Number of Chains</label>
              <input
                type="number"
                value={numChains}
                onChange={(e) => setNumChains(parseInt(e.target.value) || 5)}
                className="input-field"
                min={1}
                max={10}
              />
            </div>
            <div>
              <label className="label">Steps per Chain</label>
              <input
                type="number"
                value={stepsPerChain}
                onChange={(e) => setStepsPerChain(parseInt(e.target.value) || 1000)}
                className="input-field"
                min={100}
                max={10000}
              />
            </div>
          </div>

          {showAdvanced && (
            <div>
              <label className="label">Temperatures (comma-separated)</label>
              <input
                type="text"
                value={temperatures}
                onChange={(e) => setTemperatures(e.target.value)}
                className="input-field"
                placeholder="0.5, 1.0, 2.0, 5.0, 10.0"
              />
              <p className="text-xs text-gray-500 mt-1">
                One temperature per chain. Controls exploration vs. exploitation.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-4">
          <button type="submit" className="btn-primary px-8" disabled={isSubmitting}>
            {isSubmitting ? 'Launching Run...' : 'Start Design Run'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="btn-secondary"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
