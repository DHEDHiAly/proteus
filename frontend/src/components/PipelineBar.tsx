import clsx from 'clsx'

const STEPS = [
  { key: 'research', label: 'Research' },
  { key: 'generate', label: 'Generate' },
  { key: 'fold', label: 'Fold' },
  { key: 'evaluate', label: 'Evaluate' },
]

interface Props {
  currentPhase?: string
  currentRound?: number
  totalRounds?: number
}

export default function PipelineBar({ currentPhase, currentRound, totalRounds = 3 }: Props) {
  const phaseIndex = STEPS.findIndex((s) => s.key === currentPhase)

  return (
    <div className="flex items-center justify-between mb-4">
      {STEPS.map((step, i) => {
        const status = phaseIndex === -1 ? 'inactive' : i < phaseIndex ? 'complete' : i === phaseIndex ? 'active' : 'inactive'
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div
              className={clsx(
                'pipeline-step flex-shrink-0',
                status === 'complete' && 'bg-white/10 text-white',
                status === 'active' && 'bg-white text-black',
                status === 'inactive' && 'text-gray-600'
              )}
            >
              <span className={clsx(
                'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mr-1.5',
                status === 'complete' && 'bg-white text-black',
                status === 'active' && 'bg-black text-white',
                status === 'inactive' && 'bg-[#1a1a1a] text-gray-600'
              )}>
                {status === 'complete' ? '✓' : i + 1}
              </span>
              <span className={status === 'inactive' ? 'hidden sm:inline' : ''}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={clsx(
                'flex-1 h-px mx-2',
                status === 'complete' || (phaseIndex > i) ? 'bg-white/30' : 'bg-[#222]'
              )} />
            )}
          </div>
        )
      })}
      {currentRound && (
        <span className="text-[10px] text-gray-500 ml-2 whitespace-nowrap">
          Round {currentRound}/{totalRounds}
        </span>
      )}
    </div>
  )
}
