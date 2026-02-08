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


class SpeakerBuffer:
    """Buffer for a single speaker's audio"""

    def __init__(self, speaker_id: str, sample_rate: int):
        self.speaker_id = speaker_id
        self.sample_rate = sample_rate

        # Buffers
        self.vad_buffer = np.array([], dtype=np.int16)
        self.speech_buffer = np.array([], dtype=np.int16)

        # State
        self.is_speech_active = False
        self.speech_start_time = None
        self.last_speech_time = None
        self.last_activity_time = datetime.utcnow()


class AudioBuffer:
    """Manages audio buffering for VAD and ASR processing

    Accumulates audio from RTMS and creates packets for VAD (0.1s)
    and segments for ASR (2.5s) based on VAD results.

    Supports two modes:
    - Mixed mode: All speakers mixed together (single buffer)
    - Individual mode: Separate buffers per speaker
    """

    def __init__(
        self,
        sample_rate: int,
        vad_duration_ms: int,
        asr_duration_seconds: float,
        min_speech_duration_ms: int = 500,
        silence_timeout_seconds: float = 1.0,
        per_speaker_processing: bool = False
    ):
        self.logger = get_logger(__name__)
        self.sample_rate = sample_rate
        self.vad_duration_ms = vad_duration_ms
        self.asr_duration_seconds = asr_duration_seconds
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_seconds = silence_timeout_seconds
        self.per_speaker_processing = per_speaker_processing

        # Calculate sample sizes
        self.vad_packet_samples = samples_for_duration(vad_duration_ms, sample_rate)
        self.asr_segment_samples = int(asr_duration_seconds * sample_rate)

        if per_speaker_processing:
            # Per-speaker buffers (individual mode)
            self.speaker_buffers = {}  # speaker_id -> SpeakerBuffer
            self.logger.info("audio_buffer_mode", mode="individual_speakers")
        else:
            # Single shared buffers (mixed mode)
            self.vad_buffer = np.array([], dtype=np.int16)  # Accumulates to 0.1s
            self.speech_buffer = np.array([], dtype=np.int16)  # Accumulates speech for ASR

            # State tracking (for mixed mode)
            self.is_speech_active = False
            self.speech_start_time = None
            self.last_speech_time = None
            self.logger.info("audio_buffer_mode", mode="mixed_stream")

        # Callbacks
        self.vad_packet_callback: Optional[Callable] = None
        self.asr_segment_callback: Optional[Callable] = None

        self.logger.info(
            "audio_buffer_initialized",
            vad_packet_samples=self.vad_packet_samples,
            asr_segment_samples=self.asr_segment_samples,
            per_speaker_processing=per_speaker_processing
        )

    def set_vad_callback(self, callback: Callable) -> None:
        """Set callback for VAD packet ready (0.1s)"""
        self.vad_packet_callback = callback

    def set_asr_callback(self, callback: Callable) -> None:
        """Set callback for ASR segment ready (2.5s)"""
        self.asr_segment_callback = callback

    async def add_audio(
        self,
        audio_data: bytes,
        timestamp: Optional[datetime] = None,
        speaker_id: Optional[str] = None
    ) -> None:
        """Add incoming audio from RTMS

        Args:
            audio_data: Raw PCM audio bytes
            timestamp: Timestamp of audio chunk
            speaker_id: Speaker identifier (required for per-speaker processing)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Convert to numpy array
        audio_array = pcm_to_numpy(audio_data)

        if self.per_speaker_processing:
            # Individual speaker mode
            await self._add_audio_per_speaker(audio_array, timestamp, speaker_id)
        else:
            # Mixed mode
            await self._add_audio_mixed(audio_array, timestamp)

    async def _add_audio_mixed(
        self,
        audio_array: np.ndarray,
        timestamp: datetime
    ) -> None:
        """Add audio in mixed mode (all speakers combined)"""
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
                    AudioChunk(vad_packet, timestamp, speaker_id=None, sample_rate=self.sample_rate)
                )

    async def _add_audio_per_speaker(
        self,
        audio_array: np.ndarray,
        timestamp: datetime,
        speaker_id: Optional[str]
    ) -> None:
        """Add audio in per-speaker mode (separate buffers per speaker)"""
        if speaker_id is None:
            speaker_id = "unknown"

        # Get or create speaker buffer
        if speaker_id not in self.speaker_buffers:
            self.speaker_buffers[speaker_id] = SpeakerBuffer(speaker_id, self.sample_rate)
            self.logger.info("speaker_buffer_created", speaker_id=speaker_id)

        speaker_buffer = self.speaker_buffers[speaker_id]
        speaker_buffer.last_activity_time = timestamp

        # Add to speaker's VAD buffer
        speaker_buffer.vad_buffer = np.concatenate([speaker_buffer.vad_buffer, audio_array])

        # Check if we have enough for VAD packet(s)
        while len(speaker_buffer.vad_buffer) >= self.vad_packet_samples:
            # Extract VAD packet
            vad_packet = speaker_buffer.vad_buffer[:self.vad_packet_samples]
            speaker_buffer.vad_buffer = speaker_buffer.vad_buffer[self.vad_packet_samples:]

            # Send to VAD for processing with speaker_id
            if self.vad_packet_callback:
                await self.vad_packet_callback(
                    AudioChunk(vad_packet, timestamp, speaker_id=speaker_id, sample_rate=self.sample_rate)
                )

    async def on_vad_result(self, is_speech: bool, audio_chunk: AudioChunk) -> None:
        """Handle VAD result for an audio chunk

        Args:
            is_speech: Whether speech was detected
            audio_chunk: The audio chunk that was analyzed
        """
        if self.per_speaker_processing:
            await self._on_vad_result_per_speaker(is_speech, audio_chunk)
        else:
            await self._on_vad_result_mixed(is_speech, audio_chunk)

    async def _on_vad_result_mixed(self, is_speech: bool, audio_chunk: AudioChunk) -> None:
        """Handle VAD result in mixed mode"""
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
                await self._send_to_asr_mixed(audio_chunk.timestamp)

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
                        await self._send_to_asr_mixed(audio_chunk.timestamp)
                    else:
                        self.logger.debug(
                            "speech_segment_too_short",
                            duration_ms=len(self.speech_buffer) / self.sample_rate * 1000
                        )

                    # Reset speech tracking
                    self.is_speech_active = False
                    self.speech_buffer = np.array([], dtype=np.int16)

    async def _on_vad_result_per_speaker(self, is_speech: bool, audio_chunk: AudioChunk) -> None:
        """Handle VAD result in per-speaker mode"""
        speaker_id = audio_chunk.speaker_id or "unknown"

        if speaker_id not in self.speaker_buffers:
            self.logger.warning("vad_result_for_unknown_speaker", speaker_id=speaker_id)
            return

        speaker_buffer = self.speaker_buffers[speaker_id]
        current_time = datetime.utcnow()

        if is_speech:
            # Speech detected for this speaker
            if not speaker_buffer.is_speech_active:
                speaker_buffer.is_speech_active = True
                speaker_buffer.speech_start_time = current_time
                self.logger.debug(
                    "speech_started",
                    speaker_id=speaker_id,
                    timestamp=current_time.isoformat()
                )

            speaker_buffer.last_speech_time = current_time

            # Add to speaker's speech buffer
            speaker_buffer.speech_buffer = np.concatenate([
                speaker_buffer.speech_buffer,
                audio_chunk.data
            ])

            # Check if we have enough for ASR (2.5s)
            if len(speaker_buffer.speech_buffer) >= self.asr_segment_samples:
                await self._send_to_asr_per_speaker(speaker_id, audio_chunk.timestamp)

        else:
            # No speech detected for this speaker
            if speaker_buffer.is_speech_active:
                # Check if silence timeout exceeded
                silence_duration = (current_time - speaker_buffer.last_speech_time).total_seconds()

                if silence_duration >= self.silence_timeout_seconds:
                    # End of speech segment for this speaker
                    self.logger.debug(
                        "speech_ended",
                        speaker_id=speaker_id,
                        silence_duration=silence_duration,
                        buffer_samples=len(speaker_buffer.speech_buffer)
                    )

                    # Send remaining speech to ASR if above minimum duration
                    min_samples = samples_for_duration(
                        self.min_speech_duration_ms,
                        self.sample_rate
                    )

                    if len(speaker_buffer.speech_buffer) >= min_samples:
                        await self._send_to_asr_per_speaker(speaker_id, audio_chunk.timestamp)
                    else:
                        self.logger.debug(
                            "speech_segment_too_short",
                            speaker_id=speaker_id,
                            duration_ms=len(speaker_buffer.speech_buffer) / self.sample_rate * 1000
                        )

                    # Reset speech tracking for this speaker
                    speaker_buffer.is_speech_active = False
                    speaker_buffer.speech_buffer = np.array([], dtype=np.int16)

    async def _send_to_asr_mixed(self, timestamp: datetime) -> None:
        """Send accumulated speech buffer to ASR (mixed mode)

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
            duration_seconds=duration_seconds,
            mode="mixed"
        )

        # Send to ASR callback
        if self.asr_segment_callback:
            await self.asr_segment_callback(
                AudioChunk(segment, timestamp, speaker_id=None, sample_rate=self.sample_rate)
            )

    async def _send_to_asr_per_speaker(self, speaker_id: str, timestamp: datetime) -> None:
        """Send accumulated speech buffer to ASR (per-speaker mode)

        Args:
            speaker_id: Speaker identifier
            timestamp: Timestamp of the audio segment
        """
        if speaker_id not in self.speaker_buffers:
            return

        speaker_buffer = self.speaker_buffers[speaker_id]

        if len(speaker_buffer.speech_buffer) == 0:
            return

        # Extract segment (up to asr_segment_samples)
        segment = speaker_buffer.speech_buffer[:self.asr_segment_samples]
        speaker_buffer.speech_buffer = speaker_buffer.speech_buffer[self.asr_segment_samples:]

        duration_seconds = len(segment) / self.sample_rate
        self.logger.info(
            "sending_to_asr",
            speaker_id=speaker_id,
            samples=len(segment),
            duration_seconds=duration_seconds,
            mode="per_speaker"
        )

        # Send to ASR callback with speaker_id
        if self.asr_segment_callback:
            await self.asr_segment_callback(
                AudioChunk(segment, timestamp, speaker_id=speaker_id, sample_rate=self.sample_rate)
            )

    async def flush(self) -> None:
        """Flush remaining audio in buffers"""
        if self.per_speaker_processing:
            # Flush all speaker buffers
            for speaker_id, speaker_buffer in self.speaker_buffers.items():
                if len(speaker_buffer.speech_buffer) > 0:
                    min_samples = samples_for_duration(
                        self.min_speech_duration_ms,
                        self.sample_rate
                    )

                    if len(speaker_buffer.speech_buffer) >= min_samples:
                        await self._send_to_asr_per_speaker(speaker_id, datetime.utcnow())

            self.logger.info(
                "audio_buffer_flushed",
                mode="per_speaker",
                speakers_flushed=len(self.speaker_buffers)
            )
        else:
            # Flush mixed buffer
            if len(self.speech_buffer) > 0:
                min_samples = samples_for_duration(
                    self.min_speech_duration_ms,
                    self.sample_rate
                )

                if len(self.speech_buffer) >= min_samples:
                    await self._send_to_asr_mixed(datetime.utcnow())

            self.logger.info("audio_buffer_flushed", mode="mixed")
