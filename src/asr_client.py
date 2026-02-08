"""HTTP client for Automatic Speech Recognition (ASR) via KServe/FastAPI.

Sends audio + contextual prompt to a remote ASR server and returns
word-level transcription results.
"""

import base64
from typing import List, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from .utils import get_logger


logger = get_logger(__name__)


class ASRWord(BaseModel):
    """A single transcribed word with timing."""
    start: float
    end: float
    text: str


class ASRSegment(BaseModel):
    """A transcription segment containing words."""
    words: List[ASRWord] = []
    text: str = ""
    no_speech_prob: float = 0.0


class ASRRequest(BaseModel):
    """Request payload for the ASR server. Adjust when implementing KServe server."""
    audio_base64: str
    sample_rate: int = 16000
    prompt: str = ""
    recog_sent_history: List[str] = []
    speaker_id: Optional[str] = None


class ASRResponse(BaseModel):
    """Response from the ASR server. Adjust when implementing KServe server."""
    segments: List[ASRSegment] = []


class ASRClient:
    """HTTP client for remote ASR inference.

    Sends audio + context via POST to a KServe endpoint and returns
    parsed word-level transcription results.
    """

    def __init__(self, url: str, timeout_seconds: float = 30.0):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.http_client: Optional[httpx.AsyncClient] = None

        logger.info("asr_client_initialized", url=url, timeout=timeout_seconds)

    async def connect(self) -> bool:
        """Create the HTTP client session."""
        self.http_client = httpx.AsyncClient(timeout=self.timeout_seconds)
        logger.info("asr_client_ready", url=self.url)
        return True

    async def transcribe(
        self,
        audio: np.ndarray,
        prompt: str = "",
        recog_sent_history: Optional[List[str]] = None,
        speaker_id: Optional[str] = None,
    ) -> ASRResponse:
        """POST audio + context to ASR server, return parsed response.

        Args:
            audio: float32 numpy array of audio samples.
            prompt: Contextual prompt from committed words.
            recog_sent_history: Recent committed sentences for context.
            speaker_id: Optional speaker identifier.

        Returns:
            ASRResponse with word-level transcription segments.
        """
        if not self.http_client:
            logger.error("asr_client_not_connected")
            return ASRResponse()

        request = ASRRequest(
            audio_base64=base64.b64encode(audio.astype(np.float32).tobytes()).decode(),
            sample_rate=16000,
            prompt=prompt,
            recog_sent_history=recog_sent_history or [],
            speaker_id=speaker_id,
        )

        try:
            duration_sec = len(audio) / 16000
            logger.info(
                "asr_request_sending",
                audio_duration=round(duration_sec, 2),
                prompt_length=len(prompt),
                speaker_id=speaker_id,
            )

            response = await self.http_client.post(self.url, json=request.model_dump())
            response.raise_for_status()
            asr_response = ASRResponse.model_validate(response.json())

            total_words = sum(len(seg.words) for seg in asr_response.segments)
            logger.info("asr_response_received", total_words=total_words)

            return asr_response

        except httpx.HTTPStatusError as e:
            logger.error("asr_http_error", status_code=e.response.status_code, error=str(e))
            return ASRResponse()
        except httpx.ConnectError as e:
            logger.error("asr_connect_error", error=str(e))
            return ASRResponse()
        except Exception as e:
            logger.error("asr_request_error", error=str(e))
            return ASRResponse()

    async def disconnect(self) -> None:
        """Close the HTTP client session."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            logger.info("asr_client_disconnected")
