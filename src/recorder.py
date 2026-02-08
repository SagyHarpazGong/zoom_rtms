"""Meeting audio recorder"""

import wave
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import numpy as np

from .utils import get_logger, numpy_to_pcm


class AudioRecorder:
    """Records meeting audio to WAV files

    Supports multi-track recording for multiple speakers.
    """

    def __init__(
        self,
        output_dir: str,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        audio_format: str = "wav"
    ):
        self.logger = get_logger(__name__)
        self.output_dir = Path(output_dir)
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.audio_format = audio_format

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Recording state
        self.is_recording = False
        self.session_id: Optional[str] = None
        self.session_start: Optional[datetime] = None

        # Audio buffers per speaker
        self.speaker_buffers: Dict[str, np.ndarray] = {}

        # File handles
        self.wav_files: Dict[str, wave.Wave_write] = {}

    def start_recording(self, session_id: str) -> None:
        """Start recording session

        Args:
            session_id: Unique session identifier
        """
        if self.is_recording:
            self.logger.warning("recording_already_active")
            return

        self.session_id = session_id
        self.session_start = datetime.utcnow()
        self.is_recording = True

        self.logger.info(
            "recording_started",
            session_id=session_id,
            output_dir=str(self.output_dir)
        )

    def add_audio(
        self,
        audio_data: np.ndarray,
        speaker_id: str = "mixed"
    ) -> None:
        """Add audio data to recording

        Args:
            audio_data: Audio samples as numpy array
            speaker_id: Speaker identifier (or "mixed" for all speakers)
        """
        if not self.is_recording:
            return

        try:
            # Initialize speaker buffer if needed
            if speaker_id not in self.speaker_buffers:
                self.speaker_buffers[speaker_id] = np.array([], dtype=np.int16)
                self._create_wav_file(speaker_id)

            # Append audio data
            self.speaker_buffers[speaker_id] = np.concatenate([
                self.speaker_buffers[speaker_id],
                audio_data
            ])

            # Write to file (buffered)
            if speaker_id in self.wav_files:
                pcm_data = numpy_to_pcm(audio_data)
                self.wav_files[speaker_id].writeframes(pcm_data)

            self.logger.debug(
                "audio_recorded",
                speaker_id=speaker_id,
                samples=len(audio_data)
            )

        except Exception as e:
            self.logger.error("recording_error", speaker_id=speaker_id, error=str(e))

    def _create_wav_file(self, speaker_id: str) -> None:
        """Create WAV file for speaker

        Args:
            speaker_id: Speaker identifier
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.session_id}_{speaker_id}_{timestamp}.wav"
            filepath = self.output_dir / filename

            # Create WAV file
            wav_file = wave.open(str(filepath), 'wb')
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)

            self.wav_files[speaker_id] = wav_file

            self.logger.info(
                "wav_file_created",
                speaker_id=speaker_id,
                path=str(filepath)
            )

        except Exception as e:
            self.logger.error("wav_file_creation_error", error=str(e))

    def stop_recording(self) -> Dict[str, Path]:
        """Stop recording and close files

        Returns:
            Dictionary mapping speaker_id to file path
        """
        if not self.is_recording:
            self.logger.warning("no_active_recording")
            return {}

        self.is_recording = False
        recorded_files = {}

        # Close all WAV files
        for speaker_id, wav_file in self.wav_files.items():
            try:
                wav_file.close()
                filepath = Path(wav_file._file.name)
                recorded_files[speaker_id] = filepath

                duration = len(self.speaker_buffers[speaker_id]) / self.sample_rate
                self.logger.info(
                    "recording_closed",
                    speaker_id=speaker_id,
                    duration_seconds=duration,
                    path=str(filepath)
                )

            except Exception as e:
                self.logger.error("wav_file_close_error", speaker_id=speaker_id, error=str(e))

        # Clear state
        self.wav_files.clear()
        self.speaker_buffers.clear()
        self.session_id = None

        self.logger.info(
            "recording_stopped",
            files_saved=len(recorded_files)
        )

        return recorded_files

    def get_recording_duration(self, speaker_id: Optional[str] = None) -> float:
        """Get recording duration in seconds

        Args:
            speaker_id: Optional speaker ID, or None for longest duration

        Returns:
            Duration in seconds
        """
        if not self.speaker_buffers:
            return 0.0

        if speaker_id and speaker_id in self.speaker_buffers:
            return len(self.speaker_buffers[speaker_id]) / self.sample_rate

        # Return longest duration across all speakers
        max_samples = max(len(buf) for buf in self.speaker_buffers.values())
        return max_samples / self.sample_rate
