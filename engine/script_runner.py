"""
Playback Arbitration Engine & Isolated Script Runner.
Enforces Option 2: Fixture-Aware Scoping with Non-Overlapping Partitions.
"""

import math
import random
import threading
import time
from typing import Dict, Set, List, Optional, Any

import config
from .mixer import DMXMixer, get_mixer

_runner_lock = threading.Lock()
_global_runner_instance: Optional["ScriptRunner"] = None


class ScriptDMXHelper:
    """Scoped helper provided to dynamic show scripts to constrain writes to their declared footprint."""

    def __init__(self, mixer: DMXMixer, footprint: Set[int], owner_tag: str):
        self._mixer = mixer
        self._footprint = footprint
        self._owner_tag = owner_tag

    def set(self, channel: int, value: int) -> bool:
        # Enforce footprint boundary
        if channel not in self._footprint:
            return False
        return self._mixer.set_channel(channel, value, owner=self._owner_tag)

    def set_many(self, channel_map: Dict[Any, Any]) -> int:
        filtered = {}
        for ch, val in channel_map.items():
            try:
                ch_int = int(ch)
                if ch_int in self._footprint:
                    filtered[ch_int] = val
            except (ValueError, TypeError):
                continue
        return self._mixer.set_channels(filtered, owner=self._owner_tag)

    def get(self, channel: int) -> int:
        return self._mixer.get_channel(channel)


class ScriptTimeProxy:
    """
    Proxies the standard time module inside show scripts.
    Dynamically scales sleep durations using ScriptRunner.get_speed_multiplier()
    and responds immediately to stop_event.
    """

    def __init__(self, runner: "ScriptRunner", stop_event: threading.Event):
        self._runner = runner
        self._stop_event = stop_event

    def sleep(self, seconds: float) -> None:
        mult = self._runner.get_speed_multiplier()
        effective_mult = max(0.05, mult)
        scaled_duration = max(0.001, float(seconds) / effective_mult)
        end_time = time.time() + scaled_duration

        # Slice sleep into 20ms chunks for rapid abort responsiveness
        while not self._stop_event.is_set():
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            time.sleep(min(0.02, remaining))

    def time(self) -> float:
        return time.time()

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


class ScriptExecutionHandle:
    def __init__(
        self,
        script_id: int,
        name: str,
        footprint: Set[int],
        thread: threading.Thread,
        stop_event: threading.Event,
    ):
        self.script_id = script_id
        self.name = name
        self.footprint = footprint
        self.thread = thread
        self.stop_event = stop_event
        self.start_time = time.time()
        self.error: Optional[str] = None
        self.finished = False


class ScriptRunner:
    """
    Manages procedural lighting effect threads.
    Resolves resource collisions by cooperatively halting overlapping scripts.
    """

    def __init__(self, mixer: Optional[DMXMixer] = None):
        self.mixer = mixer or get_mixer()
        self._active_scripts: Dict[int, ScriptExecutionHandle] = {}
        self._speed_multiplier: float = 1.0  # Dynamic speed multiplier (0.1x to 5.0x)
        self._lock = threading.Lock()

    def set_speed_multiplier(self, multiplier: float) -> float:
        """Sets global speed multiplier (clamped to 0.1x - 5.0x)."""
        clamped = max(0.1, min(5.0, float(multiplier)))
        with self._lock:
            self._speed_multiplier = clamped
        return clamped

    def get_speed_multiplier(self) -> float:
        """Returns the current global speed multiplier."""
        with self._lock:
            return self._speed_multiplier

    def start_script(
        self,
        script_id: int,
        name: str,
        footprint: List[int],
        python_code: str,
    ) -> Dict[str, Any]:
        """
        Starts a procedural routine.
        If any currently active script overlaps this footprint, it is cleanly stopped first.
        """
        footprint_set = set(int(ch) for ch in footprint if 1 <= int(ch) <= config.UNIVERSE_SIZE)
        if not footprint_set:
            return {"success": False, "error": "Script has an empty or invalid channel footprint."}

        halted_scripts = []

        with self._lock:
            # 1. Collision Arbitration: Detect overlapping scripts
            collided_ids = []
            for active_id, handle in self._active_scripts.items():
                if handle.thread.is_alive() and bool(handle.footprint & footprint_set):
                    collided_ids.append(active_id)

            # 2. Halt collided scripts cooperatively
            for c_id in collided_ids:
                h = self._active_scripts[c_id]
                h.stop_event.set()
                halted_scripts.append({"id": c_id, "name": h.name})

        # Wait outside main lock for clean termination (with 250ms hard-kill timeout)
        for c_id in collided_ids:
            with self._lock:
                h = self._active_scripts.get(c_id)
            if h and h.thread.is_alive():
                h.thread.join(timeout=config.SCRIPT_KILL_TIMEOUT_SEC)
            with self._lock:
                if c_id in self._active_scripts:
                    self._active_scripts.pop(c_id, None)

        # 3. Create execution thread for new script
        stop_event = threading.Event()
        owner_tag = f"Script:{script_id}"
        time_proxy = ScriptTimeProxy(self, stop_event)

        def _safe_import(name, *args, **kwargs):
            if name == "time":
                return time_proxy
            if name in ("math", "random"):
                return __import__(name, *args, **kwargs)
            raise ImportError(f"Importing '{name}' is prohibited in show scripts.")

        def _worker():
            handle = None
            try:
                # Compile code
                compiled = compile(python_code, f"<show_script_{script_id}>", "exec")
                helper = ScriptDMXHelper(self.mixer, footprint_set, owner_tag)
                script_globals = {
                    "__builtins__": {
                        "__import__": _safe_import,
                        "range": range,
                        "len": len,
                        "int": int,
                        "float": float,
                        "bool": bool,
                        "abs": abs,
                        "min": min,
                        "max": max,
                        "round": round,
                        "sum": sum,
                        "list": list,
                        "dict": dict,
                        "tuple": tuple,
                        "set": set,
                        "print": print,
                    },
                    "dmx": helper,
                    "stop_event": stop_event,
                    "time": time_proxy,
                    "math": math,
                    "random": random,
                }
                exec(compiled, script_globals)
            except Exception as e:
                with self._lock:
                    if script_id in self._active_scripts:
                        self._active_scripts[script_id].error = str(e)
            finally:
                # Script ended: release channel ownership
                self.mixer.release_channels(list(footprint_set), owner_tag)
                with self._lock:
                    if script_id in self._active_scripts:
                        self._active_scripts[script_id].finished = True

        thread = threading.Thread(
            target=_worker,
            name=f"ScriptRunner-{script_id}-{name}",
            daemon=True,
        )

        handle = ScriptExecutionHandle(
            script_id=script_id,
            name=name,
            footprint=footprint_set,
            thread=thread,
            stop_event=stop_event,
        )

        with self._lock:
            self._active_scripts[script_id] = handle
            thread.start()

        return {
            "success": True,
            "script_id": script_id,
            "footprint": list(footprint_set),
            "halted_collisions": halted_scripts,
        }

    def stop_script(self, script_id: int) -> bool:
        """Stops a single running procedural script."""
        with self._lock:
            handle = self._active_scripts.get(script_id)
            if not handle:
                return False
            handle.stop_event.set()

        if handle.thread.is_alive():
            handle.thread.join(timeout=config.SCRIPT_KILL_TIMEOUT_SEC)

        with self._lock:
            self._active_scripts.pop(script_id, None)

        self.mixer.release_channels(list(handle.footprint), f"Script:{script_id}")
        return True

    def kill_all(self) -> int:
        """Panic: Halts all running script threads without altering channel levels."""
        with self._lock:
            handles = list(self._active_scripts.values())
            for h in handles:
                h.stop_event.set()

        stopped_count = 0
        for h in handles:
            if h.thread.is_alive():
                h.thread.join(timeout=config.SCRIPT_KILL_TIMEOUT_SEC)
            self.mixer.release_channels(list(h.footprint), f"Script:{h.script_id}")
            stopped_count += 1

        with self._lock:
            self._active_scripts.clear()

        return stopped_count

    def get_active_scripts(self) -> List[Dict[str, Any]]:
        """Returns metadata for all running procedural scripts."""
        with self._lock:
            # Clean out finished scripts
            finished_ids = [s_id for s_id, h in self._active_scripts.items() if not h.thread.is_alive()]
            for f_id in finished_ids:
                h = self._active_scripts.pop(f_id)
                self.mixer.release_channels(list(h.footprint), f"Script:{h.script_id}")

            results = []
            for s_id, h in self._active_scripts.items():
                results.append(
                    {
                        "script_id": h.script_id,
                        "name": h.name,
                        "footprint": sorted(list(h.footprint)),
                        "running": h.thread.is_alive(),
                        "uptime_sec": round(time.time() - h.start_time, 1),
                        "error": h.error,
                    }
                )
            return results

    def is_running(self, script_id: int) -> bool:
        with self._lock:
            h = self._active_scripts.get(script_id)
            return h is not None and h.thread.is_alive()


def get_script_runner() -> ScriptRunner:
    """Singleton getter for the script runner arbiter."""
    global _global_runner_instance
    if _global_runner_instance is None:
        with _runner_lock:
            if _global_runner_instance is None:
                _global_runner_instance = ScriptRunner()
    return _global_runner_instance
