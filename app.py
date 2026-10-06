"""
FastAPI Application Entry Point for AI-Assisted DMX Web Controller.
Provides REST APIs, WebSockets for 40 Hz universe diagnostics, and static web UI hosting.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from database.db import get_db
from database.repositories import (
    FixtureRepository,
    PresetRepository,
    ShowScriptRepository,
    SettingsRepository,
    HealthLogRepository,
)
from engine.mixer import get_mixer
from engine.hardware import get_hardware_daemon
from engine.script_runner import get_script_runner
from ai.gemini_client import get_gemini_client
from ai.self_healing import AIDoctor
from ai.terminal_troubleshooter import TerminalTroubleshooter
from ai.show_generator import ShowScriptGenerator, validate_script_ast
from ai.fixture_wizard import FixtureWizardSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and Hardware Daemon
    db = get_db()
    db.init_database()
    hw_daemon = get_hardware_daemon()
    hw_daemon.start()

    # Run initial health check in background
    doctor = AIDoctor()
    try:
        doctor.diagnose_and_heal()
    except Exception:
        pass

    yield

    # Shutdown: Stop hardware daemon and kill any running show scripts
    get_script_runner().kill_all()
    hw_daemon.stop()


app = FastAPI(
    title="AI-Assisted DMX Web Controller",
    description="Production-grade local lighting controller for Linux Mint and Enttec Open DMX USB.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


# ---------------------------------------------------------
# UI Shell Route
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = config.TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html template not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------
# Fixture CRUD Endpoints
# ---------------------------------------------------------
@app.get("/api/fixtures")
def get_fixtures(active_only: bool = False):
    repo = FixtureRepository()
    return {"fixtures": repo.get_all(active_only=active_only)}


@app.post("/api/fixtures")
async def create_fixture(request: Request):
    data = await request.json()
    repo = FixtureRepository()
    try:
        fixture_id = repo.create(fixture_data=data, channels=data.get("channels", []))
        return {"success": True, "fixture_id": fixture_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/fixtures/{fixture_id}")
async def update_fixture(fixture_id: int, request: Request):
    data = await request.json()
    repo = FixtureRepository()
    ok = repo.update(fixture_id, fixture_data=data, channels=data.get("channels"))
    if not ok:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return {"success": True}


@app.delete("/api/fixtures/{fixture_id}")
def delete_fixture(fixture_id: int):
    repo = FixtureRepository()
    ok = repo.delete(fixture_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return {"success": True}


@app.post("/api/fixtures/{fixture_id}/toggle")
async def toggle_fixture(fixture_id: int, request: Request):
    data = await request.json()
    repo = FixtureRepository()
    ok = repo.toggle_active(fixture_id, is_active=bool(data.get("is_active", True)))
    if not ok:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return {"success": True}


# ---------------------------------------------------------
# Preset (Static Scene) Endpoints
# ---------------------------------------------------------
@app.get("/api/presets")
def get_presets():
    repo = PresetRepository()
    return {"presets": repo.get_all()}


@app.post("/api/presets")
async def create_preset(request: Request):
    data = await request.json()
    repo = PresetRepository()
    preset_id = repo.create(
        name=data["name"],
        channel_payload=data.get("channel_payload", {}),
        description=data.get("description", ""),
        category=data.get("category", "custom"),
    )
    return {"success": True, "preset_id": preset_id}


@app.post("/api/presets/{preset_id}/trigger")
async def trigger_preset(preset_id: int, request: Request):
    repo = PresetRepository()
    preset = repo.get_by_id(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    fade_time = 0.0
    try:
        body = await request.json()
        fade_time = float(body.get("fade_time", 0.0))
    except Exception:
        pass

    mixer = get_mixer()
    owner_tag = f"Preset:{preset_id}"
    if fade_time > 0.05:
        mixer.fade_to_channels(preset["channel_payload"], duration_sec=fade_time, owner=owner_tag)
        return {"success": True, "preset_id": preset_id, "fade_time": fade_time}
    else:
        updated = mixer.set_channels(preset["channel_payload"], owner=owner_tag)
        return {"success": True, "preset_id": preset_id, "channels_updated": updated, "fade_time": 0.0}


@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: int):
    repo = PresetRepository()
    ok = repo.delete(preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"success": True}


# ---------------------------------------------------------
# Grand Master Intensity Fader Endpoints
# ---------------------------------------------------------
@app.get("/api/master/grand_master")
def get_grand_master():
    mixer = get_mixer()
    level = mixer.get_grand_master()
    return {"level": level, "percent": int(round(level * 100))}


@app.post("/api/master/grand_master")
async def set_grand_master(request: Request):
    data = await request.json()
    mixer = get_mixer()
    if "percent" in data:
        level = float(data["percent"]) / 100.0
    else:
        level = float(data.get("level", 1.0))
    applied = mixer.set_grand_master(level)
    return {"success": True, "level": applied, "percent": int(round(applied * 100))}


# ---------------------------------------------------------
# Show Scripts (Procedural Routines) Endpoints
# ---------------------------------------------------------
@app.get("/api/scripts")
def get_scripts(page: Optional[int] = None):
    repo = ShowScriptRepository()
    runner = get_script_runner()
    scripts = repo.get_all(page=page)
    # Augment with live running status
    for s in scripts:
        s["is_running"] = runner.is_running(s["id"])
    return {"scripts": scripts}


@app.post("/api/scripts")
async def create_script(request: Request):
    data = await request.json()
    code = data.get("python_code", "")
    is_safe, err_msg = validate_script_ast(code)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"AST Security Check Failed: {err_msg}")

    repo = ShowScriptRepository()
    script_id = repo.create(
        name=data["name"],
        footprint_channels=data.get("footprint_channels", []),
        python_code=code,
        description=data.get("description", ""),
        is_favorite=data.get("is_favorite", 0),
        ui_page=data.get("ui_page", 1),
        created_by_ai=data.get("created_by_ai", 0),
    )
    return {"success": True, "script_id": script_id}


@app.post("/api/scripts/{script_id}/start")
def start_script(script_id: int):
    repo = ShowScriptRepository()
    script = repo.get_by_id(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    runner = get_script_runner()
    res = runner.start_script(
        script_id=script["id"],
        name=script["name"],
        footprint=script["footprint_channels"],
        python_code=script["python_code"],
    )
    return res


@app.post("/api/scripts/{script_id}/stop")
def stop_script(script_id: int):
    runner = get_script_runner()
    ok = runner.stop_script(script_id)
    return {"success": ok, "script_id": script_id}


@app.delete("/api/scripts/{script_id}")
def delete_script(script_id: int):
    runner = get_script_runner()
    runner.stop_script(script_id)
    repo = ShowScriptRepository()
    ok = repo.delete(script_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Script not found")
    return {"success": True}


@app.get("/api/scripts/running")
def get_running_scripts():
    runner = get_script_runner()
    return {"active_scripts": runner.get_active_scripts()}


@app.get("/api/scripts/speed")
def get_script_speed():
    runner = get_script_runner()
    return {"multiplier": runner.get_speed_multiplier()}


@app.post("/api/scripts/speed")
async def set_script_speed(request: Request):
    data = await request.json()
    multiplier = float(data.get("multiplier", 1.0))
    runner = get_script_runner()
    applied = runner.set_speed_multiplier(multiplier)
    return {"success": True, "multiplier": applied}


# ---------------------------------------------------------
# Panic Controls
# ---------------------------------------------------------
@app.post("/api/panic/blackout")
def panic_blackout():
    """Emergency master blackout: all channels to 0 and halt all scripts."""
    runner = get_script_runner()
    stopped = runner.kill_all()
    mixer = get_mixer()
    mixer.blackout()
    return {"success": True, "message": "Master Blackout Engaged", "scripts_stopped": stopped}


@app.post("/api/panic/kill_effects")
def panic_kill_effects():
    """Halts all procedural script threads, holding current channel levels."""
    runner = get_script_runner()
    stopped = runner.kill_all()
    return {"success": True, "message": "All Effects Terminated", "scripts_stopped": stopped}


# ---------------------------------------------------------
# AI Features: Show Generator & Fixture Wizard
# ---------------------------------------------------------
@app.post("/api/ai/generate_show")
async def generate_show_routine(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    fixtures = FixtureRepository().get_all(active_only=True)
    generator = ShowScriptGenerator()
    res = generator.generate_show(prompt=prompt, fixtures_context=fixtures)
    return res


@app.post("/api/ai/wizard/doc_lookup")
async def wizard_doc_lookup(request: Request):
    data = await request.json()
    wizard = FixtureWizardSession()
    res = wizard.doc_lookup(
        fixture_name=data.get("name", "Generic Fixture"),
        manufacturer=data.get("manufacturer", "Generic"),
        spec_text=data.get("spec_text", ""),
        start_channel=int(data.get("start_channel", 1)),
    )
    return res


@app.post("/api/ai/wizard/probe/start")
async def wizard_probe_start(request: Request):
    data = await request.json()
    wizard = FixtureWizardSession()
    res = wizard.start_probe_session(
        fixture_name=data.get("name", "Generic Probe"),
        start_channel=int(data.get("start_channel", 1)),
        channel_count=int(data.get("channel_count", 4)),
    )
    return res


@app.post("/api/ai/wizard/probe/step")
async def wizard_probe_step(request: Request):
    data = await request.json()
    wizard = FixtureWizardSession()
    res = wizard.submit_probe_feedback(
        session_id=int(data["session_id"]),
        user_feedback=data.get("user_feedback", ""),
    )
    return res


# ---------------------------------------------------------
# AI Doctor & Diagnostics Endpoints
# ---------------------------------------------------------
@app.get("/api/ai/doctor/status")
def doctor_status():
    doctor = AIDoctor()
    return doctor.diagnose_and_heal()


@app.post("/api/ai/doctor/diagnose")
def doctor_diagnose():
    doctor = AIDoctor()
    return doctor.diagnose_and_heal()


# ---------------------------------------------------------
# Interactive Terminal Troubleshooter Endpoints
# ---------------------------------------------------------
@app.get("/api/ai/troubleshoot/recipes")
def troubleshoot_recipes():
    troubleshooter = TerminalTroubleshooter()
    return {"recipes": troubleshooter.get_quick_recipes()}


@app.post("/api/ai/troubleshoot/command")
async def troubleshoot_command(request: Request):
    data = await request.json()
    troubleshooter = TerminalTroubleshooter()
    res = troubleshooter.generate_command(
        issue_description=data.get("issue_description", ""),
        recipe_key=data.get("recipe_key"),
    )
    return res


@app.post("/api/ai/troubleshoot/analyze")
async def troubleshoot_analyze(request: Request):
    data = await request.json()
    troubleshooter = TerminalTroubleshooter()
    res = troubleshooter.analyze_output(
        issue_description=data.get("issue_description", ""),
        command_run=data.get("command_run", ""),
        terminal_output=data.get("terminal_output", ""),
    )
    return res


# ---------------------------------------------------------
# Application Settings & Maintenance Endpoints
# ---------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    repo = SettingsRepository()
    all_settings = repo.get_all()
    # Mask API key for security
    raw_key = all_settings.get("gemini_api_key", "")
    all_settings["has_gemini_key"] = bool(raw_key and len(raw_key) > 5)
    all_settings["gemini_api_key_masked"] = (
        f"{raw_key[:4]}...{raw_key[-4:]}" if len(raw_key) >= 8 else ("Configured" if raw_key else "Not Set")
    )
    return {"settings": all_settings, "hardware": get_hardware_daemon().get_status()}


@app.post("/api/settings")
async def update_settings(request: Request):
    data = await request.json()
    repo = SettingsRepository()
    hw_daemon = get_hardware_daemon()

    for k, v in data.items():
        if k in ("gemini_api_key", "gemini_model", "driver", "serial_port", "fps"):
            repo.set(k, str(v))

    # Apply hardware updates if driver or port changed
    if "driver" in data or "serial_port" in data:
        new_driver = data.get("driver", repo.get("driver", "enttec_open"))
        new_port = data.get("serial_port", repo.get("serial_port", config.DEFAULT_SERIAL_PORT))
        hw_daemon.set_driver(new_driver, port=new_port)

    if "fps" in data:
        try:
            hw_daemon.set_fps(int(data["fps"]))
        except ValueError:
            pass

    return {"success": True, "settings": repo.get_all()}


@app.get("/api/settings/backup")
def export_backup():
    db = get_db()
    backup_data = db.export_backup_json()
    return JSONResponse(
        content=backup_data,
        headers={"Content-Disposition": "attachment; filename=dmx_controller_backup.json"},
    )


@app.post("/api/settings/reset")
def reset_database():
    db = get_db()
    db.reset_factory_defaults()
    return {"success": True, "message": "Database reset to factory defaults with sample fixtures and presets."}


# ---------------------------------------------------------
# Real-Time WebSocket for Universe State (30-40 Hz)
# ---------------------------------------------------------
@app.websocket("/ws/universe")
async def universe_websocket(websocket: WebSocket):
    await websocket.accept()
    mixer = get_mixer()
    hw_daemon = get_hardware_daemon()

    try:
        while True:
            # Broadcast frame state, ownership, and daemon stats at ~30 FPS
            state = mixer.get_universe_state()
            state["hw_status"] = hw_daemon.get_status()
            await websocket.send_json(state)
            await asyncio.sleep(0.033)  # ~30 Hz UI update loop
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass
