"""Tests for AudioBuffer component"""

import pytest
import asyncio
import numpy as np
from datetime import datetime

from src.audio_buffer import AudioBuffer, AudioChunk
from src.utils import numpy_to_pcm, samples_for_duration


@pytest.fixture
def audio_buffer():
    """Create AudioBuffer instance for testing"""
    return AudioBuffer(
        sample_rate=16000,
        vad_duration_ms=100,
        asr_duration_seconds=2.5,
        min_speech_duration_ms=500,
        silence_timeout_seconds=1.0
    )


@pytest.fixture
def sample_audio():
    """Generate sample audio data"""
    # Generate 1 second of audio
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)

    # Generate sine wave
    frequency = 440  # A4 note
    t = np.linspace(0, duration, samples)
    audio = (np.sin(2 * np.pi * frequency * t) * 32767 / 2).astype(np.int16)

    return numpy_to_pcm(audio)


class TestAudioBuffer:
    """Test AudioBuffer functionality"""

    def test_initialization(self, audio_buffer):
        """Test AudioBuffer initialization"""
        assert audio_buffer.sample_rate == 16000
        assert audio_buffer.vad_duration_ms == 100
        assert audio_buffer.asr_duration_seconds == 2.5
        assert audio_buffer.vad_packet_samples == samples_for_duration(100, 16000)

    @pytest.mark.asyncio
    async def test_vad_packet_accumulation(self, audio_buffer, sample_audio):
        """Test that audio accumulates to VAD packet size"""
        vad_packets = []

        async def vad_callback(chunk: AudioChunk):
            vad_packets.append(chunk)

        audio_buffer.set_vad_callback(vad_callback)

        # Add audio in small chunks
        chunk_size = 320  # 20ms at 16kHz
        for i in range(0, len(sample_audio), chunk_size):
            chunk = sample_audio[i:i + chunk_size]
            await audio_buffer.add_audio(chunk)

        # Should have accumulated into VAD packets (0.1s = 1600 samples)
        assert len(vad_packets) > 0
        for packet in vad_packets:
            assert len(packet.data) == audio_buffer.vad_packet_samples

    @pytest.mark.asyncio
    async def test_speech_segment_accumulation(self, audio_buffer):
        """Test that speech segments accumulate to ASR size"""
        asr_segments = []

        async def asr_callback(chunk: AudioChunk):
            asr_segments.append(chunk)

        audio_buffer.set_asr_callback(asr_callback)

        # Simulate VAD packets with speech detection
        vad_packet_size = audio_buffer.vad_packet_samples
        num_packets = 30  # 3 seconds of speech

        for i in range(num_packets):
            audio_data = np.random.randint(-1000, 1000, vad_packet_size, dtype=np.int16)
            chunk = AudioChunk(audio_data, datetime.utcnow(), sample_rate=16000)

            # Simulate speech detection
            await audio_buffer.on_vad_result(is_speech=True, audio_chunk=chunk)

        # Should have accumulated into ASR segments (2.5s)
        assert len(asr_segments) > 0

        # First segment should be exactly ASR segment size
        assert len(asr_segments[0].data) == audio_buffer.asr_segment_samples

    @pytest.mark.asyncio
    async def test_silence_timeout(self, audio_buffer):
        """Test that silence timeout triggers ASR"""
        asr_segments = []

        async def asr_callback(chunk: AudioChunk):
            asr_segments.append(chunk)

        audio_buffer.set_asr_callback(asr_callback)

        # Add some speech
        vad_packet_size = audio_buffer.vad_packet_samples
        for i in range(10):  # 1 second of speech
            audio_data = np.random.randint(-1000, 1000, vad_packet_size, dtype=np.int16)
            chunk = AudioChunk(audio_data, datetime.utcnow(), sample_rate=16000)
            await audio_buffer.on_vad_result(is_speech=True, audio_chunk=chunk)

        # Add silence to trigger timeout
        for i in range(15):  # 1.5 seconds of silence
            audio_data = np.zeros(vad_packet_size, dtype=np.int16)
            chunk = AudioChunk(audio_data, datetime.utcnow(), sample_rate=16000)
            await audio_buffer.on_vad_result(is_speech=False, audio_chunk=chunk)
            await asyncio.sleep(0.1)  # Simulate time passing

        # Should have triggered ASR due to silence timeout
        assert len(asr_segments) > 0

    def test_callback_registration(self, audio_buffer):
        """Test callback registration"""
        async def vad_callback(chunk):
            pass

        async def asr_callback(chunk):
            pass

        audio_buffer.set_vad_callback(vad_callback)
        audio_buffer.set_asr_callback(asr_callback)

        assert audio_buffer.vad_packet_callback == vad_callback
        assert audio_buffer.asr_segment_callback == asr_callback


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
