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

  // Build Partition Matrix Grid (512 blocks)
  buildPartitionMatrix();

  // Load Initial Data
  loadPresets();
  loadScripts();

  // -------------------------------------------------------
  // Presets Management
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
          await API.post(`/api/presets/${p.id}/trigger`);
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
