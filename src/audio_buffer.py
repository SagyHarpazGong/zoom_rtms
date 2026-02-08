"""Audio buffering and accumulation for VAD and ASR processing"""

import asyncio
from typing import Optional, Callable
import numpy as np
from dataclasses import dataclass
from datetime import datetime

from .utils import get_logger, pcm_to_numpy, samples_for_duration


@dataclass
class AudioChunk:
    """Represents a chunk of audio data with metadata"""
    data: np.ndarray
    timestamp: datetime
    speaker_id: Optional[str] = None
    sample_rate: int = 16000


class AudioBuffer:
    """Manages audio buffering for VAD and ASR processing

    Accumulates audio from RTMS and creates packets for VAD (0.1s)
    and segments for ASR (2.5s) based on VAD results.
    """

    def __init__(
        self,
        sample_rate: int,
        vad_duration_ms: int,
        asr_duration_seconds: float,
        min_speech_duration_ms: int = 500,
        silence_timeout_seconds: float = 1.0
    ):
        self.logger = get_logger(__name__)
        self.sample_rate = sample_rate
        self.vad_duration_ms = vad_duration_ms
        self.asr_duration_seconds = asr_duration_seconds
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_seconds = silence_timeout_seconds

        # Calculate sample sizes
        self.vad_packet_samples = samples_for_duration(vad_duration_ms, sample_rate)
        self.asr_segment_samples = int(asr_duration_seconds * sample_rate)

        # Buffers for each processing stage
        self.vad_buffer = np.array([], dtype=np.int16)  # Accumulates to 0.1s
        self.speech_buffer = np.array([], dtype=np.int16)  # Accumulates speech for ASR

        # State tracking
        self.is_speech_active = False
        self.speech_start_time = None
        self.last_speech_time = None

        # Callbacks
        self.vad_packet_callback: Optional[Callable] = None
        self.asr_segment_callback: Optional[Callable] = None

        self.logger.info(
            "audio_buffer_initialized",
            vad_packet_samples=self.vad_packet_samples,
            asr_segment_samples=self.asr_segment_samples
        )

    def set_vad_callback(self, callback: Callable) -> None:
        """Set callback for VAD packet ready (0.1s)"""
        self.vad_packet_callback = callback

    def set_asr_callback(self, callback: Callable) -> None:
        """Set callback for ASR segment ready (2.5s)"""
        self.asr_segment_callback = callback

    async def add_audio(self, audio_data: bytes, timestamp: Optional[datetime] = None) -> None:
        """Add incoming audio from RTMS

        Args:
            audio_data: Raw PCM audio bytes
            timestamp: Timestamp of audio chunk
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Convert to numpy array
        audio_array = pcm_to_numpy(audio_data)

        # Add to VAD buffer
        self.vad_buffer = np.concatenate([self.vad_buffer, audio_array])

        # Check if we have enough for VAD packet(s)
        while len(self.vad_buffer) >= self.vad_packet_samples:
            # Extract VAD packet
            vad_packet = self.vad_buffer[:self.vad_packet_samples]
            self.vad_buffer = self.vad_buffer[self.vad_packet_samples:]

            # Send to VAD for processing
            if self.vad_packet_callback:
                await self.vad_packet_callback(
                    AudioChunk(vad_packet, timestamp, sample_rate=self.sample_rate)
                )

    async def on_vad_result(self, is_speech: bool, audio_chunk: AudioChunk) -> None:
        """Handle VAD result for an audio chunk

        Args:
            is_speech: Whether speech was detected
            audio_chunk: The audio chunk that was analyzed
        """
        current_time = datetime.utcnow()

        if is_speech:
            # Speech detected
            if not self.is_speech_active:
                self.is_speech_active = True
                self.speech_start_time = current_time
                self.logger.debug("speech_started", timestamp=current_time.isoformat())

            self.last_speech_time = current_time

            # Add to speech buffer
            self.speech_buffer = np.concatenate([self.speech_buffer, audio_chunk.data])

            # Check if we have enough for ASR (2.5s)
            if len(self.speech_buffer) >= self.asr_segment_samples:
                await self._send_to_asr(audio_chunk.timestamp)

        else:
            # No speech detected
            if self.is_speech_active:
                # Check if silence timeout exceeded
                silence_duration = (current_time - self.last_speech_time).total_seconds()

                if silence_duration >= self.silence_timeout_seconds:
                    # End of speech segment
                    self.logger.debug(
                        "speech_ended",
                        silence_duration=silence_duration,
                        buffer_samples=len(self.speech_buffer)
                    )

                    # Send remaining speech to ASR if above minimum duration
                    min_samples = samples_for_duration(
                        self.min_speech_duration_ms,
                        self.sample_rate
                    )

                    if len(self.speech_buffer) >= min_samples:
                        await self._send_to_asr(audio_chunk.timestamp)
                    else:
                        self.logger.debug(
                            "speech_segment_too_short",
                            duration_ms=len(self.speech_buffer) / self.sample_rate * 1000
                        )

                    # Reset speech tracking
                    self.is_speech_active = False
                    self.speech_buffer = np.array([], dtype=np.int16)

    async def _send_to_asr(self, timestamp: datetime) -> None:
        """Send accumulated speech buffer to ASR

        Args:
            timestamp: Timestamp of the audio segment
        """
        if len(self.speech_buffer) == 0:
            return

        # Extract segment (up to asr_segment_samples)
        segment = self.speech_buffer[:self.asr_segment_samples]
        self.speech_buffer = self.speech_buffer[self.asr_segment_samples:]

        duration_seconds = len(segment) / self.sample_rate
        self.logger.info(
            "sending_to_asr",
            samples=len(segment),
            duration_seconds=duration_seconds
        )

        # Send to ASR callback
        if self.asr_segment_callback:
            await self.asr_segment_callback(
                AudioChunk(segment, timestamp, sample_rate=self.sample_rate)
            )

    async def flush(self) -> None:
        """Flush remaining audio in buffers"""
        if len(self.speech_buffer) > 0:
            min_samples = samples_for_duration(
                self.min_speech_duration_ms,
                self.sample_rate
            )

            if len(self.speech_buffer) >= min_samples:
                await self._send_to_asr(datetime.utcnow())

        self.logger.info("audio_buffer_flushed")
