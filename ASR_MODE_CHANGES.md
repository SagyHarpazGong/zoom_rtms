# ASR Mode Feature

Added support for choosing between custom ASR pipeline and RTMS built-in transcription.

## Configuration

Add to `config.yaml`:

```yaml
asr_mode: "custom"  # Options: "custom", "rtms"
```

## Modes

### Custom Mode (`asr_mode: "custom"`)
- **Pipeline:** RTMS audio → VAD (local) → SpeechProcessor → ASR (HTTP) → LCP → Transcription
- **Components:** Initializes VAD client, ASR client, AudioBuffer, SpeechProcessor, SharedConversationContext
- **Features:** Full control, LCP deduplication, shared conversation context, rolling 30s buffer
- **Requirements:** Requires ASR server endpoint configured in `asr.url`

### RTMS Mode (`asr_mode: "rtms"`)
- **Pipeline:** RTMS transcription → Transcription Handler (direct)
- **Components:** Only RTMS client and TranscriptionHandler
- **Features:** Simpler setup, uses Zoom's built-in transcription
- **Requirements:** No ASR server needed
- **Limitations:** No LCP deduplication, no shared conversation context, no VAD control

## Changes

### New Files
- None

### Modified Files

#### `src/rtms_client.py`
- Added `set_transcription_callback()` method
- Added `@self.client.onTranscription` callback handler in `_setup_callbacks()`
- Transcription data forwarded to callback with participant_id and timestamp

#### `config.yaml`
- Added `asr_mode` configuration option with comments explaining both modes

#### `main.py`
- Added `self.asr_mode` attribute
- Conditional initialization of VAD, ASR, AudioBuffer, SpeechProcessor based on mode
- Added `_on_rtms_transcription()` handler for RTMS mode
- Updated `_setup_callbacks()` to wire audio callback (custom) or transcription callback (rtms)
- Updated `_connect_services()` to skip VAD/ASR connection in RTMS mode
- Updated `stop()` to conditionally flush processors/buffer only if they exist

## Usage

### Switch to RTMS Mode
1. Edit `config.yaml`: `asr_mode: "rtms"`
2. Run system normally - no ASR server needed
3. Transcriptions will come directly from RTMS

### Switch to Custom Mode
1. Edit `config.yaml`: `asr_mode: "custom"`
2. Ensure ASR server is running at configured `asr.url`
3. System will use custom pipeline with LCP

## Notes

- Both modes support `stream_mode` (mixed/individual)
- VAD may still be useful in RTMS mode for future features (currently not used)
- RTMS transcription format may need adjustment based on actual SDK response structure
