# Multi-Speaker Processing Modes

The Zoom RTMS transcription system supports two modes for handling multiple speakers in a meeting.

## Overview

| Mode | Description | Use Case | ASR Requirements |
|------|-------------|----------|------------------|
| **Mixed Mode** (Option 1) | All speakers combined into one audio stream | Your ASR does speaker diarization | ASR must identify speakers from mixed audio |
| **Individual Mode** (Option 2) | Separate audio streams per speaker | Pre-separated speaker processing | ASR doesn't need diarization |

## Configuration

### Option 1: Mixed Stream Mode (Default)

**Best for:** Most use cases where ASR handles speaker identification

```yaml
# config.yaml
audio:
  sample_rate: 16000
  channels: 1
  bit_depth: 16
  encoding: "pcm"
  stream_mode: "mixed"  # ← Set to "mixed"

asr:
  enable_diarization: true  # ← ASR must do speaker identification
```

**How it works:**
```
Zoom Meeting (3 speakers)
    ↓
RTMS SDK: AUDIO_MIXED_STREAM
    ↓
One combined audio stream
    ↓
Single VAD buffer
    ↓
Single speech buffer
    ↓
ASR Server (with diarization)
    ↓
Transcription with speaker labels
```

**Advantages:**
- ✅ Simpler processing pipeline
- ✅ Lower memory usage
- ✅ Easier to implement
- ✅ Works with any number of speakers
- ✅ No per-speaker overhead

**Requirements:**
- ASR server must support speaker diarization
- ASR must identify "who said what" from mixed audio

### Option 2: Individual Stream Mode

**Best for:** When you want pre-separated speaker audio or your ASR doesn't do diarization

```yaml
# config.yaml
audio:
  sample_rate: 16000
  channels: 1
  bit_depth: 16
  encoding: "pcm"
  stream_mode: "individual"  # ← Set to "individual"

asr:
  enable_diarization: false  # ← Optional, already separated
```

**How it works:**
```
Zoom Meeting (3 speakers)
    ↓
RTMS SDK: AUDIO_INDIVIDUAL_STREAMS
    ↓
3 separate audio streams (one per speaker)
    ↓
Per-speaker VAD buffers
    ↓
Per-speaker speech buffers
    ↓
ASR Server (no diarization needed)
    ↓
Transcription already labeled by speaker
```

**Advantages:**
- ✅ Clean speaker separation from Zoom
- ✅ Each speaker processed independently
- ✅ No speaker diarization needed in ASR
- ✅ Better for speaker-specific processing
- ✅ Easier to apply different models per speaker

**Disadvantages:**
- ❌ More complex processing pipeline
- ❌ Higher memory usage (buffers per speaker)
- ❌ More VAD/ASR calls (one per speaker)
- ❌ Need to manage per-speaker state

## How to Switch Between Modes

### Change Configuration

Edit `config.yaml`:

```yaml
# For Mixed Mode (Option 1)
audio:
  stream_mode: "mixed"

# For Individual Mode (Option 2)
audio:
  stream_mode: "individual"
```

That's it! No code changes needed.

### Restart the Application

```bash
# Stop current instance (Ctrl+C)

# Start with new configuration
python main.py --mode webhook

# Or in direct mode
python main.py --mode direct --meeting-uuid <uuid> ...
```

## What Happens Under the Hood

### Mixed Mode Behavior

1. **RTMS Configuration:**
   - `data_opt` = `AUDIO_MIXED_STREAM`
   - Zoom mixes all speaker audio before sending

2. **Audio Buffer:**
   - Single `vad_buffer` for all audio
   - Single `speech_buffer` for accumulated speech
   - One set of state variables

3. **Processing:**
   - All audio goes to one VAD analysis
   - Speech from any speaker accumulates together
   - ASR receives mixed audio with multiple speakers

4. **Speaker Identification:**
   - ASR server identifies speakers from audio
   - Returns `speaker_id` in transcription result

### Individual Mode Behavior

1. **RTMS Configuration:**
   - `data_opt` = `AUDIO_INDIVIDUAL_STREAMS`
   - Zoom sends separate stream per speaker

2. **Audio Buffer:**
   - Dictionary of `SpeakerBuffer` objects (one per speaker)
   - Each speaker has own `vad_buffer` and `speech_buffer`
   - State tracked independently per speaker

3. **Processing:**
   - Each speaker's audio analyzed separately by VAD
   - Speech from each speaker accumulated separately
   - ASR receives audio from single speaker at a time

4. **Speaker Identification:**
   - `speaker_id` already known from Zoom
   - Passed through entire pipeline
   - ASR receives pre-labeled audio

## Audio Data Flow

### Mixed Mode

```python
# Audio arrives with participant_id
audio_data, participant_id = rtms_audio

# Passed to buffer but participant_id not used for buffering
audio_buffer.add_audio(audio_data, timestamp, speaker_id=participant_id)

# All audio goes to single buffer (participant_id ignored for buffering)
vad_buffer += audio_data  # Single buffer

# VAD processes combined audio
vad_result = vad_server.process(vad_buffer, speaker_id=None)

# Speech accumulated in single buffer
if vad_result.is_speech:
    speech_buffer += audio_chunk.data  # All speakers together

# ASR receives mixed audio
asr_result = asr_server.transcribe(speech_buffer, speaker_id=None)
# ASR must determine: "Speaker 1 said X, Speaker 2 said Y"
```

### Individual Mode

```python
# Audio arrives with participant_id
audio_data, participant_id = rtms_audio

# Passed to buffer with participant_id
audio_buffer.add_audio(audio_data, timestamp, speaker_id=participant_id)

# Goes to speaker-specific buffer
speaker_buffer = buffers[participant_id]
speaker_buffer.vad_buffer += audio_data  # Per-speaker buffer

# VAD processes this speaker's audio
vad_result = vad_server.process(
    speaker_buffer.vad_buffer,
    speaker_id=participant_id
)

# Speech accumulated per speaker
if vad_result.is_speech:
    speaker_buffer.speech_buffer += audio_chunk.data  # This speaker only

# ASR receives single speaker's audio
asr_result = asr_server.transcribe(
    speaker_buffer.speech_buffer,
    speaker_id=participant_id
)
# ASR knows: "This audio is from participant_id"
```

## Performance Considerations

### Mixed Mode

- **Memory:** ~50MB base + ~1MB per minute of audio
- **CPU:** Minimal (one VAD/ASR pipeline)
- **Network:** Single stream to VAD/ASR
- **Latency:** Same as single speaker

### Individual Mode

- **Memory:** ~50MB base + ~1MB per speaker per minute
- **CPU:** Higher (N VAD/ASR pipelines for N speakers)
- **Network:** N streams to VAD/ASR (one per speaker)
- **Latency:** Same per speaker, but N parallel streams

### Example: 5 Speaker Meeting

| Metric | Mixed Mode | Individual Mode |
|--------|-----------|-----------------|
| Memory | ~55MB | ~75MB |
| VAD calls/sec | 10 | 50 (10 per speaker) |
| ASR calls | ~1 per 2.5s | ~5 per 2.5s |
| Network bandwidth | 1x | 5x |

## When to Use Each Mode

### Use Mixed Mode When:

✅ Your ASR has good speaker diarization
✅ You want simpler infrastructure
✅ You have many speakers (>5)
✅ Resource efficiency matters
✅ You don't need per-speaker audio processing
✅ Standard meeting transcription use case

### Use Individual Mode When:

✅ Your ASR doesn't do speaker diarization
✅ You need pre-separated speaker audio
✅ You want to apply different processing per speaker
✅ You have few speakers (<5)
✅ You need perfect speaker separation
✅ You want to train per-speaker models
✅ You need speaker-specific audio features

## Testing

### Test Mixed Mode

```bash
# Edit config.yaml
audio:
  stream_mode: "mixed"

# Start system
python main.py --mode webhook

# Join meeting and speak
# Check logs for:
✓ "audio_buffer_mode: mixed_stream"
✓ "sending_to_asr, mode: mixed"
✓ ASR receives combined audio
```

### Test Individual Mode

```bash
# Edit config.yaml
audio:
  stream_mode: "individual"

# Start system
python main.py --mode webhook

# Join meeting with multiple speakers
# Check logs for:
✓ "audio_buffer_mode: individual_speakers"
✓ "speaker_buffer_created, speaker_id: 123"
✓ "sending_to_asr, speaker_id: 123, mode: per_speaker"
✓ ASR receives per-speaker audio
```

## Troubleshooting

### Issue: "No speaker_id in individual mode"

**Cause:** RTMS not sending participant IDs

**Solution:**
- Check Zoom app has correct permissions
- Verify `AUDIO_INDIVIDUAL_STREAMS` is configured
- Check logs for participant events

### Issue: "Too many VAD/ASR calls in individual mode"

**Cause:** Many speakers all talking at once

**Solution:**
- This is expected behavior in individual mode
- Each speaker triggers separate processing
- Consider switching to mixed mode if resources are limited

### Issue: "Speaker buffers growing too large"

**Cause:** Speakers not speaking but buffers still allocated

**Solution:**
- Buffers are cleaned up when flush() is called
- Inactive speakers are maintained but should be minimal memory
- System automatically manages per-speaker state

## Logging

### Mixed Mode Logs

```
INFO  audio_buffer_mode mode=mixed_stream
INFO  sending_to_asr samples=40000 duration_seconds=2.5 mode=mixed
```

### Individual Mode Logs

```
INFO  audio_buffer_mode mode=individual_speakers
INFO  speaker_buffer_created speaker_id=participant_123
INFO  sending_to_asr speaker_id=participant_123 samples=40000 duration_seconds=2.5 mode=per_speaker
INFO  speech_started speaker_id=participant_456
```

## Summary

| Feature | Mixed Mode | Individual Mode |
|---------|-----------|-----------------|
| **Configuration** | `stream_mode: "mixed"` | `stream_mode: "individual"` |
| **Zoom RTMS** | `AUDIO_MIXED_STREAM` | `AUDIO_INDIVIDUAL_STREAMS` |
| **Buffers** | Single shared | Per-speaker |
| **VAD calls** | One stream | N streams |
| **ASR calls** | Mixed audio | Per-speaker audio |
| **Speaker ID** | From ASR | From Zoom |
| **Memory** | Lower | Higher |
| **CPU** | Lower | Higher |
| **Simplicity** | Simpler | More complex |
| **Use Case** | General meetings | Advanced processing |

Choose the mode that best fits your ASR capabilities and use case!
