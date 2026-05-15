'use client';
import { useRef, useCallback } from 'react';
import { useAppStore } from '@/store/appStore';
import { getToken, WS_BASE } from '@/lib/api';

export function useMicrophone(meetingId: string) {
  const audioWsRef    = useRef<WebSocket | null>(null);
  const audioCtxRef   = useRef<AudioContext | null>(null);
  const processorRef  = useRef<ScriptProcessorNode | null>(null);
  const streamRef     = useRef<MediaStream | null>(null);

  const setConnectionStatus = useAppStore((s) => s.setConnectionStatus);
  const logEvent             = useAppStore((s) => s.logEvent);

  const float32ToInt16 = (f32: Float32Array): Int16Array => {
    const out = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      out[i] = Math.max(-32768, Math.min(32767, Math.round(f32[i] * 32767)));
    }
    return out;
  };

  const startMic = useCallback(async () => {
    if (!meetingId) { logEvent('No meeting selected'); return; }

    let token: string;
    try { token = await getToken(); }
    catch (e) { logEvent(`Auth error: ${(e as Error).message}`); return; }

    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      logEvent(`Mic denied: ${(e as Error).message}`);
      return;
    }

    const audioWs = new WebSocket(`${WS_BASE}/ws/audio/${meetingId}?token=${token}`);
    audioWs.binaryType = 'arraybuffer';
    audioWs.onopen  = () => logEvent('Audio stream connected');
    audioWs.onclose = () => logEvent('Audio stream disconnected');
    audioWsRef.current = audioWs;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext) as typeof AudioContext;
    const ctx = new AudioCtx({ sampleRate: 16000 });
    audioCtxRef.current = ctx;

    const source    = ctx.createMediaStreamSource(streamRef.current);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (audioWs.readyState !== WebSocket.OPEN) return;
      const pcm = float32ToInt16(e.inputBuffer.getChannelData(0));
      audioWs.send(pcm.buffer);
    };

    source.connect(processor);
    processor.connect(ctx.destination);

    setConnectionStatus('recording');
    logEvent('Microphone started');
  }, [meetingId, setConnectionStatus, logEvent]);

  const stopMic = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioWsRef.current?.close();
    audioWsRef.current = null;

    setConnectionStatus('connected');
    logEvent('Microphone stopped');
  }, [setConnectionStatus, logEvent]);

  return { startMic, stopMic };
}
