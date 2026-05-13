import { useState, useCallback, useRef, useEffect } from 'react'
import { useWebSocket } from './useWebSocket'
import type { WebSocketMessage, ChainState } from '../types'

interface RunProgress {
  steps: number[]
  chainEnergies: { chainIndex: number; energies: number[] }[]
  bestEnergies: { chainIndex: number; bestEnergy: number }[]
  acceptanceRates: { chainIndex: number; rate: number }[]
  currentStep: number
  totalSteps: number
  bestEnergy: number | null
  bestSequence: string | null
  converged: boolean
  running: boolean
}

export function useRunStatus(runId: string | null) {
  const [progress, setProgress] = useState<RunProgress>({
    steps: [],
    chainEnergies: [],
    bestEnergies: [],
    acceptanceRates: [],
    currentStep: 0,
    totalSteps: 0,
    bestEnergy: null,
    bestSequence: null,
    converged: false,
    running: false,
  })

  const progressRef = useRef(progress)
  progressRef.current = progress

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    setProgress((prev) => {
      const next = { ...prev }

      if (msg.type === 'progress' && msg.chain_index !== undefined) {
        next.running = true
        next.currentStep = msg.step || 0
        next.totalSteps = msg.total_steps || 0

        const ci = msg.chain_index
        let chainData = next.chainEnergies.find((c) => c.chainIndex === ci)
        if (!chainData) {
          chainData = { chainIndex: ci, energies: [] }
          next.chainEnergies = [...next.chainEnergies, chainData]
        }
        chainData.energies = [...chainData.energies, msg.current_energy || 0]

        if (!next.steps.includes(msg.step || 0)) {
          next.steps = [...next.steps, msg.step || 0]
        }

        let bestData = next.bestEnergies.find((c) => c.chainIndex === ci)
        if (!bestData) {
          bestData = { chainIndex: ci, bestEnergy: msg.best_energy || 0 }
          next.bestEnergies = [...next.bestEnergies, bestData]
        } else {
          bestData.bestEnergy = msg.best_energy || bestData.bestEnergy
        }

        let rateData = next.acceptanceRates.find((c) => c.chainIndex === ci)
        if (!rateData) {
          rateData = { chainIndex: ci, rate: msg.acceptance_rate || 0 }
          next.acceptanceRates = [...next.acceptanceRates, rateData]
        } else {
          rateData.rate = msg.acceptance_rate || rateData.rate
        }

        if (msg.best_energy !== undefined) {
          next.bestEnergy = msg.best_energy
        }
        if (msg.best_sequence) {
          next.bestSequence = msg.best_sequence
        }
      }

      if (msg.type === 'complete') {
        next.running = false
        next.converged = msg.converged || false
        if (msg.best_energy !== undefined) next.bestEnergy = msg.best_energy
        if (msg.best_sequence) next.bestSequence = msg.best_sequence
      }

      if (msg.type === 'error') {
        next.running = false
      }

      return next
    })
  }, [])

  useWebSocket(runId, handleMessage)

  const reset = useCallback(() => {
    setProgress({
      steps: [],
      chainEnergies: [],
      bestEnergies: [],
      acceptanceRates: [],
      currentStep: 0,
      totalSteps: 0,
      bestEnergy: null,
      bestSequence: null,
      converged: false,
      running: false,
    })
  }, [])

  return { progress, reset }
}
