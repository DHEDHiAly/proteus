import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

interface AcceptanceChartProps {
  acceptanceRates: { chainIndex: number; rate: number }[]
  temperatures: number[]
}

export default function AcceptanceChart({ acceptanceRates, temperatures }: AcceptanceChartProps) {
  const data = acceptanceRates.map((chain) => ({
    name: `Chain ${chain.chainIndex + 1}`,
    rate: parseFloat((chain.rate * 100).toFixed(1)),
    temp: temperatures[chain.chainIndex] || '?',
  }))

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Acceptance Rates</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" fontSize={12} />
          <YAxis
            domain={[0, 100]}
            label={{ value: 'Acceptance Rate (%)', angle: -90, position: 'insideLeft' }}
            fontSize={12}
          />
          <Tooltip
            contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
            formatter={(value: number) => [`${value.toFixed(1)}%`, 'Acceptance Rate']}
          />
          <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
