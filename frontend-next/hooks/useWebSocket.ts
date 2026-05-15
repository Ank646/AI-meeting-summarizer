'use client';
import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import { getToken, WS_BASE } from '@/lib/api';
import type { LiveEvent, ExtractionData, TranscriptData } from '@/lib/types';

export function useWebSocket(meetingId: string) {
  const wsRef = useRef<WebSocket | null>(null);

  const setConnectionStatus = useAppStore((s) => s.setConnectionStatus);
  const logEvent             = useAppStore((s) => s.logEvent);
  const addUtterances        = useAppStore((s) => s.addUtterances);
  const addTasks             = useAppStore((s) => s.addTasks);
  const addDecisions         = useAppStore((s) => s.addDecisions);
  const addRisks             = useAppStore((s) => s.addRisks);
  const addTopics            = useAppStore((s) => s.addTopics);
  const setScore             = useAppStore((s) => s.setScore);

  const handleEvent = useCallback((event: LiveEvent) => {
    logEvent(`[${event.event_type}]`);
    switch (event.event_type) {
      case 'transcript': {
        const d = event.data as TranscriptData;
        addUtterances(d.utterances, d.is_stable);
        break;
      }
      case 'extraction': {
        const d = event.data as ExtractionData;
        if (d.tasks?.length)     addTasks(d.tasks);
        if (d.decisions?.length) addDecisions(d.decisions);
        if (d.risks?.length)     addRisks(d.risks);
        if (d.topics?.length)    addTopics(d.topics);
        if (d.score)             setScore(d.score);
        break;
      }
      case 'connected': {
        const d = event.data as { message?: string };
        logEvent(d.message ?? 'connected');
        break;
      }
      case 'pass2_complete':
        logEvent('Pass-2 analysis complete');
        break;
      default:
        break;
    }
  }, [logEvent, addUtterances, addTasks, addDecisions, addRisks, addTopics, setScore]);

  const connect = useCallback(async () => {
    if (!meetingId) return;
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }

    setConnectionStatus('connecting');
    logEvent(`Connecting to meeting ${meetingId.slice(0, 8)}…`);

    let token: string;
    try {
      token = await getToken();
    } catch (e) {
      logEvent(`Auth error: ${(e as Error).message}`);
      setConnectionStatus('disconnected');
      return;
    }

    const ws = new WebSocket(`${WS_BASE}/ws/dashboard/${meetingId}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      logEvent('WebSocket connected');
    };
    ws.onclose = () => {
      setConnectionStatus('disconnected');
      logEvent('WebSocket disconnected');
    };
    ws.onerror = () => logEvent('WebSocket error');
    ws.onmessage = (e) => {
      try { handleEvent(JSON.parse(e.data as string) as LiveEvent); }
      catch { logEvent('Parse error'); }
    };
  }, [meetingId, setConnectionStatus, logEvent, handleEvent]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => () => { wsRef.current?.close(); }, []);

  return { connect, disconnect };
}
