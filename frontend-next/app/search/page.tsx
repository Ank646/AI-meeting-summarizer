'use client';
import { useState, useRef } from 'react';
import { Search, Sparkles, ChevronRight, Clock } from 'lucide-react';
import { hybridSearch } from '@/lib/api';
import { MOCK_SEARCH_RESULTS } from '@/lib/mockData';
import { useMode } from '@/hooks/useMode';
import type { SearchResult } from '@/lib/types';

const SUGGESTIONS = [
  'React Native decision',
  'database migration blocker',
  'API rate limiting fix',
  'Q3 sprint priorities',
  'authentication refactor deadline',
];

export default function SearchPage() {
  const { mode }               = useMode();
  const [query, setQuery]      = useState('');
  const [results, setResults]  = useState<SearchResult[]>([]);
  const [loading, setLoading]  = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError]      = useState('');
  const inputRef               = useRef<HTMLInputElement>(null);

  async function doSearch(q?: string) {
    const term = q ?? query;
    if (!term.trim()) return;
    if (q) setQuery(q);
    setLoading(true); setError('');
    try {
      const data = mode === 'test'
        ? MOCK_SEARCH_RESULTS.filter((r) =>
            r.chunk_text.toLowerCase().includes(term.toLowerCase()) ||
            r.meeting_title.toLowerCase().includes(term.toLowerCase()),
          ).concat(MOCK_SEARCH_RESULTS)   // pad with all results for demo
          .slice(0, 5)
        : await hybridSearch(term);
      setResults(data);
      setSearched(true);
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Hero search area */}
      <div className="px-8 py-10 text-center border-b border-[var(--border)]"
        style={{ background: 'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(124,58,237,0.15), transparent)' }}>
        <div className="flex items-center justify-center gap-2 mb-2">
          <Sparkles size={16} className="text-[var(--violet-l)]" />
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--violet-l)]">Semantic Search</p>
        </div>
        <h1 className="text-2xl font-black text-[var(--text)] mb-1">Search Your Meetings</h1>
        <p className="text-sm text-[var(--muted)] mb-6">Hybrid vector + graph retrieval across all transcripts</p>

        {/* Search bar */}
        <div className="max-w-2xl mx-auto">
          <div className="relative flex items-center">
            <Search size={16} className="absolute left-4 text-[var(--muted)]" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doSearch()}
              placeholder="Ask anything about your meetings…"
              className="w-full pl-11 pr-32 py-3.5 text-sm rounded-2xl bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:border-[var(--violet)] transition-colors"
            />
            <button
              onClick={() => doSearch()}
              disabled={loading || !query.trim()}
              className="absolute right-2 px-4 py-2 text-xs font-bold text-white rounded-xl transition-all disabled:opacity-40"
              style={{ background: 'linear-gradient(135deg,#7c3aed,#4f46e5)' }}
            >
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>

          {/* Suggestions */}
          {!searched && (
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => doSearch(s)}
                  className="flex items-center gap-1 text-[11px] text-[var(--muted)] hover:text-[var(--violet-l)] px-3 py-1 rounded-full bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--violet)]/40 transition-all">
                  <Clock size={10} /> {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="px-8 py-6 max-w-3xl">
        {error && (
          <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
        )}

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((n) => <div key={n} className="h-28 rounded-2xl shimmer" />)}
          </div>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="text-center py-12">
            <div className="text-4xl mb-3">🔍</div>
            <p className="text-sm text-[var(--muted)]">No results for "{query}"</p>
          </div>
        )}

        <div className="space-y-4">
          {results.map((r, i) => <ResultCard key={i} result={r} idx={i} />)}
        </div>
      </div>
    </div>
  );
}

function ResultCard({ result, idx }: { result: SearchResult; idx: number }) {
  const pct = Math.round(result.similarity * 100);
  const matchColor = pct >= 80 ? '#6ee7b7' : pct >= 60 ? '#fcd34d' : '#fca5a5';

  return (
    <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-5 hover:border-[var(--border2)] transition-all duration-200 fade-up"
      style={{ animationDelay: `${idx * 60}ms` }}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-xs font-bold" style={{ color: 'var(--violet-l)' }}>{result.meeting_title}</p>
            <span className="text-[10px] text-[var(--muted)] font-mono">chunk #{result.chunk_index}</span>
          </div>
          <p className="text-[10px] text-[var(--muted)]">
            {new Date(result.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-1 px-2.5 py-1 rounded-full flex-shrink-0"
          style={{ background: `${matchColor}18`, border: `1px solid ${matchColor}30` }}>
          <span className="text-[11px] font-black" style={{ color: matchColor }}>{pct}%</span>
          <span className="text-[10px] text-[var(--muted)]">match</span>
        </div>
      </div>

      {/* Text */}
      <p className="text-sm text-[var(--text2)] leading-relaxed mb-3 px-3 py-2.5 rounded-xl bg-[var(--surface2)] border border-[var(--border)]">
        {result.chunk_text}
      </p>

      {/* Graph context */}
      {result.graph_context && (
        <div className="space-y-2 pt-3 border-t border-[var(--border)]">
          {result.graph_context.related_decisions.map((d, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className="text-green-400 flex-shrink-0 font-semibold">Decision</span>
              <span className="text-[var(--muted)]">{d}</span>
              <ChevronRight size={10} className="text-[var(--muted)] mt-0.5 ml-auto flex-shrink-0" />
            </div>
          ))}
          {result.graph_context.related_tasks.map((t, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className="text-blue-400 flex-shrink-0 font-semibold">Task</span>
              <span className="text-[var(--muted)]">{t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
