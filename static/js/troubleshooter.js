/**
 * Interactive AI Terminal Troubleshooter Script.
 * Generates safe diagnostic commands and parses terminal output.
 */

document.addEventListener("DOMContentLoaded", () => {
  const issueText = document.getElementById("troubleshoot-issue");
  const btnGenerate = document.getElementById("btn-generate-command");
  const cmdWrapper = document.getElementById("cmd-box-wrapper");
  const generatedCmd = document.getElementById("generated-command");
  const cmdExplanation = document.getElementById("command-explanation");
  const btnCopyCmd = document.getElementById("btn-copy-command");
  const terminalOutput = document.getElementById("terminal-output");
  const btnAnalyze = document.getElementById("btn-analyze-output");
  const solutionBox = document.getElementById("solution-box");
  const solutionDiag = document.getElementById("solution-diagnosis");
  const remediationList = document.getElementById("remediation-commands-list");
  const verificationStep = document.getElementById("verification-step");
  const pills = document.querySelectorAll(".recipe-pills .pill");

  let lastGeneratedCommand = "";

  // Quick Recipe Pills
  pills.forEach((pill) => {
    pill.addEventListener("click", async () => {
      const recipeKey = pill.getAttribute("data-recipe");
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");

      if (issueText) {
        issueText.value = pill.textContent.trim();
      }

      await requestCommand(recipeKey);
    });
  });

  // Generate Command Button
  if (btnGenerate) {
    btnGenerate.addEventListener("click", async () => {
      const text = issueText ? issueText.value.trim() : "";
      await requestCommand(null, text);
    });
  }

  async function requestCommand(recipeKey = null, customDescription = "") {
    if (cmdWrapper) cmdWrapper.classList.remove("hidden");
    if (generatedCmd) generatedCmd.textContent = "Formulating safe diagnostic command...";
    if (cmdExplanation) cmdExplanation.textContent = "";

    try {
      const resp = await API.post("/api/ai/troubleshoot/command", {
        recipe_key: recipeKey,
        issue_description: customDescription,
      });

      lastGeneratedCommand = resp.command;
      if (generatedCmd) generatedCmd.textContent = resp.command;
      if (cmdExplanation) cmdExplanation.textContent = resp.explanation;
    } catch (err) {
      if (generatedCmd) generatedCmd.textContent = "Error generating command: " + err.message;
    }
  }

  // Copy Command Button
  if (btnCopyCmd) {
    btnCopyCmd.addEventListener("click", () => {
      const cmd = generatedCmd ? generatedCmd.textContent : "";
      if (cmd) {
        navigator.clipboard.writeText(cmd).then(() => {
          const originalText = btnCopyCmd.textContent;
          btnCopyCmd.textContent = "✓ Copied!";
          setTimeout(() => {
            btnCopyCmd.textContent = originalText;
          }, 1500);
        });
      }
    });
  }

  // Analyze Terminal Output Button
  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", async () => {
      const output = terminalOutput ? terminalOutput.value.trim() : "";
      if (!output) {
        alert("Please paste the output from your terminal first.");
        return;
      }

      if (solutionBox) solutionBox.classList.remove("hidden");
      if (solutionDiag) solutionDiag.textContent = "Gemini AI is analyzing your terminal output...";
      if (remediationList) remediationList.innerHTML = "";
      if (verificationStep) verificationStep.innerHTML = "";

      try {
        const desc = issueText ? issueText.value.trim() : "";
        const resp = await API.post("/api/ai/troubleshoot/analyze", {
          issue_description: desc,
          command_run: lastGeneratedCommand,
          terminal_output: output,
        });

        renderSolution(resp);
      } catch (err) {
        if (solutionDiag) solutionDiag.textContent = "Failed to analyze output: " + err.message;
      }
    });
  }

  function renderSolution(resp) {
    if (!solutionBox || !solutionDiag) return;

    solutionDiag.textContent = resp.diagnosis || "Analysis complete.";

    if (remediationList) {
      remediationList.innerHTML = "";
      if (resp.remediation_commands && resp.remediation_commands.length > 0) {
        resp.remediation_commands.forEach((c) => {
          const item = document.createElement("div");
          item.className = "remediation-command-item";
          item.innerHTML = `
            <div>
              <code>${escapeHtml(c.command)}</code>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">${escapeHtml(c.explanation)}</div>
            </div>
            <button class="btn btn-sm btn-ghost" title="Copy">📋 Copy</button>
          `;
          item.querySelector("button").addEventListener("click", () => {
            navigator.clipboard.writeText(c.command);
          });
          remediationList.appendChild(item);
        });
      }
    }

    if (verificationStep) {
      if (resp.verification_command) {
        verificationStep.innerHTML = `
          <div style="font-size: 12px; margin-top: 10px; color: var(--accent-cyan);">
            <strong>Verification Step:</strong> Run <code>${escapeHtml(resp.verification_command)}</code> in your terminal to confirm the resolution.
          </div>
        `;
      } else {
        verificationStep.innerHTML = "";
      }
    }
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
