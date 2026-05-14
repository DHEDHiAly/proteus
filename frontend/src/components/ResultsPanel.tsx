import { useState } from 'react';

interface Candidate {
  rank: number;
  sequence: string;
  binding_score: number;
  stability_score: number;
  solubility_score: number;
  total_energy?: number;
  num_mutations_from_seed?: number;
  kd_nM?: number;
  serum_half_life_min?: number;
  selectivity_ratio?: number;
  toxicity_flag?: boolean;
}

interface ResultsPanelProps {
  candidates: Candidate[];
  seed?: string;
  onInspect: (seq: string) => void;
  onExport: (seq: string, format: string) => void;
  onSave?: (candidate: Candidate) => void;
}

export default function ResultsPanel({ candidates, seed, onInspect, onExport, onSave }: ResultsPanelProps) {
  const [sortBy, setSortBy] = useState<'binding_score' | 'stability_score' | 'total_energy'>('binding_score');
  const [filterText, setFilterText] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; seq: string } | null>(null);
  const [savedRanks, setSavedRanks] = useState<Set<number>>(new Set());

  const sorted = [...candidates]
    .filter((c) => !filterText || c.sequence.includes(filterText.toUpperCase()))
    .sort((a, b) => {
      if (sortBy === 'total_energy') return (a.total_energy || 0) - (b.total_energy || 0);
      return (b[sortBy] || 0) - (a[sortBy] || 0);
    });

  const toggleSelect = (rank: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(rank)) next.delete(rank); else next.add(rank);
      return next;
    });
  };

  const handleContextMenu = (e: React.MouseEvent, seq: string) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, seq });
  };

  const highlightMutations = (seq: string) => {
    if (!seed) return seq;
    return seq.split('').map((aa, i) => {
      if (i < seed.length && aa !== seed[i]) {
        return `<span class="text-red-400 font-bold">${aa}</span>`;
      }
      return aa;
    }).join('');
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2">
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}
          className="bg-[#111] border border-[#222] rounded px-2 py-1 text-[10px] text-gray-400">
          <option value="binding_score">Binding Score</option>
          <option value="stability_score">Stability</option>
          <option value="total_energy">Energy</option>
        </select>
        <input type="text" value={filterText} onChange={(e) => setFilterText(e.target.value)}
          placeholder="Filter sequence..." className="input-field text-[10px] flex-1" />
        {selected.size > 0 && (
          <button onClick={() => {
            const seqs = sorted.filter((c) => selected.has(c.rank)).map((c) => c.sequence);
            const blob = new Blob([seqs.join('\n')], { type: 'text/plain' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = `proteus-batch-${Date.now()}.fasta`; a.click();
          }} className="text-[10px] text-gray-400 hover:text-white">
            Export {selected.size}
          </button>
        )}
      </div>

      <div className="space-y-1 max-h-[500px] overflow-y-auto">
        {sorted.map((c) => (
          <div
            key={c.rank}
            onClick={() => toggleSelect(c.rank)}
            onContextMenu={(e) => handleContextMenu(e, c.sequence)}
            className={`flex items-center space-x-2 px-2 py-1.5 rounded-lg border cursor-pointer transition-all text-[10px] ${
              selected.has(c.rank) ? 'border-white/30 bg-white/5' : 'border-[#1a1a1a] hover:border-[#333]'
            }`}
          >
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold flex-shrink-0 ${
              c.rank === 1 ? 'bg-white text-black' : 'bg-[#1a1a1a] text-gray-500'
            }`}>{c.rank}</span>
            <div className="flex-1 min-w-0">
              <div
                className="font-mono text-[10px] truncate"
                dangerouslySetInnerHTML={{ __html: highlightMutations(c.sequence) }}
              />
              <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[8px] text-gray-600 mt-0.5">
                <span>Binding: {(c.binding_score * 100).toFixed(0)}%</span>
                {c.kd_nM != null && (
                  <span>Kd: {c.kd_nM < 1000 ? c.kd_nM.toFixed(0) + ' nM' : (c.kd_nM / 1000).toFixed(1) + ' μM'}</span>
                )}
                <span>Stab: {(c.stability_score * 100).toFixed(0)}%</span>
                {c.total_energy != null && <span>E: {c.total_energy.toFixed(3)}</span>}
              </div>
              {c.toxicity_flag && (
                <span className="inline-block mt-0.5 text-[7px] bg-red-900/40 text-red-400 border border-red-900/50 px-1 py-0.5 rounded">
                  High Tox Risk
                </span>
              )}
              {!c.toxicity_flag && c.selectivity_ratio != null && c.selectivity_ratio >= 5 && (
                <span className="inline-block mt-0.5 text-[7px] bg-green-900/30 text-green-500 border border-green-900/40 px-1 py-0.5 rounded">
                  Selective {c.selectivity_ratio.toFixed(1)}x
                </span>
              )}
              {!c.toxicity_flag && c.selectivity_ratio != null && c.selectivity_ratio >= 2 && c.selectivity_ratio < 5 && (
                <span className="inline-block mt-0.5 text-[7px] bg-yellow-900/30 text-yellow-600 border border-yellow-900/40 px-1 py-0.5 rounded">
                  Moderate {c.selectivity_ratio.toFixed(1)}x
                </span>
              )}
            </div>
            <div className="flex space-x-1 flex-shrink-0">
              <button onClick={(e) => { e.stopPropagation(); onInspect(c.sequence); }}
                className="px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-400 hover:text-white text-[8px]">
                View
              </button>
              <button onClick={(e) => { e.stopPropagation(); onExport(c.sequence, 'json'); }}
                className="px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-400 hover:text-white text-[8px]">
                ↓
              </button>
              {onSave && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSave(c);
                    setSavedRanks((prev) => new Set([...prev, c.rank]));
                  }}
                  disabled={savedRanks.has(c.rank)}
                  className={`px-1.5 py-0.5 rounded text-[8px] transition-all ${
                    savedRanks.has(c.rank)
                      ? 'bg-[#1a1a1a] text-green-700 cursor-default'
                      : 'bg-[#1a1a1a] text-gray-400 hover:text-white'
                  }`}
                >
                  {savedRanks.has(c.rank) ? '✓' : 'Save'}
                </button>
              )}
            </div>
          </div>
        ))}
        {sorted.length === 0 && (
          <p className="text-center text-gray-600 text-[10px] py-8">No candidates yet</p>
        )}
      </div>

      {contextMenu && (
        <>
          <div className="fixed inset-0 z-50" onClick={() => setContextMenu(null)} />
          <div className="fixed z-50 bg-[#111] border border-[#333] rounded-lg shadow-xl py-1 text-xs"
               style={{ left: contextMenu.x, top: contextMenu.y }}>
            {['PDB', 'FASTA', 'JSON', 'PNG'].map((fmt) => (
              <button key={fmt} onClick={() => { onExport(contextMenu.seq, fmt); setContextMenu(null); }}
                className="w-full text-left px-3 py-1.5 text-gray-400 hover:text-white hover:bg-white/5 text-[10px]">
                Export as {fmt}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
