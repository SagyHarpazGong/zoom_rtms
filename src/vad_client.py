"""WebSocket client for Voice Activity Detection (VAD) server"""

import asyncio
import json
from typing import Optional, Callable
import websockets
from websockets.exceptions import ConnectionClosed

from .utils import get_logger, numpy_to_pcm
from .audio_buffer import AudioChunk


class VADClient:
    """WebSocket client for VAD server

    Sends 0.1s audio packets and receives voice activity detection results.
    """

    def __init__(
        self,
        ws_url: str,
        reconnect_attempts: int = 5,
        reconnect_delay: int = 2
    ):
        self.logger = get_logger(__name__)
        self.ws_url = ws_url
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.result_callback: Optional[Callable] = None
        self._running = False

    def set_result_callback(self, callback: Callable) -> None:
        """Set callback for VAD results

        Callback signature: async def callback(is_speech: bool, audio_chunk: AudioChunk)
        """
        self.result_callback = callback

    async def connect(self) -> bool:
        """Connect to VAD WebSocket server

        Returns:
            True if connected successfully
        """
        for attempt in range(self.reconnect_attempts):
            try:
                self.logger.info(
                    "vad_connecting",
                    url=self.ws_url,
                    attempt=attempt + 1
                )

                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=10
                )

                self.is_connected = True
                self.logger.info("vad_connected")

                # Start receiving responses
                asyncio.create_task(self._receive_loop())

                return True

            except Exception as e:
                self.logger.warning(
                    "vad_connection_failed",
                    attempt=attempt + 1,
                    error=str(e)
                )

                if attempt < self.reconnect_attempts - 1:
                    await asyncio.sleep(self.reconnect_delay)

        self.logger.error("vad_connection_failed_all_attempts")
        return False

    async def _receive_loop(self) -> None:
        """Continuously receive VAD results"""
        self._running = True

        try:
            while self._running and self.websocket:
                try:
                    message = await self.websocket.recv()

                    # Parse VAD result
                    result = json.loads(message) if isinstance(message, str) else message

                    # Extract speech detection result
                    is_speech = result.get("is_speech", False)
                    audio_id = result.get("audio_id")

                    self.logger.debug(
                        "vad_result_received",
                        is_speech=is_speech,
                        audio_id=audio_id
                    )

                    # Note: We'll need to track audio chunks to match results
                    # For now, pass the result through callback
                    if self.result_callback and hasattr(self, '_pending_audio'):
                        await self.result_callback(is_speech, self._pending_audio)

                except ConnectionClosed:
                    self.logger.warning("vad_connection_closed")
                    self.is_connected = False
                    # Attempt reconnection
                    await self.connect()
                    break

                except Exception as e:
                    self.logger.error("vad_receive_error", error=str(e))

        except Exception as e:
            self.logger.error("vad_receive_loop_error", error=str(e))
        finally:
            self._running = False

    async def process_audio(self, audio_chunk: AudioChunk) -> None:
        """Send audio packet to VAD server

        Args:
            audio_chunk: Audio chunk to process (should be 0.1s)
        """
        if not self.is_connected or not self.websocket:
            self.logger.warning("vad_not_connected")
            return

        try:
            # Store for matching with result
            self._pending_audio = audio_chunk

            # Convert numpy array to PCM bytes
            pcm_data = numpy_to_pcm(audio_chunk.data)

            # Create message payload
            # Note: Adjust format based on your VAD server's expected format
            message = {
                "audio": pcm_data.hex(),  # Hex-encoded audio data
                "sample_rate": audio_chunk.sample_rate,
                "timestamp": audio_chunk.timestamp.isoformat(),
                "audio_id": id(audio_chunk)  # For tracking
            }

            # Send as JSON (or binary depending on server)
            await self.websocket.send(json.dumps(message))

            self.logger.debug(
                "vad_audio_sent",
                samples=len(audio_chunk.data),
                timestamp=audio_chunk.timestamp.isoformat()
            )

        except Exception as e:
            self.logger.error("vad_send_error", error=str(e))
            self.is_connected = False

    async def disconnect(self) -> None:
        """Disconnect from VAD server"""
        self._running = False

        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("vad_disconnected")
            except Exception as e:
                self.logger.error("vad_disconnect_error", error=str(e))

        self.is_connected = False
        self.websocket = None
