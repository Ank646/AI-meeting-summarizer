'use client';
import { useEffect, useState } from 'react';

interface Props {
  value: number;   // 0–1
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
}

function scoreColor(pct: number) {
  if (pct >= 75) return ['#10b981', '#34d399'];
  if (pct >= 50) return ['#f59e0b', '#fbbf24'];
  if (pct >= 25) return ['#f97316', '#fb923c'];
  return ['#ef4444', '#f87171'];
}

function scoreLabel(pct: number) {
  if (pct >= 80) return 'Excellent';
  if (pct >= 60) return 'Good';
  if (pct >= 40) return 'Fair';
  if (pct >= 20) return 'Poor';
  return 'Critical';
}

export default function ScoreRing({ value, size = 120, strokeWidth = 10, label, sublabel }: Props) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setDisplayed(value), 100);
    return () => clearTimeout(t);
  }, [value]);

  const pct       = Math.round(displayed * 100);
  const r         = (size - strokeWidth) / 2;
  const circ      = 2 * Math.PI * r;
  const offset    = circ - (circ * displayed);
  const [c1, c2]  = scoreColor(pct);
  const center    = size / 2;
  const gradId    = `ring-grad-${size}`;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          <defs>
            <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={c1} />
              <stop offset="100%" stopColor={c2} />
            </linearGradient>
          </defs>
          {/* Track */}
          <circle cx={center} cy={center} r={r}
            fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={strokeWidth} />
          {/* Progress */}
          <circle cx={center} cy={center} r={r}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{
              transform: 'rotate(-90deg)',
              transformOrigin: 'center',
              transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)',
            }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-black text-[var(--text)]" style={{ fontSize: size * 0.22, color: c1 }}>
            {pct}
          </span>
          <span className="text-[var(--muted)]" style={{ fontSize: size * 0.1 }}>score</span>
        </div>
      </div>
      {label && <p className="text-xs font-bold" style={{ color: c1 }}>{label || scoreLabel(pct)}</p>}
      {sublabel && <p className="text-[10px] text-[var(--muted)]">{sublabel}</p>}
    </div>
  );
}
