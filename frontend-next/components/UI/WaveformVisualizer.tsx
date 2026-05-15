'use client';
import { useEffect, useRef, useState } from 'react';

interface Props {
  active: boolean;
  barCount?: number;
  color?: string;
  height?: number;
}

export default function WaveformVisualizer({
  active,
  barCount = 28,
  color = '#9d5cf5',
  height = 40,
}: Props) {
  const [levels, setLevels] = useState<number[]>(Array(barCount).fill(0.15));
  const frameRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!active) {
      setLevels(Array(barCount).fill(0.15));
      return;
    }

    function tick() {
      setLevels((prev) =>
        prev.map((v, i) => {
          const target = 0.1 + Math.random() * 0.9;
          const smoothed = v + (target - v) * 0.35;
          return smoothed;
        }),
      );
      frameRef.current = setTimeout(tick, 80);
    }

    tick();
    return () => {
      if (frameRef.current) clearTimeout(frameRef.current);
    };
  }, [active, barCount]);

  return (
    <div
      className="flex items-center gap-[3px]"
      style={{ height: `${height}px` }}
    >
      {levels.map((level, i) => (
        <div
          key={i}
          className="rounded-full transition-all duration-75"
          style={{
            width: '3px',
            height: `${Math.max(3, level * height)}px`,
            background: active
              ? `linear-gradient(to top, ${color}, ${color}88)`
              : `${color}33`,
            opacity: active ? 0.7 + level * 0.3 : 0.3,
          }}
        />
      ))}
    </div>
  );
}
