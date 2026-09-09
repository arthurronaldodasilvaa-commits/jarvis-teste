/* Jarvis — HUD do cérebro: relógio, clima, gauges de sistema, música, feed.
   O hologram.js chama window.jarvisHud.update(state) a cada poll. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id) || { textContent: "", style: {}, classList: { add() {}, remove() {} }, appendChild() {}, children: [], innerHTML: "" };
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

  // ---------- relógio (local, não depende do Python) ----------
  function clockTick() {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    $("clock").textContent = `${hh}:${mm}`;
    $("date").textContent = `${DIAS[d.getDay()]} ${d.getDate()} ${MESES[d.getMonth()]}`;
  }
  clockTick();
  setInterval(clockTick, 15000);

  // ---------- gauges ----------
  const gv = { cpu: 0, ram: 0, gpu: 0 };
  function setGauge(key, target) {
    gv[key] += (target - gv[key]) * 0.5;
    const v = Math.max(0, Math.min(100, gv[key]));
    const el = $("g-" + key);
    if (el) el.style.height = v + "%";
    const n = $("n-" + key);
    if (n) n.textContent = Math.round(v);
  }

  // ---------- música ----------
  let lastTrackKey = "";
  function renderTrack(tr) {
    const box = $("np");
    if (!tr || !tr.title) { box.classList.remove("on"); return; }
    box.classList.add("on");
    const key = tr.title + "|" + (tr.artist || "");
    if (key !== lastTrackKey) {
      $("np-t").textContent = tr.title;
      $("np-a").textContent = tr.artist || "";
      lastTrackKey = key;
    }
    const pct = tr.dur > 0 ? Math.min(100, (tr.pos / tr.dur) * 100) : 0;
    $("np-bar").style.width = pct + "%";
    box.style.opacity = tr.playing ? "0.9" : "0.4";
  }

  // ---------- feed de notificações ----------
  let feedSeen = 0;
  function renderFeed(notes) {
    if (!Array.isArray(notes)) return;
    const host = $("feed");
    // mostra as últimas 3
    const last = notes.slice(-3);
    if (notes.length === feedSeen && host.children.length === last.length) {
      // nada novo; só mantém
    }
    feedSeen = notes.length;
    host.innerHTML = "";
    last.forEach((n) => {
      const div = document.createElement("div");
      div.textContent = n.msg || "";
      if (n.kind) div.classList.add(n.kind);
      host.appendChild(div);
      requestAnimationFrame(() => div.classList.add("on"));
    });
  }

  // ---------- fase (pensando / pesquisando / erro) ----------
  const PHASE_TXT = {
    thinking: "PENSANDO", processing: "PROCESSANDO",
    searching: "PESQUISANDO", error: "ERRO",
  };
  function renderPhase(phase, statusEl, speaking, paused) {
    statusEl.classList.remove("thinking", "searching", "error");
    if (paused || speaking) return;
    if (phase && PHASE_TXT[phase]) {
      const cls = phase === "processing" ? "thinking" : (phase === "error" ? "error" : phase);
      statusEl.classList.add(cls === "thinking" || cls === "error" ? cls : "searching");
      statusEl.textContent = PHASE_TXT[phase];
    }
  }

  window.jarvisHud = {
    update(s) {
      if (!s) return;
      const sys = s.sys || {};
      setGauge("cpu", +sys.cpu || 0);
      setGauge("ram", +sys.ram || 0);
      setGauge("gpu", +sys.gpu || 0);
      if (typeof s.weather === "string") $("wx").textContent = s.weather;
      renderTrack(s.track);
      renderFeed(s.notes);
      const st = $("status");
      renderPhase(s.phase, st, !!s.speaking, !!s.paused);
    },
  };
})();
