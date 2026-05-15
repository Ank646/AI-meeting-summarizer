'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Video, Clock, Users, TrendingUp, Plus, Calendar, ChevronRight } from 'lucide-react';
import { listMeetings } from '@/lib/api';
import { MOCK_MEETINGS } from '@/lib/mockData';
import { useMode } from '@/hooks/useMode';
import { useAppStore } from '@/store/appStore';
import type { Meeting } from '@/lib/types';
import ScoreRing from '@/components/UI/ScoreRing';

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  completed:  { label: 'Completed',  color: '#6ee7b7', bg: 'rgba(16,185,129,0.12)' },
  recording:  { label: '● Recording', color: '#fca5a5', bg: 'rgba(239,68,68,0.12)' },
  processing: { label: 'Processing', color: '#fcd34d', bg: 'rgba(245,158,11,0.12)' },
  scheduled:  { label: 'Scheduled',  color: '#93c5fd', bg: 'rgba(59,130,246,0.12)' },
  failed:     { label: 'Failed',     color: '#94a3b8', bg: 'rgba(100,116,139,0.10)' },
};

function fmt(secs?: number) {
  if (!secs) return '—';
  const m = Math.floor(secs / 60), h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

export default function MeetingsPage() {
  const { mode }      = useMode();
  const setMeetingId  = useAppStore((s) => s.setMeetingId);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');

  useEffect(() => {
    async function load() {
      setLoading(true); setError('');
      try {
        setMeetings(mode === 'test' ? MOCK_MEETINGS : await listMeetings());
      } catch (e) { setError((e as Error).message); }
      finally { setLoading(false); }
    }
    load();
  }, [mode]);

  return (
    <div className="h-full overflow-y-auto">
      {/* Page header */}
      <div className="sticky top-0 z-10 px-8 py-6 flex items-center justify-between border-b border-[var(--border)] glass">
        <div>
          <h1 className="text-xl font-black text-[var(--text)]">Meetings</h1>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            {loading ? 'Loading…' : `${meetings.length} meetings`}
          </p>
        </div>
        <Link href="/dashboard"
          className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-white rounded-xl transition-all hover:opacity-85"
          style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)' }}>
          <Plus size={13} /> New Session
        </Link>
      </div>

      <div className="px-8 py-6">
        {error && (
          <div className="mb-5 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 gap-4">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-32 rounded-2xl shimmer" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {meetings.map((m, i) => {
              const s = STATUS_CONFIG[m.status] ?? STATUS_CONFIG.failed;
              return (
                <div key={m.id}
                  className="group rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5 hover:border-[var(--border2)] transition-all duration-200 fade-up"
                  style={{ animationDelay: `${i * 60}ms` }}>

                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: 'linear-gradient(135deg,rgba(124,58,237,0.2),rgba(79,70,229,0.15))', border: '1px solid rgba(124,58,237,0.2)' }}>
                      <Video size={18} className="text-[var(--violet-l)]" />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div>
                          <p className="text-sm font-bold text-[var(--text)] mb-0.5">{m.title}</p>
                          <p className="text-[10px] font-mono text-[var(--muted)]">{m.id.slice(0, 16)}…</p>
                        </div>
                        <span className="text-[10px] font-bold px-2.5 py-1 rounded-full flex-shrink-0"
                          style={{ background: s.bg, color: s.color }}>
                          {s.label}
                        </span>
                      </div>

                      {/* Meta */}
                      <div className="flex flex-wrap items-center gap-4">
                        <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                          <Clock size={11} /> {fmt(m.duration_seconds)}
                        </span>
                        {m.participant_count && (
                          <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                            <Users size={11} /> {m.participant_count}
                          </span>
                        )}
                        <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                          <Calendar size={11} /> {new Date(m.created_at).toLocaleDateString()}
                        </span>
                        {m.score !== undefined && (
                          <span className="flex items-center gap-1.5 text-[11px]" style={{ color: '#6ee7b7' }}>
                            <TrendingUp size={11} /> {Math.round(m.score * 100)}% score
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Score ring */}
                    {m.score !== undefined && (
                      <div className="flex-shrink-0">
                        <ScoreRing value={m.score} size={60} strokeWidth={6} />
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-4 mt-4 pt-4 border-t border-[var(--border)]">
                    <Link href={`/meetings/${m.id}`}
                      className="flex items-center gap-1 text-xs font-semibold text-[var(--violet-l)] hover:text-white transition-colors">
                      View Details <ChevronRight size={12} />
                    </Link>
                    <button onClick={() => setMeetingId(m.id)}
                      className="text-xs font-semibold text-[var(--muted)] hover:text-[var(--text2)] transition-colors">
                      Load in Dashboard →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
