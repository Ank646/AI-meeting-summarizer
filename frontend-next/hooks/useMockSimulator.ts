'use client';
import { useRef, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import {
  generateTranscriptEvent,
  generateExtractionEvent,
  resetMockState,
} from '@/lib/mockData';
import type { ExtractionData, TranscriptData } from '@/lib/types';

const TRANSCRIPT_INTERVAL_MS = 2000;
const EXTRACTION_INTERVAL_MS = 4000;

export function useMockSimulator(meetingId: string) {
  const transcriptTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const extractionTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const setConnectionStatus = useAppStore((s) => s.setConnectionStatus);
  const logEvent             = useAppStore((s) => s.logEvent);
  const addUtterances        = useAppStore((s) => s.addUtterances);
  const addTasks             = useAppStore((s) => s.addTasks);
  const addDecisions         = useAppStore((s) => s.addDecisions);
  const addRisks             = useAppStore((s) => s.addRisks);
  const addTopics            = useAppStore((s) => s.addTopics);
  const setScore             = useAppStore((s) => s.setScore);

  const startSimulation = useCallback(() => {
    const id = meetingId || 'mock-meeting-id';
    resetMockState();
    setConnectionStatus('recording');
    logEvent('[TEST] Simulation started');

    transcriptTimer.current = setInterval(() => {
      const event = generateTranscriptEvent(id);
      const d = event.data as TranscriptData;
      addUtterances(d.utterances, d.is_stable);
      logEvent(`[transcript] chunk=${d.chunk_index}`);
    }, TRANSCRIPT_INTERVAL_MS);

    extractionTimer.current = setInterval(() => {
      const event = generateExtractionEvent(id);
      if (!event) return;
      const d = event.data as ExtractionData;
      if (d.tasks?.length)     addTasks(d.tasks);
      if (d.decisions?.length) addDecisions(d.decisions);
      if (d.risks?.length)     addRisks(d.risks);
      if (d.topics?.length)    addTopics(d.topics);
      if (d.score)             setScore(d.score);
      logEvent(`[extraction] +${d.tasks.length}t +${d.decisions.length}d +${d.risks.length}r`);
    }, EXTRACTION_INTERVAL_MS);
  }, [meetingId, setConnectionStatus, logEvent, addUtterances, addTasks, addDecisions, addRisks, addTopics, setScore]);

  const stopSimulation = useCallback(() => {
    if (transcriptTimer.current) { clearInterval(transcriptTimer.current); transcriptTimer.current = null; }
    if (extractionTimer.current) { clearInterval(extractionTimer.current); extractionTimer.current = null; }
    setConnectionStatus('disconnected');
    logEvent('[TEST] Simulation stopped');
  }, [setConnectionStatus, logEvent]);

  return { startSimulation, stopSimulation };
}
