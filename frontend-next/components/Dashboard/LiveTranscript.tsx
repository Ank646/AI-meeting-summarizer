'use client';
import { useEffect, useRef } from 'react';
import { useAppStore } from '@/store/appStore';
import EmptyState from '@/components/UI/EmptyState';

const PALETTES: Record<string, { bg: string; text: string; border: string; initials: string }> = {};
const COLORS = [
  { bg: 'rgba(124,58,237,0.15)', text: '#c4b5fd', border: 'rgba(124,58,237,0.35)' },
  { bg: 'rgba(6,182,212,0.15)',  text: '#67e8f9', border: 'rgba(6,182,212,0.35)'  },
  { bg: 'rgba(16,185,129,0.15)', text: '#6ee7b7', border: 'rgba(16,185,129,0.35)' },
  { bg: 'rgba(245,158,11,0.15)', text: '#fcd34d', border: 'rgba(245,158,11,0.35)' },
  { bg: 'rgba(236,72,153,0.15)', text: '#f9a8d4', border: 'rgba(236,72,153,0.35)' },
  { bg: 'rgba(59,130,246,0.15)', text: '#93c5fd', border: 'rgba(59,130,246,0.35)' },
];
let ci = 0;

function getPalette(speaker: string) {
  if (!PALETTES[speaker]) {
    PALETTES[speaker] = { ...COLORS[ci % COLORS.length], initials: speaker.replace('SPEAKER_', 'S').slice(0, 2).toUpperCase() };
    ci++;
  }
  return PALETTES[speaker];
}

export default function LiveTranscript() {
  const utterances = useAppStore((s) => s.utterances);
  const bottomRef  = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [utterances.length]);

  if (utterances.length === 0) {
    return (
      <EmptyState
        icon="🎙️"
        title="Waiting for audio…"
        subtitle="Start a Demo session or connect Live to see real-time transcription with speaker diarization."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-5">
      {utterances.map((u, i) => {
        const p = getPalette(u.speaker ?? 'UNKNOWN');
        const fmt = (s: number) => `${Math.floor(s / 60)}:${(Math.floor(s % 60)).toString().padStart(2, '0')}`;
        return (
          <div key={i} className="flex gap-3 fade-up">
            <div className="flex flex-col items-center gap-1 flex-shrink-0">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center text-[11px] font-black"
                style={{ background: p.bg, color: p.text, border: `1.5px solid ${p.border}` }}>
                {p.initials}
              </div>
              {i < utterances.length - 1 && (
                <div className="w-px h-4 opacity-30" style={{ background: p.text }} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[11px] font-bold tracking-wider uppercase" style={{ color: p.text }}>
                  {(u.speaker ?? 'UNKNOWN').replace('SPEAKER_', 'Speaker ')}
                </span>
                {u.start !== undefined && (
                  <span className="text-[10px] text-[var(--muted)] font-mono bg-[var(--surface3)] px-1.5 py-0.5 rounded-md">
                    {fmt(u.start)}
                  </span>
                )}
              </div>
              <div className="text-sm text-[var(--text2)] leading-relaxed px-3 py-2.5 rounded-xl rounded-tl-sm"
                style={{ background: p.bg, border: `1px solid ${p.border}44` }}>
                {u.text}
              </div>
            </div>
          </div>
        );
      })}

      {/* Typing dots */}
      <div className="flex gap-3 items-center fade-in">
        <div className="w-8 h-8 rounded-xl shimmer flex-shrink-0" />
        <div className="flex gap-1.5 px-3 py-2.5 rounded-xl bg-[var(--surface3)] border border-[var(--border)]">
          {[0, 1, 2].map((i) => (
            <span key={i} className="w-1.5 h-1.5 rounded-full bg-[var(--violet-l)]"
              style={{ animation: 'bounce-dot 1.2s ease-in-out infinite', animationDelay: `${i * 0.2}s` }} />
          ))}
        </div>
      </div>
      <div ref={bottomRef} />
    </div>
  );
}
