'use client';
import { useAppStore } from '@/store/appStore';
import { Chip } from './TaskPanel';
import type { ExtractedRisk } from '@/lib/types';
import EmptyState from '@/components/UI/EmptyState';

const SEV_COLORS: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#10b981',
};

export default function RiskPanel() {
  const risks = useAppStore((s) => s.risks);

  if (risks.length === 0) {
    return <EmptyState icon="🛡️" title="No risks detected" subtitle="Risks and blockers identified during the conversation will appear here." />;
  }

  return (
    <div className="space-y-2.5">
      {risks.map((r, i) => <RiskCard key={i} risk={r} />)}
    </div>
  );
}

function RiskCard({ risk }: { risk: ExtractedRisk }) {
  const sColor = SEV_COLORS[risk.severity] ?? '#64748b';
  return (
    <div className="rounded-xl bg-[var(--surface2)] border border-[var(--border)] p-3.5 fade-up hover:border-orange-500/30 transition-colors"
      style={{ borderLeftColor: sColor, borderLeftWidth: 3 }}>
      <p className="text-sm text-[var(--text)] leading-snug mb-2.5">{risk.description}</p>
      {risk.mitigation && (
        <div className="text-xs text-[var(--muted)] mb-2 pl-3 border-l-2 border-green-500/40">
          <span className="text-green-400 font-semibold">Mitigation:</span> {risk.mitigation}
        </div>
      )}
      <div className="flex items-center flex-wrap gap-1.5">
        <Chip color={risk.severity === 'critical' ? 'red' : risk.severity === 'high' ? 'orange' : 'yellow'}>
          {risk.severity.toUpperCase()}
        </Chip>
        {risk.is_blocker && <Chip color="red">🚫 BLOCKER</Chip>}
        <span className="text-[10px] font-mono text-orange-400 ml-auto">
          {Math.round(risk.confidence * 100)}%
        </span>
      </div>
    </div>
  );
}
