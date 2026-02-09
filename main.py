"""Main entry point for Zoom RTMS Real-Time Transcription System"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import yaml
import numpy as np
import rtms

from src.utils import setup_logging, get_logger, pcm_to_numpy
from src.rtms_client import RTMSClient, RTMSWebhookHandler
from src.vad_client import VADClient
from src.asr_client import ASRClient
from src.audio_buffer import AudioBuffer, AudioChunk
from src.speech_processor import SpeechProcessor, SharedConversationContext
from src.transcription_handler import TranscriptionHandler
from src.recorder import AudioRecorder


class RTMSTranscriptionSystem:
    """Main system orchestrating RTMS transcription pipeline"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(__name__)

        # ASR mode and stream mode
        self.asr_mode = config.get('asr_mode', 'custom')  # 'custom' or 'rtms'
        self.stream_mode = config['audio'].get('stream_mode', 'mixed')
        self.per_speaker_processing = (self.stream_mode == 'individual')

        # Initialize components
        self._init_clients()
        self._init_audio_buffer()
        self._init_speech_processors()
        self._init_transcription_handler()
        self._init_recorder()

        # State
        self.is_running = False
        self.meeting_id: Optional[str] = None

    def _init_clients(self) -> None:
        """Initialize clients based on ASR mode"""
        # Zoom RTMS client (always needed)
        self.rtms_client = RTMSClient(
            client_id=self.config['zoom']['client_id'],
            client_secret=self.config['zoom']['client_secret'],
            sample_rate=self.config['audio']['sample_rate'],
            channels=self.config['audio']['channels'],
            stream_mode=self.stream_mode
        )

        if self.asr_mode == 'custom':
            # Custom ASR pipeline: VAD + ASR + LCP
            self.vad_client = VADClient(
                threshold=self.config['vad']['threshold'],
                model_path=self.config['vad'].get('model_path', ''),
            )

            self.asr_client = ASRClient(
                url=self.config['asr']['url'],
                timeout_seconds=self.config['asr']['timeout_seconds'],
            )
        else:
            # RTMS mode: use built-in transcription
            self.vad_client = None
            self.asr_client = None

        self.logger.info("clients_initialized", asr_mode=self.asr_mode, stream_mode=self.stream_mode)

    def _init_audio_buffer(self) -> None:
        """Initialize audio buffer manager (only for custom ASR mode)"""
        if self.asr_mode == 'custom':
            self.audio_buffer = AudioBuffer(
                sample_rate=self.config['audio']['sample_rate'],
                vad_duration_ms=self.config['vad']['packet_duration_ms'],
                per_speaker_processing=self.per_speaker_processing,
            )

            # Set callback for VAD packets
            self.audio_buffer.set_vad_callback(self._on_vad_packet_ready)

            self.logger.info(
                "audio_buffer_initialized",
                stream_mode=self.stream_mode,
                per_speaker_processing=self.per_speaker_processing,
            )
        else:
            self.audio_buffer = None
            self.logger.info("audio_buffer_skipped", asr_mode=self.asr_mode)

    def _init_speech_processors(self) -> None:
        """Initialize shared conversation context and speech processors (only for custom ASR mode)"""
        if self.asr_mode == 'custom':
            sp_config = self.config['speech_processor']

            # Shared conversation context — one per meeting, shared across all speakers.
            # Holds recog_sent_history and all committed words from all speakers.
            self.shared_context = SharedConversationContext(
                history_size=sp_config.get('history_size', 30),
            )

            self.speech_processors: Dict[str, SpeechProcessor] = {}

            if not self.per_speaker_processing:
                # Mixed mode: one shared processor
                self.speech_processors['__mixed__'] = SpeechProcessor(
                    asr_client=self.asr_client,
                    shared_context=self.shared_context,
                    speaker_id=None,
                    stride_sec=sp_config['stride_seconds'],
                    silence_timeout_sec=sp_config['silence_timeout_seconds'],
                    pre_speech_buffer_sec=sp_config.get('pre_speech_buffer_seconds', 1.0),
                )
            # Individual mode: processors created on-demand per speaker

            self.logger.info("speech_processors_initialized", mode=self.stream_mode)
        else:
            self.shared_context = None
            self.speech_processors = {}
            self.logger.info("speech_processors_skipped", asr_mode=self.asr_mode)

    def _init_transcription_handler(self) -> None:
        """Initialize transcription handler"""
        trans_config = self.config['transcription']
        rec_config = self.config['recording']

        self.transcription_handler = TranscriptionHandler(
            output_format=trans_config['output_format'],
            enable_timestamps=trans_config['enable_timestamps'],
            enable_speaker_labels=trans_config['enable_speaker_labels'],
            real_time_output=trans_config['real_time_output'],
            output_dir=rec_config['output_dir'] if rec_config['enabled'] else None
        )

        self.logger.info("transcription_handler_initialized")

    def _init_recorder(self) -> None:
        """Initialize audio recorder"""
        rec_config = self.config['recording']

        if not rec_config['enabled']:
            self.recorder = None
            return

        self.recorder = AudioRecorder(
            output_dir=rec_config['output_dir'],
            sample_rate=self.config['audio']['sample_rate'],
            channels=self.config['audio']['channels'],
            sample_width=self.config['audio']['bit_depth'] // 8,
            audio_format=rec_config['audio_format']
        )

        self.logger.info("recorder_initialized")

    def _get_speech_processor(self, speaker_id: Optional[str]) -> SpeechProcessor:
        """Get or create SpeechProcessor for a speaker.

        Args:
            speaker_id: Speaker identifier (None for mixed mode).

        Returns:
            SpeechProcessor for the given speaker.
        """
        if not self.per_speaker_processing:
            return self.speech_processors['__mixed__']

        key = speaker_id or 'unknown'
        if key not in self.speech_processors:
            sp_config = self.config['speech_processor']
            self.speech_processors[key] = SpeechProcessor(
                asr_client=self.asr_client,
                shared_context=self.shared_context,
                speaker_id=key,
                stride_sec=sp_config['stride_seconds'],
                silence_timeout_sec=sp_config['silence_timeout_seconds'],
                pre_speech_buffer_sec=sp_config.get('pre_speech_buffer_seconds', 1.0),
            )
            self.logger.info("speech_processor_created", speaker_id=key)

        return self.speech_processors[key]

    async def start(
        self,
        meeting_uuid: str,
        rtms_stream_id: str,
        server_urls: list,
        signature: Optional[str] = None
    ) -> None:
        """Start the transcription system

        Args:
            meeting_uuid: Zoom meeting UUID
            rtms_stream_id: RTMS stream ID
            server_urls: List of RTMS server URLs
            signature: Authentication signature (optional)
        """
        self.meeting_id = meeting_uuid
        self.is_running = True

        self.logger.info("system_starting", meeting_uuid=meeting_uuid)

        try:
            # Connect to services
            await self._connect_services()

            # Set up callbacks
            self._setup_callbacks()

            # Join RTMS meeting
            if not self.rtms_client.join(meeting_uuid, rtms_stream_id, server_urls, signature):
                raise RuntimeError("Failed to join RTMS meeting")

            # Start recording if enabled
            if self.recorder:
                self.recorder.start_recording(meeting_uuid)

            # Start transcription session
            self.transcription_handler.start_session(meeting_uuid)

            self.logger.info("system_started", meeting_uuid=meeting_uuid)

            # Main event loop
            while self.is_running:
                self.rtms_client.poll()
                await asyncio.sleep(0.01)

        except Exception as e:
            self.logger.error("system_error", error=str(e))
            raise
        finally:
            await self.stop()

    async def _connect_services(self) -> None:
        """Connect to VAD and ASR services (only for custom ASR mode)"""
        if self.asr_mode == 'custom':
            results = await asyncio.gather(
                self.vad_client.connect(),
                self.asr_client.connect(),
                return_exceptions=True
            )

            if not all(results):
                raise RuntimeError("Failed to connect to VAD or ASR services")

            self.logger.info("services_connected")
        else:
            self.logger.info("services_skipped", asr_mode=self.asr_mode)

    def _setup_callbacks(self) -> None:
        """Setup callbacks between components based on ASR mode"""
        if self.asr_mode == 'custom':
            # Custom mode: RTMS audio → Audio Buffer → VAD → SpeechProcessor
            self.rtms_client.set_audio_callback(self._on_rtms_audio)
        else:
            # RTMS mode: RTMS transcription → Transcription Handler directly
            self.rtms_client.set_transcription_callback(self._on_rtms_transcription)

        # RTMS participant events (always needed)
        self.rtms_client.set_participant_joined_callback(self._on_participant_joined)

    async def _on_rtms_audio(
        self,
        audio_data: bytes,
        participant_id: str,
        timestamp: datetime
    ) -> None:
        """Handle audio from RTMS

        Args:
            audio_data: Raw PCM audio bytes
            participant_id: Participant identifier
            timestamp: Audio timestamp
        """
        # Add to audio buffer (will trigger VAD packet creation)
        await self.audio_buffer.add_audio(audio_data, timestamp, speaker_id=participant_id)

        # Record audio if enabled
        if self.recorder:
            audio_array = pcm_to_numpy(audio_data)
            self.recorder.add_audio(audio_array, participant_id)

    async def _on_vad_packet_ready(self, audio_chunk: AudioChunk) -> None:
        """Handle VAD packet ready (0.1s): run VAD, forward to SpeechProcessor.

        Args:
            audio_chunk: Audio chunk for VAD processing.
        """
        # 1. Run local VAD
        vad_result = self.vad_client.process_audio(audio_chunk)

        # 2. Get or create SpeechProcessor for this speaker
        processor = self._get_speech_processor(audio_chunk.speaker_id)

        # 3. Convert int16 PCM to float32 for SpeechProcessor
        audio_float32 = audio_chunk.data.astype(np.float32) / 32768.0

        # 4. Forward VAD result + audio to SpeechProcessor
        timestamp = audio_chunk.timestamp.timestamp()  # datetime -> float seconds
        newly_committed = await processor.on_vad_result(
            is_speech=vad_result.is_speech,
            audio_float32=audio_float32,
            timestamp=timestamp,
        )

        # 5. Forward committed words to TranscriptionHandler
        for start_time, end_time, text in newly_committed:
            self.transcription_handler.add_transcription(
                text=text,
                speaker_id=audio_chunk.speaker_id,
                timestamp=audio_chunk.timestamp,
                start_time=start_time,
                end_time=end_time,
            )

    async def _on_rtms_transcription(
        self,
        transcription: Dict[str, Any],
        participant_id: str,
        timestamp: datetime
    ) -> None:
        """Handle transcription from RTMS (RTMS mode only).

        Args:
            transcription: Transcription result from RTMS
            participant_id: Participant identifier
            timestamp: Transcription timestamp
        """
        text = transcription.get('text', '')
        confidence = transcription.get('confidence')
        start_time = transcription.get('start_time')
        end_time = transcription.get('end_time')

        if text:
            self.transcription_handler.add_transcription(
                text=text,
                speaker_id=participant_id,
                timestamp=timestamp,
                confidence=confidence,
                start_time=start_time,
                end_time=end_time,
            )

    def _on_participant_joined(self, participant_id: str, event: Dict[str, Any]) -> None:
        """Handle participant joined event

        Args:
            participant_id: Participant identifier
            event: Event data
        """
        participant_name = event.get('participant_name')

        if participant_name:
            self.transcription_handler.update_speaker_name(
                participant_id,
                participant_name
            )

    async def stop(self) -> None:
        """Stop the transcription system"""
        self.is_running = False

        self.logger.info("system_stopping")

        # Flush speech processors (custom mode only)
        if self.asr_mode == 'custom' and self.speech_processors:
            for processor in self.speech_processors.values():
                committed = await processor.flush()
                for start_time, end_time, text in committed:
                    self.transcription_handler.add_transcription(
                        text=text,
                        speaker_id=processor.speaker_id,
                        timestamp=datetime.utcnow(),
                        start_time=start_time,
                        end_time=end_time,
                    )

        # Flush audio buffer (custom mode only)
        if self.audio_buffer:
            await self.audio_buffer.flush()

        # Disconnect clients (custom mode only)
        if self.asr_mode == 'custom':
            await asyncio.gather(
                self.vad_client.disconnect(),
                self.asr_client.disconnect(),
                return_exceptions=True
            )

        # Leave RTMS meeting
        self.rtms_client.leave()

        # Stop recording
        if self.recorder:
            recorded_files = self.recorder.stop_recording()
            self.logger.info("recordings_saved", files=list(recorded_files.values()))

        # Save transcription
        transcript_path = self.transcription_handler.save_transcription()
        if transcript_path:
            self.logger.info("transcription_saved", path=str(transcript_path))

        # Print statistics
        stats = self.transcription_handler.get_statistics()
        self.logger.info("transcription_statistics", **stats)

        self.logger.info("system_stopped")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def start_with_webhook(config: Dict[str, Any]):
    """Start system with webhook integration

    This mode listens for Zoom webhooks and automatically joins meetings.
    """
    logger = get_logger(__name__)
    logger.info("starting_webhook_mode")

    stream_mode = config['audio'].get('stream_mode', 'mixed')

    # Create webhook handler
    webhook_handler = RTMSWebhookHandler(
        client_id=config['zoom']['client_id'],
        client_secret=config['zoom']['client_secret'],
        port=config.get('webhook', {}).get('port', 8080),
        path=config.get('webhook', {}).get('path', '/webhook'),
        stream_mode=stream_mode
    )

    # Track systems by stream ID
    systems: Dict[str, RTMSTranscriptionSystem] = {}

    def on_meeting_started(client: RTMSClient, payload: Dict[str, Any]):
        """Called when a meeting starts"""
        rtms_stream_id = payload.get('rtms_stream_id')

        logger.info("meeting_started_webhook", rtms_stream_id=rtms_stream_id)

        system = RTMSTranscriptionSystem(config)
        system.rtms_client = client

        # Setup callbacks
        system._setup_callbacks()

        if system.recorder:
            system.recorder.start_recording(rtms_stream_id)

        system.transcription_handler.start_session(rtms_stream_id)
        system.is_running = True

        systems[rtms_stream_id] = system

        # Connect services
        asyncio.create_task(system._connect_services())

    def on_meeting_ended(rtms_stream_id: str, payload: Dict[str, Any]):
        """Called when a meeting ends"""
        logger.info("meeting_ended_webhook", rtms_stream_id=rtms_stream_id)

        if rtms_stream_id in systems:
            system = systems[rtms_stream_id]
            asyncio.create_task(system.stop())
            del systems[rtms_stream_id]

    # Set callbacks
    webhook_handler.set_meeting_started_callback(on_meeting_started)
    webhook_handler.set_meeting_ended_callback(on_meeting_ended)

    # Start webhook server
    webhook_handler.start()

    logger.info("webhook_server_running")

    # Keep running
    try:
        while True:
            webhook_handler.poll_all()
            await asyncio.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("webhook_mode_interrupted")


async def start_direct(
    config: Dict[str, Any],
    meeting_uuid: str,
    rtms_stream_id: str,
    server_urls: list
):
    """Start system with direct meeting connection

    This mode directly joins a specific meeting.
    """
    logger = get_logger(__name__)
    logger.info("starting_direct_mode", meeting_uuid=meeting_uuid)

    system = RTMSTranscriptionSystem(config)
    await system.start(meeting_uuid, rtms_stream_id, server_urls)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Zoom RTMS Real-Time Transcription System"
    )
    parser.add_argument(
        "--mode",
        choices=["webhook", "direct"],
        default="webhook",
        help="Operation mode: webhook (listen for events) or direct (join specific meeting)"
    )
    parser.add_argument(
        "--meeting-uuid",
        help="Meeting UUID (required for direct mode)"
    )
    parser.add_argument(
        "--rtms-stream-id",
        help="RTMS stream ID (required for direct mode)"
    )
    parser.add_argument(
        "--server-urls",
        nargs='+',
        help="RTMS server URLs (required for direct mode)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(config['logging'])

    logger = get_logger(__name__)
    logger.info("starting_rtms_transcription_system", mode=args.mode)

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start system
    try:
        if args.mode == "webhook":
            await start_with_webhook(config)
        else:  # direct mode
            if not all([args.meeting_uuid, args.rtms_stream_id, args.server_urls]):
                print("Error: direct mode requires --meeting-uuid, --rtms-stream-id, and --server-urls")
                sys.exit(1)

            await start_direct(
                config,
                args.meeting_uuid,
                args.rtms_stream_id,
                args.server_urls
            )

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
    except Exception as e:
        logger.error("system_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
