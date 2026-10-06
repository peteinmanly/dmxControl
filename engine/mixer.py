"""
In-memory 512-byte DMX universe buffer and thread-safe channel ownership arbiter.
Zero disk I/O latency for 35-44 Hz rendering.
"""

import threading
from typing import Dict, List, Optional, Tuple, Any

_mixer_lock = threading.Lock()
_global_mixer_instance: Optional["DMXMixer"] = None


class DMXMixer:
    def __init__(self, universe_size: int = 512):
        self.universe_size = universe_size
        self._buffer = bytearray(self.universe_size)
        self._ownership: List[Optional[str]] = [None] * self.universe_size
        self._lock = threading.Lock()

    def set_channel(self, channel: int, value: int, owner: Optional[str] = None) -> bool:
        """Sets a single DMX channel (1-512) to value (0-255) with optional ownership tag."""
        if not (1 <= channel <= self.universe_size):
            return False
        clamped_val = max(0, min(255, int(value)))
        idx = channel - 1
        with self._lock:
            self._buffer[idx] = clamped_val
            if owner is not None:
                self._ownership[idx] = owner
        return True

    def set_channels(self, channel_map: Dict[Any, Any], owner: Optional[str] = None) -> int:
        """Bulk updates channels from a dict {ch: val}. Channels 1-based."""
        updated = 0
        with self._lock:
            for ch_raw, val_raw in channel_map.items():
                try:
                    ch = int(ch_raw)
                    val = max(0, min(255, int(val_raw)))
                    if 1 <= ch <= self.universe_size:
                        idx = ch - 1
                        self._buffer[idx] = val
                        if owner is not None:
                            self._ownership[idx] = owner
                        updated += 1
                except (ValueError, TypeError):
                    continue
        return updated

    def get_channel(self, channel: int) -> int:
        """Gets the current level of a channel (1-512)."""
        if not (1 <= channel <= self.universe_size):
            return 0
        with self._lock:
            return self._buffer[channel - 1]

    def get_frame(self) -> bytes:
        """Returns a snapshot of the raw 512-byte DMX frame."""
        with self._lock:
            return bytes(self._buffer)

    def get_frame_list(self) -> List[int]:
        """Returns a list of 512 integers for JSON serialization."""
        with self._lock:
            return list(self._buffer)

    def get_channel_ownership(self) -> List[Optional[str]]:
        """Returns a list of 512 ownership strings (e.g. 'Script:2', 'Preset:1', or None)."""
        with self._lock:
            return list(self._ownership)

    def release_channels(self, channels: List[int], owner: str) -> None:
        """Releases channel ownership if current owner matches."""
        with self._lock:
            for ch in channels:
                if 1 <= ch <= self.universe_size:
                    idx = ch - 1
                    if self._ownership[idx] == owner:
                        self._ownership[idx] = None

    def blackout(self) -> None:
        """Emergency master blackout: Sets all 512 channels to 0 and clears all ownership."""
        with self._lock:
            for i in range(self.universe_size):
                self._buffer[i] = 0
                self._ownership[i] = None

    def get_universe_state(self) -> Dict[str, Any]:
        """Returns complete state for WebSocket diagnostics."""
        with self._lock:
            channels = list(self._buffer)
            ownership = list(self._ownership)
            non_zero = sum(1 for v in channels if v > 0)
            locked = sum(1 for o in ownership if o is not None)
            return {
                "channels": channels,
                "ownership": ownership,
                "non_zero_count": non_zero,
                "locked_count": locked,
            }


def get_mixer() -> DMXMixer:
    """Singleton getter for the DMX mixer."""
    global _global_mixer_instance
    if _global_mixer_instance is None:
        with _mixer_lock:
            if _global_mixer_instance is None:
                _global_mixer_instance = DMXMixer()
    return _global_mixer_instance
