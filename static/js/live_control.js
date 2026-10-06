/**
 * Tab 1: Live Busking Control Dashboard.
 * Manages Presets, Dynamic Show Scripts, Panic controls, and AI Show Generator.
 */

document.addEventListener("DOMContentLoaded", () => {
  const presetGrid = document.getElementById("preset-grid");
  const scriptGrid = document.getElementById("script-grid");
  const matrixStrip = document.getElementById("partition-matrix");
  const btnBlackout = document.getElementById("btn-master-blackout");
  const btnKillEffects = document.getElementById("btn-kill-effects");

  // AI Show Generator Elements
  const btnOpenAiShow = document.getElementById("btn-open-ai-show-modal");
  const modalAiShow = document.getElementById("modal-ai-show");
  const btnSubmitAiShow = document.getElementById("btn-submit-ai-show");
  const aiShowPrompt = document.getElementById("ai-show-prompt");
  const aiShowResult = document.getElementById("ai-show-result");
  const aiShowTitle = document.getElementById("ai-show-title");
  const aiShowDesc = document.getElementById("ai-show-desc");
  const aiShowFootprint = document.getElementById("ai-show-footprint");
  const aiShowCode = document.getElementById("ai-show-code");
  const btnTestAiShow = document.getElementById("btn-test-ai-show");
  const btnSaveAiShow = document.getElementById("btn-save-ai-show");

  // Grand Master & Tempo Elements
  const grandMasterSlider = document.getElementById("grand-master-slider");
  const grandMasterPct = document.getElementById("grand-master-pct");
  const headerGmPct = document.getElementById("header-grand-master-pct");
  const faderFill = document.getElementById("fader-fill");
  const faderTrack = document.getElementById("fader-track");
  const btnMasterFull = document.getElementById("btn-master-full");
  const btnMasterZero = document.getElementById("btn-master-zero");

  const scriptSpeedSlider = document.getElementById("script-speed-slider");
  const scriptSpeedPct = document.getElementById("script-speed-pct");
  const btnTapTempo = document.getElementById("btn-tap-tempo");
  const tapTempoBpm = document.getElementById("tap-tempo-bpm");

  // View Switcher Elements
  const liveGrid = document.getElementById("live-grid");
  const viewBtnSplit = document.getElementById("view-btn-split");
  const viewBtnPresets = document.getElementById("view-btn-presets");
  const viewBtnScripts = document.getElementById("view-btn-scripts");
  const viewModeHint = document.getElementById("view-mode-hint");
  const btnTogglePresetsFullscreen = document.getElementById("btn-toggle-presets-fullscreen");
  const btnToggleScriptsFullscreen = document.getElementById("btn-toggle-scripts-fullscreen");

  // Build Partition Matrix Grid (512 blocks)
  buildPartitionMatrix();

  // Load Initial Data & Controls
  loadPresets();
  loadScripts();
  initGrandMaster();
  initSpeedAndTapTempo();
  initLiveViewModes();

  // -------------------------------------------------------
  // View Modes: Split View vs Fullscreen Presets vs Scripts
  // (Zero network traffic / zero DMX commands triggered)
  // -------------------------------------------------------
  function initLiveViewModes() {
    if (!liveGrid) return;

    // Restore saved view mode preference
    const savedMode = localStorage.getItem("dmx_live_view_mode") || "split";
    applyLiveViewMode(savedMode, false);

    if (viewBtnSplit) {
      viewBtnSplit.addEventListener("click", () => applyLiveViewMode("split", true));
    }
    if (viewBtnPresets) {
      viewBtnPresets.addEventListener("click", () => applyLiveViewMode("presets", true));
    }
    if (viewBtnScripts) {
      viewBtnScripts.addEventListener("click", () => applyLiveViewMode("scripts", true));
    }

    if (btnTogglePresetsFullscreen) {
      btnTogglePresetsFullscreen.addEventListener("click", () => {
        const isAlreadyPresetsOnly =
          document.body.classList.contains("fullscreen-presets-active") ||
          liveGrid.classList.contains("view-presets-only");
        applyLiveViewMode(isAlreadyPresetsOnly ? "split" : "presets", true);
      });
    }

    if (btnToggleScriptsFullscreen) {
      btnToggleScriptsFullscreen.addEventListener("click", () => {
        const isAlreadyScriptsOnly =
          document.body.classList.contains("fullscreen-scripts-active") ||
          liveGrid.classList.contains("view-scripts-only");
        applyLiveViewMode(isAlreadyScriptsOnly ? "split" : "scripts", true);
      });
    }

    // Allow user to press Escape to exit fullscreen mode at any time
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (
          document.body.classList.contains("fullscreen-presets-active") ||
          document.body.classList.contains("fullscreen-scripts-active")
        ) {
          applyLiveViewMode("split", true);
        }
      }
    });
  }

  function applyLiveViewMode(mode, save = true) {
    if (!liveGrid) return;

    [viewBtnSplit, viewBtnPresets, viewBtnScripts].forEach((b) => b && b.classList.remove("active"));
    liveGrid.classList.remove("view-presets-only", "view-scripts-only");
    document.body.classList.remove("fullscreen-presets-active", "fullscreen-scripts-active");

    if (btnTogglePresetsFullscreen) {
      btnTogglePresetsFullscreen.classList.remove("btn-exit-fullscreen");
      btnTogglePresetsFullscreen.textContent = "⛶ Fullscreen";
    }
    if (btnToggleScriptsFullscreen) {
      btnToggleScriptsFullscreen.classList.remove("btn-exit-fullscreen");
      btnToggleScriptsFullscreen.textContent = "⛶ Fullscreen";
    }

    if (mode === "presets") {
      liveGrid.classList.add("view-presets-only");
      document.body.classList.add("fullscreen-presets-active");
      if (viewBtnPresets) viewBtnPresets.classList.add("active");
      if (btnTogglePresetsFullscreen) {
        btnTogglePresetsFullscreen.classList.add("btn-exit-fullscreen");
        btnTogglePresetsFullscreen.textContent = "⤺ Exit Fullscreen";
      }
      if (viewModeHint) viewModeHint.innerHTML = "<span>Presets Fullscreen Mode (Master fader on right)</span>";
    } else if (mode === "scripts") {
      liveGrid.classList.add("view-scripts-only");
      document.body.classList.add("fullscreen-scripts-active");
      if (viewBtnScripts) viewBtnScripts.classList.add("active");
      if (btnToggleScriptsFullscreen) {
        btnToggleScriptsFullscreen.classList.add("btn-exit-fullscreen");
        btnToggleScriptsFullscreen.textContent = "⤺ Exit Fullscreen";
      }
      if (viewModeHint) viewModeHint.innerHTML = "<span>Scripts Fullscreen Mode (Master fader on right)</span>";
    } else {
      mode = "split";
      if (viewBtnSplit) viewBtnSplit.classList.add("active");
      if (viewModeHint) viewModeHint.innerHTML = "<span>Showing Presets & Scripts side-by-side</span>";
    }

    if (save) {
      try {
        localStorage.setItem("dmx_live_view_mode", mode);
      } catch (e) {}
    }
  }

  // -------------------------------------------------------
  // Full-Length Vertical Grand Master Fader (Right-Hand Side)
  // -------------------------------------------------------
  let gmDebounceTimer = null;
  let isDraggingFader = false;

  function initGrandMaster() {
    if (!grandMasterSlider) return;

    // Fetch initial level from server
    API.get("/api/master/grand_master")
      .then((data) => {
        if (data && data.percent !== undefined) {
          updateGrandMasterUI(data.percent);
        }
      })
      .catch((err) => console.error("Could not fetch grand master:", err));

    function updateGrandMasterUI(pct) {
      const clamped = Math.max(0, Math.min(100, Math.round(pct)));
      if (grandMasterSlider) grandMasterSlider.value = clamped;
      if (grandMasterPct) grandMasterPct.textContent = `${clamped}%`;
      if (headerGmPct) headerGmPct.textContent = `${clamped}%`;
      if (faderFill) faderFill.style.height = `${clamped}%`;
    }

    function commitGrandMaster(pct) {
      updateGrandMasterUI(pct);
      clearTimeout(gmDebounceTimer);
      gmDebounceTimer = setTimeout(async () => {
        try {
          await API.post("/api/master/grand_master", { percent: pct });
        } catch (err) {
          console.error("Failed to set grand master:", err);
        }
      }, 30);
    }

    // Native vertical range slider input event
    grandMasterSlider.addEventListener("input", (e) => {
      commitGrandMaster(parseInt(e.target.value, 10));
    });

    // Touch & Pointer drag on the fader track (ergonomic for iPad)
    if (faderTrack) {
      function calculatePctFromPointer(e) {
        const rect = faderTrack.getBoundingClientRect();
        const relativeY = e.clientY - rect.top;
        const normalized = 1 - (relativeY / rect.height);
        return Math.max(0, Math.min(100, Math.round(normalized * 100)));
      }

      faderTrack.addEventListener("pointerdown", (e) => {
        isDraggingFader = true;
        try {
          faderTrack.setPointerCapture(e.pointerId);
        } catch (err) {}
        commitGrandMaster(calculatePctFromPointer(e));
      });

      faderTrack.addEventListener("pointermove", (e) => {
        if (isDraggingFader) {
          commitGrandMaster(calculatePctFromPointer(e));
        }
      });

      const stopDrag = (e) => {
        if (isDraggingFader) {
          isDraggingFader = false;
          try {
            faderTrack.releasePointerCapture(e.pointerId);
          } catch (err) {}
        }
      };

      faderTrack.addEventListener("pointerup", stopDrag);
      faderTrack.addEventListener("pointercancel", stopDrag);
    }

    // Snap buttons (FULL & ZERO)
    if (btnMasterFull) {
      btnMasterFull.addEventListener("click", () => commitGrandMaster(100));
    }
    if (btnMasterZero) {
      btnMasterZero.addEventListener("click", () => commitGrandMaster(0));
    }

    // Sync from live WebSocket updates if user is not actively touching the fader
    window.addEventListener("universe-update", (e) => {
      if (isDraggingFader) return;
      const data = e.detail;
      if (data && data.grand_master !== undefined) {
        const pct = Math.round(data.grand_master * 100);
        // Only update if difference is meaningful to prevent slider flicker
        if (Math.abs(parseInt(grandMasterSlider.value, 10) - pct) > 1) {
          updateGrandMasterUI(pct);
        }
      }
    });
  }

  // -------------------------------------------------------
  // Presets Management (With Crossfade Transition)
  // -------------------------------------------------------
  async function loadPresets() {
    if (!presetGrid) return;
    try {
      const data = await API.get("/api/presets");
      renderPresets(data.presets || []);
    } catch (e) {
      presetGrid.innerHTML = `<p class="error-text">Failed to load presets: ${e.message}</p>`;
    }
  }

  function renderPresets(presets) {
    presetGrid.innerHTML = "";
    if (presets.length === 0) {
      presetGrid.innerHTML = "<p class='hint-text'>No presets created yet.</p>";
      return;
    }

    presets.forEach((p) => {
      const tile = document.createElement("div");
      tile.className = "preset-tile";
      tile.dataset.id = p.id;
      tile.innerHTML = `
        <div>
          <div class="preset-title">${escapeHtml(p.name)}</div>
          <div class="preset-desc">${escapeHtml(p.description || "Static scene look")}</div>
        </div>
        <div class="preset-tag">${escapeHtml(p.category || "look")}</div>
      `;

      tile.addEventListener("click", async () => {
        try {
          const fadeSelect = document.getElementById("preset-fade-select");
          const fadeTime = fadeSelect ? parseFloat(fadeSelect.value) : 0.0;
          await API.post(`/api/presets/${p.id}/trigger`, { fade_time: fadeTime });
          document.querySelectorAll(".preset-tile").forEach((t) => t.classList.remove("active-preset"));
          tile.classList.add("active-preset");
        } catch (err) {
          alert(`Error triggering preset: ${err.message}`);
        }
      });

      presetGrid.appendChild(tile);
    });
  }

  // -------------------------------------------------------
  // Show Scripts Management
  // -------------------------------------------------------
  async function loadScripts() {
    if (!scriptGrid) return;
    try {
      const data = await API.get("/api/scripts");
      renderScripts(data.scripts || []);
    } catch (e) {
      scriptGrid.innerHTML = `<p class="error-text">Failed to load scripts: ${e.message}</p>`;
    }
  }

  function renderScripts(scripts) {
    scriptGrid.innerHTML = "";
    if (scripts.length === 0) {
      scriptGrid.innerHTML = "<p class='hint-text'>No procedural scripts found.</p>";
      return;
    }

    scripts.forEach((s) => {
      const tile = document.createElement("div");
      tile.className = `script-tile ${s.is_running ? "running" : ""}`;
      tile.dataset.id = s.id;

      const footprintText = s.footprint_channels && s.footprint_channels.length > 0
        ? `Ch ${s.footprint_channels[0]}..${s.footprint_channels[s.footprint_channels.length - 1]}`
        : "Unassigned";

      tile.innerHTML = `
        <div class="script-top">
          <div class="script-title">${escapeHtml(s.name)}</div>
          <span class="script-badge ${s.is_running ? "badge-running" : "badge-stopped"}">
            ${s.is_running ? "RUNNING" : "STOPPED"}
          </span>
        </div>
        <div class="script-desc">${escapeHtml(s.description || "Dynamic procedural routine")}</div>
        <div class="script-footer">
          <span class="footprint-chip">${footprintText}</span>
          <button class="btn-toggle-script ${s.is_running ? "stop-btn" : "start-btn"}">
            ${s.is_running ? "Stop" : "Play"}
          </button>
        </div>
      `;

      const toggleBtn = tile.querySelector(".btn-toggle-script");
      toggleBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          if (s.is_running) {
            await API.post(`/api/scripts/${s.id}/stop`);
          } else {
            await API.post(`/api/scripts/${s.id}/start`);
          }
          await loadScripts();
        } catch (err) {
          alert(`Script execution error: ${err.message}`);
        }
      });

      scriptGrid.appendChild(tile);
    });
  }

  // -------------------------------------------------------
  // Procedural Script Speed & Tap Tempo Management
  // -------------------------------------------------------
  let speedDebounceTimer = null;
  let tapTimes = [];

  function initSpeedAndTapTempo() {
    if (!scriptSpeedSlider) return;

    // Fetch initial speed
    API.get("/api/scripts/speed")
      .then((data) => {
        if (data && data.multiplier !== undefined) {
          const mult = parseFloat(data.multiplier);
          scriptSpeedSlider.value = mult;
          if (scriptSpeedPct) scriptSpeedPct.textContent = `${mult.toFixed(2)}x`;
          const bpm = Math.round(mult * 120);
          if (tapTempoBpm) tapTempoBpm.textContent = `${bpm} BPM`;
        }
      })
      .catch((err) => console.error("Could not fetch script speed:", err));

    scriptSpeedSlider.addEventListener("input", (e) => {
      const mult = parseFloat(e.target.value);
      if (scriptSpeedPct) scriptSpeedPct.textContent = `${mult.toFixed(2)}x`;
      const bpm = Math.round(mult * 120);
      if (tapTempoBpm) tapTempoBpm.textContent = `${bpm} BPM`;

      clearTimeout(speedDebounceTimer);
      speedDebounceTimer = setTimeout(async () => {
        try {
          await API.post("/api/scripts/speed", { multiplier: mult });
        } catch (err) {
          console.error("Failed to update speed:", err);
        }
      }, 50);
    });

    if (btnTapTempo) {
      btnTapTempo.addEventListener("click", async () => {
        const now = performance.now();
        if (tapTimes.length > 0 && now - tapTimes[tapTimes.length - 1] > 2500) {
          tapTimes = [];
        }
        tapTimes.push(now);
        if (tapTimes.length > 6) tapTimes.shift();

        // Visual bounce animation
        btnTapTempo.classList.add("tapped");
        setTimeout(() => btnTapTempo.classList.remove("tapped"), 120);

        if (tapTimes.length >= 2) {
          const intervals = [];
          for (let i = 1; i < tapTimes.length; i++) {
            intervals.push(tapTimes[i] - tapTimes[i - 1]);
          }
          const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
          const rawBpm = Math.round(60000 / avgInterval);
          const clampedBpm = Math.max(40, Math.min(240, rawBpm));
          const multiplier = Math.max(0.25, Math.min(4.0, Math.round((clampedBpm / 120.0) * 20) / 20));

          if (tapTempoBpm) tapTempoBpm.textContent = `${clampedBpm} BPM`;
          if (scriptSpeedSlider) scriptSpeedSlider.value = multiplier;
          if (scriptSpeedPct) scriptSpeedPct.textContent = `${multiplier.toFixed(2)}x`;

          try {
            await API.post("/api/scripts/speed", { multiplier });
          } catch (err) {
            console.error("Failed to sync tempo speed:", err);
          }
        }
      });
    }
  }

  // -------------------------------------------------------
  // Panic Controls
  // -------------------------------------------------------
  if (btnBlackout) {
    btnBlackout.addEventListener("click", async () => {
      try {
        await API.post("/api/panic/blackout");
        document.querySelectorAll(".preset-tile").forEach((t) => t.classList.remove("active-preset"));
        await loadScripts();
      } catch (err) {
        alert(`Blackout error: ${err.message}`);
      }
    });
  }

  if (btnKillEffects) {
    btnKillEffects.addEventListener("click", async () => {
      try {
        await API.post("/api/panic/kill_effects");
        await loadScripts();
      } catch (err) {
        alert(`Kill effects error: ${err.message}`);
      }
    });
  }

  // -------------------------------------------------------
  // Channel Partition Matrix (512 tiny blocks)
  // -------------------------------------------------------
  function buildPartitionMatrix() {
    if (!matrixStrip) return;
    matrixStrip.innerHTML = "";
    for (let i = 1; i <= 512; i++) {
      const block = document.createElement("div");
      block.className = "matrix-block";
      block.id = `mb-${i}`;
      block.title = `DMX Ch ${i}`;
      matrixStrip.appendChild(block);
    }
  }

  // Update Matrix on WebSocket Frame Update
  window.addEventListener("universe-update", (e) => {
    const data = e.detail;
    if (!data || !data.channels || !data.ownership) return;

    for (let i = 0; i < 512; i++) {
      const el = document.getElementById(`mb-${i + 1}`);
      if (!el) continue;

      const owner = data.ownership[i];
      const level = data.channels[i];

      el.className = "matrix-block";
      if (owner && owner.startsWith("Script:")) {
        el.classList.add("owner-script");
      } else if (owner && owner.startsWith("Preset:")) {
        el.classList.add("owner-preset");
      }

      if (level > 0) {
        el.classList.add("level-active");
      }
    }
  });

  // -------------------------------------------------------
  // AI Show Generator
  // -------------------------------------------------------
  if (btnOpenAiShow && modalAiShow) {
    btnOpenAiShow.addEventListener("click", () => {
      modalAiShow.classList.remove("hidden");
    });
  }

  if (btnSubmitAiShow) {
    btnSubmitAiShow.addEventListener("click", async () => {
      const prompt = aiShowPrompt ? aiShowPrompt.value.trim() : "";
      if (!prompt) {
        alert("Please enter a prompt describing your desired lighting effect.");
        return;
      }

      btnSubmitAiShow.disabled = true;
      btnSubmitAiShow.textContent = "Generating with Gemini 3.8 Flash...";

      try {
        const resp = await API.post("/api/ai/generate_show", { prompt });
        if (!resp.success) {
          alert(`AI generation failed: ${resp.error || "Unknown error"}`);
          return;
        }

        if (aiShowResult) aiShowResult.classList.remove("hidden");
        if (aiShowTitle) aiShowTitle.value = resp.name || "AI Routine";
        if (aiShowDesc) aiShowDesc.value = resp.description || prompt;
        if (aiShowFootprint) aiShowFootprint.value = JSON.stringify(resp.footprint_channels || []);
        if (aiShowCode) aiShowCode.value = resp.python_code || "";
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        btnSubmitAiShow.disabled = false;
        btnSubmitAiShow.textContent = "Generate Show Script";
      }
    });
  }

  if (btnSaveAiShow) {
    btnSaveAiShow.addEventListener("click", async () => {
      try {
        let footprint = [];
        try {
          footprint = JSON.parse(aiShowFootprint.value);
        } catch {
          footprint = [1, 2, 3, 4];
        }

        await API.post("/api/scripts", {
          name: aiShowTitle.value,
          description: aiShowDesc.value,
          footprint_channels: footprint,
          python_code: aiShowCode.value,
          created_by_ai: 1,
        });

        modalAiShow.classList.add("hidden");
        await loadScripts();
      } catch (err) {
        alert(`Save failed: ${err.message}`);
      }
    });
  }

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
