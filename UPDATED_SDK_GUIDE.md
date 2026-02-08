# Updated Guide - Using Official Zoom RTMS SDK

## What Changed

The project has been updated to use the **official Zoom RTMS Python SDK** (`rtms` package), which provides:

✅ **Built-in authentication** - Automatic signature generation
✅ **Simplified connection** - No manual WebSocket handling
✅ **Robust callbacks** - Native audio, video, and transcript callbacks
✅ **Webhook support** - Automatic meeting join via webhooks
✅ **Production-ready** - Officially supported by Zoom

## Installation

```bash
pip install -r requirements.txt
```

The `rtms` SDK is now included in requirements.txt.

## Two Operation Modes

### 1. Webhook Mode (Recommended)

Listen for Zoom webhooks and automatically join meetings when they start.

**Setup:**

1. Configure your Zoom app to send webhooks to your server:
   ```
   https://your-server.com:8080/webhook
   ```

2. Update `config.yaml`:
   ```yaml
   zoom:
     client_id: "your_zoom_client_id"
     client_secret: "your_zoom_client_secret"

   webhook:
     port: 8080
     path: "/webhook"
   ```

3. Run in webhook mode:
   ```bash
   python main.py --mode webhook
   ```

**How it works:**
- Server listens for `meeting.rtms_started` events from Zoom
- Automatically creates RTMS client and joins meeting
- Starts transcription automatically
- Handles `meeting.rtms_ended` events to cleanup

**Use with ngrok for testing:**
```bash
# Terminal 1: Start ngrok
ngrok http 8080

# Terminal 2: Run the system
python main.py --mode webhook

# Use the ngrok URL as your Zoom webhook endpoint
```

### 2. Direct Mode

Manually join a specific meeting with RTMS credentials.

```bash
python main.py --mode direct \
  --meeting-uuid "abc123..." \
  --rtms-stream-id "stream123..." \
  --server-urls "https://rtms1.zoom.us" "https://rtms2.zoom.us"
```

**When to use:**
- Testing specific meetings
- Manual control over which meetings to join
- Custom webhook handling elsewhere

## Configuration

### config.yaml

```yaml
# Zoom RTMS Configuration
zoom:
  client_id: "your_zoom_client_id"          # From Zoom Marketplace app
  client_secret: "your_zoom_client_secret"  # From Zoom Marketplace app

# Webhook Configuration
webhook:
  port: 8080          # Port for webhook server
  path: "/webhook"    # Path for webhook endpoint

# VAD Server (unchanged)
vad:
  ws_url: "ws://localhost:8001/vad"
  packet_duration_ms: 100  # 0.1 seconds

# ASR Server (unchanged)
asr:
  ws_url: "ws://localhost:8002/asr"
  segment_duration_seconds: 2.5  # 2.5 seconds
  enable_diarization: true

# Audio, buffering, recording, transcription (unchanged)
# ... rest of config ...
```

### Environment Variables

Or use `.env` file:

```bash
ZM_RTMS_CLIENT=your_client_id
ZM_RTMS_SECRET=your_client_secret
ZM_RTMS_PORT=8080
ZM_RTMS_PATH=/webhook
```

## How Audio Flows with SDK

```
Zoom Meeting
    │
    ↓ RTMS SDK (official)
@client.onAudioData callback
    │ (20ms PCM frames by default)
    ↓
Audio Buffer
    │ (accumulate to 100ms)
    ↓
VAD Client → VAD Server (0.1s packets)
    │
    ↓ (speech detection)
Speech Buffer
    │ (accumulate to 2.5s)
    ↓
ASR Client → ASR Server (2.5s segments)
    │
    ↓ (transcription)
Transcription Handler
    │
    ↓
Output + Recording
```

## SDK Audio Configuration

The SDK automatically configures audio parameters in `rtms_client.py:_configure_audio_params()`:

```python
params = rtms.AudioParams(
    content_type=rtms.AudioContentType['RAW_AUDIO'],
    codec=rtms.AudioCodec['PCM'],
    sample_rate=rtms.AudioSampleRate['SR_16K'],  # 16kHz
    channel=rtms.AudioChannel['MONO'],            # Mono
    data_opt=rtms.AudioDataOption['AUDIO_MIXED_STREAM'],  # Mixed audio
    duration=20,      # 20ms frames
    frame_size=640    # 16kHz * 1 channel * 20ms / 1000
)
```

**Supported configurations:**
- **Sample rates**: 8kHz, 16kHz, 32kHz, 48kHz
- **Channels**: Mono, Stereo
- **Codecs**: PCM (raw), Opus
- **Data options**:
  - `AUDIO_MIXED_STREAM` - All participants mixed
  - `AUDIO_SINGLE_ACTIVE_STREAM` - Active speaker only
  - Individual participant streams

## SDK Callbacks

The RTMS SDK provides these callbacks (configured in `rtms_client.py`):

```python
@client.onJoinConfirm
def on_join_confirm(result, reason):
    """Called when join succeeds/fails"""

@client.onSessionUpdate
def on_session_update(state):
    """Called on session state changes"""

@client.onParticipantEvent
def on_participant_event(event):
    """Called when participants join/leave"""

@client.onAudioData
def on_audio_data(buffer, size, timestamp, metadata):
    """Called for each audio frame (20ms by default)"""
    # This is where audio enters our pipeline

@client.onVideoData
def on_video_data(buffer, size, timestamp, metadata):
    """Called for video frames (optional)"""

@client.onTranscriptData
def on_transcript_data(buffer, size, timestamp, metadata):
    """Called for Zoom's built-in transcripts (optional)"""

@client.onLeave
def on_leave(reason):
    """Called when leaving meeting"""
```

## Zoom App Setup

### 1. Create Zoom App

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Click "Develop" → "Build App"
3. Choose "General App"
4. Enable "Event Subscriptions"

### 2. Configure Webhooks

**Event subscriptions:**
- `meeting.rtms_started` - Meeting RTMS stream starts
- `meeting.rtms_ended` - Meeting RTMS stream ends

**Webhook endpoint:**
```
https://your-domain.com:8080/webhook
```

Or for testing with ngrok:
```
https://abc123.ngrok.io/webhook
```

### 3. Get Credentials

From your Zoom app settings:
- **Client ID** → Put in `config.yaml` as `client_id`
- **Client Secret** → Put in `config.yaml` as `client_secret`

### 4. Enable RTMS

In your Zoom app settings:
- Go to "Features"
- Enable "Real-time Media Streams (RTMS)"
- Configure required permissions

## Examples

### Example 1: Basic Webhook Setup

```python
# Minimal example using webhook mode
import asyncio
from main import main

if __name__ == "__main__":
    asyncio.run(main())
```

Run:
```bash
python main.py --mode webhook --config config.yaml
```

### Example 2: Custom Processing

```python
# src/rtms_client.py callback in action
@client.onAudioData
def on_audio_data(buffer, size, timestamp, metadata):
    # Audio data arrives here as PCM bytes
    audio_data = bytes(buffer[:size])

    # Forward to our pipeline
    # → Audio Buffer → VAD → Speech Buffer → ASR → Transcription
```

### Example 3: Multi-Meeting Support

The webhook handler automatically manages multiple concurrent meetings:

```python
# Webhook handler tracks multiple meetings
webhook_handler = RTMSWebhookHandler(client_id, client_secret)

# Each meeting.rtms_started event creates a new client
# Each client has its own:
# - RTMS connection
# - VAD/ASR processing
# - Transcription handler
# - Audio recorder
```

## Differences from Previous Version

| Aspect | Old (Custom WebSocket) | New (Official SDK) |
|--------|------------------------|-------------------|
| **Connection** | Manual WebSocket implementation | SDK handles connection |
| **Authentication** | Manual JWT generation | `rtms.generate_signature()` |
| **Audio callbacks** | Custom message parsing | Native `@client.onAudioData` |
| **Participant tracking** | Manual parsing | Native `@client.onParticipantEvent` |
| **Reconnection** | Manual retry logic | SDK handles automatically |
| **Event loop** | Fully async | Poll + async hybrid |
| **Webhooks** | Not included | Built-in `@rtms.onWebhookEvent` |

## Troubleshooting

### Issue: "Failed to join RTMS meeting"

**Check:**
- Client ID and secret are correct
- Meeting has RTMS enabled
- `meeting_uuid` and `rtms_stream_id` are valid
- Server URLs are correct

### Issue: "No audio received"

**Check:**
- Audio params are configured (see logs for "audio_params_configured")
- Meeting has active audio
- `@client.onAudioData` callback is being called (check logs)

### Issue: "Webhook not receiving events"

**Check:**
- Webhook server is running (`webhook_server_running` in logs)
- Port 8080 is accessible (not blocked by firewall)
- Zoom app is configured with correct webhook URL
- ngrok tunnel is active (if using ngrok)
- Webhook endpoint validation passed in Zoom settings

### Issue: "Import error: No module named 'rtms'"

**Fix:**
```bash
pip install rtms
# or
pip install -r requirements.txt
```

## Advanced Usage

### Custom Audio Processing

Modify `rtms_client.py:_configure_audio_params()` to change audio settings:

```python
# Get individual participant streams instead of mixed
params = rtms.AudioParams(
    # ... other params ...
    data_opt=rtms.AudioDataOption['AUDIO_INDIVIDUAL_STREAMS']
)
```

### Video Processing

Enable video callbacks:

```python
# Configure video
params = rtms.VideoParams(
    content_type=rtms.VideoContentType['RAW_VIDEO'],
    codec=rtms.VideoCodec['H264'],
    resolution=rtms.VideoResolution['HD'],
    data_opt=rtms.VideoDataOption['VIDEO_SINGLE_ACTIVE_STREAM'],
    fps=30
)
client.setVideoParams(params)

# Handle video data
@client.onVideoData
def on_video_data(buffer, size, timestamp, metadata):
    video_frame = bytes(buffer[:size])
    # Process video frame
```

### Use Zoom's Built-in Transcripts

Instead of VAD/ASR pipeline, use Zoom's native transcription:

```python
@client.onTranscriptData
def on_transcript_data(buffer, size, timestamp, metadata):
    transcript = buffer[:size].decode('utf-8')
    speaker = metadata.userName
    print(f"{speaker}: {transcript}")
```

## Performance Notes

- **Polling overhead**: SDK uses polling (`client._poll_if_needed()`) which is called every 10ms
- **Audio latency**: 20ms frames by default (configurable via `duration` parameter)
- **Memory**: SDK manages its own buffers, minimal overhead
- **CPU**: Efficient C++ core with Python bindings

## Next Steps

1. **Setup Zoom app** with webhook endpoint
2. **Configure credentials** in `config.yaml`
3. **Start in webhook mode** for production use
4. **Test with your VAD/ASR servers** - adjust message formats as needed
5. **Deploy with proper SSL** - Zoom requires HTTPS for webhooks (use ngrok or proper SSL certs)

## Resources

- [Official RTMS SDK Documentation](https://zoom.github.io/rtms/py/)
- [RTMS SDK GitHub](https://github.com/zoom/rtms)
- [Zoom RTMS Quickstart](https://github.com/zoom/rtms-quickstart-py)
- [Zoom Developer Docs](https://developers.zoom.us/docs/rtms/)
