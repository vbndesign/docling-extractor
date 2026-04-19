/* Docling Extractor — app.js
 * Frontend-spec §5.1 (health check), §5.7 (dropzone), §5.11 (copy path), §9 (a11y).
 * Loaded with `defer`; HTMX script is loaded synchronously earlier in <head>. */

(function () {
  "use strict";

  // §5.7 — Dropzone: click, drag&drop → populate hidden input → trigger HTMX submit.
  function wireDropzone() {
    var dz = document.getElementById("pdf-dropzone");
    if (!dz) return;
    var input = dz.querySelector('input[type="file"]');
    if (!input) return;

    // Click/keyboard delegation opens the native file picker.
    dz.addEventListener("click", function (e) {
      if (e.target === input) return;
      input.click();
    });
    dz.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        input.click();
      }
    });

    dz.addEventListener("dragover", function (e) {
      e.preventDefault();
      dz.classList.add("is-dragging");
    });
    dz.addEventListener("dragleave", function () {
      dz.classList.remove("is-dragging");
    });
    dz.addEventListener("drop", function (e) {
      e.preventDefault();
      dz.classList.remove("is-dragging");
      var files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length > 0) {
        input.files = files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    // Auto-submit when a file is chosen (either by drop or by browse dialog).
    input.addEventListener("change", function () {
      if (input.files && input.files.length > 0 && window.htmx) {
        window.htmx.trigger(dz, "submit");
      }
    });
  }

  // §5.11 — Copy-to-clipboard with ephemeral "Copied!" feedback.
  function wireCopyButtons() {
    document.body.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-copy]");
      if (!btn) return;
      var text = btn.getAttribute("data-copy");
      if (!text || !navigator.clipboard) return;
      var original = btn.textContent;
      navigator.clipboard
        .writeText(text)
        .then(function () {
          btn.textContent = "Copied!";
        })
        .catch(function () {
          btn.textContent = "Copy failed";
        })
        .finally(function () {
          setTimeout(function () {
            btn.textContent = original;
          }, 1500);
        });
    });
  }

  // §5.1 — One-shot health check (no polling, arch §7.3 rationale).
  function setHealth(variant, label) {
    var dot = document.querySelector("[data-health-dot]");
    var text = document.querySelector("[data-health-label]");
    if (dot) {
      dot.classList.remove("status-dot--success", "status-dot--error");
      dot.classList.add("status-dot--" + variant);
    }
    if (text) text.textContent = label;
  }

  async function pingHealth() {
    try {
      var res = await fetch("/health", { cache: "no-store" });
      if (res.ok) setHealth("success", "SERVICE_ACTIVE");
      else setHealth("error", "SERVICE_DEGRADED");
    } catch (_) {
      setHealth("error", "SERVICE_DOWN");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireDropzone();
    wireCopyButtons();
    pingHealth();
  });
})();
