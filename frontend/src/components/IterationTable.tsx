import type { IterationRound } from '../types/agent'

interface Props {
  rounds: IterationRound[]
  onSelect?: (seq: string) => void
}

export default function IterationTable({ rounds, onSelect }: Props) {
  if (!rounds || rounds.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#222] text-gray-500">
            <th className="text-left py-2 pr-3 font-medium">Round</th>
            <th className="text-left py-2 pr-3 font-medium">Sequence</th>
            <th className="text-right py-2 pr-3 font-medium">Binding</th>
            <th className="text-right py-2 pr-3 font-medium">Stability</th>
            <th className="text-right py-2 pr-3 font-medium">Energy</th>
            <th className="text-right py-2 font-medium">pLDDT</th>
          </tr>
        </thead>
        <tbody>
          {rounds.map((r, i) => (
            <tr
              key={i}
              onClick={() => onSelect?.(r.sequence)}
              className={`border-b border-[#1a1a1a] hover:bg-[#1a1a1a] cursor-pointer transition-colors ${r.is_best ? 'bg-white/5' : ''}`}
            >
              <td className="py-2 pr-3 flex items-center space-x-1">
                <span>{r.round}</span>
                {r.is_best && <span className="text-[10px]">*</span>}
              </td>
              <td className="py-2 pr-3 font-mono text-[11px] truncate max-w-[140px]">{r.sequence}</td>
              <td className="py-2 pr-3 text-right">{(r.binding_score * 100).toFixed(0)}%</td>
              <td className="py-2 pr-3 text-right">{(r.stability_score * 100).toFixed(0)}%</td>
              <td className="py-2 pr-3 text-right text-gray-400">{typeof r.total_energy === 'number' ? r.total_energy.toFixed(3) : '-'}</td>
              <td className="py-2 text-right">{r.fold_plddt != null ? r.fold_plddt.toFixed(3) : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
