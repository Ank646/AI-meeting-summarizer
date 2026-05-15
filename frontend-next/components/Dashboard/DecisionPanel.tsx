'use client';
import { useAppStore } from '@/store/appStore';
import { Chip } from './TaskPanel';
import type { ExtractedDecision } from '@/lib/types';
import EmptyState from '@/components/UI/EmptyState';

export default function DecisionPanel() {
  const decisions = useAppStore((s) => s.decisions);

  if (decisions.length === 0) {
    return <EmptyState icon="⚖️" title="No decisions yet" subtitle="Firm decisions made during the meeting will appear here." />;
  }

  return (
    <div className="space-y-2.5">
      {decisions.map((d, i) => <DecisionCard key={i} decision={d} />)}
    </div>
  );
}

function DecisionCard({ decision }: { decision: ExtractedDecision }) {
  return (
    <div className="rounded-xl bg-[var(--surface2)] border border-[var(--border)] p-3.5 fade-up hover:border-green-500/30 transition-colors"
      style={{ borderLeftColor: '#10b981', borderLeftWidth: 3 }}>
      <p className="text-sm text-[var(--text)] leading-snug mb-2.5">{decision.description}</p>
      {decision.rationale && (
        <p className="text-xs text-[var(--muted)] italic mb-2 leading-relaxed">"{decision.rationale}"</p>
      )}
      <div className="flex items-center gap-1.5">
        {decision.made_by && <Chip color="green">✓ {decision.made_by}</Chip>}
        <span className="text-[10px] font-mono text-green-400 ml-auto">
          {Math.round(decision.confidence * 100)}%
        </span>
      </div>
    </div>
  );
}
