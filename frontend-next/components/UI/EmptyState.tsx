interface Props {
  icon: string;
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon, title, subtitle, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center fade-in">
      <div className="text-5xl mb-4 float-anim">{icon}</div>
      <p className="text-base font-bold text-[var(--text2)] mb-1">{title}</p>
      <p className="text-sm text-[var(--muted)] max-w-xs leading-relaxed">{subtitle}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
