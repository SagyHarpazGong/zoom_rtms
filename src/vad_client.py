"""Local Voice Activity Detection (VAD) client.

Runs VAD inference locally (synchronous, in-process).
Currently a placeholder that returns is_speech=True for all audio.
"""

from pydantic import BaseModel

from .utils import get_logger
from .audio_buffer import AudioChunk


logger = get_logger(__name__)


class VADResponse(BaseModel):
    """Result from local VAD inference."""
    is_speech: bool
    confidence: float = 1.0
    speech_probability: float = 1.0


class VADClient:
    """Local VAD inference client.

    Processes 0.1s audio packets and returns speech detection results
    synchronously. No network calls needed.
    """

    def __init__(self, threshold: float = 0.5, model_path: str = ""):
        self.threshold = threshold
        self.model_path = model_path
        # TODO: Load VAD model here when implementing real inference

        logger.info("vad_client_initialized", threshold=threshold, model_path=model_path)

    def process_audio(self, audio_chunk: AudioChunk) -> VADResponse:
        """Run local VAD inference on audio packet.

        Args:
            audio_chunk: Audio chunk to process (0.1s / 1600 samples at 16kHz).

        Returns:
            VADResponse with speech detection result.
        """
        # TODO: Implement actual VAD inference
        # Placeholder: always returns speech detected
        return VADResponse(is_speech=True, confidence=1.0, speech_probability=1.0)

    async def connect(self) -> bool:
        """No-op for local inference."""
        logger.info("vad_client_ready")
        return True

    async def disconnect(self) -> None:
        """No-op for local inference."""
        pass
