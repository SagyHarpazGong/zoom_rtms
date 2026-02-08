"""
Hypothesis buffer for managing committed and uncommitted transcription words.

Implements longest-common-prefix (LCP) algorithm for stable streaming transcription.
Uses exact n-gram matching for deduplication across consecutive ASR calls.

Adapted from remove_later/src/hypothesis_buffer.py.
"""

import re
from typing import Dict, List, Tuple

from .utils import get_logger

logger = get_logger(__name__)


def normalize_word(word: str) -> str:
    """Normalize a word for case-insensitive and punctuation-insensitive comparison.

    Args:
        word: Raw word string from ASR output.

    Returns:
        Normalized lowercase string with punctuation removed.
    """
    return re.sub(r'[^\w\s]', '', word).lower().strip()


class HypothesisBuffer:
    """Manages buffering of partially and fully committed transcription hypotheses.

    Uses exact n-gram matching for deduplication and longest-common-prefix (LCP)
    for determining which words are stable enough to commit.
    """

    def __init__(self):
        self.commited_in_buffer: List[Tuple[float, float, str]] = []
        self.buffer: List[Tuple[float, float, str]] = []
        self.new: List[Tuple[float, float, str]] = []
        self.last_commited_time = 0.0

    def insert(self, new: List[Dict[str, float | str]], offset: float) -> None:
        """Insert newly transcribed words while removing overlapping n-gram duplicates.

        Args:
            new: List of word dicts with 'start', 'end', 'text' keys.
            offset: Time offset in seconds to add to word timestamps.
        """
        self.new = [(term['start'] + offset, term['end'] + offset, term['text']) for term in new]

        logger.debug(
            "hypothesis_insert",
            num_words=len(self.new),
            offset=round(offset, 2),
            last_commited_time=round(self.last_commited_time, 2),
        )

        self.new = [(a, b, w) for a, b, w in self.new if a > self.last_commited_time - 0.1]

        if len(self.new) >= 1:
            a, b, w = self.new[0]
            if abs(a - self.last_commited_time) < 1:
                if self.commited_in_buffer:
                    cn = len(self.commited_in_buffer)
                    nn = len(self.new)
                    for i in range(1, min(min(cn, nn), 5) + 1):
                        c = " ".join(
                            [normalize_word(self.commited_in_buffer[-j][2]) for j in range(1, i + 1)][::-1]
                        )
                        tail = " ".join(
                            [normalize_word(self.new[j - 1][2]) for j in range(1, i + 1)]
                        )
                        if c == tail:
                            for j in range(i):
                                self.new.pop(0)
                            logger.debug("hypothesis_dedup", removed_words=i)
                            break

    def flush(self) -> List[Tuple[float, float, str]]:
        """Commit stable words via longest-common-prefix matching between buffer and new.

        Returns:
            List of newly committed word tuples (start, end, text).
        """
        commit = []

        while self.new:
            na, nb, nw = self.new[0]

            if len(self.buffer) == 0:
                break

            ba, bb, bw = self.buffer[0]

            if normalize_word(nw) == normalize_word(bw):
                commit.append((na, nb, nw))
                self.last_commited_time = nb
                self.buffer.pop(0)
                self.new.pop(0)
            else:
                break

        self.buffer = self.new
        self.new = []
        self.commited_in_buffer.extend(commit)

        if commit:
            logger.debug("hypothesis_flush", committed=len(commit), buffer_remaining=len(self.buffer))

        return commit

    def pop_commited(self, time: float) -> List[Tuple[float, float, str]]:
        """Remove and return committed words that end at or before the specified timestamp.

        Args:
            time: Threshold timestamp. Words with end_time <= this value are removed.

        Returns:
            List of removed word tuples.
        """
        removed = []
        while self.commited_in_buffer and self.commited_in_buffer[0][1] <= time:
            word_removed = self.commited_in_buffer.pop(0)
            removed.append(word_removed)
        return removed

    def complete(self) -> List[Tuple[float, float, str]]:
        """Return all uncommitted words remaining in the buffer for final commit.

        Called at end of speech segment to finalize remaining words.

        Returns:
            List of uncommitted word tuples from the buffer.
        """
        return self.buffer
