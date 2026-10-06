"""
Gemini AI Client Interface.
Uses the modern google-genai SDK (gemini-3.8-flash) with database-backed API key storage.
"""

import json
import os
import re
from typing import Dict, Any, Optional

import config
from database.repositories import SettingsRepository

try:
    from google import genai
except ImportError:
    genai = None

_global_gemini_client: Optional["GeminiClient"] = None


class GeminiClient:
    def __init__(self, settings_repo: Optional[SettingsRepository] = None):
        self.settings_repo = settings_repo or SettingsRepository()

    def get_api_key(self) -> str:
        # Check SQLite settings first, then environment variable
        stored_key = self.settings_repo.get("gemini_api_key", "")
        if stored_key and stored_key.strip():
            return stored_key.strip()
        env_key = os.getenv("GEMINI_API_KEY", "")
        return env_key.strip() if env_key else ""

    def get_model(self) -> str:
        return self.settings_repo.get("gemini_model", config.DEFAULT_GEMINI_MODEL) or config.DEFAULT_GEMINI_MODEL

    def is_configured(self) -> bool:
        key = self.get_api_key()
        return bool(key and len(key) >= 10)

    def _get_genai_client(self):
        if genai is None:
            raise RuntimeError("The 'google-genai' package is not installed. Please run 'pip install google-genai'.")
        key = self.get_api_key()
        if not key:
            raise ValueError("Gemini API key is not configured. Please set it in Settings or via GEMINI_API_KEY.")
        return genai.Client(api_key=key)

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        """Generates text using the Gemini API."""
        if not self.is_configured():
            return "Gemini API key is not configured. Please supply an API key in Settings."

        client = self._get_genai_client()
        model = self.get_model()

        # Handle SDK calls
        try:
            # Check interactions API or generate_content
            if hasattr(client, "interactions"):
                kwargs: Dict[str, Any] = {"model": model, "input": prompt}
                if system_instruction:
                    kwargs["system_instruction"] = system_instruction
                resp = client.interactions.create(**kwargs)
                return resp.output_text or ""
            elif hasattr(client, "models"):
                resp = client.models.generate_content(model=model, contents=prompt)
                return resp.text or ""
            else:
                return "Unsupported google-genai client structure."
        except Exception as e:
            return f"Gemini API Error: {str(e)}"

    def generate_json(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """Generates and extracts clean JSON from Gemini output."""
        augmented_prompt = (
            f"{prompt}\n\nIMPORTANT: Respond with pure JSON only. Do not enclose in markdown ticks if possible."
        )
        raw_text = self.generate_text(augmented_prompt, system_instruction=system_instruction)

        # Clean markdown code blocks if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        # Extract first JSON object or array match
        match = re.search(r"(\{.*\}|\[.*\])", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(0)

        try:
            return json.loads(clean_text)
        except Exception as e:
            return {
                "error": f"Failed to parse JSON response: {str(e)}",
                "raw_response": raw_text,
            }


def get_gemini_client() -> GeminiClient:
    global _global_gemini_client
    if _global_gemini_client is None:
        _global_gemini_client = GeminiClient()
    return _global_gemini_client
