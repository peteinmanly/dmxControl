/**
 * Tab 2: Fixtures & Patch Management Script.
 * Handles Fixture CRUD, AI Documentation Lookup, and Interactive Channel Probing Wizard.
 */

document.addEventListener("DOMContentLoaded", () => {
  const fixtureList = document.getElementById("fixture-list");
  const btnAddManual = document.getElementById("btn-add-fixture-manual");
  const modalAdd = document.getElementById("modal-add-fixture");
  const btnSaveManual = document.getElementById("btn-save-manual-fixture");

  // Wizard Elements
  const btnOpenWizard = document.getElementById("btn-open-wizard-modal");
  const modalWizard = document.getElementById("modal-fixture-wizard");
  const tabProbe = document.getElementById("tab-wizard-probe");
  const tabDoc = document.getElementById("tab-wizard-doc");
  const paneProbe = document.getElementById("pane-wizard-probe");
  const paneDoc = document.getElementById("pane-wizard-doc");

  // Path B Probe Elements
  const probeSetupStep = document.getElementById("probe-setup-step");
  const probeActiveStep = document.getElementById("probe-active-step");
  const btnStartProbe = document.getElementById("btn-start-probe");
  const probeStepBadge = document.getElementById("probe-step-badge");
  const probeQuestionText = document.getElementById("probe-question-text");
  const probeActionText = document.getElementById("probe-action-text");
  const probeUserFeedback = document.getElementById("probe-user-feedback");
  const btnSubmitProbeStep = document.getElementById("btn-submit-probe-step");
  const btnFinalizeProbe = document.getElementById("btn-finalize-probe");

  // Path A Doc Elements
  const btnSubmitDoc = document.getElementById("btn-submit-doc-lookup");

  let activeProbeSessionId = null;

  // Load Fixtures
  loadFixtures();

  async function loadFixtures() {
    if (!fixtureList) return;
    try {
      const data = await API.get("/api/fixtures");
      renderFixtures(data.fixtures || []);
    } catch (e) {
      fixtureList.innerHTML = `<p class="error-text">Failed to load fixtures: ${e.message}</p>`;
    }
  }

  function renderFixtures(fixtures) {
    fixtureList.innerHTML = "";
    if (fixtures.length === 0) {
      fixtureList.innerHTML = "<p class='hint-text'>No fixtures patched in Universe 1.</p>";
      return;
    }

    fixtures.forEach((fix) => {
      const card = document.createElement("div");
      card.className = "fixture-card";

      const channelPills = (fix.channels || [])
        .map(
          (c) =>
            `<span class="ch-pill" title="${c.label}">Ch ${fix.start_channel + c.channel_offset}: ${c.channel_type}</span>`
        )
        .join("");

      card.innerHTML = `
        <div class="fixture-card-header">
          <div>
            <div class="fixture-name">${escapeHtml(fix.name)}</div>
            <div class="fixture-meta">${escapeHtml(fix.model || "Generic")} • Group: ${escapeHtml(fix.group_tag || "general")}</div>
          </div>
          <button class="btn btn-sm btn-ghost delete-fix-btn" title="Delete Fixture">🗑️</button>
        </div>
        <div style="font-size: 12px; margin-bottom: 8px;">
          <strong>Channels:</strong> ${fix.start_channel}..${fix.start_channel + fix.channel_count - 1} (${fix.channel_count} CH)
        </div>
        <div class="channel-map-pills">${channelPills}</div>
      `;

      card.querySelector(".delete-fix-btn").addEventListener("click", async () => {
        if (confirm(`Remove fixture '${fix.name}' from universe patch?`)) {
          await API.delete(`/api/fixtures/${fix.id}`);
          await loadFixtures();
        }
      });

      fixtureList.appendChild(card);
    });
  }

  // -------------------------------------------------------
  // Manual Fixture Creation
  // -------------------------------------------------------
  if (btnAddManual && modalAdd) {
    btnAddManual.addEventListener("click", () => modalAdd.classList.remove("hidden"));
  }

  if (btnSaveManual) {
    btnSaveManual.addEventListener("click", async () => {
      const name = document.getElementById("man-fix-name").value.trim();
      const start = parseInt(document.getElementById("man-fix-start").value, 10);
      const count = parseInt(document.getElementById("man-fix-count").value, 10);
      const group = document.getElementById("man-fix-group").value.trim();
      const typesRaw = document.getElementById("man-fix-channels").value.split(",");

      if (!name) {
        alert("Please enter a fixture name.");
        return;
      }

      const channels = typesRaw.map((t, idx) => ({
        channel_offset: idx,
        channel_type: t.trim() || "dimmer",
        label: `Ch ${idx + 1} (${t.trim()})`,
        default_value: 0,
      }));

      try {
        await API.post("/api/fixtures", {
          name,
          start_channel: start,
          channel_count: count,
          group_tag: group,
          channels,
        });
        modalAdd.classList.add("hidden");
        await loadFixtures();
      } catch (err) {
        alert(`Error saving fixture: ${err.message}`);
      }
    });
  }

  // -------------------------------------------------------
  // AI Wizard Navigation
  // -------------------------------------------------------
  if (btnOpenWizard && modalWizard) {
    btnOpenWizard.addEventListener("click", () => modalWizard.classList.remove("hidden"));
  }

  if (tabProbe && tabDoc) {
    tabProbe.addEventListener("click", () => {
      tabProbe.classList.add("active");
      tabDoc.classList.remove("active");
      paneProbe.classList.remove("hidden");
      paneDoc.classList.add("hidden");
    });
    tabDoc.addEventListener("click", () => {
      tabDoc.classList.add("active");
      tabProbe.classList.remove("active");
      paneDoc.classList.remove("hidden");
      paneProbe.classList.add("hidden");
    });
  }

  // -------------------------------------------------------
  // Path B: Interactive Probing Wizard
  // -------------------------------------------------------
  if (btnStartProbe) {
    btnStartProbe.addEventListener("click", async () => {
      const name = document.getElementById("probe-fix-name").value.trim();
      const start = parseInt(document.getElementById("probe-start-ch").value, 10);
      const count = parseInt(document.getElementById("probe-ch-count").value, 10);

      btnStartProbe.disabled = true;
      btnStartProbe.textContent = "Zeroing DMX channels & initializing probe...";

      try {
        const resp = await API.post("/api/ai/wizard/probe/start", {
          name,
          start_channel: start,
          channel_count: count,
        });

        activeProbeSessionId = resp.session_id;
        probeSetupStep.classList.add("hidden");
        probeActiveStep.classList.remove("hidden");

        renderProbeStep(resp.current_step);
      } catch (err) {
        alert(`Failed to start probe: ${err.message}`);
      } finally {
        btnStartProbe.disabled = false;
        btnStartProbe.textContent = "Begin Interactive Probing";
      }
    });
  }

  if (btnSubmitProbeStep) {
    btnSubmitProbeStep.addEventListener("click", async () => {
      const feedback = probeUserFeedback ? probeUserFeedback.value.trim() : "";
      if (!feedback) {
        alert("Please describe what reaction you observed on the light.");
        return;
      }

      btnSubmitProbeStep.disabled = true;
      btnSubmitProbeStep.textContent = "Processing observation...";

      try {
        const resp = await API.post("/api/ai/wizard/probe/step", {
          session_id: activeProbeSessionId,
          user_feedback: feedback,
        });

        if (probeUserFeedback) probeUserFeedback.value = "";

        if (resp.completed) {
          alert(resp.message || "Fixture successfully reverse-engineered and patched!");
          modalWizard.classList.add("hidden");
          resetProbeUI();
          await loadFixtures();
        } else {
          renderProbeStep(resp.current_step);
        }
      } catch (err) {
        alert(`Step failed: ${err.message}`);
      } finally {
        btnSubmitProbeStep.disabled = false;
        btnSubmitProbeStep.textContent = "Submit Observation";
      }
    });
  }

  if (btnFinalizeProbe) {
    btnFinalizeProbe.addEventListener("click", async () => {
      try {
        const resp = await API.post("/api/ai/wizard/probe/step", {
          session_id: activeProbeSessionId,
          user_feedback: "finalize",
        });
        alert(resp.message || "Fixture profile finalized!");
        modalWizard.classList.add("hidden");
        resetProbeUI();
        await loadFixtures();
      } catch (err) {
        alert(`Finalize failed: ${err.message}`);
      }
    });
  }

  function renderProbeStep(step) {
    if (!step) return;
    if (probeStepBadge) probeStepBadge.textContent = `Step ${step.step_index}`;
    if (probeQuestionText) probeQuestionText.textContent = step.question;
    if (probeActionText) probeActionText.textContent = step.action;
  }

  function resetProbeUI() {
    activeProbeSessionId = null;
    if (probeSetupStep) probeSetupStep.classList.remove("hidden");
    if (probeActiveStep) probeActiveStep.classList.add("hidden");
  }

  // -------------------------------------------------------
  // Path A: Documentation / Spec Lookup
  // -------------------------------------------------------
  if (btnSubmitDoc) {
    btnSubmitDoc.addEventListener("click", async () => {
      const name = document.getElementById("doc-fix-name").value.trim();
      const mfg = document.getElementById("doc-fix-mfg").value.trim();
      const start = parseInt(document.getElementById("doc-start-ch").value, 10);
      const spec = document.getElementById("doc-spec-text").value.trim();

      if (!spec) {
        alert("Please paste documentation or DMX manual text.");
        return;
      }

      btnSubmitDoc.disabled = true;
      btnSubmitDoc.textContent = "Gemini parsing DMX profile...";

      try {
        const resp = await API.post("/api/ai/wizard/doc_lookup", {
          name: name || "Generic Fixture",
          manufacturer: mfg || "Generic",
          start_channel: start,
          spec_text: spec,
        });

        if (!resp.success) {
          alert(`Lookup failed: ${resp.error}`);
          return;
        }

        alert(`Successfully parsed and patched fixture '${resp.profile.name}'!`);
        modalWizard.classList.add("hidden");
        await loadFixtures();
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        btnSubmitDoc.disabled = false;
        btnSubmitDoc.textContent = "Parse and Patch Fixture";
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
