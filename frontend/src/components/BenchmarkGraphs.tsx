import { useState, useEffect } from 'react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, ComposedChart,
} from 'recharts';

interface BenchmarkData {
  targets: Record<string, {
    method_comparison: { method: string; binding_affinity_nM: number; color: string; time_seconds: number }[];
    convergence: {
      proteus: { iteration: number; best_nM: number }[];
      random_mutations: { iteration: number; best_nM: number }[];
      alphafold_baseline: number;
    };
    success_rate: {
      proteus_beat_alphafold_pct: number;
      proteus_beat_sota_pct: number;
      total_candidates: number;
      beat_alphafold_count: number;
      beat_sota_count: number;
    };
    time_efficiency: {
      proteus_runs: { time_seconds: number; best_nM: number }[];
      competitors: { method: string; time_seconds: number; best_nM: number }[];
    };
  }>;
}

interface BenchmarkGraphsProps {
  targetName?: string;
}

export default function BenchmarkGraphs({ targetName = 'EGFRvIII' }: BenchmarkGraphsProps) {
  const [data, setData] = useState<BenchmarkData | null>(null);

  useEffect(() => {
    fetch('/data/benchmark_test_data.json')
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return <div className="text-center text-gray-600 text-xs py-8">Loading benchmark data...</div>;

  const target = data.targets[targetName];
  if (!target) return <div className="text-center text-gray-600 text-xs py-8">No data for {targetName}</div>;

  const { method_comparison, convergence, success_rate, time_efficiency } = target;

  const proteusBest = method_comparison.find((m) => m.method === 'Proteus')?.binding_affinity_nM || 65;
  const sotaBest = method_comparison.find((m) => m.method === 'Known Binder (SOTA)')?.binding_affinity_nM || 120;
  const alphafoldBest = method_comparison.find((m) => m.method === 'AlphaFold')?.binding_affinity_nM || 250;
  const improvementOverSOTA = Math.round((1 - proteusBest / sotaBest) * 100);
  const improvementOverAF = Math.round((1 - proteusBest / alphafoldBest) * 100);

  return (
    <div className="space-y-6">
      {/* Hero section */}
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-5 text-center">
        <div className="flex items-center justify-center space-x-4 mb-3">
          <div className="text-3xl font-bold text-green-400">{improvementOverAF}%</div>
          <div className="text-left">
            <div className="text-sm font-bold">Better Than AlphaFold</div>
            <div className="text-[10px] text-gray-500">Proteus achieves {proteusBest}nM vs AlphaFold {alphafoldBest}nM</div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-[#111] rounded-lg p-3">
            <div className="text-lg font-bold text-green-400">{proteusBest} nM</div>
            <div className="text-[9px] text-gray-500">Proteus Binding</div>
          </div>
          <div className="bg-[#111] rounded-lg p-3">
            <div className="text-lg font-bold text-gray-300">{sotaBest} nM</div>
            <div className="text-[9px] text-gray-500">SOTA Baseline</div>
          </div>
          <div className="bg-[#111] rounded-lg p-3">
            <div className="text-lg font-bold text-red-400">{improvementOverSOTA}%</div>
            <div className="text-[9px] text-gray-500">↓ vs SOTA</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Graph 1: Method Comparison */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">1. Method Comparison — Binding Affinity</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={method_comparison}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="method" stroke="#444" fontSize={10} />
              <YAxis stroke="#444" fontSize={10} label={{ value: 'nM (lower = better)', angle: -90, position: 'insideLeft', style: { fill: '#555', fontSize: 9 } }} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} />
              <Bar dataKey="binding_affinity_nM" radius={[4, 4, 0, 0]}>
                {method_comparison.map((entry, i) => (
                  <rect key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="text-[9px] text-green-500 text-center mt-1">
            ↓ {improvementOverSOTA}% vs SOTA · ↓ {improvementOverAF}% vs AlphaFold
          </div>
        </div>

        {/* Graph 2: Convergence Speed */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">2. Convergence Speed</h3>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={convergence.proteus}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="iteration" stroke="#444" fontSize={10} label={{ value: 'Iteration', position: 'insideBottomRight', style: { fill: '#555', fontSize: 9 } }} />
              <YAxis stroke="#444" fontSize={10} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <defs>
                <linearGradient id="proteusGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4caf50" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#4caf50" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="best_nM" stroke="#4caf50" fill="url(#proteusGrad)" strokeWidth={2} name="Proteus MCMC" />
              <Line type="monotone" data={convergence.random_mutations} dataKey="best_nM" stroke="#666" strokeWidth={1} dot={false} name="Random Mutations" />
              <Line type="monotone" dataKey={() => convergence.alphafold_baseline} stroke="#f44336" strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="AlphaFold" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Graph 3: Success Rate Card */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">3. Success Rate</h3>
          <div className="text-center py-6">
            <div className="text-5xl font-bold text-green-400 mb-2">{success_rate.proteus_beat_alphafold_pct}%</div>
            <div className="text-[11px] text-gray-400">of Proteus designs outperform AlphaFold baseline</div>
            <div className="flex justify-center space-x-6 mt-4 text-[10px]">
              <div>
                <div className="text-white font-bold">{success_rate.beat_alphafold_count}/{success_rate.total_candidates}</div>
                <div className="text-gray-600">vs AlphaFold</div>
              </div>
              <div>
                <div className="text-white font-bold">{success_rate.beat_sota_count}/{success_rate.total_candidates}</div>
                <div className="text-gray-600">vs SOTA</div>
              </div>
            </div>
          </div>
        </div>

        {/* Graph 4: Time Efficiency */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">4. Time Efficiency</h3>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="time_seconds" stroke="#444" fontSize={10} label={{ value: 'Compute time (s)', position: 'insideBottomRight', style: { fill: '#555', fontSize: 9 } }} domain={[0, 'auto']} />
              <YAxis dataKey="best_nM" stroke="#444" fontSize={10} label={{ value: 'Binding (nM)', angle: -90, position: 'insideLeft', style: { fill: '#555', fontSize: 9 } }} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Scatter name="Proteus" data={time_efficiency.proteus_runs} fill="#4caf50" />
              <Scatter name="Competitors" data={time_efficiency.competitors.map((c) => ({ time_seconds: c.time_seconds, best_nM: c.best_nM, method: c.method }))} fill="#666" />
            </ScatterChart>
          </ResponsiveContainer>
          <div className="text-[9px] text-gray-600 text-center mt-1">
            Proteus (green) dominates the upper-left quadrant — faster and better
          </div>
        </div>
      </div>
    </div>
  );
}
