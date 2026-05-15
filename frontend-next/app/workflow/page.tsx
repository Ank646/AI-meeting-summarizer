'use client';

const LAYERS = [
  {
    id: 'client', label: 'Client Layer', color: '#3b82f6',
    nodes: [
      { id: 'browser', label: 'Next.js Dashboard', sub: 'React + Zustand', icon: '🖥️' },
      { id: 'mic',     label: 'Microphone Stream', sub: 'PCM 16kHz',       icon: '🎙️' },
    ],
  },
  {
    id: 'gateway', label: 'API Gateway', color: '#7c3aed',
    nodes: [
      { id: 'ws_audio', label: 'WS /audio',     sub: 'FastAPI',      icon: '🔊' },
      { id: 'ws_dash',  label: 'WS /dashboard', sub: 'FastAPI',      icon: '📡' },
      { id: 'rest',     label: 'REST /meetings', sub: 'FastAPI',      icon: '🔌' },
    ],
  },
  {
    id: 'queue', label: 'Message Queue', color: '#f59e0b',
    nodes: [
      { id: 'streams',  label: 'Redis Streams',  sub: 'MAXLEN 5000',      icon: '📨' },
      { id: 'pubsub',   label: 'Redis Pub/Sub',  sub: 'Live broadcast',   icon: '📢' },
    ],
  },
  {
    id: 'workers', label: 'Celery Workers', color: '#10b981',
    nodes: [
      { id: 'asr',      label: 'ASR Worker',       sub: 'Whisper large-v3',    icon: '🤖' },
      { id: 'diar',     label: 'Diarization',      sub: 'pyannote.audio 3.1',  icon: '🗣️' },
      { id: 'extract',  label: 'LLM Extraction',   sub: '4-layer pipeline',    icon: '🧠' },
      { id: 'graph',    label: 'Graph Worker',      sub: 'Neo4j updates',       icon: '🕸️' },
    ],
  },
  {
    id: 'storage', label: 'Storage Layer', color: '#ec4899',
    nodes: [
      { id: 'pg',       label: 'PostgreSQL',   sub: '+ pgvector HNSW', icon: '🐘' },
      { id: 'neo4j',    label: 'Neo4j',        sub: 'Graph DB',        icon: '🔗' },
      { id: 'minio',    label: 'MinIO',        sub: 'Object Store',    icon: '🗃️' },
      { id: 'redis_c',  label: 'Redis Cache',  sub: 'TTL queries',     icon: '⚡' },
    ],
  },
];

const STEPS = [
  { n: '01', title: 'Audio Capture',        color: '#3b82f6', desc: 'Browser mic → PCM int16 frames → WebSocket /ws/audio → Redis Stream XADD (MAXLEN 5000)' },
  { n: '02', title: 'VAD + Preprocessing',  color: '#6366f1', desc: 'WebRTC VAD silence removal → ffmpeg normalisation to -3dBFS → 16kHz mono WAV chunks' },
  { n: '03', title: 'ASR (Pass 1)',          color: '#7c3aed', desc: 'Whisper large-v3 sliding window W=10s S=8s O=2s → word timestamps → token stabiliser (k=3)' },
  { n: '04', title: 'Speaker Diarization',  color: '#9333ea', desc: 'pyannote.audio 3.1 → word-to-speaker alignment by midpoint timestamp intersection' },
  { n: '05', title: 'Context Buffer',        color: '#a855f7', desc: 'Rolling k=3 Redis List: T(i-2)+T(i-1)+T(i) joined context window for LLM extraction' },
  { n: '06', title: '4-Layer Extraction',   color: '#06b6d4', desc: 'L1 Regex heuristics → L2 LLM deterministic (t=0) → L3 Self-consistency (t=0.4, Jaccard) → L4 Sigmoid confidence' },
  { n: '07', title: 'Topic Segmentation',   color: '#0ea5e9', desc: 'Consecutive chunk cosine similarity < 0.55 → segment boundaries → LLM 4-word topic labels' },
  { n: '08', title: 'Execution Scoring',    color: '#10b981', desc: 'Score = 0.4·(O/T) + 0.3·(D/T) − 0.2·(V/T) − 0.1·(B/T) clamped [0, 1]' },
  { n: '09', title: 'Graph Memory',         color: '#f59e0b', desc: 'Neo4j: Meeting → Decision (REVISES) → Task (DEPENDS_ON) → Risk (BLOCKS) → Topic (TAGGED_WITH)' },
  { n: '10', title: 'Hybrid Retrieval',     color: '#f97316', desc: 'pgvector HNSW ANN + Neo4j graph context + PostgreSQL FTS → ranked deduplicated results' },
  { n: '11', title: 'Live Broadcast',       color: '#ef4444', desc: 'Redis Pub/Sub → /ws/dashboard WebSocket fan-out → real-time UI update in < 200ms' },
  { n: '12', title: 'Pass 2 Reconciliation', color: '#ec4899', desc: 'Full-file Whisper + deep extraction → DELETE low-confidence < 0.6 → INSERT refined results' },
];

const STACK = [
  ['API Gateway',       'FastAPI + Uvicorn',         'Async WebSocket + REST'],
  ['ASR',               'faster-whisper large-v3',   'GPU int8, word timestamps'],
  ['Diarization',       'pyannote.audio 3.1',        'Speaker segmentation'],
  ['LLM Extraction',    'Ollama / Mistral-7B',       '4-layer, Pydantic v2'],
  ['Embeddings',        'BGE-large-en-v1.5 (1024d)', 'sentence-transformers'],
  ['Message Queue',     'Redis Streams',             'XADD/XREADGROUP MAXLEN=5000'],
  ['Task Queue',        'Celery 5',                  'asr / diarization / extraction / graph'],
  ['Vector DB',         'PostgreSQL + pgvector',     'HNSW cosine m=16 ef=64'],
  ['Graph DB',          'Neo4j 5 + APOC',            'Decision evolution, dependencies'],
  ['Object Store',      'MinIO S3',                  '{org_id}/{meeting_id}/audio.wav'],
  ['Cache / Pub-Sub',   'Redis 7',                   'Pub/Sub events + TTL caching'],
  ['Frontend',          'Next.js 14',                'App Router, Zustand, Tailwind, Recharts'],
];

export default function WorkflowPage() {
  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 px-8 py-5 glass border-b border-[var(--border)]">
        <h1 className="text-xl font-black text-[var(--text)]">System Architecture</h1>
        <p className="text-xs text-[var(--muted)] mt-0.5">End-to-end pipeline: audio → ASR → diarization → extraction → graph → dashboard</p>
      </div>

      <div className="px-8 py-6 space-y-8">

        {/* Layered diagram */}
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] p-6">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-6">System Layers</p>
          <div className="space-y-5">
            {LAYERS.map((layer, li) => (
              <div key={layer.id} className="fade-up" style={{ animationDelay: `${li * 80}ms` }}>
                <div className="flex items-center gap-2 mb-2.5">
                  <div className="w-2 h-2 rounded-full" style={{ background: layer.color }} />
                  <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: layer.color }}>{layer.label}</p>
                </div>
                <div className="flex flex-wrap gap-2.5 pl-4">
                  {layer.nodes.map((node) => (
                    <div key={node.id}
                      className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border"
                      style={{ background: `${layer.color}0d`, borderColor: `${layer.color}28` }}>
                      <span className="text-lg">{node.icon}</span>
                      <div>
                        <p className="text-xs font-semibold text-[var(--text)]">{node.label}</p>
                        <p className="text-[10px] text-[var(--muted)]">{node.sub}</p>
                      </div>
                    </div>
                  ))}
                </div>
                {li < LAYERS.length - 1 && (
                  <div className="flex items-center gap-1 mt-3 pl-5">
                    <div className="w-px h-4 bg-[var(--border2)]" />
                    <span className="text-[10px] text-[var(--muted)]">↓</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline steps */}
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-4">Processing Pipeline</p>
          <div className="grid grid-cols-1 gap-2.5">
            {STEPS.map((s, i) => (
              <div key={s.n}
                className="flex gap-4 items-start rounded-2xl bg-[var(--surface)] border border-[var(--border)] px-4 py-3 hover:border-[var(--border2)] transition-colors fade-up"
                style={{ animationDelay: `${i * 40}ms` }}>
                <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 font-black text-sm"
                  style={{ background: `${s.color}18`, color: s.color, border: `1px solid ${s.color}30` }}>
                  {s.n}
                </div>
                <div>
                  <p className="text-sm font-bold text-[var(--text)] mb-0.5">{s.title}</p>
                  <p className="text-xs text-[var(--muted)] leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tech stack table */}
        <div className="rounded-2xl bg-[var(--surface)] border border-[var(--border)] overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface2)]">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--muted)]">Technology Stack</p>
          </div>
          <table className="w-full text-xs">
            <tbody>
              {STACK.map(([comp, tech, notes], i) => (
                <tr key={comp} className={`border-b border-[var(--border)] ${i % 2 === 0 ? '' : 'bg-[var(--surface2)]/40'}`}>
                  <td className="px-5 py-3 font-semibold text-[var(--text2)] w-40">{comp}</td>
                  <td className="px-5 py-3 font-mono text-[var(--violet-l)]">{tech}</td>
                  <td className="px-5 py-3 text-[var(--muted)]">{notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
