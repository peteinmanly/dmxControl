"""
AI Doctor & Self-Healing Telemetry Engine.
Monitors hardware communication, Linux Mint user permissions, conflicting daemons,
database integrity, and runtime script errors.
"""

import glob
import grp
import os
import platform
import subprocess
from typing import Dict, Any, List, Optional

import config
from database.db import get_db
from database.repositories import HealthLogRepository, SettingsRepository
from engine.hardware import get_hardware_daemon
from engine.script_runner import get_script_runner
from .gemini_client import get_gemini_client


class AIDoctor:
    def __init__(self):
        self.db = get_db()
        self.health_repo = HealthLogRepository(self.db)
        self.settings_repo = SettingsRepository(self.db)
        self.gemini = get_gemini_client()

    def collect_telemetry(self) -> Dict[str, Any]:
        """Gathers system, kernel, serial hardware, permission, and application metrics."""
        telemetry: Dict[str, Any] = {
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "linux_mint": self._check_linux_distro(),
            "user_permissions": self._check_user_permissions(),
            "serial_devices": self._check_serial_ports(),
            "daemons": self._check_conflicting_daemons(),
            "database_integrity": self.db.check_integrity(),
            "hardware_daemon": get_hardware_daemon().get_status(),
            "running_scripts": get_script_runner().get_active_scripts(),
        }
        return telemetry

    def _check_linux_distro(self) -> Dict[str, Any]:
        info = {"is_linux_mint": False, "distro_name": "Unknown", "version": ""}
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r") as f:
                    content = f.read().lower()
                    info["is_linux_mint"] = "linux mint" in content
                    for line in content.splitlines():
                        if line.startswith("pretty_name="):
                            info["distro_name"] = line.split("=", 1)[1].strip('"\'')
                        elif line.startswith("version_id="):
                            info["version"] = line.split("=", 1)[1].strip('"\'')
            except Exception:
                pass
        return info

    def _check_user_permissions(self) -> Dict[str, Any]:
        uid = os.getuid() if hasattr(os, "getuid") else 1000
        in_dialout = False
        user_groups = []
        try:
            # Check groups for current user
            gids = os.getgroups()
            for gid in gids:
                try:
                    gname = grp.getgrgid(gid).gr_name
                    user_groups.append(gname)
                    if gname in ("dialout", "uucp"):
                        in_dialout = True
                except Exception:
                    continue
        except Exception:
            pass

        # On macOS or Windows, dialout is not applicable
        if platform.system() != "Linux":
            in_dialout = True

        return {
            "uid": uid,
            "groups": user_groups,
            "in_dialout": in_dialout,
            "permission_hint": "User in dialout group" if in_dialout else "User NOT in dialout group. Run: sudo usermod -a -G dialout $USER",
        }

    def _check_serial_ports(self) -> Dict[str, Any]:
        by_id = glob.glob("/dev/serial/by-id/*")
        tty_usb = sorted(glob.glob("/dev/ttyUSB*"))
        has_enttec = any("enttec" in p.lower() or "ftdi" in p.lower() for p in by_id)
        
        # Check latency timers on Linux
        latency_timers = {}
        for dev in tty_usb:
            dev_name = os.path.basename(dev)
            lat_path = f"/sys/bus/usb-serial/devices/{dev_name}/latency_timer"
            if os.path.exists(lat_path):
                try:
                    with open(lat_path, "r") as f:
                        latency_timers[dev] = int(f.read().strip())
                except Exception:
                    pass

        return {
            "by_id": by_id,
            "tty_usb": tty_usb,
            "has_enttec_match": has_enttec,
            "latency_timers": latency_timers,
        }

    def _check_conflicting_daemons(self) -> Dict[str, Any]:
        """Checks for Linux Mint services known to conflict with FTDI serial (like brltty)."""
        brltty_active = False
        if platform.system() == "Linux":
            try:
                res = subprocess.run(["systemctl", "is-active", "brltty"], capture_output=True, text=True, timeout=1)
                brltty_active = res.stdout.strip() == "active"
            except Exception:
                pass
        return {
            "brltty_active": brltty_active,
            "conflict_detected": brltty_active,
        }

    def diagnose_and_heal(self) -> Dict[str, Any]:
        """
        Executes a diagnostic scan.
        Applies safe automated fixes and consults Gemini AI if configured.
        """
        telemetry = self.collect_telemetry()
        detected_issues = []
        auto_actions_taken = []
        user_commands = []

        # 1. Deterministic Rule Checks
        user_perm = telemetry["user_permissions"]
        if not user_perm["in_dialout"] and platform.system() == "Linux":
            detected_issues.append("Current Linux Mint user does not belong to the 'dialout' group.")
            user_commands.append({
                "command": f"sudo usermod -a -G dialout {os.environ.get('USER', '$USER')} && newgrp dialout",
                "explanation": "Grants passwordless permission to access /dev/ttyUSB0 without requiring root."
            })

        daemons = telemetry["daemons"]
        if daemons["brltty_active"]:
            detected_issues.append("Conflicting 'brltty' (Braille TTY) service is active and locking FTDI USB devices.")
            user_commands.append({
                "command": "sudo systemctl stop brltty && sudo systemctl mask brltty",
                "explanation": "Prevents brltty from intercepting and breaking the Enttec Open DMX USB connection."
            })

        hw_status = telemetry["hardware_daemon"]
        is_hw_connected = hw_status.get("hardware_connected", False)
        driver_diag = hw_status.get("driver_diagnostics", {})
        if hw_status.get("driver_mode") == "enttec_open" and not is_hw_connected:
            # Check if port changed or can be auto-recovered
            candidate_ports = telemetry["serial_devices"]["by_id"] or telemetry["serial_devices"]["tty_usb"]
            if candidate_ports:
                target_port = candidate_ports[0]
                rebound = get_hardware_daemon().set_driver("enttec_open", port=target_port)
                if rebound:
                    auto_actions_taken.append(f"Auto-bound Enttec driver to detected port {target_port}.")
                else:
                    detected_issues.append(f"Enttec Open DMX failed to open on {target_port}: {driver_diag.get('last_error')}")
            else:
                detected_issues.append("No physical USB serial device detected for Enttec Open DMX USB.")

        # Latency timer warning on Linux
        latency_timers = telemetry["serial_devices"].get("latency_timers", {})
        for port, lat_val in latency_timers.items():
            if lat_val > 1:
                user_commands.append({
                    "command": f"echo 1 | sudo tee /sys/bus/usb-serial/devices/{os.path.basename(port)}/latency_timer",
                    "explanation": f"Reduces FTDI driver latency from {lat_val}ms to 1ms for jitter-free 40 Hz DMX frames."
                })

        # Database health check
        db_health = telemetry["database_integrity"]
        if not db_health.get("ok"):
            detected_issues.append(f"Database integrity issue: {db_health.get('details')}")
            # Self-healing database check
            try:
                self.db.init_database()
                auto_actions_taken.append("Executed database schema integrity migration.")
            except Exception as e:
                detected_issues.append(f"Database repair failed: {str(e)}")

        # Script execution errors
        for script in telemetry["running_scripts"]:
            if script.get("error"):
                detected_issues.append(f"Script #{script['script_id']} ('{script['name']}') crashed: {script['error']}")

        # 2. Consult Gemini AI if configured and issues exist
        ai_analysis: Optional[Dict[str, Any]] = None
        if self.gemini.is_configured() and detected_issues:
            prompt = f"""
You are the AI Doctor for an open-source DMX lighting controller running on a Linux Mint host with an Enttec Open DMX USB interface.
The user's lighting system has encountered the following issues:
{json_dumps(detected_issues)}

System Telemetry Summary:
- OS: {telemetry['os']} (Linux Mint: {telemetry['linux_mint']})
- User Permissions: {telemetry['user_permissions']}
- Serial Devices Detected: {telemetry['serial_devices']}
- Daemons: {telemetry['daemons']}
- Hardware Status: {telemetry['hardware_daemon']}

Provide a structured JSON diagnosis with the following keys:
1. "diagnosis": Clear, empathetic explanation of what went wrong and why.
2. "severity": "warning" or "critical".
3. "user_instructions": Plain-English recommendations for the user.
4. "recommended_commands": List of bash command objects with keys "command" and "explanation".
"""
            try:
                ai_resp = self.gemini.generate_json(prompt, system_instruction="Respond with pure JSON only.")
                if isinstance(ai_resp, dict) and "diagnosis" in ai_resp:
                    ai_analysis = ai_resp
                    if "recommended_commands" in ai_resp and isinstance(ai_resp["recommended_commands"], list):
                        user_commands.extend(ai_resp["recommended_commands"])
            except Exception as e:
                ai_analysis = {"error": f"Gemini consultation failed: {str(e)}"}

        critical_issues = [
            i for i in detected_issues if ("failed" in i.lower() or "crashed" in i.lower() or "integrity" in i.lower())
        ]
        if critical_issues:
            overall_status = "CRITICAL"
        elif not is_hw_connected:
            overall_status = "DISCONNECTED"
        elif detected_issues:
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"

        # Record to Health Logs
        if detected_issues or auto_actions_taken:
            self.health_repo.log(
                category="system",
                severity="critical" if overall_status == "CRITICAL" else "warning",
                message=f"Health check: {len(detected_issues)} issue(s) found",
                details={
                    "issues": detected_issues,
                    "auto_actions": auto_actions_taken,
                    "ai_analysis": ai_analysis,
                },
                remediated=1 if not detected_issues else 0,
            )

        return {
            "status": overall_status,
            "issues": detected_issues,
            "auto_actions_taken": auto_actions_taken,
            "recommended_commands": user_commands,
            "ai_analysis": ai_analysis,
            "telemetry": telemetry,
        }


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, indent=2)
