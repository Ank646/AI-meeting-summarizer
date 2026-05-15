"""
Voice Activity Detection using WebRTC VAD.
Filters non-speech frames before passing audio to Whisper,
reducing hallucinations and saving compute.
"""

import webrtcvad
import numpy as np
from typing import List, Tuple
import structlog

logger = structlog.get_logger()

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20                                      # VAD works on 10/20/30ms
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) # 320 samples


class VoiceActivityDetector:
    """
    WebRTC VAD wrapper.
    aggressiveness: 0 (least aggressive) → 3 (most aggressive)
    Higher aggressiveness → more background noise filtered → may clip quiet speech
    """

    def __init__(self, aggressiveness: int = 2):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.aggressiveness = aggressiveness

    def is_speech_frame(self, frame_bytes: bytes) -> bool:
        """Check if a 20ms PCM frame contains speech."""
        try:
            return self.vad.is_speech(frame_bytes, SAMPLE_RATE)
        except Exception:
            return True   # default: pass through on error

    def filter_speech(
        self,
        audio: np.ndarray,
        padding_ms: int = 300,
    ) -> Tuple[np.ndarray, List[Tuple[float, float]]]:
        """
        Extract speech-only segments from audio.

        Returns:
          - speech_audio: float32 array with silence removed
          - segments: list of (start_sec, end_sec) speech intervals

        Uses a ring-buffer approach to pad speech boundaries and avoid
        clipping the beginning/end of words.
        """
        padding_frames = padding_ms // FRAME_DURATION_MS
        frames = list(self._frame_generator(audio))

        if not frames:
            return audio, []

        voiced_frames = []
        speech_segments = []
        ring_buffer: List[Tuple[bytes, int, bool]] = []
        in_speech = False
        speech_start_idx = 0

        for frame_idx, frame_bytes in enumerate(frames):
            is_speech = self.is_speech_frame(frame_bytes)
            ring_buffer.append((frame_bytes, frame_idx, is_speech))

            if not in_speech:
                num_voiced = sum(1 for _, _, s in ring_buffer[-padding_frames:] if s)
                if len(ring_buffer) >= padding_frames and num_voiced > padding_frames * 0.6:
                    in_speech = True
                    speech_start_idx = ring_buffer[0][1]
                    for fb, _, _ in ring_buffer:
                        voiced_frames.append(fb)
                    ring_buffer = []
            else:
                voiced_frames.append(frame_bytes)
                num_unvoiced = sum(1 for _, _, s in ring_buffer[-padding_frames:] if not s)
                if len(ring_buffer) >= padding_frames and num_unvoiced > padding_frames * 0.9:
                    speech_end_sec = frame_idx * FRAME_SAMPLES / SAMPLE_RATE
                    speech_start_sec = speech_start_idx * FRAME_SAMPLES / SAMPLE_RATE
                    speech_segments.append((speech_start_sec, speech_end_sec))
                    in_speech = False
                    ring_buffer = []

        # Close any open segment
        if in_speech and voiced_frames:
            speech_end_sec = len(frames) * FRAME_SAMPLES / SAMPLE_RATE
            speech_start_sec = speech_start_idx * FRAME_SAMPLES / SAMPLE_RATE
            speech_segments.append((speech_start_sec, speech_end_sec))

        if not voiced_frames:
            logger.debug("VAD: no speech detected, returning original audio")
            return audio, []

        # Reconstruct speech-only audio
        combined = b"".join(voiced_frames)
        speech_array = np.frombuffer(combined, dtype=np.int16).astype(np.float32) / 32768.0
        return speech_array, speech_segments

    def _frame_generator(self, audio: np.ndarray):
        """Yield 20ms PCM int16 frames from a float32 audio array."""
        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        for start in range(0, len(audio_int16) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
            yield audio_int16[start: start + FRAME_SAMPLES].tobytes()
