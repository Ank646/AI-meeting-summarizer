'use client';
import { useAppStore } from '@/store/appStore';
import { Terminal } from 'lucide-react';

export default function EventLog() {
  const eventLog = useAppStore((s) => s.eventLog);
  const clearLog = useAppStore((s) => s.clearLog);

  return (
    <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <Terminal size={12} className="text-[var(--muted)]" />
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Event Log</p>
        </div>
        <button onClick={clearLog}
          className="text-[10px] text-[var(--muted)] hover:text-[var(--text)] transition-colors">
          clear
        </button>
      </div>
      <div className="space-y-0.5 max-h-36 overflow-y-auto font-mono">
        {eventLog.length === 0 ? (
          <p className="text-[10px] text-[var(--muted)]">No events yet…</p>
        ) : (
          eventLog.map((e, i) => (
            <div key={i} className="flex gap-2 text-[10px] leading-relaxed">
              <span className="text-[var(--muted2)] flex-shrink-0">{e.ts}</span>
              <span className="text-[var(--text2)] break-all">{e.msg}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
