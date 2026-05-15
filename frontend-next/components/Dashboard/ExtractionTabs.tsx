'use client';
import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import TaskPanel from './TaskPanel';
import DecisionPanel from './DecisionPanel';
import RiskPanel from './RiskPanel';
import clsx from 'clsx';

type Tab = 'tasks' | 'decisions' | 'risks';

const TABS: { id: Tab; label: string; color: string }[] = [
  { id: 'tasks',     label: 'Tasks',     color: '#3b82f6' },
  { id: 'decisions', label: 'Decisions', color: '#10b981' },
  { id: 'risks',     label: 'Risks',     color: '#f97316' },
];

export default function ExtractionTabs() {
  const [active, setActive] = useState<Tab>('tasks');
  const counts = {
    tasks:     useAppStore((s) => s.tasks.length),
    decisions: useAppStore((s) => s.decisions.length),
    risks:     useAppStore((s) => s.risks.length),
  };

  return (
    <div className="flex flex-col border-t border-[var(--border)] bg-[var(--surface)]" style={{ maxHeight: '44%' }}>
      {/* Tabs */}
      <div className="flex gap-0 border-b border-[var(--border)] flex-shrink-0">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setActive(t.id)}
            className={clsx(
              'flex items-center gap-2 px-5 py-3 text-xs font-semibold border-b-2 transition-all duration-200',
              active === t.id
                ? 'border-b-[var(--violet)] text-[var(--text)] bg-[var(--surface2)]'
                : 'border-transparent text-[var(--muted)] hover:text-[var(--text2)]',
            )}
            style={active === t.id ? { borderBottomColor: t.color } : {}}
          >
            {t.label}
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
              style={{
                background: counts[t.id] > 0 ? `${t.color}22` : 'var(--surface3)',
                color: counts[t.id] > 0 ? t.color : 'var(--muted)',
              }}>
              {counts[t.id]}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="overflow-y-auto flex-1 p-4">
        {active === 'tasks'     && <TaskPanel />}
        {active === 'decisions' && <DecisionPanel />}
        {active === 'risks'     && <RiskPanel />}
      </div>
    </div>
  );
}
