'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Clock, Users, Calendar } from 'lucide-react';
import { getMeeting } from '@/lib/api';
import { MOCK_MEETINGS, MOCK_TASKS, MOCK_DECISIONS, MOCK_RISKS } from '@/lib/mockData';
import { useMode } from '@/hooks/useMode';
import type { Meeting } from '@/lib/types';
import ScoreRing from '@/components/UI/ScoreRing';
import { Chip } from '@/components/Dashboard/TaskPanel';

export default function MeetingDetailPage() {
  const { id }  = useParams<{ id: string }>();
  const { mode } = useMode();
  const [meeting, setMeeting] = useState<Meeting | null>(null);

  useEffect(() => {
    if (!id) return;
    if (mode === 'test') {
      setMeeting(MOCK_MEETINGS.find((x) => x.id === id) ?? null);
    } else {
      getMeeting(id).then(setMeeting).catch(console.error);
    }
  }, [id, mode]);

  if (!meeting) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-8 w-64 rounded-xl shimmer" />
        <div className="h-40 rounded-2xl shimmer" />
      </div>
    );
  }

  const tasks     = mode === 'test' ? MOCK_TASKS.slice(0, 4)     : [];
  const decisions = mode === 'test' ? MOCK_DECISIONS             : [];
  const risks     = mode === 'test' ? MOCK_RISKS.slice(0, 2)     : [];

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 px-8 py-5 glass border-b border-[var(--border)]">
        <Link href="/meetings" className="flex items-center gap-1.5 text-xs text-[var(--muted)] hover:text-[var(--text2)] mb-3 transition-colors">
          <ArrowLeft size={13} /> Back to Meetings
        </Link>
        <div className="flex items-start gap-4">
          <div className="flex-1">
            <h1 className="text-xl font-black text-[var(--text)]">{meeting.title}</h1>
            <div className="flex items-center gap-4 mt-2">
              <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                <Calendar size={11} /> {new Date(meeting.created_at).toLocaleString()}
              </span>
              {meeting.participant_count && (
                <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                  <Users size={11} /> {meeting.participant_count} participants
                </span>
              )}
              {meeting.duration_seconds && (
                <span className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
                  <Clock size={11} /> {Math.floor(meeting.duration_seconds / 60)}m
                </span>
              )}
            </div>
          </div>
          {meeting.score !== undefined && (
            <ScoreRing value={meeting.score} size={80} strokeWidth={8} />
          )}
        </div>
      </div>

      <div className="px-8 py-6 space-y-6">
        {/* Tasks */}
        <Section title="Action Items" count={tasks.length} color="#3b82f6">
          {tasks.map((t, i) => (
            <div key={i} className="rounded-xl bg-[var(--surface)] border border-[var(--border)] p-4 fade-up"
              style={{ borderLeftColor: '#3b82f6', borderLeftWidth: 3 }}>
              <p className="text-sm text-[var(--text)] mb-2">{t.description}</p>
              <div className="flex gap-1.5 flex-wrap">
                {t.assignee && <Chip color="blue">👤 {t.assignee}</Chip>}
                {t.deadline_raw && <Chip color="violet">📅 {t.deadline_raw}</Chip>}
              </div>
            </div>
          ))}
        </Section>

        {/* Decisions */}
        <Section title="Decisions Made" count={decisions.length} color="#10b981">
          {decisions.map((d, i) => (
            <div key={i} className="rounded-xl bg-[var(--surface)] border border-[var(--border)] p-4 fade-up"
              style={{ borderLeftColor: '#10b981', borderLeftWidth: 3 }}>
              <p className="text-sm text-[var(--text)] mb-1">{d.description}</p>
              {d.rationale && <p className="text-xs text-[var(--muted)] italic">{d.rationale}</p>}
            </div>
          ))}
        </Section>

        {/* Risks */}
        <Section title="Risks & Blockers" count={risks.length} color="#f97316">
          {risks.map((r, i) => (
            <div key={i} className="rounded-xl bg-[var(--surface)] border border-[var(--border)] p-4 fade-up"
              style={{ borderLeftColor: r.is_blocker ? '#ef4444' : '#f97316', borderLeftWidth: 3 }}>
              <p className="text-sm text-[var(--text)] mb-2">{r.description}</p>
              <div className="flex gap-1.5">
                <Chip color={r.severity === 'critical' ? 'red' : 'orange'}>{r.severity.toUpperCase()}</Chip>
                {r.is_blocker && <Chip color="red">🚫 BLOCKER</Chip>}
              </div>
            </div>
          ))}
        </Section>
      </div>
    </div>
  );
}

function Section({ title, count, color, children }: { title: string; count: number; color: string; children: React.ReactNode }) {
  if (count === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <p className="text-sm font-bold" style={{ color }}>{title}</p>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${color}20`, color }}>
          {count}
        </span>
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}
