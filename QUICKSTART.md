# Quick Start Guide

## Prerequisites

1. **Python 3.8+** installed
2. **VAD Server** running and accessible via WebSocket
3. **ASR Server** running and accessible via WebSocket
4. **Zoom RTMS** API credentials

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the System

Edit `config.yaml` with your settings:

```yaml
# Zoom credentials
zoom:
  rtms_url: "wss://rtms.zoom.us/ws"
  api_key: "your_api_key"
  api_secret: "your_api_secret"

# VAD server endpoint
vad:
  ws_url: "ws://localhost:8001/vad"

# ASR server endpoint
asr:
  ws_url: "ws://localhost:8002/asr"
```

Or use environment variables (copy `.env.example` to `.env`):

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run the System

```bash
python main.py --meeting-id <your_zoom_meeting_id>
```

## Architecture Overview

### Audio Flow

```
┌─────────────┐
│  Zoom RTMS  │ ← Audio streams from meeting
└──────┬──────┘
       │ Raw audio (20-40ms chunks)
       ↓
┌─────────────────┐
│  Audio Buffer   │ ← Accumulates audio
└──────┬──────────┘
       │ 0.1s packets
       ↓
┌─────────────┐
│ VAD Client  │ ← Voice Activity Detection
└──────┬──────┘
       │ Speech/Non-speech labels
       ↓
┌─────────────────┐
│ Speech Buffer   │ ← Accumulates speech segments
└──────┬──────────┘
       │ 2.5s speech segments
       ↓
┌─────────────┐
│ ASR Client  │ ← Speech Recognition
└──────┬──────┘
       │ Transcriptions
       ↓
┌──────────────────────┐
│ Transcription Handler│ ← Output & Recording
└──────────────────────┘
```

### Components

1. **RTMS Client**: Connects to Zoom and receives audio
2. **Audio Buffer**: Manages audio accumulation
   - Buffers incoming audio to 0.1s packets for VAD
   - Accumulates speech segments to 2.5s for ASR
3. **VAD Client**: Detects voice activity in 0.1s packets
4. **ASR Client**: Transcribes 2.5s speech segments
5. **Transcription Handler**: Outputs and saves transcriptions
6. **Recorder**: Saves raw audio (optional)

## Configuration Details

### Audio Settings

```yaml
audio:
  sample_rate: 16000  # 16kHz (standard for speech)
  channels: 1         # Mono
  bit_depth: 16       # 16-bit PCM
```

### Buffering Settings

```yaml
buffering:
  vad_buffer_size_ms: 100              # VAD packet size
  speech_buffer_size_seconds: 5.0      # Max speech buffer
  silence_timeout_seconds: 1.0         # Silence before ASR trigger
  min_speech_duration_ms: 500          # Min speech to process
```

### Output Formats

Supported transcription output formats:
- `json`: Structured JSON with metadata
- `text`: Plain text with optional timestamps and speakers
- `srt`: Subtitle format

## WebSocket Message Formats

### VAD Server Expected Format

**Request** (to VAD server):
```json
{
  "audio": "hex_encoded_pcm_data",
  "sample_rate": 16000,
  "timestamp": "2024-01-01T12:00:00.000Z",
  "audio_id": 12345
}
```

**Response** (from VAD server):
```json
{
  "is_speech": true,
  "audio_id": 12345,
  "confidence": 0.95
}
```

### ASR Server Expected Format

**Request** (to ASR server):
```json
{
  "audio": "hex_encoded_pcm_data",
  "sample_rate": 16000,
  "timestamp": "2024-01-01T12:00:00.000Z",
  "audio_id": 12345,
  "enable_diarization": true,
  "speaker_id": "participant_123"
}
```

**Response** (from ASR server):
```json
{
  "text": "Hello, this is a transcribed sentence",
  "speaker_id": "speaker_1",
  "confidence": 0.92,
  "audio_id": 12345,
  "start_time": 0.0,
  "end_time": 2.5
}
```

## Customization

### Adjusting VAD Packet Size

To change the VAD packet duration (default 0.1s):

```yaml
vad:
  packet_duration_ms: 200  # Change to 0.2 seconds
```

### Adjusting ASR Segment Size

To change the ASR segment duration (default 2.5s):

```yaml
asr:
  segment_duration_seconds: 3.0  # Change to 3 seconds
```

### Changing Output Format

```yaml
transcription:
  output_format: "text"  # or "json", "srt"
  enable_timestamps: true
  enable_speaker_labels: true
  real_time_output: true
```

## Troubleshooting

### Connection Issues

If connections fail:
1. Check that VAD and ASR servers are running
2. Verify WebSocket URLs in `config.yaml`
3. Check firewall settings
4. Review logs in `logs/` directory

### Audio Issues

If no audio is received:
1. Verify Zoom RTMS credentials
2. Check meeting ID is correct
3. Ensure meeting has audio enabled
4. Review RTMS connection logs

### Performance Issues

If experiencing delays:
1. Reduce buffer sizes
2. Adjust silence timeout
3. Check network latency to servers
4. Consider running VAD/ASR locally

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

## Next Steps

- Implement proper Zoom RTMS authentication (see `rtms_client.py:_generate_token()`)
- Adjust message formats to match your VAD/ASR servers
- Add error recovery and retry logic
- Implement metrics and monitoring
- Add support for multiple meetings simultaneously
- Optimize buffer sizes for your use case

## Support

For issues and questions:
- Check logs in `logs/zoom_rtms.log`
- Review configuration in `config.yaml`
- Ensure all prerequisites are met
