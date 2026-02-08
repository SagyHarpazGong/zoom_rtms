# Zoom RTMS Real-Time Transcription System

A Python-based system for real-time transcription of Zoom meetings using the **official Zoom RTMS SDK**, with Voice Activity Detection (VAD) and Automatic Speech Recognition (ASR).

> **✨ Now using the official Zoom RTMS Python SDK for reliable, production-ready connections!**

## Architecture

```
Zoom RTMS → Audio Buffer → VAD (0.1s) → Speech Segments → ASR (2.5s) → Transcription
                ↓                                           ↓
           Recording                              Real-time Output
```

### Components

1. **RTMS Client**: Connects to Zoom's RTMS WebSocket and receives audio streams
2. **VAD Client**: Processes 0.1s audio packets for voice activity detection
3. **ASR Client**: Processes 2.5s speech segments for transcription
4. **Audio Buffer**: Manages audio packet accumulation and buffering
5. **Speech Segment Manager**: Accumulates speech based on VAD results
6. **Transcription Handler**: Manages output, diarization, and recording

## Features

- ✅ Real-time audio streaming from Zoom meetings
- ✅ Voice Activity Detection (100ms packets)
- ✅ Automatic Speech Recognition (2.5s segments)
- ✅ Multi-speaker diarization support
- ✅ Real-time transcription streaming
- ✅ Meeting recording (audio + transcripts)

## Prerequisites

- Python 3.8+
- Zoom Marketplace app with RTMS enabled
- Zoom Client ID and Client Secret
- VAD server running on WebSocket
- ASR server running on WebSocket

## Configuration

Edit `config.yaml` to configure:
- Zoom RTMS credentials and endpoints
- VAD server WebSocket URL
- ASR server WebSocket URL
- Audio parameters (sample rate, channels, etc.)
- Recording settings

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Webhook Mode (Recommended)

Automatically join meetings via Zoom webhooks:

```bash
python main.py --mode webhook
```

### Direct Mode

Manually join a specific meeting:

```bash
python main.py --mode direct \
  --meeting-uuid <uuid> \
  --rtms-stream-id <stream_id> \
  --server-urls <url1> <url2>
```

See [UPDATED_SDK_GUIDE.md](UPDATED_SDK_GUIDE.md) for detailed setup instructions.

## Project Structure

```
zoom_rtms/
├── main.py                      # Entry point
├── config.yaml                  # Configuration
├── requirements.txt             # Dependencies
├── src/
│   ├── rtms_client.py          # Zoom RTMS WebSocket client
│   ├── vad_client.py           # VAD WebSocket client
│   ├── asr_client.py           # ASR WebSocket client
│   ├── audio_buffer.py         # Audio buffering logic
│   ├── speech_segment.py       # Speech segment management
│   ├── transcription_handler.py # Transcription output handler
│   ├── recorder.py             # Meeting recording
│   └── utils.py                # Utility functions
└── tests/                      # Unit tests
```

## Audio Flow

1. **RTMS Reception**: Audio received from Zoom (typically 20-40ms chunks)
2. **VAD Buffering**: Accumulate to 100ms packets (0.1s)
3. **VAD Processing**: Send to VAD server, receive voice activity status
4. **Speech Accumulation**: Buffer speech segments when VAD detects activity
5. **ASR Processing**: Send 2.5s speech segments to ASR server
6. **Transcription**: Receive and output transcriptions with speaker labels

## License

MIT
