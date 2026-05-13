import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

interface EnergyChartProps {
  chainEnergies: { chainIndex: number; energies: number[] }[]
  steps: number[]
  temperatures: number[]
}

export default function EnergyChart({ chainEnergies, steps, temperatures }: EnergyChartProps) {
  const chartData = steps.map((step, idx) => {
    const point: Record<string, number | string> = { step }
    chainEnergies.forEach((chain, ci) => {
      if (idx < chain.energies.length) {
        point[`chain_${ci}`] = parseFloat(chain.energies[idx].toFixed(4))
      }
    })
    return point
  })

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Energy Landscape</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="step"
            label={{ value: 'MCMC Step', position: 'insideBottom', offset: -5 }}
            fontSize={12}
          />
          <YAxis
            label={{ value: 'Energy', angle: -90, position: 'insideLeft' }}
            fontSize={12}
          />
          <Tooltip
            contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
          />
          <Legend />
          {chainEnergies.map((chain, ci) => (
            <Line
              key={ci}
              type="monotone"
              dataKey={`chain_${ci}`}
              stroke={COLORS[ci % COLORS.length]}
              name={`Chain ${ci + 1} (T=${temperatures[ci] || '?'})`}
              dot={false}
              strokeWidth={1.5}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
