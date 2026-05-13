import type { Candidate } from '../types'

interface CandidateTableProps {
  candidates: Candidate[]
  onSelect?: (candidate: Candidate) => void
  selectedSequence?: string | null
}

export default function CandidateTable({ candidates, onSelect, selectedSequence }: CandidateTableProps) {
  if (candidates.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500">No candidates generated yet</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <h3 className="text-lg font-semibold mb-4">Designed Candidates</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sequence</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Binding</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stability</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Solubility</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mutations</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {candidates.map((candidate) => (
              <tr
                key={candidate.rank}
                onClick={() => onSelect?.(candidate)}
                className={`
                  cursor-pointer transition-colors
                  ${selectedSequence === candidate.sequence ? 'bg-proteus-50' : 'hover:bg-gray-50'}
                `}
              >
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`
                    inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold
                    ${candidate.rank === 1 ? 'bg-yellow-100 text-yellow-800' : ''}
                    ${candidate.rank === 2 ? 'bg-gray-100 text-gray-600' : ''}
                    ${candidate.rank === 3 ? 'bg-orange-100 text-orange-700' : ''}
                    ${candidate.rank > 3 ? 'bg-gray-50 text-gray-500' : ''}
                  `}>
                    {candidate.rank}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-sm max-w-[200px] truncate">
                  {candidate.sequence}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-500 rounded-full h-2"
                        style={{ width: `${candidate.binding_score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">
                      {(candidate.binding_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center space-x-2">
                    <div className="w-16 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-500 rounded-full h-2"
                        style={{ width: `${candidate.stability_score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">
                      {(candidate.stability_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm">
                    {(candidate.solubility_score * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {candidate.num_mutations_from_seed}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
