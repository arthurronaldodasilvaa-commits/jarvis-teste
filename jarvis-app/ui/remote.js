/* Jarvis — pareamento do celular. hologram.js chama window.jarvisRemote.onState(s). */
window.jarvisRemote = (() => {
  "use strict";
  const btn = document.getElementById("phone-btn");
  const panel = document.getElementById("pair");
  const qr = document.getElementById("pair-qr");
  const urlEl = document.getElementById("pair-url");
  let url = "", shown = false;

  function open() { if (url) panel.classList.add("on"); }
  function close() { panel.classList.remove("on"); }

  if (btn) btn.addEventListener("click", open);
  const cb = document.getElementById("pair-close");
  if (cb) cb.addEventListener("click", close);
  if (panel) panel.addEventListener("click", (e) => { if (e.target === panel) close(); });
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("on")) { e.stopImmediatePropagation(); close(); }
  }, true);

  return {
    onState(s) {
      if (!s || !s.remote_url) {
        if (btn) btn.hidden = true;
        return;
      }
      if (btn) btn.hidden = false;
      if (s.remote_url !== url) {
        url = s.remote_url;
        urlEl.textContent = url.replace(/\?k=.*$/, "");     // esconde o token no texto
        if (s.remote_qr) qr.src = s.remote_qr;
        if (!shown && !localStorage.getItem("jarvis-pair-seen")) {
          shown = true;
          setTimeout(() => { panel.classList.add("on"); }, 900);
          try { localStorage.setItem("jarvis-pair-seen", "1"); } catch (e) {}
        }
      }
    },
  };
})();
