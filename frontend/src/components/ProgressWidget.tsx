import { useEffect, useRef, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

interface ProgressData {
  step: number;
  chains: { index: number; temp: number; energy: number }[];
  acceptanceRate: number;
  bestScore: number;
}

interface ProgressWidgetProps {
  runId?: string;
  isRunning: boolean;
}

const COLORS = ['#fff', '#888', '#666', '#444', '#222'];

export default function ProgressWidget({ runId, isRunning }: ProgressWidgetProps) {
  const [data, setData] = useState<ProgressData[]>([]);
  const [acceptanceRate, setAcceptanceRate] = useState(0);
  const [bestScore, setBestScore] = useState<number | null>(null);
  const [ess, setEss] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/api/v1/runs/${runId}/ws`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'progress') {
          setData((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.step === msg.step) return prev;
            const chains = msg.chain_index != null
              ? [{ index: msg.chain_index, temp: msg.temperature || 0, energy: msg.current_energy || 0 }]
              : [];
            return [...prev, { step: msg.step, chains, acceptanceRate: msg.acceptance_rate || 0, bestScore: msg.best_energy || 0 }].slice(-200);
          });
          if (msg.best_energy != null) setBestScore(msg.best_energy);
          if (msg.acceptance_rate != null) setAcceptanceRate(msg.acceptance_rate);
        }
        if (msg.ess != null) setEss(msg.ess);
      } catch {}
    };
    return () => { ws.close(); };
  }, [runId]);

  const chartData = data.map((d) => ({
    step: d.step,
    ...Object.fromEntries(d.chains.map((c) => [`chain_${c.index}`, c.energy])),
  }));

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-2">
        <div className="bg-[#111] rounded-lg p-2 text-center">
          <div className="text-lg font-bold text-white">{bestScore?.toFixed(3) || '-'}</div>
          <div className="text-[9px] text-gray-500">Best Score</div>
        </div>
        <div className="bg-[#111] rounded-lg p-2 text-center">
          <div className="text-lg font-bold text-white">{(acceptanceRate * 100).toFixed(0)}%</div>
          <div className="text-[9px] text-gray-500">Acceptance</div>
        </div>
        <div className="bg-[#111] rounded-lg p-2 text-center">
          <div className="text-lg font-bold text-white">{ess || '-'}</div>
          <div className="text-[9px] text-gray-500">ESS</div>
        </div>
        <div className="bg-[#111] rounded-lg p-2 text-center">
          <div className="flex items-center justify-center space-x-1">
            <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
            <span className="text-[10px] text-gray-400">{isRunning ? 'Running' : 'Idle'}</span>
          </div>
          <div className="text-[9px] text-gray-500">Status</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
          <XAxis dataKey="step" stroke="#444" fontSize={10} />
          <YAxis stroke="#444" fontSize={10} />
          <Tooltip
            contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: '8px', fontSize: 11 }}
            labelStyle={{ color: '#888' }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: '#666' }} />
          {[0, 1, 2, 3, 4].map((i) => (
            <Line key={i} type="monotone" dataKey={`chain_${i}`}
              stroke={COLORS[i]} dot={false} strokeWidth={1.5}
              name={`Chain ${i + 1}`} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
