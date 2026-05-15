'use client';
import { useEffect, useState } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Area, AreaChart,
} from 'recharts';
import { getOrgScore, getScoreTrend } from '@/lib/api';
import { MOCK_ORG_SCORE, MOCK_SCORE_TREND } from '@/lib/mockData';
import { useMode } from '@/hooks/useMode';
import type { OrgScore, ScoreTrend } from '@/lib/types';
import ScoreRing from '@/components/UI/ScoreRing';

const TOOLTIP_STYLE = {
  contentStyle: { background: '#0f1220', border: '1px solid #1e2540', borderRadius: 12, fontSize: 11 },
  labelStyle: { color: '#64748b' },
};

export default function AnalyticsPage() {
  const { mode }                    = useMode();
  const [orgScore, setOrgScore]     = useState<OrgScore | null>(null);
  const [trend, setTrend]           = useState<ScoreTrend[]>([]);
  const [loading, setLoading]       = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        if (mode === 'test') { setOrgScore(MOCK_ORG_SCORE); setTrend(MOCK_SCORE_TREND); }
        else {
          const [score, t] = await Promise.all([getOrgScore(), getScoreTrend()]);
          setOrgScore(score); setTrend(t);
        }
      } finally { setLoading(false); }
    }
    load();
  }, [mode]);

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 px-8 py-5 glass border-b border-[var(--border)]">
        <h1 className="text-xl font-black text-[var(--text)]">Analytics</h1>
        <p className="text-xs text-[var(--muted)] mt-0.5">Organization-wide execution intelligence</p>
      </div>

      <div className="px-8 py-6 space-y-6">

        {loading ? (
          <div className="grid grid-cols-5 gap-3">
            {[1, 2, 3, 4, 5].map((n) => <div key={n} className="h-24 rounded-2xl shimmer" />)}
          </div>
        ) : orgScore && (
          <>
            {/* KPI row with score ring */}
            <div className="flex gap-5 items-start">
              <div className="flex-shrink-0 rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6 text-center"
                style={{ background: 'linear-gradient(135deg,rgba(124,58,237,0.1),rgba(79,70,229,0.08))' }}>
                <ScoreRing value={orgScore.avg_score} size={100} strokeWidth={9} label="Avg Score" />
              </div>

              <div className="flex-1 grid grid-cols-2 gap-3">
                <KpiCard label="Meetings Analyzed" value={orgScore.meetings_analyzed} color="#93c5fd" icon="📊" />
                <KpiCard label="Total Tasks"        value={orgScore.total_tasks}       color="#c4b5fd" icon="✅" />
                <KpiCard label="Open Tasks"         value={orgScore.open_tasks}        color="#fcd34d" icon="⏳" />
                <KpiCard label="Active Blockers"    value={orgScore.blocker_count}     color="#fca5a5" icon="🚫" />
              </div>
            </div>

            {/* Score trend */}
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5">
              <p className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
                Execution Score — 30 Day Trend
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={trend}>
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#7c3aed" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#7c3aed" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1e2540" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                  <Tooltip {...TOOLTIP_STYLE}
                    formatter={(v: number) => [`${Math.round(v * 100)}%`, 'Score']} />
                  <Area type="monotone" dataKey="score" stroke="#9d5cf5" strokeWidth={2}
                    fill="url(#scoreGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Meetings per day */}
            <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5">
              <p className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
                Meetings per Day
              </p>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={trend}>
                  <CartesianGrid stroke="#1e2540" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Bar dataKey="meetings" radius={[4, 4, 0, 0]}
                    fill="url(#barGrad)">
                    <defs>
                      <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#4f46e5" />
                        <stop offset="100%" stopColor="#7c3aed" />
                      </linearGradient>
                    </defs>
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function KpiCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: string }) {
  return (
    <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-4 fade-up">
      <div className="flex items-start justify-between mb-2">
        <span className="text-xl">{icon}</span>
        <p className="text-2xl font-black" style={{ color }}>{value}</p>
      </div>
      <p className="text-[11px] font-semibold text-[var(--muted)]">{label}</p>
    </div>
  );
}
