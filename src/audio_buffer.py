"""Audio buffering for creating VAD packets from RTMS audio.

Accumulates incoming 20ms RTMS audio frames and produces 0.1s packets
for VAD processing. Supports both mixed and per-speaker modes.

Speech accumulation and ASR triggering are handled by SpeechProcessor.
"""

import asyncio
from typing import Optional, Callable
import numpy as np
from dataclasses import dataclass
from datetime import datetime

from .utils import get_logger, pcm_to_numpy, samples_for_duration


@dataclass
class AudioChunk:
    """Represents a chunk of audio data with metadata."""
    data: np.ndarray
    timestamp: datetime
    speaker_id: Optional[str] = None
    sample_rate: int = 16000


class SpeakerBuffer:
    """Buffer for a single speaker's VAD accumulation."""

    def __init__(self, speaker_id: str, sample_rate: int):
        self.speaker_id = speaker_id
        self.sample_rate = sample_rate
        self.vad_buffer = np.array([], dtype=np.int16)
        self.last_activity_time = datetime.utcnow()


class AudioBuffer:
    """Manages audio buffering to create 0.1s VAD packets.

    Accumulates audio from RTMS (20ms frames) and creates 0.1s packets
    for VAD processing via callback.

    Supports two modes:
    - Mixed mode: All speakers mixed into one stream
    - Individual mode: Separate buffers per speaker
    """

    def __init__(
        self,
        sample_rate: int,
        vad_duration_ms: int,
        per_speaker_processing: bool = False,
    ):
        self.logger = get_logger(__name__)
        self.sample_rate = sample_rate
        self.vad_duration_ms = vad_duration_ms
        self.per_speaker_processing = per_speaker_processing

        # Calculate sample size for VAD packets
        self.vad_packet_samples = samples_for_duration(vad_duration_ms, sample_rate)

        if per_speaker_processing:
            self.speaker_buffers = {}  # speaker_id -> SpeakerBuffer
            self.logger.info("audio_buffer_mode", mode="individual_speakers")
        else:
            self.vad_buffer = np.array([], dtype=np.int16)
            self.logger.info("audio_buffer_mode", mode="mixed_stream")

        # Callback for VAD packets
        self.vad_packet_callback: Optional[Callable] = None

        self.logger.info(
            "audio_buffer_initialized",
            vad_packet_samples=self.vad_packet_samples,
            per_speaker_processing=per_speaker_processing,
        )

    def set_vad_callback(self, callback: Callable) -> None:
        """Set callback for VAD packet ready (0.1s)."""
        self.vad_packet_callback = callback

    async def add_audio(
        self,
        audio_data: bytes,
        timestamp: Optional[datetime] = None,
        speaker_id: Optional[str] = None,
    ) -> None:
        """Add incoming audio from RTMS.

        Args:
            audio_data: Raw PCM audio bytes.
            timestamp: Timestamp of audio chunk.
            speaker_id: Speaker identifier (for per-speaker mode).
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        audio_array = pcm_to_numpy(audio_data)

        if self.per_speaker_processing:
            await self._add_audio_per_speaker(audio_array, timestamp, speaker_id)
        else:
            await self._add_audio_mixed(audio_array, timestamp)

    async def _add_audio_mixed(
        self,
        audio_array: np.ndarray,
        timestamp: datetime,
    ) -> None:
        """Add audio in mixed mode (all speakers combined)."""
        self.vad_buffer = np.concatenate([self.vad_buffer, audio_array])

        while len(self.vad_buffer) >= self.vad_packet_samples:
            vad_packet = self.vad_buffer[:self.vad_packet_samples]
            self.vad_buffer = self.vad_buffer[self.vad_packet_samples:]

            if self.vad_packet_callback:
                await self.vad_packet_callback(
                    AudioChunk(vad_packet, timestamp, speaker_id=None, sample_rate=self.sample_rate)
                )

    async def _add_audio_per_speaker(
        self,
        audio_array: np.ndarray,
        timestamp: datetime,
        speaker_id: Optional[str],
    ) -> None:
        """Add audio in per-speaker mode (separate buffers per speaker)."""
        if speaker_id is None:
            speaker_id = "unknown"

        if speaker_id not in self.speaker_buffers:
            self.speaker_buffers[speaker_id] = SpeakerBuffer(speaker_id, self.sample_rate)
            self.logger.info("speaker_buffer_created", speaker_id=speaker_id)

        speaker_buffer = self.speaker_buffers[speaker_id]
        speaker_buffer.last_activity_time = timestamp
        speaker_buffer.vad_buffer = np.concatenate([speaker_buffer.vad_buffer, audio_array])

        while len(speaker_buffer.vad_buffer) >= self.vad_packet_samples:
            vad_packet = speaker_buffer.vad_buffer[:self.vad_packet_samples]
            speaker_buffer.vad_buffer = speaker_buffer.vad_buffer[self.vad_packet_samples:]

            if self.vad_packet_callback:
                await self.vad_packet_callback(
                    AudioChunk(vad_packet, timestamp, speaker_id=speaker_id, sample_rate=self.sample_rate)
                )

    async def flush(self) -> None:
        """Clear remaining audio in buffers."""
        if self.per_speaker_processing:
            for speaker_buffer in self.speaker_buffers.values():
                speaker_buffer.vad_buffer = np.array([], dtype=np.int16)
            self.logger.info("audio_buffer_flushed", mode="per_speaker")
        else:
            self.vad_buffer = np.array([], dtype=np.int16)
            self.logger.info("audio_buffer_flushed", mode="mixed")
