import type { AgentMessage } from '../types/agent'
import IterationTable from './IterationTable'

interface Props {
  message: AgentMessage
  onStructureClick?: (pdbId: string, mutations: any[]) => void
}

export default function ChatMessage({ message, onStructureClick }: Props) {
  const isAgent = message.role === 'agent'
  const d = message.data

  return (
    <div className={`flex ${isAgent ? 'justify-start' : 'justify-end'} mb-3`}>
      <div className={`${isAgent ? 'max-w-[88%]' : 'max-w-[75%]'}`}>
        {isAgent && !d?.status && (
          <div className="flex items-center space-x-2 mb-1.5">
            <div className="w-5 h-5 rounded border border-white/20 flex items-center justify-center">
              <span className="text-[9px] font-bold">P</span>
            </div>
            <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Proteus</span>
          </div>
        )}

        <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isAgent
            ? d?.status === 'running'
              ? 'bg-[#1a1a1a] border border-[#333] text-gray-300'
              : d?.status === 'complete'
              ? 'bg-[#0f0f0f] border border-[#222] text-gray-200'
              : 'bg-[#111] border border-[#222] text-gray-300'
            : 'bg-white text-black'
        }`}>
          <div className="whitespace-pre-wrap font-[inherit] [&_strong]:text-white [&_em]:text-gray-400 [&_code]:text-white [&_code]:bg-white/5 [&_code]:px-1 [&_code]:rounded">
            {message.content}
          </div>

          {d?.status === 'running' && d.phase === 'generate' && (
            <div className="mt-2 flex items-center space-x-2 text-[11px] text-gray-500">
              <span className="inline-block w-2 h-2 rounded-full bg-white/30 animate-pulse" />
              <span>Running MCMC simulation...</span>
            </div>
          )}

          {(d?.status === 'round_complete' || d?.status === 'complete') && d?.pdb_id && (
            <button
              onClick={() => onStructureClick?.(d!.pdb_id!, d!.mutations || [])}
              className="mt-2 text-[11px] bg-white/10 text-white px-3 py-1.5 rounded-lg hover:bg-white/20 transition-colors inline-block"
            >
              View 3D Structure
            </button>
          )}

          {d?.status === 'complete' && d.rounds && d.rounds.length > 0 && (
            <div className="mt-3 border-t border-[#222] pt-3">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 font-medium">Iteration History</p>
              <IterationTable rounds={d.rounds} />
            </div>
          )}

          {d?.status === 'complete' && (
            <div className="mt-3 pt-2 border-t border-[#222]">
              <p className="text-[9px] text-gray-600 leading-relaxed">
                FOR RESEARCH USE ONLY. Not a medical device.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
