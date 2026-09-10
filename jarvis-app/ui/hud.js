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

  // ---------- próximos lembretes ----------
  function renderRem(list) {
    const host = $("rem");
    if (!Array.isArray(list) || !list.length) { host.innerHTML = ""; return; }
    host.innerHTML = list.slice(0, 3).map((r) => {
      const t = (r.t || "").length > 22 ? r.t.slice(0, 21) + "…" : (r.t || "");
      return `<div>⏰ ${esc(t)}<span class="rw">${esc(r.w || "")}</span></div>`;
    }).join("");
  }
  function esc(s) { return String(s).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c])); }

  // ---------- modo estudo ----------
  let studyBase = null;   // {t0_ms, elapsed_at_update, limit}
  function renderStudy(st) {
    const box = $("study-box");
    if (!st || !st.active) { box.classList.remove("on"); studyBase = null; return; }
    box.classList.add("on");
    $("study-mode").textContent = st.name || "Estudo";
    // relógio anda suave no cliente entre os updates do Python
    if (!studyBase || studyBase.serverElapsed !== st.elapsed) {
      studyBase = { at: Date.now(), serverElapsed: st.elapsed || 0, limit: st.limit || 0 };
    }
    const localElapsed = studyBase.serverElapsed + (Date.now() - studyBase.at) / 1000;
    let secs, low = false;
    if (studyBase.limit > 0) { secs = Math.max(0, studyBase.limit - localElapsed); low = secs < 300; }
    else secs = localElapsed;
    const mm = String(Math.floor(secs / 60)).padStart(2, "0");
    const ss = String(Math.floor(secs % 60)).padStart(2, "0");
    $("study-time").textContent = `${mm}:${ss}`;
    $("study-time").classList.toggle("low", low);
    $("study-sub").textContent = st.subject || "";
    $("study-score").textContent = st.q ? `${st.hits}/${st.q} questões` : "";
  }

  // ---------- feed de notificações ----------
  //  notas somem sozinhas depois de ~11s; o DOM só muda quando o conjunto muda
  const FEED_TTL = 11000;
  let feedKey = "";
  function renderFeed(notes) {
    if (!Array.isArray(notes)) return;
    const host = $("feed");
    if (!host || !host.appendChild) return;
    const now = Date.now();
    const live = notes
      .filter((n) => n && n.t && (now - n.t * 1000) < FEED_TTL)
      .slice(-3);
    const key = live.map((n) => (n.t + ":" + n.msg)).join("|");
    if (key === feedKey) return;                 // nada mudou -> não mexe no DOM
    feedKey = key;
    host.innerHTML = "";
    live.forEach((n) => {
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
      renderStudy(s.study);
      renderRem(s.reminders);
      renderTrack(s.track);
      renderFeed(s.notes);
      const st = $("status");
      renderPhase(s.phase, st, !!s.speaking, !!s.paused);
    },
  };
})();
