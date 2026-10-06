"""
AI Fixture Reverse-Engineering Wizard.
Includes:
- Path A: Direct documentation & model lookup.
- Path B: Interactive channel probing state machine interacting with the live DMX mixer.
"""

import json
from typing import Dict, Any, List, Optional

from database.db import get_db
from database.repositories import FixtureRepository, WizardSessionRepository
from engine.mixer import DMXMixer, get_mixer
from .gemini_client import get_gemini_client


class FixtureWizardSession:
    def __init__(
        self,
        mixer: Optional[DMXMixer] = None,
        fixture_repo: Optional[FixtureRepository] = None,
        session_repo: Optional[WizardSessionRepository] = None,
    ):
        self.mixer = mixer or get_mixer()
        self.fixture_repo = fixture_repo or FixtureRepository()
        self.session_repo = session_repo or WizardSessionRepository()
        self.gemini = get_gemini_client()

    def doc_lookup(self, fixture_name: str, manufacturer: str, spec_text: str, start_channel: int) -> Dict[str, Any]:
        """
        Path A: Converts documentation, manual snippet, or fixture name into a structured channel patch map.
        """
        if not self.gemini.is_configured():
            return {
                "success": False,
                "error": "Gemini API key is required for fixture documentation lookup.",
            }

        prompt = f"""
Given the following lighting fixture information, extract or infer the DMX channel profile.

FIXTURE DETAILS:
- Name/Model: {fixture_name}
- Manufacturer: {manufacturer}
- Starting DMX Address: {start_channel}
- Specification / Manual Text:
\"\"\"
{spec_text}
\"\"\"

Respond with pure JSON only:
{{
  "name": "{fixture_name}",
  "model": "{fixture_name}",
  "manufacturer": "{manufacturer}",
  "start_channel": {start_channel},
  "channel_count": 4,
  "group_tag": "wash",
  "notes": "Extracted from specification",
  "channels": [
    {{"channel_offset": 0, "channel_type": "dimmer", "label": "Master Dimmer", "default_value": 0}},
    {{"channel_offset": 1, "channel_type": "red", "label": "Red", "default_value": 0}},
    {{"channel_offset": 2, "channel_type": "green", "label": "Green", "default_value": 0}},
    {{"channel_offset": 3, "channel_type": "blue", "label": "Blue", "default_value": 0}}
  ]
}}
"""
        resp = self.gemini.generate_json(prompt)
        if isinstance(resp, dict) and "channels" in resp and "channel_count" in resp:
            try:
                fixture_id = self.fixture_repo.create(
                    fixture_data={
                        "name": resp.get("name", fixture_name),
                        "model": resp.get("model", fixture_name),
                        "manufacturer": resp.get("manufacturer", manufacturer),
                        "start_channel": int(resp.get("start_channel", start_channel)),
                        "channel_count": int(resp.get("channel_count", len(resp["channels"]))),
                        "group_tag": resp.get("group_tag", "general"),
                        "notes": resp.get("notes", "Configured via AI Doc Lookup"),
                    },
                    channels=resp["channels"],
                )
                return {"success": True, "fixture_id": fixture_id, "profile": resp}
            except Exception as e:
                return {"success": False, "error": f"Failed to commit fixture to database: {str(e)}"}

        return {"success": False, "error": "Gemini could not parse fixture profile.", "raw": resp}

    def start_probe_session(self, fixture_name: str, start_channel: int, channel_count: int) -> Dict[str, Any]:
        """
        Path B - Step 1: Initializes probing session, zeros target channel block on the mixer.
        """
        # Zero out the target footprint in DMX mixer
        zero_payload = {ch: 0 for ch in range(start_channel, start_channel + channel_count)}
        self.mixer.set_channels(zero_payload, owner="Wizard:Probe")

        session_id = self.session_repo.create_session(fixture_name, start_channel, channel_count)

        # Initial probe: Turn on channel 1 (offset 0) to test for master dimmer or direct color
        probe_ch = start_channel
        self.mixer.set_channel(probe_ch, 255, owner="Wizard:Probe")

        first_step = {
            "step_index": 1,
            "channel_tested": probe_ch,
            "action": f"Set Channel {probe_ch} to 255, all other channels in block set to 0.",
            "question": f"I have raised DMX Channel {probe_ch} to 255 while keeping other channels at 0. Did the fixture turn on (white/color), move, or remain off?",
        }
        self.session_repo.append_transcript_step(session_id, first_step, status="in_progress")

        return {
            "session_id": session_id,
            "fixture_name": fixture_name,
            "start_channel": start_channel,
            "channel_count": channel_count,
            "current_step": first_step,
        }

    def submit_probe_feedback(self, session_id: int, user_feedback: str) -> Dict[str, Any]:
        """
        Path B - Step 2..N: Records user physical observation, commands next mixer channels,
        and uses Gemini to formulate the next probe or finalize profile.
        """
        session = self.session_repo.get_session(session_id)
        if not session:
            return {"success": False, "error": "Wizard session not found."}

        transcript = session.get("transcript", [])
        start_channel = session["start_channel"]
        channel_count = session["channel_count"]
        step_idx = len(transcript) + 1

        # Record feedback on last step
        if transcript:
            transcript[-1]["user_feedback"] = user_feedback

        # Check if enough information or reached end of footprint
        if step_idx > min(channel_count, 12) or "finalize" in user_feedback.lower():
            # Finalize profile with Gemini
            return self._finalize_probe_profile(session_id, session)

        # Next probe logic
        next_offset = step_idx - 1
        target_ch = start_channel + next_offset

        # Test setting channel to 255 while keeping potential master dimmer (start_channel) at 255
        self.mixer.set_channel(start_channel, 255, owner="Wizard:Probe")
        self.mixer.set_channel(target_ch, 255, owner="Wizard:Probe")

        next_step = {
            "step_index": step_idx,
            "channel_tested": target_ch,
            "action": f"Set Channel {target_ch} to 255 (with Channel {start_channel} at 255).",
            "question": f"Now testing Channel {target_ch} (set to 255). What reaction do you observe? (e.g. Red, Green, Blue, White, Pan/Tilt movement, Strobe flash, Gobo change, or No change)",
        }
        self.session_repo.append_transcript_step(session_id, next_step, status="in_progress")

        return {
            "session_id": session_id,
            "completed": False,
            "current_step": next_step,
        }

    def _finalize_probe_profile(self, session_id: int, session: Dict[str, Any]) -> Dict[str, Any]:
        """Concludes the probing session, generates the fixture profile and commits to SQLite."""
        transcript = session.get("transcript", [])
        start_ch = session["start_channel"]
        count = session["channel_count"]
        name = session["fixture_name"]

        prompt = f"""
You are reverse-engineering a generic lighting fixture based on physical diagnostic probing.
Fixture Name: {name}
Starting Address: {start_ch}
Total Channels: {count}

Diagnostic Probe Transcript:
{json.dumps(transcript, indent=2)}

Analyze the transcript and produce the confirmed DMX fixture channel map.
Respond with pure JSON only:
{{
  "name": "{name}",
  "model": "Generic {count}CH",
  "manufacturer": "Generic",
  "start_channel": {start_ch},
  "channel_count": {count},
  "group_tag": "wash",
  "notes": "Reverse-engineered via interactive AI probing wizard",
  "channels": [
    {{"channel_offset": 0, "channel_type": "dimmer", "label": "Master Dimmer", "default_value": 0}},
    ...
  ]
}}
"""
        profile = self.gemini.generate_json(prompt) if self.gemini.is_configured() else None

        # Clean fallback profile if Gemini is unavailable
        if not isinstance(profile, dict) or "channels" not in profile:
            inferred_channels = []
            for i in range(count):
                ch_type = "dimmer" if i == 0 else ("red" if i == 1 else ("green" if i == 2 else ("blue" if i == 3 else "aux")))
                inferred_channels.append({
                    "channel_offset": i,
                    "channel_type": ch_type,
                    "label": f"Channel {i + 1}",
                    "default_value": 0,
                })
            profile = {
                "name": name,
                "model": f"Generic {count}CH",
                "manufacturer": "Generic",
                "start_channel": start_ch,
                "channel_count": count,
                "group_tag": "wash",
                "notes": "Reverse-engineered via interactive probing wizard",
                "channels": inferred_channels,
            }

        # Commit to database
        fixture_id = self.fixture_repo.create(
            fixture_data={
                "name": profile.get("name", name),
                "model": profile.get("model", f"Generic {count}CH"),
                "manufacturer": profile.get("manufacturer", "Generic"),
                "start_channel": start_ch,
                "channel_count": count,
                "group_tag": profile.get("group_tag", "wash"),
                "notes": profile.get("notes", "Reverse-engineered via AI probing wizard"),
            },
            channels=profile["channels"],
        )

        # Zero out probe channels
        zero_payload = {ch: 0 for ch in range(start_ch, start_ch + count)}
        self.mixer.set_channels(zero_payload)
        self.mixer.release_channels(list(range(start_ch, start_ch + count)), owner="Wizard:Probe")

        self.session_repo.finish_session(session_id, status="completed")

        return {
            "completed": True,
            "fixture_id": fixture_id,
            "profile": profile,
            "message": f"Successfully patched fixture '{name}' (ID: {fixture_id}) to channels {start_ch}..{start_ch + count - 1}.",
        }
