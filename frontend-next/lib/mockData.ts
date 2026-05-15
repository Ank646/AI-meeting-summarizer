/**
 * Mock data simulator for Test mode.
 * Emits realistic LiveEvents at configured intervals so every UI feature
 * can be exercised without a running backend.
 */

import type {
  LiveEvent,
  TranscriptData,
  ExtractionData,
  ExtractedTask,
  ExtractedDecision,
  ExtractedRisk,
  ExecutionScore,
  Meeting,
  SearchResult,
  OrgScore,
  ScoreTrend,
} from './types';

// ── Mock meetings ──────────────────────────────────────────────────────────

export const MOCK_MEETINGS: Meeting[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    title: 'Q3 Product Strategy Review',
    org_id: 'demo-org',
    status: 'completed',
    created_at: '2024-07-01T10:00:00Z',
    duration_seconds: 3600,
    participant_count: 6,
    score: 0.78,
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    title: 'Engineering Sprint Planning',
    org_id: 'demo-org',
    status: 'completed',
    created_at: '2024-07-02T14:00:00Z',
    duration_seconds: 2700,
    participant_count: 8,
    score: 0.62,
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    title: 'Customer Success Weekly Sync',
    org_id: 'demo-org',
    status: 'recording',
    created_at: '2024-07-03T09:00:00Z',
    duration_seconds: undefined,
    participant_count: 4,
    score: undefined,
  },
];

// ── Mock transcript lines ──────────────────────────────────────────────────

const SPEAKERS = ['Alice Chen', 'Bob Kumar', 'Carol White', 'David Park'];

const LINES = [
  "Alice: Let's review the Q3 roadmap priorities before we dive into sprint planning.",
  'Bob: I think the authentication service refactor should be our top priority. The current implementation has performance issues.',
  "Carol: Agreed. I'll take ownership of that — targeting end of next week for the initial PR.",
  "David: We also need to address the database migration. It's been blocked by the infra team for two months.",
  "Alice: That's a blocker. Let's escalate to leadership today.",
  "Bob: I can handle the escalation. I'll send an email to the CTO by end of day.",
  "Carol: For the mobile app, we need to decide whether we're going with React Native or Flutter.",
  "David: The decision has been made — we're going with React Native. It aligns better with our existing team skills.",
  "Alice: Good. Bob, can you create the technical spec by Friday?",
  'Bob: Sure, I can do that.',
  "Carol: There's a risk here — we don't have anyone with production React Native experience.",
  "David: That's a high-severity risk. We should probably budget for external consultants.",
  'Alice: Agreed. Carol, can you get quotes from three vendors by Thursday?',
  "Carol: I'll add that to my list.",
  "Bob: Should we also address the API rate limiting issue? Customers are complaining.",
  "David: That's critical. We need to implement exponential backoff in the client libraries.",
  "Alice: David, take that on. What's your timeline?",
  "David: I can have a fix deployed by end of sprint.",
  "Carol: One more thing — the analytics dashboard is showing incorrect data for some enterprise customers.",
  'Bob: I investigated that last week. It appears to be a timezone normalization bug.',
  'Alice: Severity?',
  "Bob: Medium — it's cosmetic but erodes customer trust. I'll fix it today.",
];

let lineIdx = 0;
let chunkIdx = 0;

function nextLine() {
  const line = LINES[lineIdx % LINES.length];
  lineIdx++;
  return line;
}

function makeSpeaker(line: string) {
  const match = line.match(/^(\w+):/);
  if (match) return match[1].padEnd(2, ' ');
  return SPEAKERS[lineIdx % SPEAKERS.length];
}

function makeText(line: string) {
  return line.replace(/^\w+:\s*/, '');
}

export function generateTranscriptEvent(meetingId: string): LiveEvent {
  const line = nextLine();
  chunkIdx++;
  const data: TranscriptData = {
    chunk_index: chunkIdx,
    meeting_id: meetingId,
    is_stable: chunkIdx % 3 !== 0,
    utterances: [
      {
        speaker: makeSpeaker(line),
        text: makeText(line),
        start: (chunkIdx - 1) * 8.0,
        end: chunkIdx * 8.0,
      },
    ],
  };
  return { event_type: 'transcript', meeting_id: meetingId, data };
}

// ── Mock extractions ───────────────────────────────────────────────────────

export const MOCK_TASKS: ExtractedTask[] = [
  {
    description: 'Refactor authentication service for performance improvements',
    assignee: 'Carol',
    deadline_raw: 'end of next week',
    deadline_normalized: '2024-07-12',
    is_vague: false,
    confidence: 0.92,
  },
  {
    description: 'Escalate database migration blocker to leadership',
    assignee: 'Alice',
    deadline_raw: 'today',
    deadline_normalized: '2024-07-03',
    is_vague: false,
    confidence: 0.88,
  },
  {
    description: 'Create technical spec for React Native mobile app',
    assignee: 'Bob',
    deadline_raw: 'by Friday',
    deadline_normalized: '2024-07-05',
    is_vague: false,
    confidence: 0.95,
  },
  {
    description: 'Get quotes from three React Native consultants',
    assignee: 'Carol',
    deadline_raw: 'by Thursday',
    deadline_normalized: '2024-07-04',
    is_vague: false,
    confidence: 0.87,
  },
  {
    description: 'Implement exponential backoff in client libraries for API rate limiting',
    assignee: 'David',
    deadline_raw: 'end of sprint',
    deadline_normalized: '2024-07-14',
    is_vague: false,
    confidence: 0.91,
  },
  {
    description: 'Fix timezone normalization bug in analytics dashboard',
    assignee: 'Bob',
    deadline_raw: 'today',
    deadline_normalized: '2024-07-03',
    is_vague: false,
    confidence: 0.89,
  },
];

export const MOCK_DECISIONS: ExtractedDecision[] = [
  {
    description: 'Adopt React Native over Flutter for the mobile application',
    made_by: 'David',
    rationale: 'Better alignment with existing team skills',
    confidence: 0.94,
  },
  {
    description: 'Escalate database migration blocker to CTO via email',
    made_by: 'Alice',
    rationale: 'Migration has been blocked for two months',
    confidence: 0.86,
  },
];

export const MOCK_RISKS: ExtractedRisk[] = [
  {
    description: 'No production React Native experience in the team',
    severity: 'high',
    is_blocker: false,
    mitigation: 'Budget for external consultants',
    confidence: 0.88,
  },
  {
    description: 'Database migration blocked for 2 months — risk of further delays',
    severity: 'critical',
    is_blocker: true,
    mitigation: 'Executive escalation required',
    confidence: 0.95,
  },
  {
    description: 'API rate limiting causing customer complaints',
    severity: 'high',
    is_blocker: false,
    mitigation: 'Implement exponential backoff',
    confidence: 0.91,
  },
];

const MOCK_TOPICS = [
  'Authentication Refactor',
  'Database Migration',
  'Mobile Platform Decision',
  'React Native Adoption',
  'API Rate Limiting',
  'Analytics Bug Fix',
];

let taskIdx = 0;
let decisionIdx = 0;
let riskIdx = 0;
let topicIdx = 0;

function nextScore(): ExecutionScore {
  const owned = Math.min(taskIdx + 1, MOCK_TASKS.length);
  const total = Math.max(owned, 1);
  const withDeadline = Math.round(owned * 0.8);
  const vague = 0;
  const blockers = riskIdx > 0 ? 1 : 0;
  const score =
    0.4 * (owned / total) +
    0.3 * (withDeadline / total) -
    0.2 * (vague / total) -
    0.1 * (blockers / total);
  return {
    score: Math.max(0, Math.min(1, score)),
    tasks_with_owner: owned,
    tasks_with_deadline: withDeadline,
    vague_count: vague,
    blocker_count: blockers,
    total_tasks: total,
  };
}

export function generateExtractionEvent(meetingId: string): LiveEvent | null {
  const tasks: ExtractedTask[] = [];
  const decisions: ExtractedDecision[] = [];
  const risks: ExtractedRisk[] = [];
  const topics: string[] = [];

  if (taskIdx < MOCK_TASKS.length && chunkIdx % 2 === 0) {
    tasks.push(MOCK_TASKS[taskIdx++]);
  }
  if (decisionIdx < MOCK_DECISIONS.length && chunkIdx % 4 === 0) {
    decisions.push(MOCK_DECISIONS[decisionIdx++]);
  }
  if (riskIdx < MOCK_RISKS.length && chunkIdx % 3 === 0) {
    risks.push(MOCK_RISKS[riskIdx++]);
  }
  if (topicIdx < MOCK_TOPICS.length && chunkIdx % 5 === 0) {
    topics.push(MOCK_TOPICS[topicIdx++]);
  }

  if (!tasks.length && !decisions.length && !risks.length && !topics.length) return null;

  const data: ExtractionData = {
    chunk_index: chunkIdx,
    meeting_id: meetingId,
    tasks,
    decisions,
    risks,
    topics,
    score: nextScore(),
  };
  return { event_type: 'extraction', meeting_id: meetingId, data };
}

export function resetMockState() {
  lineIdx = 0;
  chunkIdx = 0;
  taskIdx = 0;
  decisionIdx = 0;
  riskIdx = 0;
  topicIdx = 0;
}

// ── Mock search results ────────────────────────────────────────────────────

export const MOCK_SEARCH_RESULTS: SearchResult[] = [
  {
    meeting_id: '11111111-1111-1111-1111-111111111111',
    meeting_title: 'Q3 Product Strategy Review',
    chunk_text:
      'We decided to adopt React Native for the mobile application given our team skillset.',
    chunk_index: 7,
    similarity: 0.91,
    created_at: '2024-07-01T10:30:00Z',
    graph_context: {
      related_decisions: ['Adopt React Native over Flutter for the mobile application'],
      related_tasks: ['Create technical spec for React Native mobile app'],
    },
  },
  {
    meeting_id: '22222222-2222-2222-2222-222222222222',
    meeting_title: 'Engineering Sprint Planning',
    chunk_text:
      'The API rate limiting issue was flagged as a blocker. Client-side exponential backoff is the agreed solution.',
    chunk_index: 12,
    similarity: 0.85,
    created_at: '2024-07-02T14:45:00Z',
  },
];

// ── Mock org analytics ─────────────────────────────────────────────────────

export const MOCK_ORG_SCORE: OrgScore = {
  avg_score: 0.72,
  meetings_analyzed: 24,
  total_tasks: 87,
  open_tasks: 31,
  blocker_count: 4,
};

export const MOCK_SCORE_TREND: ScoreTrend[] = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
  score: 0.45 + Math.random() * 0.45,
  meetings: Math.floor(Math.random() * 4) + 1,
}));
