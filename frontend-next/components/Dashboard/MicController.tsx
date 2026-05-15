'use client';
import { useState, useEffect } from 'react';
import { Mic, Square, Play, StopCircle, Radio } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMicrophone } from '@/hooks/useMicrophone';
import { useMockSimulator } from '@/hooks/useMockSimulator';
import { useMode } from '@/hooks/useMode';
import WaveformVisualizer from '@/components/UI/WaveformVisualizer';

export default function MicController() {
  const meetingId        = useAppStore((s) => s.meetingId);
  const setMeetingId     = useAppStore((s) => s.setMeetingId);
  const resetLiveState   = useAppStore((s) => s.resetLiveState);
  const connectionStatus = useAppStore((s) => s.connectionStatus);
  const { mode }         = useMode();

  const { connect, disconnect }               = useWebSocket(meetingId);
  const { startMic, stopMic }                 = useMicrophone(meetingId);
  const { startSimulation, stopSimulation }   = useMockSimulator(meetingId);

  const [elapsed, setElapsed] = useState(0);

  const isActive    = connectionStatus === 'recording' || connectionStatus === 'connected';
  const isRecording = connectionStatus === 'recording';

  // Timer
  useEffect(() => {
    if (!isActive) { setElapsed(0); return; }
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [isActive]);

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  function handleStart() {
    if (!meetingId && mode === 'real') return;
    if (mode === 'test') startSimulation();
    else connect();
  }

  function handleStop() {
    if (mode === 'test') stopSimulation();
    else { stopMic(); disconnect(); }
    resetLiveState();
  }

  return (
    <div className="flex items-center gap-4 px-5 py-4 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0">

      {/* Waveform or idle indicator */}
      <div className="flex-shrink-0">
        {isRecording ? (
          <WaveformVisualizer active barCount={20} height={32} color="#9d5cf5" />
        ) : (
          <div className="flex gap-0.5 items-center h-8">
            {Array.from({ length: 20 }, (_, i) => (
              <div key={i} className="w-[3px] rounded-full bg-[var(--border2)]" style={{ height: `${6 + (i % 4) * 4}px` }} />
            ))}
          </div>
        )}
      </div>

      {/* Timer */}
      <div className="font-mono text-sm font-bold min-w-[48px]"
        style={{ color: isRecording ? '#f87171' : 'var(--muted)' }}>
        {fmt(elapsed)}
      </div>

      {/* Meeting ID (real mode only) */}
      {mode === 'real' && (
        <input
          type="text"
          value={meetingId}
          onChange={(e) => setMeetingId(e.target.value)}
          placeholder="Meeting UUID…"
          className="flex-1 max-w-xs px-3 py-2 text-xs bg-[var(--surface2)] border border-[var(--border)] rounded-xl text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--violet)] transition-colors"
        />
      )}

      {/* Demo label */}
      {mode === 'test' && (
        <div className="flex-1 flex items-center gap-2">
          <Radio size={13} className="text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-400">
            {isActive ? 'Simulating live meeting…' : 'Demo mode — no backend needed'}
          </span>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-2 ml-auto">
        {!isActive ? (
          <button
            onClick={handleStart}
            disabled={mode === 'real' && !meetingId}
            className="flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl text-white transition-all duration-200 disabled:opacity-40"
            style={{ background: mode === 'test' ? 'linear-gradient(135deg,#059669,#0d9488)' : 'linear-gradient(135deg,#7c3aed,#4f46e5)' }}
          >
            <Play size={13} strokeWidth={2.5} />
            {mode === 'test' ? 'Start Demo' : 'Connect Live'}
          </button>
        ) : (
          <>
            {mode === 'real' && !isRecording && (
              <button onClick={startMic}
                className="flex items-center gap-2 px-3 py-2 text-xs font-bold rounded-xl bg-[var(--surface2)] border border-[var(--border)] text-[var(--text2)] hover:border-[var(--violet)] transition-colors">
                <Mic size={12} /> Mic
              </button>
            )}
            {mode === 'real' && isRecording && (
              <button onClick={stopMic}
                className="flex items-center gap-2 px-3 py-2 text-xs font-bold rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors">
                <Square size={12} /> Stop Mic
              </button>
            )}
            <button onClick={handleStop}
              className="flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors">
              <StopCircle size={13} />
              End Session
            </button>
          </>
        )}
      </div>
    </div>
  );
}
