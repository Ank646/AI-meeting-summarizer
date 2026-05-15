// ── Core domain types ──────────────────────────────────────────────────────

export type AppMode = 'real' | 'test';

export interface WordToken {
  word: string;
  start: number;
  end: number;
  probability: number;
}

export interface Utterance {
  speaker: string;
  text: string;
  start: number;
  end: number;
  words?: WordToken[];
}

export interface TranscriptData {
  chunk_index: number;
  utterances: Utterance[];
  is_stable: boolean;
  meeting_id: string;
}

export interface ExtractedTask {
  description: string;
  assignee: string | null;
  deadline_raw: string | null;
  deadline_normalized: string | null;
  is_vague: boolean;
  confidence: number;
  dependencies?: string[];
}

export interface ExtractedDecision {
  description: string;
  made_by: string | null;
  rationale: string | null;
  confidence: number;
}

export interface ExtractedRisk {
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  is_blocker: boolean;
  mitigation: string | null;
  confidence: number;
}

export interface ExecutionScore {
  score: number;
  tasks_with_owner: number;
  tasks_with_deadline: number;
  vague_count: number;
  blocker_count: number;
  total_tasks: number;
}

export interface ExtractionData {
  chunk_index: number;
  meeting_id: string;
  tasks: ExtractedTask[];
  decisions: ExtractedDecision[];
  risks: ExtractedRisk[];
  topics: string[];
  score: ExecutionScore | null;
}

export type LiveEventType =
  | 'connected'
  | 'transcript'
  | 'extraction'
  | 'pass2_complete'
  | 'error';

export interface LiveEvent {
  event_type: LiveEventType;
  meeting_id: string;
  data: TranscriptData | ExtractionData | { message: string } | unknown;
}

// ── Meeting ────────────────────────────────────────────────────────────────

export type MeetingStatus = 'scheduled' | 'recording' | 'processing' | 'completed' | 'failed';

export interface Meeting {
  id: string;
  title: string;
  org_id: string;
  status: MeetingStatus;
  created_at: string;
  duration_seconds?: number;
  participant_count?: number;
  score?: number;
}

// ── Search ─────────────────────────────────────────────────────────────────

export interface SearchResult {
  meeting_id: string;
  meeting_title: string;
  chunk_text: string;
  chunk_index: number;
  similarity: number;
  created_at: string;
  graph_context?: GraphContext;
}

export interface GraphContext {
  related_decisions: string[];
  related_tasks: string[];
}

// ── Analytics ──────────────────────────────────────────────────────────────

export interface OrgScore {
  avg_score: number;
  meetings_analyzed: number;
  total_tasks: number;
  open_tasks: number;
  blocker_count: number;
}

export interface ScoreTrend {
  date: string;
  score: number;
  meetings: number;
}

// ── Connection state ───────────────────────────────────────────────────────

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'recording';

export interface EventLogEntry {
  ts: string;
  msg: string;
}
