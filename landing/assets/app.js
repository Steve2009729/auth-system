"use strict";

/* ── Toast ───────────────────────────────────────────────────────────────── */
const toast = document.getElementById("toast");
let toastTimer;

function showToast(msg, ms = 2000) {
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), ms);
}

/* ── Clipboard ───────────────────────────────────────────────────────────── */
function copyText(text, btn) {
  const write = () => {
    if (btn) {
      const prev = btn.innerHTML;
      btn.innerHTML =
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg> Copied!';
      btn.classList.add("copied");
      setTimeout(() => { btn.innerHTML = prev; btn.classList.remove("copied"); }, 2000);
    }
    showToast("Copied to clipboard");
  };

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(write).catch(() => fallback(text, write));
  } else {
    fallback(text, write);
  }
}

function fallback(text, cb) {
  const ta = document.createElement("textarea");
  ta.value = text;
  Object.assign(ta.style, { position: "fixed", top: "-9999px", left: "-9999px" });
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand("copy"); cb(); } catch (_) { /* silent */ }
  document.body.removeChild(ta);
}

document.querySelectorAll(".copy-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const targetId = btn.dataset.copyTarget;
    const rawText  = btn.dataset.copyText;
    if (targetId) {
      const el = document.getElementById(targetId);
      if (el) copyText(el.innerText.trim(), btn);
    } else if (rawText) {
      copyText(rawText, btn);
    }
  });
});

/* ── API code tabs ───────────────────────────────────────────────────────── */
const apiCopyBtn = document.getElementById("api-copy-btn");

document.querySelectorAll("[data-group='api']").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;

    // Update tab button states
    document.querySelectorAll("[data-group='api']").forEach(b => {
      b.classList.remove("active-tab");
      b.setAttribute("aria-selected", "false");
    });
    btn.classList.add("active-tab");
    btn.setAttribute("aria-selected", "true");

    // Swap panels
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
    const panel = document.getElementById(`api-panel-${tab}`);
    if (panel) panel.classList.remove("hidden");

    // Keep copy button in sync
    if (apiCopyBtn) apiCopyBtn.dataset.copyTarget = `api-code-${tab}`;
  });
});
