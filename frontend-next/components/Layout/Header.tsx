'use client';
import { Zap } from 'lucide-react';
import ModeToggle from './ModeToggle';
import { useAppStore } from '@/store/appStore';
import { useMode } from '@/hooks/useMode';
import type { ConnectionStatus } from '@/lib/types';

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  disconnected: 'Disconnected',
  connecting:   'Connecting…',
  connected:    'Connected',
  recording:    '● Recording',
};

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  disconnected: 'text-[var(--muted)]',
  connecting:   'text-yellow-400',
  connected:    'text-[var(--green)]',
  recording:    'text-red-400',
};

export default function Header() {
  const connectionStatus = useAppStore((s) => s.connectionStatus);
  const { mode } = useMode();

  return (
    <header className="flex items-center justify-between px-6 py-3 bg-[var(--surface)] border-b border-[var(--border)] flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-[var(--accent)]" />
        <span className="text-sm font-bold tracking-wide">
          <span className="text-[var(--accent)]">AI</span>{' '}
          <span className="text-[var(--text)]">Execution Intelligence</span>
        </span>
      </div>

      {/* Status + mode badge */}
      <div className="flex items-center gap-4">
        {/* Status */}
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connectionStatus === 'recording'
                ? 'bg-red-400 status-pulse'
                : connectionStatus === 'connected'
                ? 'bg-[var(--green)] status-pulse'
                : 'bg-[var(--muted)]'
            }`}
          />
          <span className={`text-xs font-medium ${STATUS_COLORS[connectionStatus]}`}>
            {STATUS_LABELS[connectionStatus]}
          </span>
        </div>

        {/* Mode badge */}
        {mode === 'test' && (
          <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-900/50 text-emerald-400 border border-emerald-700">
            TEST MODE
          </span>
        )}

        <ModeToggle />
      </div>
    </header>
  );
}
