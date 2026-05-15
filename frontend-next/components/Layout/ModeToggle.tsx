'use client';
import { useMode } from '@/hooks/useMode';

export default function ModeToggle() {
  const { mode, switchMode } = useMode();

  return (
    <div className="flex items-center w-full p-1 rounded-xl bg-[var(--surface3)] border border-[var(--border)]">
      <button
        onClick={() => switchMode('real')}
        className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all duration-200 ${
          mode === 'real'
            ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/20'
            : 'text-[var(--muted)] hover:text-[var(--text2)]'
        }`}
      >
        Live
      </button>
      <button
        onClick={() => switchMode('test')}
        className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all duration-200 ${
          mode === 'test'
            ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-500/20'
            : 'text-[var(--muted)] hover:text-[var(--text2)]'
        }`}
      >
        Demo
      </button>
    </div>
  );
}
