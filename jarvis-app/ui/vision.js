/* Jarvis — visão extra: gestos de mídia (fora do modo holograma) + leitura de QR.
   camera.js chama window.jarvisVision.tick(handsResult) a cada frame de vídeo.
   hologram.js chama window.jarvisVision.onControl(state) no poll.               */
window.jarvisVision = (() => {
  "use strict";

  const api = () => (window.pywebview && window.pywebview.api) || null;
  function dbg(m) { const a = api(); if (a && a.log) a.log("vision: " + m); }

  // ---------------- gestos de mídia ----------------
  const g = {
    trail: [],            // {x, t}
    fistN: 0, palmN: 0,
    lastAct: 0, lastVol: 0,
    hint: document.getElementById("cam-help"),
  };
  const now = () => performance.now();
  const COOL = 1100;

  function media(action, times) {
    const a = api();
    if (a && a.media) a.media(action, times || 1);
    g.lastAct = now();
    flash({ next: "⏭ próxima", prev: "⏮ anterior", play: "⏯ play/pause",
            vol_up: "🔊 +", vol_down: "🔉 −" }[action] || action);
  }
  let flashT = 0, flashMsg = "";
  function flash(msg) { flashMsg = msg; flashT = now(); }
  window.jarvisVision_flash = () => (now() - flashT < 900 ? flashMsg : "");

  function mediaGestures(hands) {
    if (!hands || !hands.length) { g.trail.length = 0; g.fistN = g.palmN = 0; return; }
    const h = hands[0];
    const lm = h.landmarks;
    const c = { x: (lm[0].x + lm[9].x) / 2, y: (lm[0].y + lm[9].y) / 2 };
    const name = h.gesture && h.gesture.name;

    // --- swipe: movimento horizontal rápido de palma/mão aberta ---
    g.trail.push({ x: c.x, y: c.y, t: now() });
    while (g.trail.length && now() - g.trail[0].t > 320) g.trail.shift();
    if (g.trail.length >= 3 && (name === "palma" || name === "mao")) {
      const dx = g.trail[g.trail.length - 1].x - g.trail[0].x;
      const dy = Math.abs(g.trail[g.trail.length - 1].y - g.trail[0].y);
      if (Math.abs(dx) > 0.33 && dy < 0.14 && now() - g.lastAct > COOL) {
        // vídeo espelhado: mão indo p/ a direita (dx>0) = "puxar" = próxima
        media(dx > 0 ? "next" : "prev");
        g.trail.length = 0;
      }
    }

    // --- punho fechado ~1s: play/pause ---
    if (name === "punho") {
      g.fistN++;
      if (g.fistN >= 30 && !g.fistFired && now() - g.lastAct > COOL) { media("play"); g.fistFired = true; }
    } else { g.fistN = 0; g.fistFired = false; }

    // --- palma parada + subir/descer: volume ---
    g.palmN = name === "palma" ? g.palmN + 1 : 0;
    if (g.palmN > 8 && now() - g.lastVol > 240) {
      const vy = c.y - (g._palmY == null ? c.y : g._palmY);
      if (Math.abs(vy) > 0.018) {
        media(vy < 0 ? "vol_up" : "vol_down");
        g.lastVol = now();
      }
    }
    g._palmY = c.y;
  }

  // ---------------- leitura de QR ----------------
  let detector = null, scanning = false, scanStop = 0;
  function initDetector() {
    if (detector || !("BarcodeDetector" in window)) return;
    try { detector = new window.BarcodeDetector({ formats: ["qr_code"] }); }
    catch (e) { dbg("BarcodeDetector: " + e.message); }
  }
  function startScan() {
    if (scanning) return;
    initDetector();
    scanning = true; scanStop = now() + 9000;
    flash("👁 procurando QR…");
    dbg("scan QR iniciado" + (detector ? "" : " (sem BarcodeDetector)"));
  }
  async function scanFrame(video) {
    if (!scanning) return;
    if (now() > scanStop) { scanning = false; flash("nenhum QR encontrado"); return; }
    if (!detector) return;
    try {
      const codes = await detector.detect(video);
      if (codes && codes.length && codes[0].rawValue) {
        scanning = false;
        const txt = codes[0].rawValue;
        flash("✓ " + txt.slice(0, 40));
        const a = api();
        if (a && a.scan_result) a.scan_result("qr", txt);
        dbg("QR: " + txt);
      }
    } catch (_) { /* frame não pronto */ }
  }

  // ---------------- presença (volta pro cérebro se ninguém aparece) ----------------
  let autoReturnS = 0, lastSeen = now(), _presence = null, _lastAvg = null;
  function presence(hands, video) {
    if (autoReturnS <= 0) return;
    if (hands && hands.length) { lastSeen = now(); return; }
    // proxy de "tem gente": variação de brilho no frame
    if (video && video.videoWidth) {
      if (!_presence) { _presence = document.createElement("canvas"); _presence.width = 32; _presence.height = 24; }
      const cx = _presence.getContext("2d");
      cx.drawImage(video, 0, 0, 32, 24);
      const d = cx.getImageData(0, 0, 32, 24).data;
      let sum = 0; for (let i = 0; i < d.length; i += 4) sum += d[i] + d[i + 1] + d[i + 2];
      const avg = sum / (32 * 24 * 3);
      if (_lastAvg != null && Math.abs(avg - _lastAvg) > 4) lastSeen = now();
      _lastAvg = avg;
    }
    if (now() - lastSeen > autoReturnS * 1000) {
      const a = api();
      if (a && a.set_view) a.set_view("brain");
      lastSeen = now();
      dbg("sem presença — voltando pro cérebro");
    }
  }

  // ---------------- API ----------------
  let mediaOn = true;
  return {
    tick(handsResult, video) {
      const hands = (handsResult && handsResult.hands) || [];
      const holoBusy = window.jarvisHolo &&
        (window.jarvisHolo.count() > 0 || (window.jarvisHolo.hasSelection && window.jarvisHolo.hasSelection()));
      if (mediaOn && !holoBusy) mediaGestures(hands);
      if (video) scanFrame(video);
      presence(hands, video);
    },
    onControl(s) {
      if (s && s.scan === "qr") startScan();
      if (s && typeof s.media_gestures === "boolean") mediaOn = s.media_gestures;
      if (s && typeof s.auto_return === "number") autoReturnS = s.auto_return;
    },
  };
})();
