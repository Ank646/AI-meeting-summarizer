import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type {
  AppMode,
  ConnectionStatus,
  TranscriptData,
  ExtractedTask,
  ExtractedDecision,
  ExtractedRisk,
  ExecutionScore,
  EventLogEntry,
  Meeting,
} from '@/lib/types';

interface AppState {
  // ── Mode ──────────────────────────────────────────────────────────────
  mode: AppMode;
  setMode: (m: AppMode) => void;

  // ── Active meeting ─────────────────────────────────────────────────────
  meetingId: string;
  setMeetingId: (id: string) => void;

  // ── Connection ─────────────────────────────────────────────────────────
  connectionStatus: ConnectionStatus;
  setConnectionStatus: (s: ConnectionStatus) => void;

  // ── Transcript ─────────────────────────────────────────────────────────
  utterances: TranscriptData['utterances'];
  addUtterances: (u: TranscriptData['utterances'], stable: boolean) => void;
  clearTranscript: () => void;

  // ── Extractions ────────────────────────────────────────────────────────
  tasks: ExtractedTask[];
  decisions: ExtractedDecision[];
  risks: ExtractedRisk[];
  topics: Set<string>;
  score: ExecutionScore | null;
  addTasks: (items: ExtractedTask[]) => void;
  addDecisions: (items: ExtractedDecision[]) => void;
  addRisks: (items: ExtractedRisk[]) => void;
  addTopics: (items: string[]) => void;
  setScore: (s: ExecutionScore) => void;
  clearExtractions: () => void;

  // ── Event log ──────────────────────────────────────────────────────────
  eventLog: EventLogEntry[];
  logEvent: (msg: string) => void;
  clearLog: () => void;

  // ── Meetings list ──────────────────────────────────────────────────────
  meetings: Meeting[];
  setMeetings: (m: Meeting[]) => void;

  // ── Reset all live state ───────────────────────────────────────────────
  resetLiveState: () => void;
}

export const useAppStore = create<AppState>()(
  immer((set) => ({
    // Mode
    mode: 'test',
    setMode: (m) => set((s) => { s.mode = m; }),

    // Meeting
    meetingId: '',
    setMeetingId: (id) => set((s) => { s.meetingId = id; }),

    // Connection
    connectionStatus: 'disconnected',
    setConnectionStatus: (status) => set((s) => { s.connectionStatus = status; }),

    // Transcript
    utterances: [],
    addUtterances: (u, stable) =>
      set((s) => {
        // Cap at 500 utterances to avoid memory bloat
        const combined = [...s.utterances, ...u];
        s.utterances = combined.slice(-500);
      }),
    clearTranscript: () => set((s) => { s.utterances = []; }),

    // Extractions
    tasks: [],
    decisions: [],
    risks: [],
    topics: new Set(),
    score: null,
    addTasks: (items) => set((s) => { s.tasks.push(...items); }),
    addDecisions: (items) => set((s) => { s.decisions.push(...items); }),
    addRisks: (items) => set((s) => { s.risks.push(...items); }),
    addTopics: (items) =>
      set((s) => {
        items.forEach((t) => s.topics.add(t));
      }),
    setScore: (score) => set((s) => { s.score = score; }),
    clearExtractions: () =>
      set((s) => {
        s.tasks = [];
        s.decisions = [];
        s.risks = [];
        s.topics = new Set();
        s.score = null;
      }),

    // Event log
    eventLog: [],
    logEvent: (msg) =>
      set((s) => {
        s.eventLog.unshift({
          ts: new Date().toLocaleTimeString(),
          msg,
        });
        if (s.eventLog.length > 100) s.eventLog.pop();
      }),
    clearLog: () => set((s) => { s.eventLog = []; }),

    // Meetings list
    meetings: [],
    setMeetings: (m) => set((s) => { s.meetings = m; }),

    // Reset live state
    resetLiveState: () =>
      set((s) => {
        s.utterances = [];
        s.tasks = [];
        s.decisions = [];
        s.risks = [];
        s.topics = new Set();
        s.score = null;
        s.eventLog = [];
        s.connectionStatus = 'disconnected';
      }),
  })),
);
