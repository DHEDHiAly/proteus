import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

// ── Types ─────────────────────────────────────────────────────────────────────

interface MethodMeta {
  name: string
  category: string
  time_hours: number
  cost_dollars: number
}

interface TargetData {
  display: string
  disease_area: string
  pdb_id: string
  binding_nM: Record<string, number>
}

interface BenchmarkFile {
  metadata: {
    note: string
    methods: Record<string, MethodMeta>
  }
  targets: Record<string, TargetData>
  aggregate: {
    avg_binding_nM_by_method: Record<string, number>
    proteus_improvement_pct_vs: Record<string, number>
  }
}

// ── Constants ─────────────────────────────────────────────────────────────────

const METHOD_ORDER = [
  'proteus_mcmc',
  'md_consensus',
  'rosetta_design',
  'foldx',
  'alphafold3',
  'alphafold2',
  'rosettafold2',
  'omegafold',
  'esmfold',
  'random_baseline',
]

const TOOLTIP_STYLE = {
  background: '#111',
  border: '1px solid #333',
  borderRadius: 8,
  fontSize: 11,
  color: '#fff',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function barFill(methodKey: string): string {
  if (methodKey === 'proteus_mcmc') return '#ffffff'
  if (methodKey === 'random_baseline') return '#2a2a2a'
  return '#444'
}

function formatCost(dollars: number): string {
  if (dollars === 0) return 'Free'
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(0)}k`
  return `$${dollars}`
}

function formatTime(hours: number): string {
  if (hours < 0.01) return '<1 min'
  if (hours < 1) return `${Math.round(hours * 60)} min`
  if (hours < 24) return `${hours}h`
  return `${hours / 24}d`
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface BarTooltipProps {
  active?: boolean
  payload?: { value: number; payload: { method: string; binding: number; improvement: string } }[]
}

function BarTooltip({ active, payload }: BarTooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 space-y-0.5">
      <div className="font-medium text-white text-[11px]">{d.method}</div>
      <div className="text-gray-400 text-[10px]">{d.binding} nM</div>
      {d.improvement && (
        <div className="text-[10px]" style={{ color: '#6ee7b7' }}>{d.improvement}</div>
      )}
    </div>
  )
}

interface ScatterTooltipProps {
  active?: boolean
  payload?: { payload: { method: string; time: number; binding: number; cost: number } }[]
}

function ScatterTooltip({ active, payload }: ScatterTooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={TOOLTIP_STYLE} className="px-3 py-2 space-y-0.5">
      <div className="font-medium text-white text-[11px]">{d.method}</div>
      <div className="text-gray-400 text-[10px]">{d.binding} nM avg &bull; {formatTime(d.time)} &bull; {formatCost(d.cost)}</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ComparisonDashboard() {
  const [data, setData] = useState<BenchmarkFile | null>(null)
  const [selectedTarget, setSelectedTarget] = useState<string>('EGFRvIII')
  const [sortCol, setSortCol] = useState<'binding' | 'time' | 'cost'>('binding')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  useEffect(() => {
    fetch('/data/expanded_benchmark_data.json')
      .then((r) => r.json())
      .then((d: BenchmarkFile) => setData(d))
      .catch(console.error)
  }, [])

  const targetKeys = useMemo(() => (data ? Object.keys(data.targets) : []), [data])

  // Bar chart data for selected target
  const barData = useMemo(() => {
    if (!data) return []
    const target = data.targets[selectedTarget]
    const proteus = target.binding_nM['proteus_mcmc']
    return METHOD_ORDER.map((key) => {
      const meta = data.metadata.methods[key]
      const binding = target.binding_nM[key]
      const improvement =
        key !== 'proteus_mcmc' && binding > proteus
          ? `${Math.round(((binding - proteus) / binding) * 100)}% worse than Proteus`
          : undefined
      return {
        methodKey: key,
        method: meta.name,
        binding,
        improvement,
      }
    })
  }, [data, selectedTarget])

  // Scatter: avg binding (y) vs log time (x), sized by cost
  const scatterData = useMemo(() => {
    if (!data) return []
    return METHOD_ORDER.map((key) => {
      const meta = data.metadata.methods[key]
      const avgBinding = data.aggregate.avg_binding_nM_by_method[key]
      return {
        methodKey: key,
        method: meta.name,
        time: meta.time_hours,
        binding: avgBinding,
        cost: meta.cost_dollars,
      }
    })
  }, [data])

  // Sortable table
  const tableRows = useMemo(() => {
    if (!data) return []
    const target = data.targets[selectedTarget]
    const rows = METHOD_ORDER.map((key) => {
      const meta = data.metadata.methods[key]
      const binding = target.binding_nM[key]
      const proteus = target.binding_nM['proteus_mcmc']
      const delta = key === 'proteus_mcmc' ? null : Math.round(((binding - proteus) / binding) * 100)
      return { key, name: meta.name, category: meta.category, binding, time: meta.time_hours, cost: meta.cost_dollars, delta }
    })
    rows.sort((a, b) => {
      const v = sortCol === 'binding' ? a.binding - b.binding : sortCol === 'time' ? a.time - b.time : a.cost - b.cost
      return sortDir === 'asc' ? v : -v
    })
    return rows
  }, [data, selectedTarget, sortCol, sortDir])

  const handleSort = (col: typeof sortCol) => {
    if (col === sortCol) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 text-sm animate-pulse">Loading comparison data...</div>
      </div>
    )
  }

  const proteusAvg = data.aggregate.avg_binding_nM_by_method['proteus_mcmc']
  const af2Avg = data.aggregate.avg_binding_nM_by_method['alphafold2']
  const proteusImprovementVsAF2 = Math.round(((af2Avg - proteusAvg) / af2Avg) * 100)

  return (
    <div className="space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-lg font-bold">Method Comparison</h1>
        <p className="text-gray-500 text-[11px] mt-0.5">
          Proteus MCMC vs 9 alternative approaches across 10 disease targets
        </p>
      </div>

      {/* Summary stat strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Proteus Avg Binding', value: `${proteusAvg} nM`, sub: 'across 10 targets' },
          { label: 'vs AlphaFold2', value: `${proteusImprovementVsAF2}% better`, sub: 'binding affinity' },
          { label: 'Compute Time', value: '<1 min', sub: 'vs hours/days' },
          { label: 'Compute Cost', value: 'Free', sub: 'vs up to $100k' },
        ].map((s) => (
          <div key={s.label} className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</div>
            <div className="text-xl font-bold mt-1 text-white">{s.value}</div>
            <div className="text-[10px] text-gray-600 mt-0.5">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Target selector */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Select target</div>
        <div className="flex flex-wrap gap-2">
          {targetKeys.map((key) => (
            <button
              key={key}
              onClick={() => setSelectedTarget(key)}
              className={`text-[11px] px-3 py-1.5 rounded-lg border transition-all ${
                selectedTarget === key
                  ? 'bg-white text-black border-white'
                  : 'bg-transparent text-gray-400 border-[#222] hover:border-white/30'
              }`}
            >
              {data.targets[key].display.split(' (')[0]}
            </button>
          ))}
        </div>
        <div className="text-[10px] text-gray-600 mt-1.5">
          {data.targets[selectedTarget].display} &bull; {data.targets[selectedTarget].disease_area} &bull; PDB: {data.targets[selectedTarget].pdb_id}
        </div>
      </div>

      {/* Bar chart + Scatter */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* 1. Per-target binding bar chart */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[11px] font-medium text-gray-400 mb-1 uppercase tracking-wider">
            1. Binding Affinity — {data.targets[selectedTarget].display.split(' (')[0]}
          </h3>
          <p className="text-[10px] text-gray-600 mb-3">nM (lower = stronger binding)</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} layout="vertical" margin={{ left: 90, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
              <XAxis type="number" stroke="#444" fontSize={10} />
              <YAxis type="category" dataKey="method" stroke="#444" fontSize={10} width={88} />
              <Tooltip content={<BarTooltip />} />
              <Bar dataKey="binding" radius={[0, 4, 4, 0]}>
                {barData.map((entry) => (
                  <Cell key={entry.methodKey} fill={barFill(entry.methodKey)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 2. Speed vs Quality scatter */}
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
          <h3 className="text-[11px] font-medium text-gray-400 mb-1 uppercase tracking-wider">
            2. Speed vs Quality (All Targets Avg)
          </h3>
          <p className="text-[10px] text-gray-600 mb-3">Lower-left = faster AND stronger binding</p>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 8, right: 20, bottom: 20, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis
                dataKey="time"
                type="number"
                scale="log"
                domain={['auto', 'auto']}
                stroke="#444"
                fontSize={10}
                label={{ value: 'Time (hours, log scale)', position: 'insideBottom', offset: -12, style: { fill: '#666', fontSize: 10 } }}
                tickFormatter={(v) => (v < 1 ? `${(v * 60).toFixed(0)}min` : `${v}h`)}
              />
              <YAxis
                dataKey="binding"
                type="number"
                stroke="#444"
                fontSize={10}
                label={{ value: 'Avg binding (nM)', angle: -90, position: 'insideLeft', style: { fill: '#666', fontSize: 10 } }}
              />
              <Tooltip content={<ScatterTooltip />} />
              <Scatter data={scatterData} shape={(props: any) => {
                const { cx, cy, payload } = props
                const isProteus = payload.methodKey === 'proteus_mcmc'
                const r = isProteus ? 8 : 5
                return <circle cx={cx} cy={cy} r={r} fill={isProteus ? '#fff' : '#444'} stroke={isProteus ? '#fff' : '#555'} strokeWidth={1} />
              }} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. Sortable comparison table */}
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl p-4">
        <h3 className="text-[11px] font-medium text-gray-400 mb-3 uppercase tracking-wider">
          3. Full Method Comparison — {data.targets[selectedTarget].display.split(' (')[0]}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#222] text-gray-500">
                <th className="text-left py-2 pr-4 font-medium">Method</th>
                <th className="text-left py-2 pr-4 font-medium text-gray-600">Category</th>
                <th
                  className="text-right py-2 pr-4 font-medium cursor-pointer hover:text-white transition-colors select-none"
                  onClick={() => handleSort('binding')}
                >
                  Binding (nM) {sortCol === 'binding' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  className="text-right py-2 pr-4 font-medium cursor-pointer hover:text-white transition-colors select-none"
                  onClick={() => handleSort('time')}
                >
                  Time {sortCol === 'time' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th
                  className="text-right py-2 font-medium cursor-pointer hover:text-white transition-colors select-none"
                  onClick={() => handleSort('cost')}
                >
                  Est. Cost {sortCol === 'cost' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="text-right py-2 pl-4 font-medium">vs Proteus</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row) => (
                <tr
                  key={row.key}
                  className={`border-b border-[#111] ${row.key === 'proteus_mcmc' ? 'bg-white/5' : ''}`}
                >
                  <td className={`py-2 pr-4 font-medium ${row.key === 'proteus_mcmc' ? 'text-white' : 'text-gray-300'}`}>
                    {row.name}
                  </td>
                  <td className="py-2 pr-4 text-gray-600">{row.category}</td>
                  <td className={`py-2 pr-4 text-right tabular-nums ${row.key === 'proteus_mcmc' ? 'text-white font-bold' : 'text-gray-400'}`}>
                    {row.binding}
                  </td>
                  <td className="py-2 pr-4 text-right text-gray-500">{formatTime(row.time)}</td>
                  <td className={`py-2 text-right ${row.cost > 0 ? 'text-gray-500' : 'text-gray-600'}`}>
                    {formatCost(row.cost)}
                  </td>
                  <td className="py-2 pl-4 text-right">
                    {row.delta === null ? (
                      <span className="text-gray-600">—</span>
                    ) : row.delta > 0 ? (
                      <span style={{ color: '#6ee7b7' }} className="text-[10px]">{row.delta}% worse</span>
                    ) : (
                      <span className="text-red-400 text-[10px]">better</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-[10px] text-gray-700 border-t border-[#111] pt-3">
        FOR RESEARCH USE ONLY. AlphaFold binding values are structural estimates (pLDDT-weighted contact scoring), not experimentally validated affinity predictions. Cost figures are representative estimates for equivalent compute resources.
      </p>
    </div>
  )
}
