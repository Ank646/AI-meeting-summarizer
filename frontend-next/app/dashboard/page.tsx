'use client';
import MicController      from '@/components/Dashboard/MicController';
import LiveTranscript     from '@/components/Dashboard/LiveTranscript';
import ExtractionTabs     from '@/components/Dashboard/ExtractionTabs';
import ExecutionScoreRing from '@/components/Dashboard/ExecutionScoreRing';
import TopicCloud         from '@/components/Dashboard/TopicCloud';
import EventLog           from '@/components/Dashboard/EventLog';
import { useAppStore }    from '@/store/appStore';
import { useMode }        from '@/hooks/useMode';
import { Trash2, Sparkles } from 'lucide-react';

export default function DashboardPage() {
  const clearTranscript  = useAppStore((s) => s.clearTranscript);
  const clearExtractions = useAppStore((s) => s.clearExtractions);
  const utterances       = useAppStore((s) => s.utterances);
  const { mode }         = useMode();

  return (
    <div className="flex h-full overflow-hidden">

      {/* ── Left: Transcript + Extractions ──────────────────────── */}
      <div className="flex flex-col flex-1 overflow-hidden border-r border-[var(--border)]">

        {/* Controls bar */}
        <MicController />

        {/* Transcript header */}
        <div className="flex items-center justify-between px-5 py-2.5 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={13} className="text-[var(--violet-l)]" />
            <span className="text-xs font-semibold text-[var(--text2)]">Live Transcript</span>
            {utterances.length > 0 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
                {utterances.length}
              </span>
            )}
          </div>
          <button onClick={() => { clearTranscript(); clearExtractions(); }}
            className="flex items-center gap-1 text-[10px] text-[var(--muted)] hover:text-[var(--text2)] transition-colors">
            <Trash2 size={11} /> Clear
          </button>
        </div>

        {/* Scrollable transcript */}
        <div className="flex-1 overflow-y-auto">
          <LiveTranscript />
        </div>

        {/* Extraction tabs */}
        <ExtractionTabs />
      </div>

      {/* ── Right: Score + Topics + Log ─────────────────────────── */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 overflow-y-auto p-4 bg-[var(--surface)]">

        {/* Mode banner */}
        {mode === 'test' && (
          <div className="rounded-2xl p-4 text-center fade-up"
            style={{ background: 'linear-gradient(135deg,rgba(5,150,105,0.15),rgba(13,148,136,0.12))', border: '1px solid rgba(16,185,129,0.2)' }}>
            <div className="text-2xl mb-2">🧪</div>
            <p className="text-xs font-bold text-emerald-300">Demo Mode Active</p>
            <p className="text-[10px] text-[var(--muted)] mt-1 leading-relaxed">
              Mock data simulates a live Q3 strategy meeting. Click <strong className="text-emerald-400">Start Demo</strong> above.
            </p>
          </div>
        )}

        <ExecutionScoreRing />
        <TopicCloud />
        <EventLog />
      </aside>
    </div>
  );
}
