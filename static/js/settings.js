/**
 * Tab 3: Settings & Real-Time Universe Diagnostics Script.
 */

document.addEventListener("DOMContentLoaded", () => {
  const geminiKeyInput = document.getElementById("setting-gemini-key");
  const btnToggleKey = document.getElementById("btn-toggle-key-vis");
  const geminiModelSelect = document.getElementById("setting-gemini-model");
  const btnSaveGemini = document.getElementById("btn-save-gemini");

  const driverSelect = document.getElementById("setting-driver");
  const serialPortInput = document.getElementById("setting-serial-port");
  const fpsSlider = document.getElementById("setting-fps");
  const fpsLabel = document.getElementById("fps-label");
  const btnSaveHardware = document.getElementById("btn-save-hardware");
  const btnResetDb = document.getElementById("btn-reset-db");

  const universeGrid = document.getElementById("universe-channels-grid");
  const statNonZero = document.getElementById("stat-nonzero");
  const statLocked = document.getElementById("stat-locked");

  // Build Universe 512-Cell Grid
  buildUniverseGrid();

  // Load Settings
  loadSettings();

  async function loadSettings() {
    try {
      const data = await API.get("/api/settings");
      const s = data.settings || {};

      if (geminiKeyInput && s.has_gemini_key) {
        geminiKeyInput.placeholder = `Configured (${s.gemini_api_key_masked})`;
      }
      if (geminiModelSelect && s.gemini_model) {
        geminiModelSelect.value = s.gemini_model;
      }
      if (driverSelect && s.driver) {
        driverSelect.value = s.driver;
      }
      if (serialPortInput && s.serial_port) {
        serialPortInput.value = s.serial_port;
      }
      if (fpsSlider && s.fps) {
        fpsSlider.value = s.fps;
        if (fpsLabel) fpsLabel.textContent = s.fps;
      }
    } catch (e) {
      console.warn("Failed to load settings", e);
    }
  }

  // Toggle API Key Visibility
  if (btnToggleKey && geminiKeyInput) {
    btnToggleKey.addEventListener("click", () => {
      const isPwd = geminiKeyInput.type === "password";
      geminiKeyInput.type = isPwd ? "text" : "password";
      btnToggleKey.textContent = isPwd ? "Hide" : "Show";
    });
  }

  // Save Gemini Settings
  if (btnSaveGemini) {
    btnSaveGemini.addEventListener("click", async () => {
      const keyVal = geminiKeyInput.value.trim();
      const payload = {
        gemini_model: geminiModelSelect.value,
      };
      if (keyVal) {
        payload.gemini_api_key = keyVal;
      }
      try {
        await API.post("/api/settings", payload);
        alert("Gemini settings saved successfully.");
        await loadSettings();
      } catch (err) {
        alert(`Failed to save Gemini settings: ${err.message}`);
      }
    });
  }

  // FPS Slider live label
  if (fpsSlider && fpsLabel) {
    fpsSlider.addEventListener("input", () => {
      fpsLabel.textContent = fpsSlider.value;
    });
  }

  // Save Hardware Settings
  if (btnSaveHardware) {
    btnSaveHardware.addEventListener("click", async () => {
      const payload = {
        driver: driverSelect.value,
        serial_port: serialPortInput.value.trim(),
        fps: parseInt(fpsSlider.value, 10),
      };
      try {
        await API.post("/api/settings", payload);
        alert("Hardware configuration applied.");
        await loadSettings();
      } catch (err) {
        alert(`Failed to update hardware: ${err.message}`);
      }
    });
  }

  // Reset Factory Defaults
  if (btnResetDb) {
    btnResetDb.addEventListener("click", async () => {
      if (confirm("Reset database to factory defaults? All custom presets and fixtures will be reset.")) {
        try {
          await API.post("/api/settings/reset");
          alert("Database reset to factory defaults.");
          window.location.reload();
        } catch (err) {
          alert(`Reset failed: ${err.message}`);
        }
      }
    });
  }

  // -------------------------------------------------------
  // Real-Time 512-Channel Universe Grid
  // -------------------------------------------------------
  function buildUniverseGrid() {
    if (!universeGrid) return;
    universeGrid.innerHTML = "";
    for (let i = 1; i <= 512; i++) {
      const cell = document.createElement("div");
      cell.className = "channel-cell";
      cell.id = `dmx-cell-${i}`;
      cell.innerHTML = `
        <span class="channel-cell-num">${i}</span>
        <div class="channel-fill" style="height: 0%;"></div>
        <span class="channel-cell-val">0</span>
      `;
      universeGrid.appendChild(cell);
    }
  }

  window.addEventListener("universe-update", (e) => {
    const data = e.detail;
    if (!data || !data.channels) return;

    if (statNonZero) statNonZero.textContent = data.non_zero_count;
    if (statLocked) statLocked.textContent = data.locked_count;

    // Update level bars
    for (let i = 0; i < 512; i++) {
      const cell = document.getElementById(`dmx-cell-${i + 1}`);
      if (!cell) continue;

      const val = data.channels[i];
      const owner = data.ownership ? data.ownership[i] : null;
      const fillEl = cell.querySelector(".channel-fill");
      const valEl = cell.querySelector(".channel-cell-val");

      if (valEl) valEl.textContent = val;
      if (fillEl) {
        const pct = Math.round((val / 255.0) * 100);
        fillEl.style.height = `${pct}%`;
      }

      cell.className = "channel-cell";
      if (owner && owner.startsWith("Script:")) {
        cell.classList.add("owned-script");
      } else if (owner && owner.startsWith("Preset:")) {
        cell.classList.add("owned-preset");
      }
    }
  });
});
