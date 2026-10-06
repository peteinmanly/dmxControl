/**
 * Central API Client and Global State / WebSocket Manager.
 */

const API = {
  async get(url) {
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return res.json();
  },

  async post(url, body = {}) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return res.json();
  },

  async put(url, body = {}) {
    const res = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return res.json();
  },

  async delete(url) {
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    return res.json();
  },
};

// Tab Navigation
document.addEventListener("DOMContentLoaded", () => {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTabId = btn.getAttribute("data-tab");
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPane = document.getElementById(targetTabId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Modal Closers
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-close");
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add("hidden");
    });
  });

  // Close modal when clicking outside
  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.add("hidden");
      }
    });
  });

  // Initialize WebSocket for 30-40 Hz Universe Diagnostics
  initUniverseWebSocket();
});

let universeSocket = null;
function initUniverseWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/universe`;

  try {
    universeSocket = new WebSocket(wsUrl);

    universeSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        window.dispatchEvent(new CustomEvent("universe-update", { detail: data }));

        if (data.hw_status) {
          updateHeaderHardwareStatus(data.hw_status);
        }
      } catch (e) {
        console.error("Error parsing universe frame", e);
      }
    };

    universeSocket.onclose = () => {
      setTimeout(initUniverseWebSocket, 2000);
    };

    universeSocket.onerror = () => {
      if (universeSocket) universeSocket.close();
    };
  } catch (e) {
    console.warn("WebSocket init error", e);
  }
}

function updateHeaderHardwareStatus(hw) {
  const nameEl = document.getElementById("hw-driver-name");
  const fpsEl = document.getElementById("hw-fps");
  const badgeEl = document.getElementById("hw-status-badge");
  const dot = badgeEl ? badgeEl.querySelector(".indicator-dot") : null;

  if (nameEl && fpsEl) {
    const isVirtual = hw.driver_mode === "virtual";
    nameEl.textContent = isVirtual ? "Virtual DMX" : "Enttec Open DMX";
    fpsEl.textContent = `${hw.actual_fps.toFixed(1)} FPS`;

    if (dot) {
      const isConnected = hw.driver_diagnostics && hw.driver_diagnostics.connected;
      dot.className = "indicator-dot " + (isConnected ? "dot-green" : isVirtual ? "dot-yellow" : "dot-red");
    }
  }
}
