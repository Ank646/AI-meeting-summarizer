'use client';
import { useState } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Cell,
} from 'recharts';
import {
  Cpu, Zap, GitBranch, TrendingUp, Shield, Lock,
  CheckCircle2, XCircle, MinusCircle, Star, ChevronRight,
  BarChart3, Target, Brain, AlertTriangle,
} from 'lucide-react';

// ─── Types & Data ─────────────────────────────────────────────────────────────

type Avail = 'yes' | 'no' | 'partial';

interface Feature {
  name: string;
  edge: Avail; fireflies: Avail; avoma: Avail; gong: Avail;
  exclusive?: boolean;
}
interface Category { label: string; icon: React.ReactNode; features: Feature[]; }

const PRODUCT_COLORS = {
  'Edge AI':   '#9d5cf5',
  Fireflies:   '#38bdf8',
  Avoma:       '#34d399',
  Gong:        '#fb923c',
} as const;
type Product = keyof typeof PRODUCT_COLORS;

const categories: Category[] = [
  {
    label: 'Core Transcription & Summaries',
    icon: <Brain size={14} />,
    features: [
      { name: 'High-quality meeting transcription',     edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Automatic meeting summaries',            edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Works with Zoom / Meet / Teams',         edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Multi-language transcription',           edge:'yes', fireflies:'yes',     avoma:'partial', gong:'partial' },
      { name: 'Speaker diarization',                    edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Real-time captions during meeting',      edge:'yes', fireflies:'partial', avoma:'partial', gong:'partial' },
    ],
  },
  {
    label: 'Task & Action Intelligence',
    icon: <Target size={14} />,
    features: [
      { name: 'Detect tasks from conversations',         edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Assign task owners automatically',        edge:'yes', fireflies:'yes',     avoma:'yes',     gong:'yes' },
      { name: 'Detect missing owner or deadline',        edge:'yes', fireflies:'no',      avoma:'partial', gong:'partial', exclusive:true },
      { name: "Detect vague commitments (\"we'll try\")",edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Send automatic task reminders',           edge:'yes', fireflies:'partial', avoma:'yes',     gong:'partial' },
      { name: 'Track tasks across multiple meetings',    edge:'yes', fireflies:'no',      avoma:'partial', gong:'partial', exclusive:true },
    ],
  },
  {
    label: 'Execution & Accountability',
    icon: <Zap size={14} />,
    features: [
      { name: 'Identify unclear decisions',              edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Decision tracking timeline',              edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Execution score for meetings',            edge:'yes', fireflies:'no',      avoma:'no',      gong:'partial', exclusive:true },
      { name: 'Team accountability metrics',             edge:'yes', fireflies:'no',      avoma:'partial', gong:'yes' },
      { name: 'Ask AI questions across meetings',        edge:'yes', fireflies:'partial', avoma:'partial', gong:'partial' },
      { name: 'Meeting health score over time',          edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
    ],
  },
  {
    label: 'Predictive & Strategic AI',
    icon: <TrendingUp size={14} />,
    features: [
      { name: 'Predict delayed tasks',                   edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Detect recurring blockers in meetings',   edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Strategic drift detection',               edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Cross-meeting memory graph',              edge:'yes', fireflies:'no',      avoma:'no',      gong:'no',      exclusive:true },
      { name: 'Sentiment trend analysis',                edge:'yes', fireflies:'partial', avoma:'partial', gong:'yes' },
      { name: 'Topic frequency & drift over sprints',    edge:'yes', fireflies:'no',      avoma:'no',      gong:'partial', exclusive:true },
    ],
  },
  {
    label: 'Privacy & Edge Deployment',
    icon: <Shield size={14} />,
    features: [
      { name: 'Runs on edge device (local processing)',  edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
      { name: 'Data stays inside company infra',         edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
      { name: 'Works in secure environments (gov/bank)', edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
      { name: 'Offline meeting analysis',                edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
      { name: 'On-premise deployment option',            edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
      { name: 'Custom model fine-tuning on private data',edge:'yes', fireflies:'no', avoma:'no', gong:'no', exclusive:true },
    ],
  },
];

const radarData = [
  { dim: 'Core AI',    edge:9.5, fireflies:8.5, avoma:8,   gong:8   },
  { dim: 'Task',       edge:10,  fireflies:5,   avoma:6,   gong:5.5 },
  { dim: 'Execution',  edge:10,  fireflies:2,   avoma:3,   gong:5   },
  { dim: 'Predictive', edge:10,  fireflies:1,   avoma:1,   gong:2   },
  { dim: 'Privacy',    edge:10,  fireflies:0,   avoma:0,   gong:0   },
];

const allFeatures = categories.flatMap(c => c.features);

const coverageData = (Object.keys(PRODUCT_COLORS) as Product[]).map(p => {
  const key = (p === 'Edge AI' ? 'edge' : p.toLowerCase()) as keyof Feature;
  return {
    product: p,
    full:    allFeatures.filter(f => (f[key] as Avail) === 'yes').length,
    partial: allFeatures.filter(f => (f[key] as Avail) === 'partial').length,
  };
});

const exclusiveData = categories.map(cat => ({
  cat: cat.label.replace(/ &.*/, '').replace(/Transcription.*/, 'Core').trim(),
  fullLabel: cat.label,
  exclusive: cat.features.filter(f => f.exclusive).length,
  shared:    cat.features.filter(f => !f.exclusive).length,
}));

const totalFeatures  = allFeatures.length;
const exclusiveCount = allFeatures.filter(f => f.exclusive).length;

const TOOLTIP_STYLE = {
  contentStyle: { background: '#0f1220', border: '1px solid #1e2540', borderRadius: 12, fontSize: 11 },
  labelStyle:   { color: '#64748b' },
  itemStyle:    { color: '#cbd5e1' },
};

const differentiators = [
  {
    icon: <Cpu size={22} />, color: '#9d5cf5', bg: 'rgba(124,58,237,0.12)', border: 'rgba(124,58,237,0.25)',
    title: 'Edge Device AI',
    subtitle: 'Zero-cloud intelligence',
    points: ['Runs entirely on local hardware','Zero data leaves your network','Works fully offline','Instant processing, no latency'],
  },
  {
    icon: <Zap size={22} />, color: '#38bdf8', bg: 'rgba(6,182,212,0.10)', border: 'rgba(6,182,212,0.25)',
    title: 'Execution Intelligence',
    subtitle: 'Accountability at every step',
    points: ['Detects vague commitments','Flags unclear decisions instantly','Generates meeting execution score','Tracks blockers across sprints'],
  },
  {
    icon: <GitBranch size={22} />, color: '#34d399', bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.25)',
    title: 'Decision Memory',
    subtitle: 'Cross-meeting context graph',
    points: ['Links decisions across meetings','Full decision history timeline','Strategic drift detection','Context-aware AI recall'],
  },
  {
    icon: <TrendingUp size={22} />, color: '#fb923c', bg: 'rgba(249,115,22,0.10)', border: 'rgba(249,115,22,0.25)',
    title: 'Predictive Insights',
    subtitle: 'See problems before they happen',
    points: ['Predicts task delays proactively','Surfaces recurring blockers','Topic frequency & drift analysis','Proactive team risk scoring'],
  },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function AvailIcon({ v }: { v: Avail }) {
  if (v === 'yes')     return <CheckCircle2 size={17} className="text-emerald-400 mx-auto" />;
  if (v === 'partial') return <MinusCircle  size={17} className="text-yellow-400 mx-auto"  />;
  return <XCircle size={17} className="mx-auto" style={{ color: 'rgba(239,68,68,0.5)' }} />;
}

function ScoreBar({ value, color, max = 10 }: { value: number; color: string; max?: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface3)' }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
      <span className="text-[10px] w-7 text-right shrink-0" style={{ color: 'var(--muted)' }}>{value}</span>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ProductPage() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="h-full overflow-y-auto">

      {/* ── Sticky header ─── */}
      <div className="sticky top-0 z-20 px-8 py-5 glass border-b border-[var(--border)] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <Star size={12} className="text-yellow-400" fill="currentColor" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">
              Competitive Analysis
            </span>
          </div>
          <h1 className="text-xl font-black gradient-text">Product Differentiation</h1>
        </div>
        <div className="hidden sm:flex items-center gap-2">
          {(['Fireflies','Avoma','Gong'] as const).map(p => (
            <span key={p}
              className="px-3 py-1.5 rounded-full text-[10px] font-bold border"
              style={{
                color: PRODUCT_COLORS[p],
                background: `${PRODUCT_COLORS[p]}18`,
                borderColor: `${PRODUCT_COLORS[p]}35`,
              }}>
              vs {p}
            </span>
          ))}
        </div>
      </div>

      <div className="px-8 py-6 space-y-8">

        {/* ── Positioning banner ─── */}
        <div className="relative rounded-3xl overflow-hidden border border-violet-500/20 p-8"
          style={{ background: 'linear-gradient(135deg,rgba(124,58,237,0.14) 0%,rgba(79,70,229,0.09) 50%,rgba(6,182,212,0.07) 100%)' }}>
          <div className="pointer-events-none absolute -top-12 -right-12 w-56 h-56 rounded-full opacity-25"
            style={{ background: 'radial-gradient(circle, #7c3aed 0%, transparent 70%)' }} />
          <div className="pointer-events-none absolute -bottom-8 left-28 w-40 h-40 rounded-full opacity-15"
            style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }} />
          <div className="relative z-10 max-w-3xl">
            <div className="flex items-center gap-2 mb-3">
              <Lock size={13} className="text-violet-400" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-violet-400">
                One-Line Positioning
              </span>
            </div>
            <p className="text-2xl font-black text-[var(--text)] leading-tight mb-3">
              "An AI meeting intelligence system that{' '}
              <span className="gradient-text">runs on edge devices</span>{' '}
              and ensures meetings turn into{' '}
              <span style={{ color: '#34d399' }}>real execution.</span>"
            </p>
            <p className="text-sm text-[var(--muted)] max-w-xl leading-relaxed">
              The only platform combining on-device privacy, execution scoring, and predictive
              intelligence — with zero cloud dependency. Built for regulated industries.
            </p>
          </div>
        </div>

        {/* ── Stat cards ─── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label:'Total Features Tracked', value: totalFeatures,  sub:'Across 5 categories',      color:'#9d5cf5', icon:<BarChart3 size={18}/> },
            { label:'Edge AI Exclusive',       value: exclusiveCount, sub:'Not in any competitor',    color:'#34d399', icon:<Star size={18}/> },
            { label:'Feature Coverage',        value:'100%',          sub:'Full on Edge AI',          color:'#38bdf8', icon:<CheckCircle2 size={18}/> },
            { label:'Competitors Analysed',    value: 3,              sub:'Fireflies · Avoma · Gong', color:'#fb923c', icon:<Target size={18}/> },
          ].map((s, i) => (
            <div key={s.label}
              className="fade-up rounded-2xl border p-5 flex flex-col gap-3"
              style={{
                background: `linear-gradient(135deg,${s.color}14,${s.color}06)`,
                borderColor: `${s.color}30`,
                animationDelay: `${i * 60}ms`,
              }}>
              <div className="flex items-start justify-between">
                <div className="p-2 rounded-xl" style={{ background: `${s.color}22`, color: s.color }}>
                  {s.icon}
                </div>
                <span className="text-3xl font-black" style={{ color: s.color }}>{s.value}</span>
              </div>
              <div>
                <p className="text-xs font-bold text-[var(--text2)]">{s.label}</p>
                <p className="text-[10px] text-[var(--muted)] mt-0.5">{s.sub}</p>
              </div>
            </div>
          ))}
        </div>

        {/* ── Charts: Radar + Coverage ─── */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

          <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
              Capability Radar
            </p>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData} margin={{ top: 10, right: 25, bottom: 10, left: 25 }}>
                <PolarGrid stroke="#1e2540" />
                <PolarAngleAxis dataKey="dim" tick={{ fill: '#64748b', fontSize: 11, fontWeight: 600 }} />
                <PolarRadiusAxis angle={90} domain={[0, 10]} tick={false} axisLine={false} />
                {(Object.entries(PRODUCT_COLORS) as [Product, string][]).map(([product, color]) => (
                  <Radar
                    key={product}
                    name={product}
                    dataKey={product === 'Edge AI' ? 'edge' : product.toLowerCase()}
                    stroke={color}
                    fill={color}
                    fillOpacity={product === 'Edge AI' ? 0.22 : 0.04}
                    strokeWidth={product === 'Edge AI' ? 2.5 : 1.5}
                    strokeDasharray={product !== 'Edge AI' ? '4 3' : undefined}
                  />
                ))}
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 16 }}
                  formatter={(v: string) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
                <Tooltip {...TOOLTIP_STYLE} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
              Feature Coverage by Product
            </p>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={coverageData} margin={{ top: 4, right: 8, bottom: 4, left: -10 }} barSize={32}>
                <defs>
                  {(Object.entries(PRODUCT_COLORS) as [Product, string][]).map(([p, c]) => (
                    <linearGradient key={p} id={`bar-${p.replace(' ','')}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor={c} stopOpacity={0.9} />
                      <stop offset="100%" stopColor={c} stopOpacity={0.5} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="#1e2540" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="product" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 11 }}
                  formatter={(v: string) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
                <Bar dataKey="full" name="Full Support" stackId="a" radius={[0, 0, 0, 0]}>
                  {coverageData.map(entry => (
                    <Cell key={entry.product} fill={`url(#bar-${entry.product.replace(' ','')})`} />
                  ))}
                </Bar>
                <Bar dataKey="partial" name="Partial" stackId="a" fill="#f59e0b" fillOpacity={0.5} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Exclusive horizontal bar ─── */}
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
            Edge AI Exclusive vs. Shared Features — by Category
          </p>
          <ResponsiveContainer width="100%" height={210}>
            <BarChart data={exclusiveData} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 115 }} barSize={14}>
              <defs>
                <linearGradient id="excl-grad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#7c3aed" />
                  <stop offset="100%" stopColor="#9d5cf5" />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1e2540" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="cat"
                tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 600 }}
                axisLine={false} tickLine={false} width={110} />
              <Tooltip {...TOOLTIP_STYLE}
                labelFormatter={(_: unknown, payload: { payload?: { fullLabel: string } }[]) =>
                  payload?.[0]?.payload?.fullLabel ?? ''
                } />
              <Legend wrapperStyle={{ fontSize: 11 }}
                formatter={(v: string) => <span style={{ color: '#94a3b8' }}>{v}</span>} />
              <Bar dataKey="exclusive" name="Edge AI Exclusive" fill="url(#excl-grad)" radius={[0, 4, 4, 0]} />
              <Bar dataKey="shared"    name="Shared Features"   fill="#1c2135" stroke="#252d4a" strokeWidth={1} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Key differentiators ─── */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="h-px flex-1 bg-[var(--border)]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] px-3">
              Why Edge AI Wins
            </span>
            <div className="h-px flex-1 bg-[var(--border)]" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {differentiators.map((d, i) => (
              <div key={d.title}
                className="fade-up group rounded-2xl p-5 border transition-all duration-300 hover:scale-[1.02] hover:shadow-xl"
                style={{
                  background: d.bg,
                  borderColor: d.border,
                  animationDelay: `${i * 80}ms`,
                }}>
                <div className="flex items-start justify-between mb-4">
                  <div className="p-2.5 rounded-xl border" style={{ color: d.color, background: `${d.color}18`, borderColor: `${d.color}35` }}>
                    {d.icon}
                  </div>
                  <ChevronRight size={14} className="text-[var(--muted)] group-hover:translate-x-0.5 transition-transform mt-0.5" />
                </div>
                <p className="text-sm font-black text-[var(--text)] mb-0.5">{d.title}</p>
                <p className="text-[10px] font-semibold mb-3" style={{ color: d.color }}>{d.subtitle}</p>
                <ul className="space-y-1.5">
                  {d.points.map(pt => (
                    <li key={pt} className="flex items-start gap-2">
                      <CheckCircle2 size={11} className="mt-0.5 shrink-0" style={{ color: d.color }} />
                      <span className="text-[11px] leading-snug text-[var(--muted)]">{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* ── Dimension score breakdown ─── */}
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-5">
            Dimension Scores — All Products
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
            {(Object.entries(PRODUCT_COLORS) as [Product, string][]).map(([product, color]) => {
              const dk = product === 'Edge AI' ? 'edge' : product.toLowerCase() as keyof typeof radarData[0];
              return (
                <div key={product}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                    <span className="text-xs font-bold" style={{ color }}>
                      {product}
                      {product === 'Edge AI' && (
                        <span className="ml-1.5 text-[9px] px-1.5 py-0.5 rounded-full font-black"
                          style={{ background: 'rgba(124,58,237,0.2)', color: '#9d5cf5' }}>
                          YOU
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="space-y-2.5">
                    {radarData.map(d => (
                      <div key={d.dim}>
                        <span className="text-[10px] text-[var(--muted)] block mb-1">{d.dim}</span>
                        <ScoreBar value={d[dk] as number} color={color} />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Full feature comparison table ─── */}
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] overflow-hidden">

          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-5 border-b border-[var(--border)]">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">
              Full Feature Comparison
            </p>
            <div className="flex items-center gap-4">
              {[
                { icon: <CheckCircle2 size={12} className="text-emerald-400" />, label:'Available' },
                { icon: <MinusCircle  size={12} className="text-yellow-400"  />, label:'Partial' },
                { icon: <XCircle      size={12} style={{ color:'rgba(239,68,68,0.55)' }} />, label:'None' },
              ].map(l => (
                <div key={l.label} className="flex items-center gap-1.5">
                  {l.icon}
                  <span className="text-[10px] text-[var(--muted)]">{l.label}</span>
                </div>
              ))}
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm border" style={{ background:'rgba(124,58,237,0.3)', borderColor:'rgba(124,58,237,0.5)' }} />
                <span className="text-[10px] text-[var(--muted)]">Exclusive</span>
              </div>
            </div>
          </div>

          {/* Category tabs */}
          <div className="flex overflow-x-auto border-b border-[var(--border)]" style={{ background:'rgba(10,13,24,0.6)' }}>
            {['All', ...categories.map(c =>
              c.label.replace(/ &.*/, '').replace(/Transcription.*/, 'Core').trim()
            )].map((tab, i) => (
              <button key={tab} onClick={() => setActiveTab(i)}
                className={`px-4 py-3 text-[11px] font-bold whitespace-nowrap transition-all border-b-2 ${
                  activeTab === i
                    ? 'border-violet-500 text-violet-300'
                    : 'border-transparent text-[var(--muted)] hover:text-[var(--text2)]'
                }`}>
                {tab}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--border)]" style={{ background:'rgba(28,33,53,0.7)' }}>
                  <th className="text-left px-6 py-3 text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] w-[44%]">
                    Feature
                  </th>
                  {(Object.entries(PRODUCT_COLORS) as [Product, string][]).map(([p, c]) => (
                    <th key={p} className="px-4 py-3 text-center text-[11px] font-black whitespace-nowrap" style={{ color: c }}>
                      {p === 'Edge AI' && <Star size={9} className="inline mr-1 -mt-0.5" fill="currentColor" />}
                      {p}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(activeTab === 0 ? categories : [categories[activeTab - 1]]).map(cat => (
                  <>
                    {activeTab === 0 && (
                      <tr key={`${cat.label}-hdr`} className="border-b border-[var(--border)]"
                        style={{ background:'rgba(21,25,38,0.95)' }}>
                        <td colSpan={5} className="px-6 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="text-violet-400">{cat.icon}</span>
                            <span className="text-[10px] font-black uppercase tracking-widest text-[var(--muted2)]">
                              {cat.label}
                            </span>
                          </div>
                        </td>
                      </tr>
                    )}
                    {cat.features.map(f => (
                      <tr key={f.name}
                        className="border-b border-[var(--border)] transition-colors hover:bg-[var(--surface2)]"
                        style={f.exclusive ? { background:'rgba(124,58,237,0.055)' } : undefined}>
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2.5">
                            <span className="text-xs text-[var(--text2)]">{f.name}</span>
                            {f.exclusive && (
                              <span className="shrink-0 text-[9px] font-black px-1.5 py-0.5 rounded-full border"
                                style={{ color:'#9d5cf5', background:'rgba(124,58,237,0.15)', borderColor:'rgba(124,58,237,0.3)' }}>
                                EXCLUSIVE
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className={f.exclusive ? 'inline-flex rounded-lg p-0.5 ring-1 ring-violet-500/30' : ''}>
                            <AvailIcon v={f.edge} />
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center"><AvailIcon v={f.fireflies} /></td>
                        <td className="px-4 py-3 text-center"><AvailIcon v={f.avoma} /></td>
                        <td className="px-4 py-3 text-center"><AvailIcon v={f.gong} /></td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer summary */}
          <div className="flex flex-wrap gap-4 px-6 py-4 border-t border-[var(--border)]"
            style={{ background:'rgba(21,25,38,0.95)' }}>
            {coverageData.map(row => (
              <div key={row.product} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ background: PRODUCT_COLORS[row.product as Product] }} />
                <span className="text-[10px] text-[var(--muted)]">
                  <strong style={{ color: PRODUCT_COLORS[row.product as Product] }}>{row.product}</strong>
                  {' '}{row.full} full · {row.partial} partial
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Bottom CTA summary ─── */}
        <div className="rounded-2xl p-7 text-center border border-violet-500/20"
          style={{ background:'linear-gradient(135deg,rgba(124,58,237,0.12),rgba(79,70,229,0.08),rgba(6,182,212,0.06))' }}>
          <div className="flex items-center justify-center gap-2 mb-3">
            <AlertTriangle size={13} className="text-yellow-400" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-yellow-400">Bottom Line</span>
          </div>
          <p className="text-xl font-black text-[var(--text)] mb-2">
            {exclusiveCount} features{' '}
            <span className="gradient-text">no competitor offers</span>
          </p>
          <p className="text-sm text-[var(--muted)] max-w-lg mx-auto leading-relaxed">
            While Fireflies, Avoma, and Gong cover the basics, only Edge AI delivers execution
            intelligence, predictive risk, and on-device privacy — making it the only enterprise-grade
            choice for regulated industries.
          </p>
        </div>

        <div className="h-6" />
      </div>
    </div>
  );
}
