# Architecture Documentation

## System Overview

The Zoom RTMS Real-Time Transcription System is designed to provide real-time speech transcription from Zoom meetings using Voice Activity Detection (VAD) and Automatic Speech Recognition (ASR).

## High-Level Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Zoom Meeting (Cloud)                       │
└────────────────────────────┬──────────────────────────────────┘
                             │
                    Audio Streams (RTMS)
                             │
                             ↓
┌────────────────────────────────────────────────────────────────┐
│                    RTMSTranscriptionSystem                      │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ RTMS Client  │    │  VAD Client  │    │  ASR Client  │    │
│  │  (WebSocket) │    │  (WebSocket) │    │  (WebSocket) │    │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    │
│         │                   │                    │             │
│         │                   │                    │             │
│  ┌──────▼──────────────────────────────────────────────────┐  │
│  │              Audio Buffer Manager                        │  │
│  │  • Accumulates audio to 0.1s for VAD                    │  │
│  │  • Accumulates speech to 2.5s for ASR                   │  │
│  │  • Manages speech/silence state                         │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                      │
│  ┌──────▼─────────────┐    ┌─────────────────────┐           │
│  │ Transcription      │    │  Audio Recorder     │           │
│  │ Handler            │    │  (Multi-track WAV)  │           │
│  │ • Real-time output │    │                     │           │
│  │ • Speaker labeling │    │                     │           │
│  │ • Format conversion│    │                     │           │
│  └────────────────────┘    └─────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. RTMS Client (`rtms_client.py`)

**Purpose**: Establishes WebSocket connection to Zoom's Real-Time Media Streaming service.

**Responsibilities**:
- Authenticate with Zoom RTMS API
- Subscribe to audio streams
- Receive raw audio data from meeting participants
- Track participant join/leave events
- Handle connection lifecycle and reconnection

**Key Methods**:
- `connect()`: Establish WebSocket connection
- `_subscribe_to_audio()`: Subscribe to audio streams
- `_handle_audio_data()`: Process incoming audio
- `_handle_event()`: Process RTMS events (join/leave)

**Data Flow**:
- **Input**: Zoom RTMS WebSocket connection
- **Output**: Raw PCM audio bytes + participant metadata

### 2. Audio Buffer Manager (`audio_buffer.py`)

**Purpose**: Central audio processing hub that manages buffering and routing.

**Responsibilities**:
- Accumulate incoming audio to VAD packet size (0.1s)
- Maintain speech buffer based on VAD results
- Accumulate speech segments to ASR size (2.5s)
- Detect silence timeouts
- Route audio to appropriate processors

**Key Components**:

```python
class AudioBuffer:
    vad_buffer: np.ndarray      # Accumulates to 0.1s
    speech_buffer: np.ndarray   # Accumulates speech for ASR
    is_speech_active: bool      # Current speech state
    last_speech_time: datetime  # For silence timeout detection
```

**Key Methods**:
- `add_audio()`: Add incoming audio from RTMS
- `on_vad_result()`: Process VAD detection results
- `_send_to_asr()`: Send accumulated speech to ASR

**Buffer Management Logic**:

```
1. RTMS Audio → VAD Buffer
   ├─ Accumulate until 0.1s
   └─ Send to VAD Client

2. VAD Result → Speech State
   ├─ If speech detected:
   │  ├─ Add to speech buffer
   │  └─ Check if 2.5s accumulated → Send to ASR
   └─ If no speech:
      └─ Check silence timeout → Send remaining speech to ASR

3. Silence Timeout
   └─ If speech_duration > min_duration → Send to ASR
```

### 3. VAD Client (`vad_client.py`)

**Purpose**: Interface with Voice Activity Detection server.

**Responsibilities**:
- Maintain WebSocket connection to VAD server
- Send 0.1s audio packets
- Receive speech/non-speech classifications
- Handle reconnection on failure

**Message Format**:
```json
// Request
{
  "audio": "hex_encoded_pcm",
  "sample_rate": 16000,
  "timestamp": "ISO-8601",
  "audio_id": 12345
}

// Response
{
  "is_speech": true,
  "audio_id": 12345,
  "confidence": 0.95
}
```

**Timing**:
- Packet Duration: **100ms (0.1s)**
- Sample Count: **1,600 samples** at 16kHz
- Processing Frequency: **10 packets/second**

### 4. ASR Client (`asr_client.py`)

**Purpose**: Interface with Automatic Speech Recognition server.

**Responsibilities**:
- Maintain WebSocket connection to ASR server
- Send 2.5s speech segments
- Receive transcription results
- Support speaker diarization
- Handle reconnection on failure

**Message Format**:
```json
// Request
{
  "audio": "hex_encoded_pcm",
  "sample_rate": 16000,
  "timestamp": "ISO-8601",
  "audio_id": 12345,
  "enable_diarization": true,
  "speaker_id": "participant_123"
}

// Response
{
  "text": "transcribed text",
  "speaker_id": "speaker_1",
  "confidence": 0.92,
  "audio_id": 12345,
  "start_time": 0.0,
  "end_time": 2.5
}
```

**Timing**:
- Segment Duration: **2,500ms (2.5s)**
- Sample Count: **40,000 samples** at 16kHz
- Processing Frequency: Variable based on speech activity

### 5. Transcription Handler (`transcription_handler.py`)

**Purpose**: Manage transcription output and formatting.

**Responsibilities**:
- Store transcription segments
- Format output (JSON, text, SRT)
- Add timestamps and speaker labels
- Real-time console output
- Save final transcription to file

**Output Formats**:

**JSON**:
```json
{
  "session_id": "meeting_123",
  "start_time": "2024-01-01T12:00:00Z",
  "speakers": {
    "speaker_1": "John Doe"
  },
  "transcriptions": [
    {
      "text": "Hello everyone",
      "speaker_id": "speaker_1",
      "timestamp": "2024-01-01T12:00:15Z",
      "confidence": 0.95
    }
  ]
}
```

**Text**:
```
[12:00:15] John Doe: Hello everyone
[12:00:18] Jane Smith: Hi John, how are you?
```

**SRT** (Subtitles):
```
1
00:00:15,000 --> 00:00:18,000
Hello everyone

2
00:00:18,000 --> 00:00:22,000
Hi John, how are you?
```

### 6. Audio Recorder (`recorder.py`)

**Purpose**: Record meeting audio to WAV files.

**Responsibilities**:
- Create multi-track WAV files (one per speaker)
- Stream audio to disk during meeting
- Support mixed audio track (all speakers)
- Manage file lifecycle

**File Naming**:
```
{session_id}_{speaker_id}_{timestamp}.wav
```

Example:
```
meeting_123_speaker_1_20240101_120000.wav
meeting_123_mixed_20240101_120000.wav
```

## Timing and Performance

### Audio Processing Pipeline Timing

```
RTMS Chunks:     20-40ms    ┌─┐┌─┐┌─┐┌─┐┌─┐
                           └─┘└─┘└─┘└─┘└─┘
                                │
                            Accumulate
                                │
                                ↓
VAD Packets:     100ms      ┌─────┐┌─────┐┌─────┐
                           └─────┘└─────┘└─────┘
                                │
                          VAD Detection
                                │
                                ↓
Speech Buffer:   Variable   ┌──────────────┐
                           └──────────────┘
                                │
                          Accumulate to 2.5s
                                │
                                ↓
ASR Segments:    2500ms     ┌──────────────────────────┐
                           └──────────────────────────┘
                                │
                           Transcription
                                │
                                ↓
Output:          Real-time  [12:00:15] Speaker: "text"
```

### Latency Analysis

**Total Pipeline Latency**:
- VAD accumulation: **50-100ms** (average)
- VAD processing: **10-50ms** (depends on VAD server)
- Speech accumulation: **0-2500ms** (until 2.5s or silence)
- ASR processing: **500-2000ms** (depends on ASR server)

**Total**: ~**600-4600ms** from speech start to transcription

**Optimization Opportunities**:
1. Use streaming ASR (process incrementally)
2. Reduce VAD packet size (trade accuracy for latency)
3. Overlap ASR segments (don't wait for full 2.5s)
4. Use faster ASR models

## Data Structures

### AudioChunk

```python
@dataclass
class AudioChunk:
    data: np.ndarray          # Audio samples (int16)
    timestamp: datetime       # Chunk timestamp
    speaker_id: Optional[str] # Speaker identifier
    sample_rate: int = 16000  # Sample rate in Hz
```

### TranscriptionSegment

```python
@dataclass
class TranscriptionSegment:
    text: str                      # Transcribed text
    speaker_id: Optional[str]      # Speaker identifier
    timestamp: datetime            # Segment timestamp
    confidence: Optional[float]    # Recognition confidence
    start_time: Optional[float]    # Relative start time
    end_time: Optional[float]      # Relative end time
```

## Configuration

### Critical Parameters

**Audio Settings**:
```yaml
sample_rate: 16000    # Standard for speech recognition
channels: 1           # Mono (per speaker)
bit_depth: 16         # 16-bit PCM
```

**Buffer Settings**:
```yaml
vad_duration_ms: 100                  # VAD packet size
asr_duration_seconds: 2.5             # ASR segment size
min_speech_duration_ms: 500           # Ignore short speech
silence_timeout_seconds: 1.0          # Time before ending segment
speech_buffer_size_seconds: 5.0       # Max buffer size
```

## Error Handling and Resilience

### Connection Management

All WebSocket clients implement:
1. **Automatic reconnection** with exponential backoff
2. **Connection health monitoring** via ping/pong
3. **Graceful degradation** (continue with available services)

### Buffer Overflow Protection

```python
if len(speech_buffer) > max_buffer_size:
    # Force send to ASR even if not full 2.5s
    await _send_to_asr()
```

### State Recovery

- Audio buffer maintains state across VAD/ASR failures
- Transcription handler persists periodically
- Recording flushes to disk in real-time

## Scalability Considerations

### Single Meeting

Current design handles **1 meeting** with **multiple speakers**.

### Multi-Meeting Support

To support multiple meetings:
```python
# Create separate system instance per meeting
systems = {}
for meeting_id in active_meetings:
    systems[meeting_id] = RTMSTranscriptionSystem(config)
    await systems[meeting_id].start(meeting_id)
```

### Resource Usage

Per meeting:
- **Memory**: ~50MB base + ~1MB per minute of buffered audio
- **CPU**: Minimal (mostly I/O bound)
- **Network**: ~128 Kbps per audio stream (16kHz mono PCM)

## Security Considerations

1. **Credentials**: Store Zoom API keys securely (env vars, secrets manager)
2. **Audio Data**: Consider encryption for audio in transit
3. **Transcriptions**: Implement access controls for saved transcripts
4. **PII**: Be aware of privacy regulations (GDPR, HIPAA, etc.)

## Future Enhancements

1. **Streaming ASR**: Process audio incrementally instead of 2.5s chunks
2. **Adaptive buffering**: Adjust buffer sizes based on speech patterns
3. **Speaker identification**: Use voice biometrics for speaker recognition
4. **Punctuation restoration**: Post-process transcriptions
5. **Translation**: Real-time translation support
6. **Emotion detection**: Analyze sentiment/emotion in speech
7. **Meeting summarization**: Generate meeting summaries
8. **Action item extraction**: Identify tasks and action items
