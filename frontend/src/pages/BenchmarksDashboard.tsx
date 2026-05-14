import { useState, useEffect } from 'react';
import {
  BarChart, Bar, ScatterChart, Scatter, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

interface SOTABinder {
  sequence: string;
  binding_affinity_nM: number;
  stability_score?: number;
  bbb_permeable?: boolean;
  source?: string;
}

interface ProteusCandidate {
  rank: number;
  sequence: string;
  binding_affinity_nM: number;
  stability_score?: number;
  beat_sota?: boolean;
  improvement_percent?: number;
  diversity_score?: number;
}

interface BenchmarkData {
  target_id: string;
  target_name: string;
  sota_binders: SOTABinder[];
  proteus_candidates: ProteusCandidate[];
  best_proteus_binding_nM?: number;
  best_sota_binding_nM?: number;
}

interface StatsData {
  target_id: string;
  target_name: string;
  success_rate_percent: number;
  candidates_beat_sota: number;
  avg_improvement_percent: number;
  avg_diversity_score: number;
  total_runs: number;
  sota_best_binding_nM?: number;
  proteus_best_binding_nM?: number;
  best_improvement_percent: number;
}

interface ConvergenceData {
  steps: number[];
  best_binding: number[];
  sota_line?: number;
  num_runs: number;
}

const TARGETS = [
  { id: 'EGFRvIII', label: 'EGFRvIII' },
  { id: 'PD-L1', label: 'PD-L1' },
  { id: 'KRAS_G12C', label: 'KRAS G12C' },
];

const API = '/api/v1';

function getToken() {
  return localStorage.getItem('proteus_access_token') || '';
}

export default function BenchmarksDashboard() {
  const [targetId, setTargetId] = useState('EGFRvIII');
  const [benchmarks, setBenchmarks] = useState<BenchmarkData | null>(null);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [convergence, setConvergence] = useState<ConvergenceData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData(targetId);
  }, [targetId]);

  const fetchData = async (target: string) => {
    setLoading(true);
    const headers = { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' };
    try {
      const [b, s, c] = await Promise.all([
        fetch(`${API}/benchmarks/${target}`, { headers }),
        fetch(`${API}/benchmarks/${target}/stats`, { headers }),
        fetch(`${API}/benchmarks/${target}/convergence`, { headers }),
      ]);
      if (b.ok) setBenchmarks(await b.json());
      if (s.ok) setStats(await s.json());
      if (c.ok) setConvergence(await c.json());
    } catch (e) {
      console.error('Benchmark fetch error:', e);
    }
    setLoading(false);
  };

  const proteusBest = benchmarks?.proteus_candidates?.[0];
  const sotaBest = benchmarks?.sota_binders?.[0];
  const beatSota = proteusBest && sotaBest && proteusBest.binding_affinity_nM < sotaBest.binding_affinity_nM;

  const bindingData = benchmarks ? [
    { name: 'SOTA Best', binding: sotaBest?.binding_affinity_nM || 0, fill: '#666' },
    { name: 'Proteus Best', binding: proteusBest?.binding_affinity_nM || 999, fill: beatSota ? '#fff' : '#888' },
  ] : [];

  const tradeoffData = benchmarks?.proteus_candidates.map((c) => ({
    x: c.binding_affinity_nM,
    y: c.stability_score || 0.5,
    rank: c.rank,
  })) || [];

  const convData = convergence?.steps.map((s, i) => ({
    step: s,
    best: convergence.best_binding[i] || 0,
  })) || [];

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-500 text-sm animate-pulse">Loading benchmarks...</div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold">Benchmarking Dashboard</h1>
        <p className="text-gray-500 text-[11px] mt-0.5">Proteus candidates vs state-of-the-art binders</p>
      </div>

      <div className="flex space-x-2">
        {TARGETS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTargetId(t.id)}
            className={`text-[11px] px-3 py-1.5 rounded-lg border transition-all ${
              targetId === t.id
                ? 'bg-white text-black border-white'
                : 'bg-transparent text-gray-400 border-[#222] hover:border-white/30'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Best Binding', value: stats.proteus_best_binding_nM ? `${stats.proteus_best_binding_nM.toFixed(0)} nM` : '—', sub: `SOTA: ${stats.sota_best_binding_nM?.toFixed(0) || '—'} nM`, highlight: beatSota },
            { label: 'Success Rate', value: `${stats.success_rate_percent.toFixed(1)}%`, sub: `${stats.candidates_beat_sota} beat SOTA`, highlight: stats.success_rate_percent > 50 },
            { label: 'Improvement', value: `${stats.best_improvement_percent.toFixed(1)}%`, sub: 'over SOTA baseline', highlight: stats.best_improvement_percent > 0 },
            { label: 'Diversity', value: stats.avg_diversity_score.toFixed(2), sub: 'sequence diversity', highlight: stats.avg_diversity_score > 0.5 },
          ].map((s) => (
            <div key={s.label} className={`bg-[#0a0a0a] border ${s.highlight ? 'border-white/20' : 'border-[#1a1a1a]'} rounded-xl p-4`}>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</div>
              <div className={`text-xl font-bold mt-1 ${s.highlight ? 'text-white' : 'text-gray-300'}`}>{s.value}</div>
              <div className="text-[10px] text-gray-600 mt-0.5">{s.sub}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {benchmarks && (
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
            <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">1. Binding Affinity Comparison</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={bindingData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                <XAxis dataKey="name" stroke="#444" fontSize={11} />
                <YAxis stroke="#444" fontSize={11} label={{ value: 'nM (lower = better)', angle: -90, position: 'insideLeft', style: { fill: '#666', fontSize: 10 } }} />
                <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="binding" fill="#888" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">2. Multi-Objective Trade-off</h3>
          <ResponsiveContainer width="100%" height={250}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="x" stroke="#444" fontSize={11} label={{ value: 'Binding (nM)', position: 'insideBottomRight', style: { fill: '#666', fontSize: 10 } }} />
              <YAxis dataKey="y" stroke="#444" fontSize={11} label={{ value: 'Stability', angle: -90, position: 'insideLeft', style: { fill: '#666', fontSize: 10 } }} domain={[0, 1]} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 11 }} />
              <Scatter name="Proteus" data={tradeoffData} fill="#fff" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {convergence && (
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
            <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">3. Convergence Speed</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={convData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                <XAxis dataKey="step" stroke="#444" fontSize={11} />
                <YAxis stroke="#444" fontSize={11} />
                <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line type="monotone" dataKey="best" stroke="#fff" dot={false} strokeWidth={2} name="Proteus" />
                {convergence.sota_line && (
                  <Line type="monotone" dataKey={() => convergence.sota_line} stroke="#666" strokeDasharray="5 5" strokeWidth={1.5} dot={false} name="SOTA" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {benchmarks && (
          <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
            <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">4. Success Rate Distribution</h3>
            <SuccessRateChart candidates={benchmarks.proteus_candidates} />
          </div>
        )}
      </div>

      {benchmarks && (
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">5. Candidate Diversity</h3>
          <DiversityHeatmap candidates={benchmarks.proteus_candidates} />
        </div>
      )}

      {stats && (
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">Summary Statistics</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#222] text-gray-500">
                  <th className="text-left py-2 pr-4 font-medium">Metric</th>
                  <th className="text-right py-2 font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Proteus Best Binding', stats.proteus_best_binding_nM ? `${stats.proteus_best_binding_nM.toFixed(1)} nM` : '—'],
                  ['SOTA Best Binding', stats.sota_best_binding_nM ? `${stats.sota_best_binding_nM.toFixed(1)} nM` : '—'],
                  ['Success Rate', `${stats.success_rate_percent.toFixed(1)}%`],
                  ['Candidates Beating SOTA', `${stats.candidates_beat_sota}`],
                  ['Avg Improvement', `${stats.avg_improvement_percent.toFixed(1)}%`],
                  ['Avg Diversity Score', stats.avg_diversity_score.toFixed(2)],
                  ['Total Runs', `${stats.total_runs}`],
                ].map(([metric, value]) => (
                  <tr key={metric} className="border-b border-[#1a1a1a]">
                    <td className="py-2 pr-4 text-gray-400">{metric}</td>
                    <td className="py-2 text-right text-white font-medium">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SuccessRateChart({ candidates }: { candidates: ProteusCandidate[] }) {
  const bins: Record<string, number> = {};
  candidates.forEach((c) => {
    const bin = Math.floor((c.binding_affinity_nM || 999) / 200) * 200;
    const key = `${bin}-${bin + 200}`;
    bins[key] = (bins[key] || 0) + 1;
  });
  const data = Object.entries(bins).map(([range, count]) => ({ range, count }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
        <XAxis dataKey="range" stroke="#444" fontSize={10} />
        <YAxis stroke="#444" fontSize={10} />
        <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 11 }} />
        <Bar dataKey="count" fill="#555" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function DiversityHeatmap({ candidates }: { candidates: ProteusCandidate[] }) {
  const top = candidates.slice(0, 8);
  return (
    <div>
      <div className="grid gap-[1px]" style={{ gridTemplateColumns: `repeat(${top.length}, 1fr)` }}>
        {top.map((c1, i) =>
          top.map((c2, j) => {
            const dist = Math.abs(i - j) / Math.max(top.length - 1, 1);
            return (
              <div
                key={`${i}-${j}`}
                className="aspect-square rounded-sm transition-colors hover:ring-1 hover:ring-white/30"
                style={{ background: `rgba(255,255,255,${0.05 + dist * 0.4})` }}
                title={`${c1.sequence.slice(0, 4)} vs ${c2.sequence.slice(0, 4)}: ${(dist * 100).toFixed(0)}% divergent`}
              />
            );
          })
        )}
      </div>
      <p className="text-[9px] text-gray-600 mt-2">Pairwise sequence divergence of top-8 candidates (darker = more different)</p>
    </div>
  );
}
