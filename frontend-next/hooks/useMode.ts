'use client';
import { useAppStore } from '@/store/appStore';
import type { AppMode } from '@/lib/types';

export function useMode() {
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const resetLiveState = useAppStore((s) => s.resetLiveState);

  function switchMode(m: AppMode) {
    resetLiveState();
    setMode(m);
  }

  return { mode, switchMode, isTest: mode === 'test', isReal: mode === 'real' };
}
