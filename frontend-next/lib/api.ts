import type { Meeting, SearchResult, OrgScore, ScoreTrend } from './types';

const API_BASE =
  typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? `${window.location.protocol}//${window.location.host}`
    : (process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8128');

export const WS_BASE = API_BASE.replace(/^http/, 'ws');

// ── Auth ──────────────────────────────────────────────────────────────────

let _token: string | null = null;

export async function getToken(): Promise<string> {
  if (_token) return _token;
  const res = await fetch(`${API_BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: 'demo@aiexec.com', password: 'demo1234' }),
  });
  if (!res.ok) throw new Error('Auth failed — create demo user first');
  const data = await res.json();
  _token = data.access_token as string;
  return _token;
}

export function clearToken() { _token = null; }

// ── Meetings ───────────────────────────────────────────────────────────────

export async function listMeetings(): Promise<Meeting[]> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/meetings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch meetings');
  return res.json();
}

export async function getMeeting(id: string): Promise<Meeting> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/meetings/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Meeting ${id} not found`);
  return res.json();
}

export async function createMeeting(title: string): Promise<Meeting> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/meetings`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create meeting');
  return res.json();
}

// ── Search ─────────────────────────────────────────────────────────────────

export async function hybridSearch(
  query: string,
  k = 10,
  useGraph = true,
): Promise<SearchResult[]> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k, use_graph: useGraph }),
  });
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

// ── Analytics ──────────────────────────────────────────────────────────────

export async function getOrgScore(): Promise<OrgScore> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/org/score`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch org score');
  return res.json();
}

export async function getScoreTrend(days = 30): Promise<ScoreTrend[]> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/org/score/trend?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch score trend');
  return res.json();
}

// ── Health ─────────────────────────────────────────────────────────────────

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
