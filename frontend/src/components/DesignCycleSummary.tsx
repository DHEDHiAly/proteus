import { useState } from 'react';

interface RoundData {
  round: number;
  sequence: string;
  binding_score: number;
  stability_score: number;
  solubility_score: number;
  total_energy: number;
  mutations: { position: number; from: string; to: string }[];
  rhat?: number;
  ess?: number;
  num_candidates?: number;
  steps?: number;
  chains?: number;
  kd_nM?: number;
  serum_half_life_min?: number;
  selectivity_ratio?: number;
  toxicity_flag?: boolean;
}

interface DesignCycleSummaryProps {
  rounds: RoundData[];
  totalTime: number;
  targetName: string;
}

export default function DesignCycleSummary({ rounds, totalTime, targetName }: DesignCycleSummaryProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!rounds || rounds.length === 0) return null;

  const bestRound = rounds.reduce((best, r) => (r.binding_score > best.binding_score ? r : best), rounds[0]);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] text-gray-500 mb-2 pb-2 border-b border-[#1a1a1a]">
        <span>Design Cycle — {rounds.length} rounds · {totalTime.toFixed(1)}s · Target: {targetName}</span>
        <span className="text-white font-medium">
          Best: {(bestRound.binding_score * 100).toFixed(1)}%
          {bestRound.kd_nM != null && (
            <span className="text-gray-400 font-normal ml-1">
              · Kd {bestRound.kd_nM < 1000 ? bestRound.kd_nM.toFixed(0) + ' nM' : (bestRound.kd_nM / 1000).toFixed(1) + ' μM'}
            </span>
          )}
        </span>
      </div>

      {rounds.map((r, idx) => {
        const prevBinding = idx > 0 ? rounds[idx - 1].binding_score : null;
        const improved = prevBinding !== null && r.binding_score > prevBinding;
        const isBest = r.binding_score === bestRound.binding_score;
        const isOpen = expanded === idx;

        return (
          <div
            key={idx}
            className={`rounded-lg border cursor-pointer transition-all duration-200 ${
              isOpen ? 'border-white/20 bg-white/[0.02]' : 'border-[#1a1a1a] hover:border-[#333]'
            } ${isBest ? 'ring-1 ring-white/10' : ''}`}
            onClick={() => setExpanded(isOpen ? null : idx)}
          >
            <div className="flex items-center justify-between px-3 py-2">
              <div className="flex items-center space-x-3">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold ${
                  isBest ? 'bg-white text-black' : 'bg-[#1a1a1a] text-gray-500'
                }`}>
                  {r.round}
                </span>
                <div>
                  <span className="text-[11px] font-mono text-white/80">{r.sequence}</span>
                  <div className="flex items-center space-x-2 mt-0.5">
                    <span className="text-[10px] font-bold text-white">{(r.binding_score * 100).toFixed(1)}%</span>
                    {improved && <span className="text-[10px] text-green-400">↑</span>}
                    {!improved && prevBinding !== null && <span className="text-[10px] text-gray-600">—</span>}
                    <span className="text-[9px] text-gray-600">E: {r.total_energy.toFixed(3)}</span>
                    <span className="text-[9px] text-gray-600">{r.mutations.length} muts</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {isBest && <span className="text-[9px] text-yellow-500">*</span>}
                <span className={`text-[9px] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''} text-gray-600`}>▾</span>
              </div>
            </div>

            {isOpen && (
              <div className="px-3 pb-3 pt-1 border-t border-[#1a1a1a] animate-fade-in space-y-2">
                <div className="grid grid-cols-3 gap-2 text-[9px]">
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Binding</div>
                    <div className="text-white font-bold">{(r.binding_score * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Kd estimate</div>
                    <div className="text-white font-bold">
                      {r.kd_nM != null
                        ? (r.kd_nM < 1000 ? r.kd_nM.toFixed(0) + ' nM' : (r.kd_nM / 1000).toFixed(1) + ' μM')
                        : '—'}
                    </div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Half-life</div>
                    <div className="text-white font-bold">{r.serum_half_life_min != null ? r.serum_half_life_min.toFixed(0) + ' min' : '—'}</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Selectivity</div>
                    <div className={`font-bold ${r.toxicity_flag ? 'text-red-400' : r.selectivity_ratio != null && r.selectivity_ratio >= 5 ? 'text-green-400' : 'text-yellow-500'}`}>
                      {r.selectivity_ratio != null ? r.selectivity_ratio.toFixed(1) + 'x' : '—'}
                      {r.toxicity_flag && ' !'}
                    </div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Stability</div>
                    <div className="text-white font-bold">{(r.stability_score * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Solubility</div>
                    <div className="text-white font-bold">{(r.solubility_score * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">Energy</div>
                    <div className="text-green-400 font-bold">{r.total_energy.toFixed(4)}</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">R-hat</div>
                    <div className="text-gray-300 font-bold">{r.rhat?.toFixed(4) || '—'}</div>
                  </div>
                  <div className="bg-[#0a0a0a] rounded p-2">
                    <div className="text-gray-500">ESS</div>
                    <div className="text-gray-300 font-bold">{r.ess || '—'}</div>
                  </div>
                </div>

                {r.mutations.length > 0 && (
                  <div>
                    <div className="text-[9px] text-gray-500 mb-1">Mutations ({r.mutations.length}):</div>
                    <div className="flex flex-wrap gap-1">
                      {r.mutations.map((m, mi) => (
                        <span key={mi} className="text-[8px] font-mono bg-red-900/30 text-red-300 px-1.5 py-0.5 rounded">
                          {m.from}{m.position}{m.to}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {r.steps && (
                  <div className="text-[9px] text-gray-600">
                    MCMC: {r.steps} steps × {r.chains} chains · {r.num_candidates || 0} candidates generated
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
