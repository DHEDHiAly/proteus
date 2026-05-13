import type { AgentMessage } from '../types/agent'

interface ChatMessageProps {
  message: AgentMessage
  onStructureClick?: (pdbId: string, mutations: any[]) => void
}

export default function ChatMessage({ message, onStructureClick }: ChatMessageProps) {
  const isAgent = message.role === 'agent'

  return (
    <div className={`flex ${isAgent ? 'justify-start' : 'justify-end'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isAgent
            ? 'bg-white border border-gray-200 text-gray-800'
            : 'bg-proteus-600 text-white'
        }`}
      >
        {isAgent && (
          <div className="flex items-center space-x-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-proteus-100 flex items-center justify-center">
              <span className="text-xs text-proteus-700 font-bold">P</span>
            </div>
            <span className="text-xs font-semibold text-gray-500">Proteus AI</span>
            {message.data?.status === 'running' && (
              <span className="flex items-center space-x-1 text-xs text-blue-600">
                <span className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600" />
                <span>Designing...</span>
              </span>
            )}
          </div>
        )}
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {message.content}
        </div>
        {message.data?.status === 'complete' && message.data?.pdb_id && (
          <button
            onClick={() => onStructureClick?.(message.data!.pdb_id!, message.data!.mutations || [])}
            className="mt-2 text-xs bg-proteus-50 text-proteus-700 px-3 py-1.5 rounded-lg hover:bg-proteus-100 transition-colors"
          >
            View 3D Structure
          </button>
        )}
      </div>
    </div>
  )
}
