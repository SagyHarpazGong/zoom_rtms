"""Utility functions for audio processing and logging"""

import logging
import structlog
from typing import Optional
import numpy as np


def setup_logging(config: dict) -> None:
    """Setup structured logging based on configuration"""
    log_level = getattr(logging, config.get("level", "INFO"))

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if config.get("format") == "simple"
            else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def pcm_to_numpy(pcm_data: bytes, sample_width: int = 2) -> np.ndarray:
    """Convert PCM audio bytes to numpy array

    Args:
        pcm_data: Raw PCM audio bytes
        sample_width: Bytes per sample (2 for 16-bit)

    Returns:
        Numpy array of audio samples
    """
    dtype = np.int16 if sample_width == 2 else np.int32
    return np.frombuffer(pcm_data, dtype=dtype)


def numpy_to_pcm(audio_array: np.ndarray) -> bytes:
    """Convert numpy array to PCM audio bytes

    Args:
        audio_array: Numpy array of audio samples

    Returns:
        Raw PCM audio bytes
    """
    return audio_array.astype(np.int16).tobytes()


def calculate_duration_ms(num_samples: int, sample_rate: int) -> float:
    """Calculate audio duration in milliseconds

    Args:
        num_samples: Number of audio samples
        sample_rate: Sample rate in Hz

    Returns:
        Duration in milliseconds
    """
    return (num_samples / sample_rate) * 1000


def samples_for_duration(duration_ms: float, sample_rate: int) -> int:
    """Calculate number of samples for given duration

    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz

    Returns:
        Number of samples
    """
    return int((duration_ms / 1000) * sample_rate)


class RingBuffer:
    """Thread-safe ring buffer for audio data"""

    def __init__(self, capacity_samples: int):
        self.capacity = capacity_samples
        self.buffer = np.zeros(capacity_samples, dtype=np.int16)
        self.write_pos = 0
        self.read_pos = 0
        self.size = 0

    def write(self, data: np.ndarray) -> bool:
        """Write data to buffer

        Returns:
            True if successful, False if buffer full
        """
        data_len = len(data)
        if self.size + data_len > self.capacity:
            return False

        # Handle wrap-around
        end_pos = self.write_pos + data_len
        if end_pos <= self.capacity:
            self.buffer[self.write_pos:end_pos] = data
        else:
            # Split write
            first_chunk = self.capacity - self.write_pos
            self.buffer[self.write_pos:] = data[:first_chunk]
            self.buffer[:end_pos - self.capacity] = data[first_chunk:]

        self.write_pos = end_pos % self.capacity
        self.size += data_len
        return True

    def read(self, num_samples: int) -> Optional[np.ndarray]:
        """Read data from buffer

        Returns:
            Numpy array or None if not enough data
        """
        if self.size < num_samples:
            return None

        result = np.zeros(num_samples, dtype=np.int16)
        end_pos = self.read_pos + num_samples

        if end_pos <= self.capacity:
            result[:] = self.buffer[self.read_pos:end_pos]
        else:
            # Split read
            first_chunk = self.capacity - self.read_pos
            result[:first_chunk] = self.buffer[self.read_pos:]
            result[first_chunk:] = self.buffer[:end_pos - self.capacity]

        self.read_pos = end_pos % self.capacity
        self.size -= num_samples
        return result

    def available(self) -> int:
        """Get number of samples available to read"""
        return self.size

    def clear(self) -> None:
        """Clear the buffer"""
        self.write_pos = 0
        self.read_pos = 0
        self.size = 0
