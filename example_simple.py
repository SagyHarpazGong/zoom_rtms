"""Simple example using official Zoom RTMS SDK

This demonstrates the minimal code needed to join a meeting and receive audio.
"""

import rtms
import time
import os

# Set your credentials (or use environment variables)
CLIENT_ID = os.getenv("ZM_RTMS_CLIENT", "your_client_id")
CLIENT_SECRET = os.getenv("ZM_RTMS_SECRET", "your_client_secret")


def simple_webhook_example():
    """Example: Listen for webhooks and automatically join meetings"""

    print("🚀 Starting webhook server on http://localhost:8080/webhook")
    print("📝 Configure your Zoom app to send webhooks to this endpoint\n")

    # Dictionary to track active clients
    clients = {}

    @rtms.onWebhookEvent(port=8080, path='/webhook')
    def handle_webhook(webhook):
        """Called when Zoom sends a webhook event"""
        event = webhook.get('event')
        payload = webhook.get('payload', {})

        print(f"📩 Webhook received: {event}")

        if event == 'meeting.rtms_started':
            # Meeting started - join it!
            rtms_stream_id = payload.get('rtms_stream_id')

            print(f"✅ Meeting started: {rtms_stream_id}")

            # Create RTMS client
            client = rtms.Client()

            # Setup audio parameters
            audio_params = rtms.AudioParams(
                content_type=rtms.AudioContentType['RAW_AUDIO'],
                codec=rtms.AudioCodec['PCM'],
                sample_rate=rtms.AudioSampleRate['SR_16K'],
                channel=rtms.AudioChannel['MONO'],
                data_opt=rtms.AudioDataOption['AUDIO_MIXED_STREAM'],
                duration=20,
                frame_size=640
            )
            client.setAudioParams(audio_params)

            # Setup callbacks
            @client.onJoinConfirm
            def on_join(result, reason):
                print(f"🎉 Joined meeting! Result: {result}")

            @client.onAudioData
            def on_audio(buffer, size, timestamp, metadata):
                # Audio data received!
                print(f"🎵 Audio: {size} bytes at {timestamp}")

                # TODO: Send to your VAD server here
                # TODO: Then to your ASR server
                # TODO: Then output transcription

            @client.onLeave
            def on_leave(reason):
                print(f"👋 Left meeting: {reason}")

            # Join the meeting
            client.join(
                meeting_uuid=payload.get('meeting_uuid'),
                rtms_stream_id=rtms_stream_id,
                server_urls=payload.get('server_urls'),
                signature=payload.get('signature')
            )

            clients[rtms_stream_id] = client

        elif event == 'meeting.rtms_ended':
            # Meeting ended
            rtms_stream_id = payload.get('rtms_stream_id')
            print(f"❌ Meeting ended: {rtms_stream_id}")

            if rtms_stream_id in clients:
                clients[rtms_stream_id].leave()
                del clients[rtms_stream_id]

    # Keep polling for events
    print("⏳ Waiting for webhook events...\n")

    try:
        while True:
            # Poll all active clients
            for client in clients.values():
                client._poll_if_needed()

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")


def direct_join_example(meeting_uuid, rtms_stream_id, server_urls):
    """Example: Directly join a specific meeting"""

    print(f"🚀 Joining meeting: {meeting_uuid}")

    # Create RTMS client
    client = rtms.Client()

    # Setup audio parameters for 16kHz mono PCM
    audio_params = rtms.AudioParams(
        content_type=rtms.AudioContentType['RAW_AUDIO'],
        codec=rtms.AudioCodec['PCM'],
        sample_rate=rtms.AudioSampleRate['SR_16K'],
        channel=rtms.AudioChannel['MONO'],
        data_opt=rtms.AudioDataOption['AUDIO_MIXED_STREAM'],
        duration=20,  # 20ms frames
        frame_size=640  # 16000 Hz * 1 channel * 20ms / 1000
    )
    client.setAudioParams(audio_params)

    # Setup callbacks
    @client.onJoinConfirm
    def on_join(result, reason):
        print(f"✅ Join confirmed: {result}, {reason}")

    @client.onAudioData
    def on_audio(buffer, size, timestamp, metadata):
        audio_data = bytes(buffer[:size])
        print(f"🎵 Received {size} bytes of audio at {timestamp}")

        # TODO: Your processing here
        # 1. Send to VAD server (0.1s packets)
        # 2. Based on VAD, accumulate speech
        # 3. Send to ASR server (2.5s segments)
        # 4. Output transcription

    @client.onParticipantEvent
    def on_participant(event):
        participant_id = event.get('participant_id')
        event_type = event.get('event_type')
        participant_name = event.get('participant_name', 'Unknown')

        print(f"👤 {participant_name} ({participant_id}) {event_type}")

    @client.onLeave
    def on_leave(reason):
        print(f"👋 Left meeting: {reason}")

    # Generate signature
    signature = rtms.generate_signature(
        CLIENT_ID,
        CLIENT_SECRET,
        meeting_uuid,
        rtms_stream_id
    )

    # Join meeting
    client.join(
        meeting_uuid=meeting_uuid,
        rtms_stream_id=rtms_stream_id,
        server_urls=server_urls,
        signature=signature
    )

    print("⏳ Listening for audio...\n")

    # Poll for events
    try:
        while True:
            client._poll_if_needed()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n👋 Leaving meeting...")
        client.leave()


if __name__ == "__main__":
    import sys

    print("="*60)
    print("  Simple Zoom RTMS Example")
    print("="*60)
    print()

    if len(sys.argv) == 1:
        # Default: webhook mode
        simple_webhook_example()

    elif len(sys.argv) >= 4:
        # Direct mode
        meeting_uuid = sys.argv[1]
        rtms_stream_id = sys.argv[2]
        server_urls = sys.argv[3:]

        direct_join_example(meeting_uuid, rtms_stream_id, server_urls)

    else:
        print("Usage:")
        print("  Webhook mode (default):")
        print("    python example_simple.py")
        print()
        print("  Direct mode:")
        print("    python example_simple.py <meeting_uuid> <rtms_stream_id> <server_url1> [server_url2...]")
        sys.exit(1)
