"""
Interactive AI Terminal Troubleshooter.
Helps users formulate safe Linux Mint terminal commands to diagnose issues,
and parses pasted terminal output to deliver plain-English explanations and step-by-step remediation commands.
"""

from typing import Dict, Any, List, Optional
from .gemini_client import get_gemini_client

QUICK_RECIPES = {
    "audit_usb": {
        "title": "Audit Enttec USB & Drivers",
        "description": "Inspects USB devices, FTDI serial symlinks, and /dev/ttyUSB nodes.",
        "command": "lsusb | grep -i -E 'ftdi|enttec|usb'; ls -la /dev/serial/by-id/ 2>/dev/null; ls -la /dev/ttyUSB* 2>/dev/null",
    },
    "check_permissions": {
        "title": "Check User Groups & Permissions",
        "description": "Checks if the current Linux user belongs to the 'dialout' group.",
        "command": "id -u -n; groups; ls -l /dev/ttyUSB0 2>/dev/null",
    },
    "check_conflicts": {
        "title": "Detect Conflicting Daemons (brltty)",
        "description": "Checks if Braille TTY or another process has grabbed the serial interface.",
        "command": "systemctl status brltty --no-pager 2>/dev/null; fuser -v /dev/ttyUSB0 2>/dev/null; lsof /dev/ttyUSB0 2>/dev/null",
    },
    "check_latency_and_logs": {
        "title": "Inspect Latency Timer & Kernel Logs",
        "description": "Checks FTDI 1ms latency timer setting and recent kernel USB serial messages.",
        "command": "cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer 2>/dev/null; dmesg | grep -i -E 'ftdi|usb.*serial|ttyUSB' | tail -n 20",
    },
}


class TerminalTroubleshooter:
    def __init__(self):
        self.gemini = get_gemini_client()

    def get_quick_recipes(self) -> Dict[str, Any]:
        return QUICK_RECIPES

    def generate_command(self, issue_description: str, recipe_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Formulates a safe, non-destructive Linux Mint terminal command based on user problem description.
        """
        if recipe_key and recipe_key in QUICK_RECIPES:
            rec = QUICK_RECIPES[recipe_key]
            return {
                "command": rec["command"],
                "explanation": rec["description"],
                "recipe_key": recipe_key,
                "is_ai_generated": False,
            }

        # Custom user description
        if not issue_description or not issue_description.strip():
            # Default to full audit command
            cmd = "lsusb; ls -la /dev/serial/by-id/ 2>/dev/null; groups; systemctl is-active brltty 2>/dev/null"
            return {
                "command": cmd,
                "explanation": "Standard Linux Mint DMX hardware and permission diagnostic bundle.",
                "recipe_key": "audit_usb",
                "is_ai_generated": False,
            }

        if self.gemini.is_configured():
            prompt = f"""
The user is experiencing an issue with an open-source DMX lighting controller running on a Linux Mint PC with an Enttec Open DMX USB adapter.
User's problem description:
"{issue_description}"

Generate a single safe, read-only Linux Mint bash command pipeline that will inspect the system and provide the diagnostic info needed to solve this problem.
Allowed commands: lsusb, ls, dmesg, systemctl, id, groups, fuser, lsof, cat /sys/..., grep.
DO NOT generate any commands that modify, delete, or reboot the system.

Respond in pure JSON with keys:
"command": the exact shell command string
"explanation": 1-2 sentence explanation of what this command will check
"""
            ai_resp = self.gemini.generate_json(prompt)
            if isinstance(ai_resp, dict) and "command" in ai_resp:
                return {
                    "command": ai_resp["command"],
                    "explanation": ai_resp.get("explanation", "Custom diagnostic command tailored to your problem."),
                    "recipe_key": "custom",
                    "is_ai_generated": True,
                }

        # Fallback if Gemini key is not configured
        fallback_cmd = "lsusb | grep -i ftdi; ls -la /dev/serial/by-id/ 2>/dev/null; groups; systemctl is-active brltty 2>/dev/null"
        return {
            "command": fallback_cmd,
            "explanation": "Diagnostic pipeline checking USB hardware presence, serial device nodes, user groups, and the brltty conflict daemon.",
            "recipe_key": "custom",
            "is_ai_generated": False,
        }

    def analyze_output(self, issue_description: str, command_run: str, terminal_output: str) -> Dict[str, Any]:
        """
        Parses pasted terminal output and returns plain-English diagnosis,
        step-by-step remediation commands, and verification steps.
        """
        if not terminal_output or not terminal_output.strip():
            return {
                "diagnosis": "No terminal output provided.",
                "remediation_commands": [],
                "verification_command": "",
                "user_instructions": "Please run the suggested command in your terminal and paste the output here.",
            }

        if self.gemini.is_configured():
            prompt = f"""
You are an expert Linux Mint lighting systems engineer.
A user reported the following lighting problem:
"{issue_description}"

They ran this diagnostic terminal command:
`{command_run}`

Here is the exact terminal output they received:
```
{terminal_output}
```

Analyze the terminal output and diagnose the root cause.
Respond with pure JSON containing:
1. "diagnosis": Plain-English explanation of what is happening based on the output.
2. "severity": "info", "warning", or "critical".
3. "remediation_commands": List of objects with "command" (exact bash command string) and "explanation" (what it does).
4. "verification_command": A quick terminal command to verify that the issue is fixed.
5. "user_instructions": Friendly step-by-step guidance.
"""
            ai_resp = self.gemini.generate_json(prompt)
            if isinstance(ai_resp, dict) and "diagnosis" in ai_resp:
                return ai_resp

        # Deterministic Rule Fallback (if Gemini key is not configured)
        lower_out = terminal_output.lower()
        remediations = []
        findings = []

        if "brltty" in lower_out and ("active" in lower_out or "running" in lower_out):
            findings.append("The 'brltty' (Braille TTY) service is active and locking FTDI USB devices.")
            remediations.append({
                "command": "sudo systemctl stop brltty && sudo systemctl mask brltty",
                "explanation": "Disables brltty so it stops intercepting the Enttec Open DMX USB adapter.",
            })

        if "dialout" not in lower_out and ("groups" in command_run or "id" in command_run):
            findings.append("Your Linux user account does not have permission to access serial devices.")
            remediations.append({
                "command": "sudo usermod -a -G dialout $USER && newgrp dialout",
                "explanation": "Adds your user to the dialout group for passwordless access to /dev/ttyUSB0.",
            })

        if "no such file or directory" in lower_out or "ttyusb" not in lower_out:
            findings.append("No USB serial device node (/dev/ttyUSB*) was found.")
            remediations.append({
                "command": "dmesg | grep -i usb | tail -n 15",
                "explanation": "Inspects kernel logs to see if the USB cable is detected or having physical connection issues.",
            })

        if not findings:
            findings.append("Diagnostic output processed. Hardware and permissions appear standard.")

        return {
            "diagnosis": " ".join(findings),
            "severity": "warning" if remediations else "info",
            "remediation_commands": remediations,
            "verification_command": "ls -l /dev/ttyUSB0",
            "user_instructions": "Run the remediation commands above in your terminal, then re-test connection in Settings.",
        }
