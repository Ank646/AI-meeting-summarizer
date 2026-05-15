"""
Audio preprocessor: converts raw audio bytes or PCM frames to
16 kHz mono float32 numpy arrays with noise reduction applied.
"""

import asyncio
import io
import numpy as np
import noisereduce as nr
import soundfile as sf
import structlog

logger = structlog.get_logger()

TARGET_SR = 16000


class AudioPreprocessor:
    """
    Pipeline:
      1. Format conversion via ffmpeg  (any format → 16kHz mono WAV)
      2. Stereo collapse               (mean channels)
      3. Peak normalization            (-3 dBFS)
      4. Noise reduction               (spectral subtraction)
    """

    async def preprocess_bytes(
        self, audio_bytes: bytes, source_format: str = "webm"
    ) -> np.ndarray:
        """
        Convert arbitrary audio bytes to 16kHz mono float32.
        source_format: 'webm', 'mp4', 'ogg', 'mp3', 'wav', etc.
        """
        wav_bytes = await self._ffmpeg_convert(audio_bytes, source_format)
        audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")

        if audio.ndim > 1:
            audio = audio.mean(axis=1)   # stereo → mono

        audio = self._normalize(audio)
        audio = self._reduce_noise(audio, sr)
        return audio

    async def preprocess_pcm(self, pcm_bytes: bytes) -> np.ndarray:
        """
        Process raw s16le PCM frames streamed from the browser WebSocket.
        Assumes 16kHz mono 16-bit signed integer little-endian.
        """
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0     # scale to [-1.0, 1.0]
        audio = self._normalize(audio)
        return audio

    async def _ffmpeg_convert(self, audio_bytes: bytes, source_format: str) -> bytes:
        """Run ffmpeg to re-encode audio to 16kHz mono WAV."""
        cmd = [
            "ffmpeg", "-v", "quiet",
            "-f", source_format,
            "-i", "pipe:0",
            "-ar", str(TARGET_SR),
            "-ac", "1",
            "-acodec", "pcm_s16le",
            "-f", "wav",
            "pipe:1",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=audio_bytes)
        if proc.returncode != 0:
            logger.error("ffmpeg conversion failed", stderr=stderr.decode(errors="ignore"))
            raise RuntimeError(f"ffmpeg error: {stderr.decode(errors='ignore')[:200]}")
        return stdout

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Peak-normalize to ~-3 dBFS (0.708 linear)."""
        peak = np.abs(audio).max()
        if peak > 1e-6:
            audio = audio / peak * 0.708
        return audio

    def _reduce_noise(self, audio: np.ndarray, sr: int = TARGET_SR) -> np.ndarray:
        """
        Spectral subtraction noise reduction.
        Uses the first 500ms as the noise profile.
        Skips if audio is too short or reduction fails.
        """
        try:
            noise_samples = sr // 2      # 500ms
            if len(audio) > noise_samples * 2:
                noise_clip = audio[:noise_samples]
                reduced = nr.reduce_noise(
                    y=audio,
                    sr=sr,
                    y_noise=noise_clip,
                    stationary=False,
                    prop_decrease=0.75,
                    n_fft=512,
                )
                return reduced
        except Exception as e:
            logger.debug("Noise reduction skipped", reason=str(e))
        return audio
