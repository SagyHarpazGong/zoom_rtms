"""Zoom RTMS (Real-Time Media Streaming) client using official SDK"""

import rtms
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from .utils import get_logger


class RTMSClient:
    """Client for Zoom RTMS using official Python SDK

    Connects to Zoom's Real-Time Media Streaming service and receives
    audio streams from meeting participants.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        sample_rate: int = 16000,
        channels: int = 1,
        stream_mode: str = "mixed"
    ):
        self.logger = get_logger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret
        self.sample_rate = sample_rate
        self.channels = channels
        self.stream_mode = stream_mode

        # RTMS client instance
        self.client: Optional[rtms.Client] = None

        # Callbacks
        self.audio_callback: Optional[Callable] = None
        self.transcription_callback: Optional[Callable] = None
        self.participant_joined_callback: Optional[Callable] = None
        self.participant_left_callback: Optional[Callable] = None
        self.session_update_callback: Optional[Callable] = None

        # State
        self.is_connected = False
        self.meeting_uuid: Optional[str] = None
        self.rtms_stream_id: Optional[str] = None

        # Track participants
        self.participants: Dict[str, Dict[str, Any]] = {}

        self.logger.info("rtms_client_initialized", stream_mode=stream_mode)

    def set_audio_callback(self, callback: Callable) -> None:
        """Set callback for incoming audio data

        Callback signature: async def callback(audio_data: bytes, participant_id: str, timestamp: datetime)
        """
        self.audio_callback = callback

    def set_transcription_callback(self, callback: Callable) -> None:
        """Set callback for incoming transcription data

        Callback signature: async def callback(transcription: Dict[str, Any], participant_id: str, timestamp: datetime)
        """
        self.transcription_callback = callback

    def set_participant_joined_callback(self, callback: Callable) -> None:
        """Set callback for participant joined events"""
        self.participant_joined_callback = callback

    def set_participant_left_callback(self, callback: Callable) -> None:
        """Set callback for participant left events"""
        self.participant_left_callback = callback

    def set_session_update_callback(self, callback: Callable) -> None:
        """Set callback for session updates"""
        self.session_update_callback = callback

    def join(
        self,
        meeting_uuid: str,
        rtms_stream_id: str,
        server_urls: list,
        signature: Optional[str] = None
    ) -> bool:
        """Join a meeting using RTMS

        Args:
            meeting_uuid: Zoom meeting UUID
            rtms_stream_id: RTMS stream ID
            server_urls: List of RTMS server URLs
            signature: Pre-generated signature (optional, will generate if not provided)

        Returns:
            True if join was successful
        """
        try:
            self.meeting_uuid = meeting_uuid
            self.rtms_stream_id = rtms_stream_id

            # Create RTMS client
            self.client = rtms.Client()

            # Configure audio parameters
            self._configure_audio_params()

            # Set up callbacks
            self._setup_callbacks()

            # Generate signature if not provided
            if not signature:
                signature = rtms.generate_signature(
                    self.client_id,
                    self.client_secret,
                    meeting_uuid,
                    rtms_stream_id
                )

            self.logger.info(
                "rtms_joining_meeting",
                meeting_uuid=meeting_uuid,
                rtms_stream_id=rtms_stream_id
            )

            # Join the meeting
            self.client.join(
                meeting_uuid=meeting_uuid,
                rtms_stream_id=rtms_stream_id,
                server_urls=server_urls,
                signature=signature
            )

            self.is_connected = True
            self.logger.info("rtms_joined_successfully")

            return True

        except Exception as e:
            self.logger.error("rtms_join_failed", error=str(e))
            return False

    def _configure_audio_params(self) -> None:
        """Configure audio parameters for RTMS"""
        try:
            # Map sample rate
            sample_rate_map = {
                8000: rtms.AudioSampleRate['SR_8K'],
                16000: rtms.AudioSampleRate['SR_16K'],
                32000: rtms.AudioSampleRate['SR_32K'],
                48000: rtms.AudioSampleRate['SR_48K']
            }

            # Map channels
            channel_map = {
                1: rtms.AudioChannel['MONO'],
                2: rtms.AudioChannel['STEREO']
            }

            # Determine audio data option based on stream mode
            if self.stream_mode == "individual":
                audio_data_opt = rtms.AudioDataOption['AUDIO_INDIVIDUAL_STREAMS']
            else:
                audio_data_opt = rtms.AudioDataOption['AUDIO_MIXED_STREAM']

            # Configure audio parameters
            params = rtms.AudioParams(
                content_type=rtms.AudioContentType['RAW_AUDIO'],
                codec=rtms.AudioCodec['PCM'],  # PCM for raw audio
                sample_rate=sample_rate_map.get(self.sample_rate, rtms.AudioSampleRate['SR_16K']),
                channel=channel_map.get(self.channels, rtms.AudioChannel['MONO']),
                data_opt=audio_data_opt,
                duration=20,  # 20ms frames
                frame_size=self.sample_rate * self.channels * 20 // 1000  # Calculate frame size
            )

            self.client.setAudioParams(params)

            self.logger.info(
                "audio_params_configured",
                sample_rate=self.sample_rate,
                channels=self.channels,
                stream_mode=self.stream_mode,
                data_opt=audio_data_opt
            )

        except Exception as e:
            self.logger.error("audio_config_error", error=str(e))

    def _setup_callbacks(self) -> None:
        """Setup RTMS SDK callbacks"""

        @self.client.onJoinConfirm
        def on_join_confirm(result, reason):
            """Called when join is confirmed"""
            self.logger.info(
                "rtms_join_confirmed",
                result=result,
                reason=reason
            )

        @self.client.onSessionUpdate
        def on_session_update(state):
            """Called on session state changes"""
            self.logger.info("rtms_session_update", state=state)

            if self.session_update_callback:
                self.session_update_callback(state)

        @self.client.onParticipantEvent
        def on_participant_event(event):
            """Called on participant join/leave"""
            participant_id = event.get('participant_id', 'unknown')
            event_type = event.get('event_type', 'unknown')

            self.logger.info(
                "rtms_participant_event",
                participant_id=participant_id,
                event_type=event_type
            )

            if event_type == 'join':
                self.participants[participant_id] = {
                    'id': participant_id,
                    'name': event.get('participant_name', f'Participant {participant_id}'),
                    'joined_at': datetime.utcnow()
                }

                if self.participant_joined_callback:
                    self.participant_joined_callback(participant_id, event)

            elif event_type == 'leave':
                self.participants.pop(participant_id, None)

                if self.participant_left_callback:
                    self.participant_left_callback(participant_id, event)

        @self.client.onAudioData
        def on_audio_data(buffer, size, timestamp, metadata):
            """Called when audio data is received

            Args:
                buffer: Audio data buffer (bytes)
                size: Size of audio data
                timestamp: Timestamp of audio data
                metadata: Metadata including participant info
            """
            try:
                # Extract audio data
                audio_data = bytes(buffer[:size])

                # Get participant information
                participant_id = getattr(metadata, 'participant_id', 'unknown')

                # Convert timestamp to datetime
                audio_timestamp = datetime.utcnow()  # Use current time as fallback

                self.logger.debug(
                    "rtms_audio_received",
                    size=size,
                    participant_id=participant_id
                )

                # Forward to audio callback
                if self.audio_callback:
                    import asyncio
                    # Run async callback in event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self.audio_callback(audio_data, participant_id, audio_timestamp)
                        )
                    else:
                        loop.run_until_complete(
                            self.audio_callback(audio_data, participant_id, audio_timestamp)
                        )

            except Exception as e:
                self.logger.error("audio_callback_error", error=str(e))

        @self.client.onTranscription
        def on_transcription(transcription_data, metadata):
            """Called when transcription data is received

            Args:
                transcription_data: Transcription result data
                metadata: Metadata including participant info and timing
            """
            try:
                # Get participant information
                participant_id = getattr(metadata, 'participant_id', 'unknown')

                # Convert timestamp to datetime
                transcription_timestamp = datetime.utcnow()

                self.logger.debug(
                    "rtms_transcription_received",
                    participant_id=participant_id,
                    text_length=len(str(transcription_data.get('text', '')))
                )

                # Forward to transcription callback
                if self.transcription_callback:
                    import asyncio
                    # Run async callback in event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self.transcription_callback(transcription_data, participant_id, transcription_timestamp)
                        )
                    else:
                        loop.run_until_complete(
                            self.transcription_callback(transcription_data, participant_id, transcription_timestamp)
                        )

            except Exception as e:
                self.logger.error("transcription_callback_error", error=str(e))

        @self.client.onLeave
        def on_leave(reason):
            """Called when leaving the meeting"""
            self.logger.info("rtms_left_meeting", reason=reason)
            self.is_connected = False

        self.logger.debug("rtms_callbacks_configured")

    def poll(self) -> None:
        """Poll the RTMS client for events

        Should be called regularly to process incoming events.
        """
        if self.client:
            try:
                self.client._poll_if_needed()
            except Exception as e:
                self.logger.error("rtms_poll_error", error=str(e))

    def leave(self) -> None:
        """Leave the meeting"""
        if self.client and self.is_connected:
            try:
                self.client.leave()
                self.logger.info("rtms_leave_initiated")
            except Exception as e:
                self.logger.error("rtms_leave_error", error=str(e))

        self.is_connected = False
        self.client = None

    def get_participants(self) -> Dict[str, Dict[str, Any]]:
        """Get current participants in the meeting"""
        return self.participants.copy()


class RTMSWebhookHandler:
    """Handler for Zoom RTMS webhooks

    Use this to receive webhook events from Zoom and automatically
    create RTMS clients for new meetings.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        port: int = 8080,
        path: str = '/webhook',
        stream_mode: str = "mixed"
    ):
        self.logger = get_logger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret
        self.port = port
        self.path = path
        self.stream_mode = stream_mode

        # Track active clients
        self.clients: Dict[str, RTMSClient] = {}

        # Callbacks
        self.meeting_started_callback: Optional[Callable] = None
        self.meeting_ended_callback: Optional[Callable] = None

    def set_meeting_started_callback(self, callback: Callable) -> None:
        """Set callback for meeting.rtms_started events"""
        self.meeting_started_callback = callback

    def set_meeting_ended_callback(self, callback: Callable) -> None:
        """Set callback for meeting.rtms_ended events"""
        self.meeting_ended_callback = callback

    def start(self) -> None:
        """Start listening for webhook events"""

        @rtms.onWebhookEvent(port=self.port, path=self.path)
        def handle_webhook(webhook):
            """Handle incoming webhook events"""
            event = webhook.get('event')
            payload = webhook.get('payload', {})

            self.logger.info("webhook_received", event=event)

            if event == 'meeting.rtms_started':
                self._handle_meeting_started(payload)
            elif event == 'meeting.rtms_ended':
                self._handle_meeting_ended(payload)

        self.logger.info(
            "webhook_handler_started",
            port=self.port,
            path=self.path
        )

    def _handle_meeting_started(self, payload: Dict[str, Any]) -> None:
        """Handle meeting.rtms_started event"""
        try:
            rtms_stream_id = payload.get('rtms_stream_id')

            if rtms_stream_id in self.clients:
                self.logger.warning(
                    "meeting_already_active",
                    rtms_stream_id=rtms_stream_id
                )
                return

            # Create RTMS client
            client = RTMSClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                stream_mode=self.stream_mode
            )

            # Join the meeting
            client.join(
                meeting_uuid=payload.get('meeting_uuid'),
                rtms_stream_id=rtms_stream_id,
                server_urls=payload.get('server_urls'),
                signature=payload.get('signature')
            )

            # Track client
            self.clients[rtms_stream_id] = client

            # Call callback
            if self.meeting_started_callback:
                self.meeting_started_callback(client, payload)

            self.logger.info(
                "meeting_joined",
                rtms_stream_id=rtms_stream_id
            )

        except Exception as e:
            self.logger.error("meeting_start_error", error=str(e))

    def _handle_meeting_ended(self, payload: Dict[str, Any]) -> None:
        """Handle meeting.rtms_ended event"""
        rtms_stream_id = payload.get('rtms_stream_id')

        if rtms_stream_id in self.clients:
            client = self.clients[rtms_stream_id]
            client.leave()
            del self.clients[rtms_stream_id]

            # Call callback
            if self.meeting_ended_callback:
                self.meeting_ended_callback(rtms_stream_id, payload)

            self.logger.info("meeting_ended", rtms_stream_id=rtms_stream_id)

    def poll_all(self) -> None:
        """Poll all active clients"""
        for client in self.clients.values():
            client.poll()

    def get_client(self, rtms_stream_id: str) -> Optional[RTMSClient]:
        """Get a specific client by stream ID"""
        return self.clients.get(rtms_stream_id)

    def get_all_clients(self) -> Dict[str, RTMSClient]:
        """Get all active clients"""
        return self.clients.copy()
