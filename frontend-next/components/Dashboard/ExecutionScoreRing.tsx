'use client';
import { useAppStore } from '@/store/appStore';
import ScoreRing from '@/components/UI/ScoreRing';

function scoreLabel(pct: number) {
  if (pct >= 80) return 'Excellent';
  if (pct >= 60) return 'Good';
  if (pct >= 40) return 'Fair';
  if (pct >= 20) return 'Poor';
  return 'Critical';
}

interface StatRow { label: string; value: number; color: string; }

export default function ExecutionScoreRing() {
  const score = useAppStore((s) => s.score);
  const pct   = score ? Math.round(score.score * 100) : 0;

  const stats: StatRow[] = score
    ? [
        { label: 'Owners',    value: score.tasks_with_owner,    color: '#6ee7b7' },
        { label: 'Deadlines', value: score.tasks_with_deadline, color: '#c4b5fd' },
        { label: 'Vague',     value: score.vague_count,         color: '#fcd34d' },
        { label: 'Blockers',  value: score.blocker_count,       color: '#fca5a5' },
      ]
    : [];

  return (
    <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5 text-center">
      <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-4">
        Execution Score
      </p>

      <div className="flex justify-center mb-4">
        <ScoreRing
          value={score ? score.score : 0}
          size={110}
          strokeWidth={9}
          label={score ? scoreLabel(pct) : undefined}
        />
      </div>

      {stats.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl bg-[var(--surface2)] border border-[var(--border)] py-2">
              <p className="text-lg font-black" style={{ color: s.color }}>{s.value}</p>
              <p className="text-[10px] text-[var(--muted)]">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {!score && (
        <p className="text-xs text-[var(--muted)] mt-2">No data yet</p>
      )}
    </div>
  );
}
