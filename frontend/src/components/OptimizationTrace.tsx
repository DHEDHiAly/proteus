import { useState } from 'react';
import type { TraceStep } from '../types/agent';

export type { TraceStep };

type Props = {
  trace: TraceStep[];
  round?: number;
};

export default function OptimizationTrace({ trace, round }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  if (!trace || trace.length === 0) return null;

  return (
    <div className="rounded-lg border border-[#1e1e1e] bg-[#070707] overflow-hidden text-[10px]">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center space-x-2">
          <span className="text-gray-600 uppercase tracking-wider font-medium text-[9px]">
            {round ? `Round ${round} — ` : ''}Optimization Trace
          </span>
          <span className="text-[8px] text-gray-700 font-mono">{trace.length} accepted mutations</span>
        </div>
        <span className="text-gray-700 text-[9px]">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="border-t border-[#1a1a1a]">
          {trace.map((step, i) => {
            const favorable = step.delta_energy < 0;
            const isOpen = expandedStep === i;
            return (
              <div key={i} className="border-b border-[#111] last:border-b-0">
                <button
                  onClick={() => setExpandedStep(isOpen ? null : i)}
                  className="w-full flex items-center space-x-2.5 px-3 py-1.5 hover:bg-white/[0.015] transition-colors text-left"
                >
                  {/* Step number */}
                  <span className="text-[8px] text-gray-700 font-mono w-8 flex-shrink-0">
                    s{step.step}
                  </span>

                  {/* Mutation badge */}
                  <span className="font-mono text-[9px] bg-[#111] border border-[#222] px-1.5 py-0.5 rounded text-gray-300 flex-shrink-0">
                    {step.from}{step.position}{step.to}
                  </span>

                  {/* Energy delta */}
                  <span
                    className={`font-mono text-[9px] flex-shrink-0 ${
                      favorable ? 'text-green-500' : 'text-yellow-600'
                    }`}
                  >
                    {step.delta_energy > 0 ? '+' : ''}{step.delta_energy.toFixed(3)}
                  </span>

                  {/* Temperature badge */}
                  <span className="text-[8px] text-gray-700 flex-shrink-0 font-mono">
                    T={step.temperature}
                  </span>

                  {/* Truncated narrative */}
                  <span className="text-gray-600 truncate text-[9px] flex-1 min-w-0">
                    {step.narrative.replace(/\*\*/g, '').slice(0, 60)}
                  </span>

                  <span className="text-gray-700 text-[8px] flex-shrink-0">{isOpen ? '−' : '+'}</span>
                </button>

                {isOpen && (
                  <div className="px-3 pb-2 pt-0.5 bg-black/30">
                    <p className="text-gray-500 leading-relaxed text-[9px]">
                      {step.narrative.replace(/\*\*/g, '')}
                    </p>
                    <div className="mt-1.5 flex items-center space-x-3 text-[8px] text-gray-700">
                      <span>Step {step.step}</span>
                      <span>Position {step.position}</span>
                      <span>T = {step.temperature}</span>
                      <span className={favorable ? 'text-green-600' : 'text-yellow-700'}>
                        {favorable ? 'Favorable' : 'Accepted by MCMC'}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
