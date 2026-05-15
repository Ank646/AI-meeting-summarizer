'use client';
import { useAppStore } from '@/store/appStore';

const TOPIC_COLORS = [
  'bg-violet-500/15 text-violet-300 border-violet-500/25',
  'bg-cyan-500/15   text-cyan-300   border-cyan-500/25',
  'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
  'bg-pink-500/15   text-pink-300   border-pink-500/25',
  'bg-teal-500/15   text-teal-300   border-teal-500/25',
];

export default function TopicCloud() {
  const topics = useAppStore((s) => s.topics);
  const list   = Array.from(topics);

  return (
    <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5">
      <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-3">
        Topics · {list.length}
      </p>
      {list.length === 0 ? (
        <p className="text-xs text-[var(--muted)]">Topics detected from conversation will appear here.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {list.map((t, i) => (
            <span key={t}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border fade-up ${TOPIC_COLORS[i % TOPIC_COLORS.length]}`}>
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
