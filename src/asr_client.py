"""WebSocket client for Automatic Speech Recognition (ASR) server"""

import asyncio
import json
from typing import Optional, Callable, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed

from .utils import get_logger, numpy_to_pcm
from .audio_buffer import AudioChunk


class ASRClient:
    """WebSocket client for ASR server

    Sends 2.5s speech segments and receives transcription results.
    """

    def __init__(
        self,
        ws_url: str,
        enable_diarization: bool = True,
        reconnect_attempts: int = 5,
        reconnect_delay: int = 2
    ):
        self.logger = get_logger(__name__)
        self.ws_url = ws_url
        self.enable_diarization = enable_diarization
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.transcription_callback: Optional[Callable] = None
        self._running = False
        self._pending_segments = {}  # Track sent segments for matching results

    def set_transcription_callback(self, callback: Callable) -> None:
        """Set callback for transcription results

        Callback signature: async def callback(transcription: Dict[str, Any], audio_chunk: AudioChunk)
        """
        self.transcription_callback = callback

    async def connect(self) -> bool:
        """Connect to ASR WebSocket server

        Returns:
            True if connected successfully
        """
        for attempt in range(self.reconnect_attempts):
            try:
                self.logger.info(
                    "asr_connecting",
                    url=self.ws_url,
                    attempt=attempt + 1
                )

                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=10 * 1024 * 1024  # 10MB max message size
                )

                self.is_connected = True
                self.logger.info("asr_connected")

                # Start receiving responses
                asyncio.create_task(self._receive_loop())

                return True

            except Exception as e:
                self.logger.warning(
                    "asr_connection_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )

                if attempt < self.reconnect_attempts - 1:
                    await asyncio.sleep(self.reconnect_delay)

        self.logger.error("asr_connection_failed_all_attempts")
        return False

    async def _receive_loop(self) -> None:
        """Continuously receive transcription results"""
        self._running = True

        try:
            while self._running and self.websocket:
                try:
                    message = await self.websocket.recv()

                    # Parse transcription result
                    result = json.loads(message) if isinstance(message, str) else message

                    self.logger.info(
                        "asr_result_received",
                        text=result.get("text", "")[:50],  # First 50 chars
                        speaker=result.get("speaker_id"),
                        audio_id=result.get("audio_id")
                    )

                    # Match with pending segment
                    audio_id = result.get("audio_id")
                    audio_chunk = self._pending_segments.pop(audio_id, None)

                    # Call transcription callback
                    if self.transcription_callback:
                        await self.transcription_callback(result, audio_chunk)

                except ConnectionClosed:
                    self.logger.warning("asr_connection_closed")
                    self.is_connected = False
                    # Attempt reconnection
                    await self.connect()
                    break

                except Exception as e:
                    self.logger.error("asr_receive_error", error=str(e))

        except Exception as e:
            self.logger.error("asr_receive_loop_error", error=str(e))
        finally:
            self._running = False

    async def transcribe(self, audio_chunk: AudioChunk) -> None:
        """Send speech segment to ASR server for transcription

        Args:
            audio_chunk: Audio chunk to transcribe (should be ~2.5s)
        """
        if not self.is_connected or not self.websocket:
            self.logger.warning("asr_not_connected")
            return

        try:
            # Generate unique ID for this segment
            audio_id = id(audio_chunk)
            self._pending_segments[audio_id] = audio_chunk

            # Convert numpy array to PCM bytes
            pcm_data = numpy_to_pcm(audio_chunk.data)

            # Create message payload
            # Note: Adjust format based on your ASR server's expected format
            message = {
                "audio": pcm_data.hex(),  # Hex-encoded audio data
                "sample_rate": audio_chunk.sample_rate,
                "timestamp": audio_chunk.timestamp.isoformat(),
                "audio_id": audio_id,
                "enable_diarization": self.enable_diarization,
                "speaker_id": audio_chunk.speaker_id  # If known from context
            }

            # Send as JSON (or binary depending on server)
            await self.websocket.send(json.dumps(message))

            duration = len(audio_chunk.data) / audio_chunk.sample_rate
            self.logger.debug(
                "asr_audio_sent",
                samples=len(audio_chunk.data),
                duration_seconds=duration,
                timestamp=audio_chunk.timestamp.isoformat()
            )

        except Exception as e:
            self.logger.error("asr_send_error", error=str(e))
            self.is_connected = False
            # Remove from pending
            self._pending_segments.pop(audio_id, None)

    async def disconnect(self) -> None:
        """Disconnect from ASR server"""
        self._running = False

        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("asr_disconnected")
            except Exception as e:
                self.logger.error("asr_disconnect_error", error=str(e))

        self.is_connected = False
        self.websocket = None
        self._pending_segments.clear()
