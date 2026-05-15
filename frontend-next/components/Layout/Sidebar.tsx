'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Zap, LayoutDashboard, Video, Search,
  BarChart2, GitBranch, Settings, ChevronRight,
  PanelLeftClose, PanelLeftOpen, Sun, Moon, Star,
} from 'lucide-react';
import clsx from 'clsx';
import ModeToggle from './ModeToggle';
import { useAppStore } from '@/store/appStore';
import { useUIStore } from '@/store/uiStore';

const NAV = [
  { href: '/dashboard', label: 'Live Intelligence', Icon: LayoutDashboard },
  { href: '/meetings',  label: 'Meetings',          Icon: Video            },
  { href: '/search',    label: 'Semantic Search',   Icon: Search           },
  { href: '/analytics', label: 'Analytics',         Icon: BarChart2        },
  { href: '/product',   label: 'Features',          Icon: Star             },
  { href: '/workflow',  label: 'Architecture',      Icon: GitBranch        },
];

export default function Sidebar() {
  const pathname         = usePathname();
  const connectionStatus = useAppStore((s) => s.connectionStatus);
  const tasks            = useAppStore((s) => s.tasks);
  const risks            = useAppStore((s) => s.risks);
  const isLive           = connectionStatus === 'recording' || connectionStatus === 'connected';

  const { sidebarCollapsed: c, toggleSidebar, theme, toggleTheme } = useUIStore();

  return (
    <aside
      className={clsx(
        'relative z-20 flex flex-col flex-shrink-0 glass border-r border-[var(--border)] overflow-hidden',
        'transition-[width] duration-[220ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
        c ? 'w-14' : 'w-60',
      )}
    >

      {/* ── Logo + collapse button ─── */}
      <div className={clsx(
        'flex items-center border-b border-[var(--border)] flex-shrink-0',
        c ? 'flex-col gap-2 px-0 py-4 justify-center' : 'justify-between px-4 py-4',
      )}>
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg,#7c3aed,#06b6d4)' }}
          >
            <Zap size={15} className="text-white" strokeWidth={2.5} />
          </div>
          {!c && (
            <div className="min-w-0">
              <p className="text-sm font-black tracking-tight gradient-text leading-none">Nexus</p>
              <p className="text-[10px] text-[var(--muted)] leading-none mt-0.5">AI Intelligence</p>
            </div>
          )}
        </div>

        <button
          onClick={toggleSidebar}
          title={c ? 'Expand sidebar' : 'Collapse sidebar'}
          className="rounded-lg p-1.5 flex-shrink-0 text-[var(--muted)] hover:text-[var(--text2)] hover:bg-[var(--surface3)] transition-colors"
        >
          {c ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
        </button>
      </div>

      {/* ── Mode toggle (expanded only) ─── */}
      {!c && (
        <div className="px-3 pt-3 pb-1 flex-shrink-0">
          <ModeToggle />
        </div>
      )}

      {/* ── Live indicator ─── */}
      {isLive && (
        <div className={clsx('flex-shrink-0 fade-up', c ? 'flex justify-center py-2' : 'mx-3 my-2')}>
          {c ? (
            <span className="w-2.5 h-2.5 rounded-full bg-red-400 status-pulse" title="Session Active" />
          ) : (
            <div className="px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-400 status-pulse" />
              <span className="text-xs font-semibold text-red-400">Session Active</span>
            </div>
          )}
        </div>
      )}

      {/* ── Nav ─── */}
      <nav className={clsx('flex flex-col gap-0.5 flex-1 overflow-y-auto pt-1', c ? 'px-1.5' : 'px-3')}>
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              title={c ? label : undefined}
              className={clsx(
                'group flex items-center rounded-xl text-sm font-medium transition-all duration-200',
                c ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2.5',
                active
                  ? 'nav-active text-[var(--text)]'
                  : 'text-[var(--muted)] hover:text-[var(--text2)] hover:bg-[var(--surface3)]',
              )}
            >
              <Icon
                size={15}
                className={clsx(
                  'flex-shrink-0 transition-colors',
                  active ? 'text-[var(--violet-l)]' : 'group-hover:text-[var(--text2)]',
                )}
              />
              {!c && (
                <>
                  <span className="flex-1 truncate">{label}</span>
                  {active && (
                    <ChevronRight size={11} className="text-[var(--violet-l)] opacity-60 flex-shrink-0" />
                  )}
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* ── Live stats (expanded only) ─── */}
      {isLive && !c && (tasks.length > 0 || risks.length > 0) && (
        <div className="mx-3 mb-3 p-3 rounded-xl bg-[var(--surface3)] border border-[var(--border)] space-y-2 fade-up flex-shrink-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Live Session</p>
          <div className="flex flex-wrap gap-1.5">
            {tasks.length > 0 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/20">
                {tasks.length} tasks
              </span>
            )}
            {risks.length > 0 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/20">
                {risks.length} risks
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Footer: user + theme + settings ─── */}
      <div
        className={clsx(
          'border-t border-[var(--border)] flex-shrink-0',
          c ? 'p-2 flex flex-col items-center gap-2' : 'px-4 py-3',
        )}
      >
        {c ? (
          /* Collapsed footer — stacked icon buttons */
          <>
            <button
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
              className="w-8 h-8 rounded-xl flex items-center justify-center text-[var(--muted)] hover:text-[var(--text2)] hover:bg-[var(--surface3)] transition-colors"
            >
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
            <button className="w-8 h-8 rounded-xl flex items-center justify-center text-[var(--muted)] hover:text-[var(--text2)] hover:bg-[var(--surface3)] transition-colors">
              <Settings size={14} />
            </button>
          </>
        ) : (
          /* Expanded footer */
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-black text-white flex-shrink-0"
              style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)' }}
            >
              DU
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-[var(--text)] truncate">Demo User</p>
              <p className="text-[10px] text-[var(--muted)] truncate">demo@ai</p>
            </div>
            <button
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--muted)] hover:text-[var(--text2)] hover:bg-[var(--surface3)] transition-colors flex-shrink-0"
            >
              {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
            </button>
            <Settings
              size={13}
              className="text-[var(--muted)] hover:text-[var(--text)] cursor-pointer transition-colors flex-shrink-0"
            />
          </div>
        )}
      </div>
    </aside>
  );
}
