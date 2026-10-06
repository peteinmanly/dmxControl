/**
 * AI Doctor Health Badge, Notification Banner, and Diagnostics Modal.
 */

document.addEventListener("DOMContentLoaded", () => {
  const healthBadge = document.getElementById("health-status-badge");
  const healthText = document.getElementById("health-status-text");
  const healthDot = healthBadge ? healthBadge.querySelector(".indicator-dot") : null;
  const banner = document.getElementById("health-banner");
  const bannerText = document.getElementById("health-banner-text");
  const btnOpenModal = document.getElementById("btn-open-doctor-modal");
  const btnDismissBanner = document.getElementById("btn-dismiss-banner");
  const modalDoctor = document.getElementById("modal-doctor");
  const doctorModalBody = document.getElementById("doctor-modal-body");
  const btnRerun = document.getElementById("btn-rerun-diagnostics");

  let latestDoctorData = null;

  async function checkHealthStatus() {
    try {
      const data = await API.get("/api/ai/doctor/status");
      latestDoctorData = data;
      renderHealthBadge(data);
    } catch (e) {
      console.warn("Could not fetch doctor status", e);
    }
  }

  function renderHealthBadge(data) {
    if (!healthText || !healthDot) return;

    healthText.textContent = data.status;

    if (data.status === "HEALTHY") {
      healthDot.className = "indicator-dot dot-green";
      if (banner) banner.classList.add("hidden");
    } else if (data.status === "DEGRADED") {
      healthDot.className = "indicator-dot dot-yellow";
      showBanner(data.issues[0] || "System running in degraded mode.");
    } else {
      healthDot.className = "indicator-dot dot-red";
      showBanner(data.issues[0] || "Critical hardware or system error detected.");
    }
  }

  function showBanner(msg) {
    if (banner && bannerText && !sessionStorage.getItem("banner_dismissed")) {
      bannerText.textContent = msg;
      banner.classList.remove("hidden");
    }
  }

  if (btnDismissBanner) {
    btnDismissBanner.addEventListener("click", () => {
      if (banner) banner.classList.add("hidden");
      sessionStorage.setItem("banner_dismissed", "true");
    });
  }

  function openDoctorModal() {
    if (!modalDoctor) return;
    modalDoctor.classList.remove("hidden");
    renderDoctorModal(latestDoctorData);
  }

  if (healthBadge) healthBadge.addEventListener("click", openDoctorModal);
  if (btnOpenModal) btnOpenModal.addEventListener("click", openDoctorModal);

  if (btnRerun) {
    btnRerun.addEventListener("click", async () => {
      if (doctorModalBody) {
        doctorModalBody.innerHTML = '<div class="loading-spinner">Re-running full system diagnostic scan...</div>';
      }
      try {
        const data = await API.post("/api/ai/doctor/diagnose");
        latestDoctorData = data;
        renderHealthBadge(data);
        renderDoctorModal(data);
      } catch (err) {
        if (doctorModalBody) {
          doctorModalBody.innerHTML = `<p class="error-text">Failed to run scan: ${err.message}</p>`;
        }
      }
    });
  }

  function renderDoctorModal(data) {
    if (!doctorModalBody) return;
    if (!data) {
      doctorModalBody.innerHTML = "<p>No diagnostic data available.</p>";
      return;
    }

    let html = `
      <div style="margin-bottom: 16px;">
        <strong>System Status:</strong> 
        <span class="badge ${data.status === 'HEALTHY' ? 'badge-running' : 'badge-stopped'}">${data.status}</span>
      </div>
    `;

    // Issues
    if (data.issues && data.issues.length > 0) {
      html += `
        <div style="margin-bottom: 14px;">
          <h4 style="color: var(--accent-red); margin-bottom: 6px;">Detected Issues:</h4>
          <ul style="padding-left: 20px; font-size: 13px; line-height: 1.6;">
            ${data.issues.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}
          </ul>
        </div>
      `;
    } else {
      html += `<p style="color: var(--accent-green); margin-bottom: 14px;">✓ No hardware, permission, or database faults detected.</p>`;
    }

    // Auto Actions Taken
    if (data.auto_actions_taken && data.auto_actions_taken.length > 0) {
      html += `
        <div style="margin-bottom: 14px;">
          <h4 style="color: var(--accent-cyan); margin-bottom: 6px;">Automated Fixes Applied:</h4>
          <ul style="padding-left: 20px; font-size: 13px; line-height: 1.6;">
            ${data.auto_actions_taken.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}
          </ul>
        </div>
      `;
    }

    // Recommended User Commands
    if (data.recommended_commands && data.recommended_commands.length > 0) {
      html += `
        <div style="margin-bottom: 14px;">
          <h4 style="color: var(--accent-yellow); margin-bottom: 6px;">Recommended Terminal Commands (Linux Mint):</h4>
          ${data.recommended_commands
            .map(
              (c) => `
            <div style="background: #080a0f; padding: 10px; border-radius: 4px; margin-bottom: 8px; font-family: monospace; font-size: 12px; display: flex; justify-content: space-between; align-items: center;">
              <code>${escapeHtml(c.command)}</code>
              <button class="btn btn-sm btn-ghost" onclick="navigator.clipboard.writeText('${escapeHtml(c.command).replace(/'/g, "\\'")}')">📋 Copy</button>
            </div>
            <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">${escapeHtml(c.explanation)}</p>
          `
            )
            .join("")}
        </div>
      `;
    }

    // AI Analysis
    if (data.ai_analysis && data.ai_analysis.diagnosis) {
      html += `
        <div class="solution-box" style="margin-top: 14px;">
          <div class="solution-title">Gemini AI Doctor Diagnosis:</div>
          <p style="font-size: 12px; line-height: 1.5; margin-bottom: 8px;">${escapeHtml(data.ai_analysis.diagnosis)}</p>
          ${data.ai_analysis.user_instructions ? `<p style="font-size: 12px; color: var(--text-muted);"><em>${escapeHtml(data.ai_analysis.user_instructions)}</em></p>` : ""}
        </div>
      `;
    }

    doctorModalBody.innerHTML = html;
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

  // Initial fetch and 10s poll
  checkHealthStatus();
  setInterval(checkHealthStatus, 10000);
});
