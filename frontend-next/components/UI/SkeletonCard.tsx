export default function SkeletonCard({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-4 space-y-3 ${className}`}>
      <div className="h-4 w-2/3 rounded-lg shimmer" />
      {Array.from({ length: lines - 1 }, (_, i) => (
        <div key={i} className={`h-3 rounded-lg shimmer`} style={{ width: `${60 + Math.random() * 30}%` }} />
      ))}
    </div>
  );
}
