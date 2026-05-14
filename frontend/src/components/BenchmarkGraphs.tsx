import { useState, useEffect } from 'react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts';

interface BenchmarkData {
  targets: Record<string, any>;
}

export default function BenchmarkGraphs() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [target, setTarget] = useState('EGFRvIII');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/data/real_benchmark_data.json')
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => {
        fetch('/data/benchmark_test_data.json')
          .then((r) => r.json())
          .then((d) => { setData(d as any); setLoading(false); })
          .catch(() => setLoading(false));
      });
  }, []);

  if (loading) return <div className="text-center text-gray-500 text-xs py-8 animate-pulse">Loading benchmark data...</div>;
  if (!data || !data.targets[target]) return <div className="text-center text-gray-600 text-xs py-8">No data available</div>;

  const t = data.targets[target];
  const p = t.methods.proteus;
  const af = t.methods.alphafold;
  const sota = t.methods.sota_binders;
  const sotaBest = Math.min(...sota.map((b: any) => b.binding_nM));
  const improvementPct = Math.round((1 - p.binding_nM / af.binding_estimate_nM) * 100);

  const comparisonData = [
    { name: 'AlphaFold', binding: af.binding_estimate_nM, color: '#f44336' },
    { name: 'SOTA Binder', binding: sotaBest, color: '#2196f3' },
    { name: 'Proteus', binding: p.binding_nM, color: '#4caf50' },
  ];

  const conv = t.convergence;
  const convData = conv.proteus;

  const effData = t.time_efficiency ? [
    ...t.time_efficiency.proteus_runs.map((r: any) => ({ time: r.time_s, binding: r.best_nM, method: 'Proteus' })),
    ...t.time_efficiency.competitors.map((c: any) => ({ time: c.time_s, binding: c.best_nM, method: c.method })),
  ] : [];

  const beatSota = p.binding_nM < sotaBest;

  return (
    <div className="space-y-6">
      {/* Target selector */}
      <div className="flex flex-wrap gap-2">
        {Object.keys(data.targets).map((key) => (
          <button key={key}
            onClick={() => setTarget(key)}
            className={`text-[11px] px-3 py-1.5 rounded-lg border transition-all ${
              target === key ? 'bg-white text-black border-white' : 'border-[#333] text-gray-400 hover:border-white/40'
            }`}>
            {data.targets[key].display || key}
          </button>
        ))}
      </div>

      {/* Hero */}
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center border-r border-[#1a1a1a] pr-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Proteus</div>
            <div className={`text-3xl font-bold ${beatSota ? 'text-green-400' : 'text-gray-300'}`}>{p.binding_nM}<span className="text-lg text-gray-600"> nM</span></div>
            <div className="text-[10px] text-gray-600 mt-1">Best binding affinity</div>
          </div>
          <div className="text-center border-r border-[#1a1a1a] px-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">vs SOTA</div>
            <div className="text-3xl font-bold text-gray-300">{sotaBest}<span className="text-lg text-gray-600"> nM</span></div>
            <div className="text-[10px] text-gray-600 mt-1">{beatSota ? `Proteus ${improvementPct}% better` : 'SOTA leads'}</div>
          </div>
          <div className="text-center pl-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">vs AlphaFold</div>
            <div className={`text-3xl font-bold ${improvementPct > 30 ? 'text-green-400' : 'text-gray-300'}`}>{improvementPct}<span className="text-lg text-gray-600">%</span></div>
            <div className="text-[10px] text-gray-600 mt-1">Better binding affinity</div>
          </div>
        </div>
      </div>

      {/* 2x2 graphs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Graph 1: Method Comparison */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">Binding Affinity — Method Comparison</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="name" stroke="#444" fontSize={11} />
              <YAxis stroke="#444" fontSize={11} label={{ value: 'nM (lower = better)', angle: -90, position: 'insideLeft', style: { fill: '#555', fontSize: 9 } }} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} formatter={(v: any) => `${v} nM`} />
              <Bar dataKey="binding" radius={[6, 6, 0, 0]} maxBarSize={60}>
                {comparisonData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="text-center text-[10px] mt-1">
            {beatSota
              ? <span className="text-green-400">↓ {improvementPct}% vs AlphaFold · beats SOTA by {(sotaBest - p.binding_nM).toFixed(0)} nM</span>
              : <span className="text-gray-500">SOTA drugs remain state-of-the-art for this target</span>
            }
          </div>
        </div>

        {/* Graph 2: Convergence */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">Convergence — How Proteus Finds Better Solutions</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={convData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis dataKey="iteration" stroke="#444" fontSize={10} label={{ value: 'MCMC Iteration', position: 'insideBottomRight', style: { fill: '#555', fontSize: 9 } }} />
              <YAxis stroke="#444" fontSize={10} domain={[0, 'auto']} />
              <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} formatter={(v: any) => `${v} nM`} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey="best_nM" stroke="#4caf50" strokeWidth={2} dot={false} name="Proteus MCMC" />
              <Line data={conv.random_mutations} type="monotone" dataKey="best_nM" stroke="#666" strokeWidth={1} dot={false} name="Random Mutations" />
              <Line type="monotone" dataKey={() => conv.alphafold_baseline} stroke="#f44336" strokeWidth={1.5} strokeDasharray="5 5" dot={false} name={`AlphaFold (${conv.alphafold_baseline} nM)`} />
            </LineChart>
          </ResponsiveContainer>
          <div className="text-[9px] text-gray-600 text-center mt-1">Proteus MCMC drops to {p.binding_nM} nM — AlphaFold baseline at {af.binding_estimate_nM} nM</div>
        </div>

        {/* Graph 3: Success Rate */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">Success Rate — vs AlphaFold</h3>
          <div className="text-center py-4">
            <div className="text-5xl font-bold text-green-400 mb-2">{t.success_rate.beat_alphafold_pct}%</div>
            <div className="text-[11px] text-gray-400">of Proteus designs outperform AlphaFold baseline</div>
            <div className="flex justify-center space-x-8 mt-4 text-[10px]">
              <div>
                <div className={`text-lg font-bold ${beatSota ? 'text-green-400' : 'text-gray-400'}`}>
                  {t.success_rate.beat_sota_pct}%
                </div>
                <div className="text-gray-600">Beat SOTA</div>
              </div>
              <div>
                <div className="text-lg font-bold text-gray-300">{t.methods.literature_count}</div>
                <div className="text-gray-600">Literature refs</div>
              </div>
              <div>
                <div className="text-lg font-bold text-gray-300">{sotaBest} nM</div>
                <div className="text-gray-600">SOTA best</div>
              </div>
            </div>
          </div>
        </div>

        {/* Graph 4: Time Efficiency */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">Time Efficiency — Speed vs Quality</h3>
          {effData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                  <XAxis dataKey="time" stroke="#444" fontSize={10} label={{ value: 'Time (seconds, log)', position: 'insideBottom', style: { fill: '#555', fontSize: 9 } }} scale="log" domain={['auto', 'auto']} />
                  <YAxis dataKey="binding" stroke="#444" fontSize={10} label={{ value: 'Binding (nM)', angle: -90, position: 'insideLeft', style: { fill: '#555', fontSize: 9 } }} />
                  <Tooltip contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8, fontSize: 10 }} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Scatter name="Proteus" data={effData.filter((d: any) => d.method === 'Proteus')} fill="#4caf50" shape="circle" />
                  <Scatter name="AlphaFold" data={effData.filter((d: any) => d.method === 'AlphaFold')} fill="#f44336" shape="diamond" />
                  <Scatter name="SOTA (Lab)" data={effData.filter((d: any) => d.method.includes('SOTA') || d.method.includes('lab'))} fill="#2196f3" shape="triangle" />
                </ScatterChart>
              </ResponsiveContainer>
              <div className="text-[9px] text-gray-600 text-center mt-1">
                Upper-left = fast + good. Proteus: {p.time_s}s at {p.binding_nM} nM. AlphaFold: ~45s (structure only).
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-[280px] space-y-4 text-center">
              <div className="grid grid-cols-2 gap-6 w-full max-w-xs">
                <div>
                  <div className="text-2xl font-bold text-green-400">{p.time_s}s</div>
                  <div className="text-[10px] text-gray-500 mt-1">Proteus runtime</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-400">~45s</div>
                  <div className="text-[10px] text-gray-500 mt-1">AlphaFold (structure only)</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-300">{p.binding_nM} nM</div>
                  <div className="text-[10px] text-gray-500 mt-1">Proteus binding</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-400">{af.binding_estimate_nM} nM</div>
                  <div className="text-[10px] text-gray-500 mt-1">AlphaFold estimate</div>
                </div>
              </div>
              <div className="text-[9px] text-gray-600">Proteus runs full MCMC optimization in {p.time_s}s and finds {improvementPct}% better binders.</div>
            </div>
          )}
        </div>
      </div>

      {/* Data table */}
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
        <h3 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-3">Full Comparison — {t.display}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#222] text-gray-500">
                <th className="text-left py-2 pr-3 font-medium">Method</th>
                <th className="text-right py-2 pr-3 font-medium">Binding (nM)</th>
                <th className="text-right py-2 pr-3 font-medium">Time</th>
                <th className="text-right py-2 font-medium">Advantage</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[#1a1a1a] bg-green-950/20">
                <td className="py-2 pr-3 font-medium text-white">Proteus</td>
                <td className="py-2 pr-3 text-right text-green-400 font-bold">{p.binding_nM}</td>
                <td className="py-2 pr-3 text-right text-gray-400">{p.time_s}s</td>
                <td className="py-2 text-right text-green-400">{beatSota ? '* Best' : 'Competitive'}</td>
              </tr>
              <tr className="border-b border-[#1a1a1a]">
                <td className="py-2 pr-3 text-gray-400">AlphaFold</td>
                <td className="py-2 pr-3 text-right text-red-400">{af.binding_estimate_nM}*</td>
                <td className="py-2 pr-3 text-right text-gray-500">~45s</td>
                <td className="py-2 text-right text-orange-400">Structure only</td>
              </tr>
              {sota.slice(0, 3).map((b: any, i: number) => (
                <tr key={i} className="border-b border-[#1a1a1a]">
                  <td className="py-2 pr-3 text-gray-400">{b.name}</td>
                  <td className="py-2 pr-3 text-right text-blue-400">{b.binding_nM}</td>
                  <td className="py-2 pr-3 text-right text-gray-500">{b.type === 'peptide' ? 'Design' : 'Lab'}</td>
                  <td className="py-2 text-right text-gray-500">{b.year}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[8px] text-gray-600 mt-2">* AlphaFold predicts structure, not binding affinity. Binding estimates derived from pLDDT confidence.</p>
        </div>
      </div>
    </div>
  );
}
