"""
AI Show Script Generator & AST Safety Validator.
Inspects Python Abstract Syntax Trees (AST) to ensure dynamic procedural scripts
cannot perform file I/O, network calls, or unauthorized system operations.
"""

import ast
from typing import Dict, Any, List, Optional, Tuple, Set

from .gemini_client import get_gemini_client

ALLOWED_IMPORTS = {"math", "time", "random"}
DISALLOWED_NAMES = {
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "breakpoint",
    "input",
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "requests",
    "urllib",
}


class ScriptASTValidator(ast.NodeVisitor):
    def __init__(self):
        self.errors: List[str] = []
        self.has_loop = False
        self.checks_stop_event = False
        self.calls_sleep = False

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name not in ALLOWED_IMPORTS:
                self.errors.append(f"Unauthorized import '{alias.name}'. Only {sorted(list(ALLOWED_IMPORTS))} are permitted.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module not in ALLOWED_IMPORTS:
            self.errors.append(f"Unauthorized import from '{node.module}'. Only {sorted(list(ALLOWED_IMPORTS))} are permitted.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Check function name
        if isinstance(node.func, ast.Name):
            if node.func.id in DISALLOWED_NAMES:
                self.errors.append(f"Call to prohibited function '{node.func.id}()'.")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in DISALLOWED_NAMES:
                self.errors.append(f"Call to prohibited attribute '{node.func.attr}()'.")
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "time" and node.func.attr == "sleep":
                self.calls_sleep = True
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self.has_loop = True
        # Check if condition inspects stop_event
        cond_str = ast.dump(node.test)
        if "stop_event" in cond_str:
            self.checks_stop_event = True
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.has_loop = True
        self.generic_visit(node)


def validate_script_ast(python_code: str) -> Tuple[bool, Optional[str]]:
    """
    Parses Python source code and runs AST safety validation.
    Returns (True, None) if safe, or (False, "error message") if unsafe.
    """
    try:
        tree = ast.parse(python_code)
    except SyntaxError as se:
        return False, f"Syntax Error: {str(se)}"

    validator = ScriptASTValidator()
    validator.visit(tree)

    if validator.errors:
        return False, "Security Violation: " + "; ".join(validator.errors)

    if validator.has_loop and not validator.checks_stop_event:
        return False, "Infinite Loop Warning: Continuous loops must test 'while not stop_event.is_set():' to allow clean cancellation."

    if validator.has_loop and not validator.calls_sleep:
        return False, "CPU Starvation Warning: Script loop must call 'time.sleep(...)' (e.g. 0.02 - 0.05s) between frame steps."

    return True, None


class ShowScriptGenerator:
    def __init__(self):
        self.gemini = get_gemini_client()

    def generate_show(
        self,
        prompt: str,
        fixtures_context: List[Dict[str, Any]],
        retry_count: int = 2,
    ) -> Dict[str, Any]:
        """
        Uses Gemini to generate a procedural Python show script,
        validates the code using the AST security visitor,
        and auto-repairs any violations with Gemini.
        """
        if not self.gemini.is_configured():
            return {
                "success": False,
                "error": "Gemini API key is not configured. Please supply an API key in Settings.",
            }

        # Build fixture summary for prompt
        fix_lines = []
        all_channels: Set[int] = set()
        for f in fixtures_context:
            ch_desc = ", ".join(f"Ch {f['start_channel'] + c['channel_offset']}: {c['channel_type']} ({c['label']})" for c in f.get("channels", []))
            fix_lines.append(f"- Fixture #{f['id']} '{f['name']}' (Start Ch {f['start_channel']}, {f['channel_count']} channels): {ch_desc}")
            for c in f.get("channels", []):
                all_channels.add(f['start_channel'] + c['channel_offset'])

        system_instruction = """
You are an expert lighting programmer writing real-time procedural DMX lighting routines in Python.
The script will run in an isolated thread within the DMX controller.

ENVIRONMENT SPECIFICATIONS:
1. Available objects:
   - `dmx.set(channel: int, value: int)` (value 0-255)
   - `dmx.get(channel: int) -> int`
   - `stop_event`: threading.Event object
   - `time`: standard time module (use time.sleep(0.025 to 0.05) for smooth ~25-40 FPS animation)
   - `math`: standard math module (sin, cos, radians, pi, etc.)
   - `random`: random module
2. SAFETY CONSTRAINTS:
   - DO NOT import os, sys, subprocess, or socket.
   - Use `while not stop_event.is_set():` for loops.
   - Always include `time.sleep(0.02 - 0.05)` inside any loop to prevent CPU lock.
3. OUTPUT FORMAT:
   Respond with pure JSON only:
   {
     "name": "Short Descriptive Title",
     "description": "1-2 sentence description of the visual effect",
     "footprint_channels": [1, 2, 3...],
     "python_code": "the executable python source code as a string"
   }
"""

        user_content = f"""
USER REQUEST:
"{prompt}"

PATCHED LIGHTING FIXTURES IN UNIVERSE:
{chr(10).join(fix_lines) if fix_lines else "Generic Channels 1..8 (Dimmer, Red, Green, Blue on Ch 1..4, and Ch 5..8)"}
"""

        current_prompt = user_content
        for attempt in range(retry_count + 1):
            ai_resp = self.gemini.generate_json(current_prompt, system_instruction=system_instruction)
            if not isinstance(ai_resp, dict) or "python_code" not in ai_resp:
                current_prompt += "\nError: Invalid JSON output. Return pure JSON with 'name', 'description', 'footprint_channels', and 'python_code'."
                continue

            code = ai_resp["python_code"]
            is_safe, err_msg = validate_script_ast(code)
            if is_safe:
                # Ensure footprint is valid list of ints
                footprint = ai_resp.get("footprint_channels", [])
                clean_footprint = sorted(list(set(int(c) for c in footprint if 1 <= int(c) <= config.UNIVERSE_SIZE)))
                if not clean_footprint:
                    clean_footprint = sorted(list(all_channels))[:8]

                return {
                    "success": True,
                    "name": ai_resp.get("name", "AI Show Routine"),
                    "description": ai_resp.get("description", prompt),
                    "footprint_channels": clean_footprint,
                    "python_code": code,
                    "attempts": attempt + 1,
                }
            else:
                # Feed error back to Gemini for self-repair
                current_prompt = f"""
The previous generated code failed AST security validation with error:
{err_msg}

Previous code:
```python
{code}
```

Fix the violation immediately and respond with corrected JSON.
"""

        return {
            "success": False,
            "error": f"Failed AST validation after {retry_count + 1} attempts: {err_msg}",
            "last_code": code if "code" in locals() else None,
        }
