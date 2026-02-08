"""Handler for transcription output and formatting"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from .utils import get_logger


@dataclass
class TranscriptionSegment:
    """Represents a transcription segment"""
    text: str
    speaker_id: Optional[str]
    timestamp: datetime
    confidence: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class TranscriptionHandler:
    """Handles transcription output, formatting, and storage"""

    def __init__(
        self,
        output_format: str = "json",
        enable_timestamps: bool = True,
        enable_speaker_labels: bool = True,
        real_time_output: bool = True,
        output_dir: Optional[str] = None
    ):
        self.logger = get_logger(__name__)
        self.output_format = output_format
        self.enable_timestamps = enable_timestamps
        self.enable_speaker_labels = enable_speaker_labels
        self.real_time_output = real_time_output
        self.output_dir = Path(output_dir) if output_dir else None

        # Storage
        self.transcriptions: List[TranscriptionSegment] = []
        self.speaker_names: Dict[str, str] = {}  # speaker_id -> name mapping

        # Session info
        self.session_id: Optional[str] = None
        self.session_start: Optional[datetime] = None

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def start_session(self, session_id: str) -> None:
        """Start a new transcription session

        Args:
            session_id: Unique session identifier (e.g., meeting ID)
        """
        self.session_id = session_id
        self.session_start = datetime.utcnow()
        self.transcriptions = []

        self.logger.info(
            "transcription_session_started",
            session_id=session_id,
            start_time=self.session_start.isoformat()
        )

    def add_transcription(
        self,
        text: str,
        speaker_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        confidence: Optional[float] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> None:
        """Add a new transcription segment

        Args:
            text: Transcribed text
            speaker_id: Speaker identifier
            timestamp: Timestamp of transcription
            confidence: Confidence score
            start_time: Start time relative to session start
            end_time: End time relative to session start
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        segment = TranscriptionSegment(
            text=text,
            speaker_id=speaker_id,
            timestamp=timestamp,
            confidence=confidence,
            start_time=start_time,
            end_time=end_time
        )

        self.transcriptions.append(segment)

        self.logger.info(
            "transcription_added",
            speaker=self._get_speaker_label(speaker_id),
            text=text[:50],
            confidence=confidence
        )

        # Real-time output
        if self.real_time_output:
            self._output_segment(segment)

    def update_speaker_name(self, speaker_id: str, name: str) -> None:
        """Update speaker name mapping

        Args:
            speaker_id: Speaker identifier
            name: Human-readable name
        """
        self.speaker_names[speaker_id] = name
        self.logger.debug("speaker_name_updated", speaker_id=speaker_id, name=name)

    def _get_speaker_label(self, speaker_id: Optional[str]) -> str:
        """Get speaker label (name or ID)"""
        if not speaker_id:
            return "Unknown"
        return self.speaker_names.get(speaker_id, f"Speaker {speaker_id}")

    def _output_segment(self, segment: TranscriptionSegment) -> None:
        """Output a transcription segment in real-time

        Args:
            segment: Transcription segment to output
        """
        if self.output_format == "json":
            output = json.dumps(segment.to_dict(), indent=2)
            print(output)

        elif self.output_format == "text":
            speaker_label = self._get_speaker_label(segment.speaker_id)
            timestamp_str = segment.timestamp.strftime("%H:%M:%S") if self.enable_timestamps else ""

            if self.enable_speaker_labels and self.enable_timestamps:
                print(f"[{timestamp_str}] {speaker_label}: {segment.text}")
            elif self.enable_speaker_labels:
                print(f"{speaker_label}: {segment.text}")
            elif self.enable_timestamps:
                print(f"[{timestamp_str}] {segment.text}")
            else:
                print(segment.text)

        elif self.output_format == "srt":
            # SRT subtitle format
            index = len(self.transcriptions)
            start = self._format_srt_time(segment.start_time or 0)
            end = self._format_srt_time(segment.end_time or 0)
            print(f"{index}\n{start} --> {end}\n{segment.text}\n")

    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT subtitle format

        Args:
            seconds: Time in seconds

        Returns:
            Time string in SRT format (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def save_transcription(self, filename: Optional[str] = None) -> Optional[Path]:
        """Save full transcription to file

        Args:
            filename: Optional filename, otherwise auto-generated

        Returns:
            Path to saved file or None if failed
        """
        if not self.output_dir:
            self.logger.warning("no_output_directory_configured")
            return None

        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"transcription_{self.session_id}_{timestamp}.{self.output_format}"

        output_path = self.output_dir / filename

        try:
            if self.output_format == "json":
                data = {
                    "session_id": self.session_id,
                    "start_time": self.session_start.isoformat() if self.session_start else None,
                    "speakers": self.speaker_names,
                    "transcriptions": [seg.to_dict() for seg in self.transcriptions]
                }
                output_path.write_text(json.dumps(data, indent=2))

            elif self.output_format == "text":
                lines = []
                for seg in self.transcriptions:
                    speaker_label = self._get_speaker_label(seg.speaker_id)
                    timestamp_str = seg.timestamp.strftime("%H:%M:%S") if self.enable_timestamps else ""

                    if self.enable_speaker_labels and self.enable_timestamps:
                        lines.append(f"[{timestamp_str}] {speaker_label}: {seg.text}")
                    elif self.enable_speaker_labels:
                        lines.append(f"{speaker_label}: {seg.text}")
                    elif self.enable_timestamps:
                        lines.append(f"[{timestamp_str}] {seg.text}")
                    else:
                        lines.append(seg.text)

                output_path.write_text("\n".join(lines))

            elif self.output_format == "srt":
                lines = []
                for idx, seg in enumerate(self.transcriptions, 1):
                    start = self._format_srt_time(seg.start_time or 0)
                    end = self._format_srt_time(seg.end_time or 0)
                    lines.append(f"{idx}\n{start} --> {end}\n{seg.text}\n")

                output_path.write_text("\n".join(lines))

            self.logger.info("transcription_saved", path=str(output_path))
            return output_path

        except Exception as e:
            self.logger.error("transcription_save_error", error=str(e))
            return None

    def get_transcription_text(self) -> str:
        """Get full transcription as plain text

        Returns:
            Combined transcription text
        """
        return " ".join(seg.text for seg in self.transcriptions)

    def get_statistics(self) -> Dict[str, Any]:
        """Get transcription statistics

        Returns:
            Dictionary with statistics
        """
        return {
            "total_segments": len(self.transcriptions),
            "unique_speakers": len(set(seg.speaker_id for seg in self.transcriptions if seg.speaker_id)),
            "total_words": sum(len(seg.text.split()) for seg in self.transcriptions),
            "session_duration": (datetime.utcnow() - self.session_start).total_seconds()
            if self.session_start else 0
        }
