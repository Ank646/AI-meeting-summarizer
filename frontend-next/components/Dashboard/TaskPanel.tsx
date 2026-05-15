'use client';
import { useAppStore } from '@/store/appStore';
import type { ExtractedTask } from '@/lib/types';
import EmptyState from '@/components/UI/EmptyState';

export default function TaskPanel() {
  const tasks = useAppStore((s) => s.tasks);

  if (tasks.length === 0) {
    return <EmptyState icon="✅" title="No tasks yet" subtitle="Tasks will appear here as they are detected from the conversation." />;
  }

  return (
    <div className="space-y-2.5">
      {tasks.map((t, i) => <TaskCard key={i} task={t} />)}
    </div>
  );
}

function TaskCard({ task }: { task: ExtractedTask }) {
  const conf  = Math.round(task.confidence * 100);
  const isHigh = conf >= 85;

  return (
    <div className="rounded-xl bg-[var(--surface2)] border border-[var(--border)] p-3.5 fade-up hover:border-blue-500/30 transition-colors"
      style={{ borderLeftColor: '#3b82f6', borderLeftWidth: 3 }}>
      <p className="text-sm text-[var(--text)] leading-snug mb-2.5">{task.description}</p>
      <div className="flex flex-wrap gap-1.5 items-center">
        {task.assignee && <Chip color="blue">👤 {task.assignee}</Chip>}
        {task.deadline_raw && <Chip color="violet">📅 {task.deadline_raw}</Chip>}
        {task.is_vague && <Chip color="yellow">⚠ Vague</Chip>}
        <span className={`text-[10px] font-mono ml-auto ${isHigh ? 'text-green-400' : 'text-yellow-400'}`}>
          {conf}%
        </span>
      </div>
    </div>
  );
}

const CHIP_STYLES: Record<string, string> = {
  blue:   'bg-blue-500/10   text-blue-300   border-blue-500/20',
  violet: 'bg-violet-500/10 text-violet-300 border-violet-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20',
  red:    'bg-red-500/10    text-red-300    border-red-500/20',
  green:  'bg-green-500/10  text-green-300  border-green-500/20',
  orange: 'bg-orange-500/10 text-orange-300 border-orange-500/20',
};

export function Chip({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${CHIP_STYLES[color] ?? ''}`}>
      {children}
    </span>
  );
}
