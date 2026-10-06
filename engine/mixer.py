"""
In-memory 512-byte DMX universe buffer and thread-safe channel ownership arbiter.
Zero disk I/O latency for 35-44 Hz rendering.
"""

import threading
import time
from typing import Dict, List, Optional, Tuple, Any

_mixer_lock = threading.Lock()
_global_mixer_instance: Optional["DMXMixer"] = None


class DMXMixer:
    def __init__(self, universe_size: int = 512):
        self.universe_size = universe_size
        self._buffer = bytearray(self.universe_size)
        self._ownership: List[Optional[str]] = [None] * self.universe_size
        self._grand_master: float = 1.0  # Range: 0.0 to 1.0
        self._active_fade_cancel: Optional[threading.Event] = None
        self._fade_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def set_grand_master(self, level: float) -> float:
        """Sets the grand master scaling level (0.0 to 1.0). Scales all frame outputs proportionally."""
        clamped = max(0.0, min(1.0, float(level)))
        with self._lock:
            self._grand_master = clamped
        return clamped

    def get_grand_master(self) -> float:
        """Returns the current grand master scaling level (0.0 to 1.0)."""
        with self._lock:
            return self._grand_master

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

    def fade_to_channels(
        self,
        channel_map: Dict[Any, Any],
        duration_sec: float,
        owner: Optional[str] = None,
    ) -> None:
        """
        Smoothly interpolates target channels to target levels over duration_sec at 40 Hz.
        If duration_sec <= 0.05, immediately snaps channels without a background thread.
        """
        if duration_sec <= 0.05:
            self.set_channels(channel_map, owner=owner)
            return

        with self._lock:
            # Cancel any existing crossfade in progress
            if self._active_fade_cancel is not None:
                self._active_fade_cancel.set()

            cancel_event = threading.Event()
            self._active_fade_cancel = cancel_event

            # Map {idx: (start_val, target_val)}
            targets: Dict[int, Tuple[int, int]] = {}
            for ch_raw, val_raw in channel_map.items():
                try:
                    ch = int(ch_raw)
                    if 1 <= ch <= self.universe_size:
                        idx = ch - 1
                        start_val = self._buffer[idx]
                        end_val = max(0, min(255, int(val_raw)))
                        targets[idx] = (start_val, end_val)
                        if owner is not None:
                            self._ownership[idx] = owner
                except (ValueError, TypeError):
                    continue

        if not targets:
            return

        def _fade_worker():
            start_time = time.time()
            fps = 40.0
            interval = 1.0 / fps

            while not cancel_event.is_set():
                elapsed = time.time() - start_time
                progress = elapsed / duration_sec
                if progress >= 1.0:
                    with self._lock:
                        for idx, (_, end_val) in targets.items():
                            self._buffer[idx] = end_val
                    break

                with self._lock:
                    for idx, (s_val, e_val) in targets.items():
                        curr = int(round(s_val + (e_val - s_val) * progress))
                        self._buffer[idx] = max(0, min(255, curr))

                time.sleep(interval)

        thread = threading.Thread(
            target=_fade_worker,
            name="MixerCrossfadeWorker",
            daemon=True,
        )
        with self._lock:
            self._fade_thread = thread
        thread.start()

    def get_channel(self, channel: int, scaled: bool = False) -> int:
        """Gets the level of a channel (1-512). If scaled=True, returns post-grand-master level."""
        if not (1 <= channel <= self.universe_size):
            return 0
        with self._lock:
            val = self._buffer[channel - 1]
            if scaled:
                return int(round(val * self._grand_master))
            return val

    def get_frame(self) -> bytes:
        """Returns a snapshot of the raw 512-byte DMX frame scaled by Grand Master."""
        with self._lock:
            if self._grand_master >= 0.9999:
                return bytes(self._buffer)
            gm = self._grand_master
            return bytes(int(round(b * gm)) for b in self._buffer)

    def get_frame_list(self) -> List[int]:
        """Returns a list of 512 integers scaled by Grand Master for JSON serialization."""
        with self._lock:
            if self._grand_master >= 0.9999:
                return list(self._buffer)
            gm = self._grand_master
            return [int(round(b * gm)) for b in self._buffer]

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
            if self._active_fade_cancel is not None:
                self._active_fade_cancel.set()
                self._active_fade_cancel = None
            for i in range(self.universe_size):
                self._buffer[i] = 0
                self._ownership[i] = None

    def get_universe_state(self) -> Dict[str, Any]:
        """Returns complete state for WebSocket diagnostics with scaled levels and Grand Master."""
        with self._lock:
            gm = self._grand_master
            if gm >= 0.9999:
                channels = list(self._buffer)
            else:
                channels = [int(round(b * gm)) for b in self._buffer]
            ownership = list(self._ownership)
            non_zero = sum(1 for v in channels if v > 0)
            locked = sum(1 for o in ownership if o is not None)
            return {
                "channels": channels,
                "ownership": ownership,
                "non_zero_count": non_zero,
                "locked_count": locked,
                "grand_master": gm,
            }


def get_mixer() -> DMXMixer:
    """Singleton getter for the DMX mixer."""
    global _global_mixer_instance
    if _global_mixer_instance is None:
        with _mixer_lock:
            if _global_mixer_instance is None:
                _global_mixer_instance = DMXMixer()
    return _global_mixer_instance
