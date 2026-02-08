"""Per-speaker speech processor and shared conversation context.

Adapted from remove_later/src/asr_server.py (OnlineASRServer).

Architecture for multi-speaker:
- One SharedConversationContext per meeting (shared across all speakers)
  Holds: recog_sent_history, all committed words from all speakers
- One SpeechProcessor per speaker (individual mode) or one shared (mixed mode)
  Holds: audio buffer, hypothesis buffer, speech state, per-speaker committed words

The reference implementation (remove_later/) is mono — one audio stream, one ASR server.
In our multi-speaker case, each speaker is an individual mono stream processed independently,
but the conversation context (prompt + recog_sent_history) is shared so that speaker A's
committed words improve ASR accuracy for speaker B.
"""

import re
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

from .utils import get_logger
from .hypothesis_buffer import HypothesisBuffer
from .asr_client import ASRClient

logger = get_logger(__name__)


class SharedConversationContext:
    """Shared conversation context across all speakers in a meeting.

    Collects committed words from ALL speakers and maintains a unified
    recog_sent_history. Used by each SpeechProcessor to build ASR prompts
    with full conversation context, not just the current speaker's history.

    In the reference mono implementation, a single OnlineASRServer holds both
    the audio buffer and the conversation context. In multi-speaker mode we
    split them: audio/hypothesis stay per-speaker, conversation context is shared.
    """

    def __init__(self, history_size: int = 30):
        self.history_size = history_size

        # All committed words from all speakers, chronologically ordered.
        # Tuple: (start_time, end_time, text, speaker_id)
        self.all_committed_words: List[Tuple[float, float, str, Optional[str]]] = []

        # Shared recognition sentence history — the conversation so far.
        # Fed to ASR as context for all speakers.
        self.recog_sent_history: List[str] = []

        logger.info("shared_context_initialized", history_size=history_size)

    def add_committed_words(
        self,
        words: List[Tuple[float, float, str]],
        speaker_id: Optional[str] = None,
    ) -> None:
        """Register newly committed words from a speaker.

        Called by SpeechProcessor after LCP produces committed words.
        Updates the shared conversation history.

        Args:
            words: List of (start, end, text) tuples from one speaker.
            speaker_id: Which speaker committed these words.
        """
        if not words:
            return

        for start, end, text in words:
            self.all_committed_words.append((start, end, text, speaker_id))

        # Keep chronological order (words from different speakers may interleave)
        self.all_committed_words.sort(key=lambda w: w[0])

        # Update recog_sent_history
        committed_text = " ".join(w[2] for w in words)
        if committed_text.strip():
            sentences = re.split(
                r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s',
                committed_text.strip(),
            )
            self.recog_sent_history.extend(sentences)
            if len(self.recog_sent_history) > self.history_size:
                self.recog_sent_history = self.recog_sent_history[-self.history_size:]

        logger.debug(
            "shared_context_updated",
            speaker_id=speaker_id,
            new_words=len(words),
            total_words=len(self.all_committed_words),
            history_sentences=len(self.recog_sent_history),
        )

    def build_prompt(self, before_time: float) -> str:
        """Build ASR prompt from all speakers' committed words before a given time.

        This gives the ASR model full conversation context: when transcribing
        speaker B, the prompt includes what speaker A recently said.

        Args:
            before_time: Only include words whose end_time <= this value.
                Typically the current speaker's buffer_time_offset.

        Returns:
            Space-separated string of all committed words before the threshold.
        """
        return " ".join(w[2] for w in self.all_committed_words if w[1] <= before_time)


class SpeechProcessor:
    """Per-speaker ASR orchestrator managing the full pipeline from VAD result to committed words.

    Each speaker has its own:
    - audio_buffer (float32, up to 30s rolling)
    - hypothesis_buffer (LCP matching per this speaker's ASR results)
    - speech state (in_speech, silence timeout, stride timing)
    - per-speaker committed_words (for buffer trimming at word boundaries)

    Shared via shared_context:
    - recog_sent_history (conversation-level, all speakers)
    - all committed words from all speakers (for ASR prompt building)
    """

    SAMPLING_RATE = 16000
    WHISPER_MAX_AUDIO_SEC = 30.0

    def __init__(
        self,
        asr_client: ASRClient,
        shared_context: SharedConversationContext,
        speaker_id: Optional[str] = None,
        stride_sec: float = 5.0,
        silence_timeout_sec: float = 1.0,
        pre_speech_buffer_sec: float = 1.0,
    ):
        self.asr_client = asr_client
        self.shared_context = shared_context
        self.speaker_id = speaker_id
        self.stride_sec = stride_sec
        self.silence_timeout_sec = silence_timeout_sec
        self.pre_speech_buffer_sec = pre_speech_buffer_sec
        self.buffer_trimming_sec = self.WHISPER_MAX_AUDIO_SEC - stride_sec

        # Audio buffer (float32, per-speaker)
        self.audio_buffer = np.array([], dtype=np.float32)
        self.buffer_time_offset: float = 0.0

        # LCP (per-speaker)
        self.hypothesis_buffer = HypothesisBuffer()
        # Per-speaker committed words — needed for buffer trimming at
        # this speaker's own word boundaries.
        self.committed_words: List[Tuple[float, float, str]] = []

        # Speech state (per-speaker)
        self.in_speech = False
        self.last_speech_time: Optional[float] = None
        self.last_asr_time: Optional[float] = None

        # Pre-speech buffer (1s left-margin context, per-speaker)
        self.pre_speech_buffer: Deque[np.ndarray] = deque()

        logger.info(
            "speech_processor_initialized",
            speaker_id=speaker_id,
            stride_sec=stride_sec,
            silence_timeout_sec=silence_timeout_sec,
        )

    async def on_vad_result(
        self,
        is_speech: bool,
        audio_float32: np.ndarray,
        timestamp: float,
    ) -> List[Tuple[float, float, str]]:
        """Main entry point: process a VAD result with its audio.

        Args:
            is_speech: Whether speech was detected in this packet.
            audio_float32: Audio samples as float32 numpy array.
            timestamp: Absolute timestamp in seconds.

        Returns:
            List of newly committed word tuples (start, end, text).
        """
        newly_committed = []

        if is_speech:
            self.last_speech_time = timestamp

            if not self.in_speech:
                self._on_speech_start(timestamp)

            # Append audio to buffer
            self.audio_buffer = np.append(self.audio_buffer, audio_float32)

            # Check if stride interval elapsed -> trigger ASR
            if self.last_asr_time is not None:
                time_since_last_asr = timestamp - self.last_asr_time
                if time_since_last_asr >= self.stride_sec:
                    newly_committed = await self._process_asr(timestamp, is_last_chunk=False)

        else:
            # Silence
            if self.in_speech and self.last_speech_time is not None:
                silence_duration = timestamp - self.last_speech_time
                if silence_duration >= self.silence_timeout_sec:
                    newly_committed = await self._on_speech_end(timestamp)
            else:
                # Not in speech: buffer for pre-speech context
                self.pre_speech_buffer.append(audio_float32)

        return newly_committed

    def _on_speech_start(self, timestamp: float) -> None:
        """Handle speech start: prepend pre-speech audio as left-margin context."""
        self.in_speech = True

        logger.info("speech_start", speaker_id=self.speaker_id, timestamp=round(timestamp, 2))

        # Prepend up to pre_speech_buffer_sec of buffered silence
        if len(self.pre_speech_buffer) > 0:
            pre_speech_audio = np.concatenate(list(self.pre_speech_buffer))
            max_pre_speech_samples = int(self.pre_speech_buffer_sec * self.SAMPLING_RATE)
            if len(pre_speech_audio) > max_pre_speech_samples:
                pre_speech_audio = pre_speech_audio[-max_pre_speech_samples:]

            self.audio_buffer = pre_speech_audio
            pre_speech_duration = len(pre_speech_audio) / self.SAMPLING_RATE
            self.buffer_time_offset = timestamp - pre_speech_duration
            self.pre_speech_buffer.clear()
        else:
            self.audio_buffer = np.array([], dtype=np.float32)
            self.buffer_time_offset = timestamp

        # Reinitialize hypothesis buffer for new speech segment
        self.hypothesis_buffer = HypothesisBuffer()
        self.hypothesis_buffer.last_commited_time = self.buffer_time_offset

        self.last_asr_time = timestamp

    async def _on_speech_end(self, timestamp: float) -> List[Tuple[float, float, str]]:
        """Handle speech end: trigger final ASR and commit remaining words.

        Returns:
            List of all newly committed words from the final ASR + complete().
        """
        self.in_speech = False

        logger.info("speech_end", speaker_id=self.speaker_id, timestamp=round(timestamp, 2))

        newly_committed = await self._process_asr(timestamp, is_last_chunk=True)

        return newly_committed

    async def _process_asr(
        self, timestamp: float, is_last_chunk: bool = False
    ) -> List[Tuple[float, float, str]]:
        """Process accumulated audio through ASR and commit stable words.

        Uses shared_context for prompt and recog_sent_history so that
        words committed by other speakers provide context for this speaker's ASR.

        Args:
            timestamp: Current absolute timestamp.
            is_last_chunk: Whether this is the final processing for current speech segment.

        Returns:
            List of newly committed word tuples.
        """
        chunk_dur = len(self.audio_buffer) / self.SAMPLING_RATE

        if chunk_dur < self.stride_sec and not is_last_chunk:
            return []

        if chunk_dur == 0:
            return []

        logger.info(
            "asr_processing",
            speaker_id=self.speaker_id,
            audio_duration=round(chunk_dur, 2),
            is_last_chunk=is_last_chunk,
        )

        # Cap to Whisper's 30s max
        if chunk_dur > self.WHISPER_MAX_AUDIO_SEC:
            max_samples = int(self.WHISPER_MAX_AUDIO_SEC * self.SAMPLING_RATE)
            audio_to_transcribe = self.audio_buffer[-max_samples:]
            audio_offset = self.buffer_time_offset + (chunk_dur - self.WHISPER_MAX_AUDIO_SEC)
        else:
            audio_to_transcribe = self.audio_buffer
            audio_offset = self.buffer_time_offset

        # Build prompt from ALL speakers' committed words (shared context)
        prompt = self.shared_context.build_prompt(self.buffer_time_offset)

        # Call ASR with shared conversation history
        asr_response = await self.asr_client.transcribe(
            audio=audio_to_transcribe,
            prompt=prompt,
            recog_sent_history=self.shared_context.recog_sent_history,
            speaker_id=self.speaker_id,
        )

        self.last_asr_time = timestamp

        # Extract words from response
        words = []
        for segment in asr_response.segments:
            if segment.no_speech_prob > 0.9:
                continue
            for word_info in segment.words:
                text = word_info.text.strip()
                if text:
                    words.append({'start': word_info.start, 'end': word_info.end, 'text': text})

        # Insert into per-speaker hypothesis buffer
        self.hypothesis_buffer.insert(words, offset=audio_offset)

        # Flush: LCP matching -> committed words
        newly_committed = self.hypothesis_buffer.flush()

        if newly_committed:
            # Update per-speaker committed words (for buffer trimming)
            self.committed_words.extend(newly_committed)

            # Update shared conversation context (for prompt + history)
            self.shared_context.add_committed_words(newly_committed, self.speaker_id)

            committed_text = " ".join(word[2] for word in newly_committed)
            logger.info(
                "words_committed",
                speaker_id=self.speaker_id,
                count=len(newly_committed),
                text=committed_text[:100],
            )

        # Buffer trimming (uses per-speaker committed words)
        if len(self.audio_buffer) / self.SAMPLING_RATE > self.buffer_trimming_sec:
            self._trim_buffer_at_committed_word(timestamp)

        # Final chunk: commit all remaining uncommitted words
        if is_last_chunk:
            final_uncommitted = self.hypothesis_buffer.complete()
            if final_uncommitted:
                logger.info(
                    "final_words_committed",
                    speaker_id=self.speaker_id,
                    count=len(final_uncommitted),
                )
                self.committed_words.extend(final_uncommitted)
                self.shared_context.add_committed_words(final_uncommitted, self.speaker_id)
                newly_committed.extend(final_uncommitted)

        return newly_committed

    def _trim_buffer_at_committed_word(self, current_time: float) -> None:
        """Trim audio and hypothesis buffers at this speaker's committed word boundary."""
        if not self.committed_words:
            return

        buffer_duration = len(self.audio_buffer) / self.SAMPLING_RATE
        target_trim_time = self.buffer_time_offset + (buffer_duration / 2)

        trim_time = None
        for word in reversed(self.committed_words):
            if word[1] <= target_trim_time:
                trim_time = word[1]
                break

        if trim_time is None or trim_time <= self.buffer_time_offset:
            return

        cut_seconds = trim_time - self.buffer_time_offset
        if cut_seconds > 0:
            cut_samples = int(cut_seconds * self.SAMPLING_RATE)
            self.audio_buffer = self.audio_buffer[cut_samples:]
            self.buffer_time_offset = trim_time

            removed_words = self.hypothesis_buffer.pop_commited(trim_time)

            logger.debug(
                "buffer_trimmed",
                speaker_id=self.speaker_id,
                cut_seconds=round(cut_seconds, 2),
                removed_words=len(removed_words),
                new_offset=round(self.buffer_time_offset, 2),
            )

    async def flush(self) -> List[Tuple[float, float, str]]:
        """Flush remaining audio for clean shutdown.

        Returns:
            List of newly committed words from final processing.
        """
        if self.in_speech and len(self.audio_buffer) > 0:
            timestamp = self.buffer_time_offset + len(self.audio_buffer) / self.SAMPLING_RATE
            return await self._process_asr(timestamp, is_last_chunk=True)
        return []
