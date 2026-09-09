/* Jarvis — rastreamento de mão (MediaPipe Hands, local) com IDENTIDADE ESTÁVEL.
   Cada mão ganha um id e o mantém entre frames (casando pelo pulso).
   O desenho fica no camera.js. */
window.jarvisHands = (() => {
  "use strict";

  let hands = null, running = false, ready = false, busy = false, errStreak = 0;
  let tracked = [];        // [{id, lm, handed, score, lastSeen, role, gesture}]
  let nextId = 1;
  let latest = { hands: [], t: 0 };

  function dbg(m) {
    const a = window.pywebview && window.pywebview.api;
    if (a && a.log) a.log("hands: " + m);
  }

  function process(res) {
    const mh = res.multiHandedness || [];
    const raw = (res.multiHandLandmarks || [])
      .map((lm, i) => ({ lm, handed: mh[i] ? mh[i].label : "?", score: mh[i] ? mh[i].score : 1 }))
      .filter((h) => h.lm && h.lm.length === 21 && h.lm[0] && typeof h.lm[0].x === "number");

    const now = performance.now();
    const used = new Set();
    for (const d of raw) {
      let best = null, bd = 0.20;
      for (const tk of tracked) {
        if (used.has(tk.id)) continue;
        const dist = Math.hypot(d.lm[0].x - tk.lm[0].x, d.lm[0].y - tk.lm[0].y);
        if (dist < bd) { bd = dist; best = tk; }
      }
      if (best) {
        best.lm = d.lm; best.handed = d.handed; best.score = d.score; best.lastSeen = now;
        used.add(best.id);
      } else {
        tracked.push({ id: nextId++, lm: d.lm, handed: d.handed, score: d.score,
          lastSeen: now, role: null, gesture: null });
        used.add(tracked[tracked.length - 1].id);
      }
    }
    // some quem não aparece há > 220 ms
    tracked = tracked.filter((tk) => now - tk.lastSeen < 220);
    // 2 rastreados quase no mesmo pulso -> mão fantasma: fica com a mais confiante
    if (tracked.length === 2) {
      const dist = Math.hypot(tracked[0].lm[0].x - tracked[1].lm[0].x,
                              tracked[0].lm[0].y - tracked[1].lm[0].y);
      if (dist < 0.11) tracked = [tracked[0].score >= tracked[1].score ? tracked[0] : tracked[1]];
    }
    tracked.forEach((tk) => {
      tk.gesture = window.jarvisGestures ? window.jarvisGestures.classify(tk.lm) : null;
    });
    // ordena por id (estável) — a de menor id fica na posição 0
    tracked.sort((a, b) => a.id - b.id);
    latest = {
      hands: tracked.map((tk) => ({
        id: tk.id, landmarks: tk.lm, handed: tk.handed, gesture: tk.gesture,
        get role() { return tk.role; }, set role(v) { tk.role = v; },
      })),
      t: now,
    };
  }

  async function ensure() {
    if (hands) return hands;
    if (typeof Hands === "undefined") { dbg("lib Hands não carregou"); return null; }
    hands = new Hands({ locateFile: (f) => "lib/mp_hands/" + f });
    hands.setOptions({
      maxNumHands: 2, modelComplexity: 0,
      minDetectionConfidence: 0.75, minTrackingConfidence: 0.6, selfieMode: false,
    });
    let _logAt = 0;
    hands.onResults((res) => {
      try {
        process(res);
        errStreak = 0;
        const now = performance.now();
        if (now - _logAt > 5000) { _logAt = now; dbg("rastreando " + tracked.length + " mão(s)"); }
      } catch (e) {
        dbg("onResults erro: " + (e && e.message));
      }
      busy = false;
    });
    try { await hands.initialize(); ready = true; dbg("inicializado"); }
    catch (e) { dbg("initialize falhou: " + e.message); }
    return hands;
  }

  async function start() { running = true; tracked = []; errStreak = 0; await ensure(); }
  function stop() { running = false; busy = false; tracked = []; latest = { hands: [], t: 0 }; }

  async function feed(video) {
    if (!running || !ready || busy || errStreak > 6) return;
    if (!video || !video.videoWidth) return;
    busy = true;
    try {
      await hands.send({ image: video });
    } catch (e) {
      busy = false;
      errStreak++;
      if (errStreak === 1) dbg("send erro: " + (e && e.message));
      if (errStreak === 7) { dbg("muitos erros — pausando 2s"); setTimeout(() => { errStreak = 0; }, 2000); }
    }
  }

  return {
    start, stop, feed,
    results: () => latest,
    isReady: () => ready,
    CONNECTIONS: () => (typeof HAND_CONNECTIONS !== "undefined" ? HAND_CONNECTIONS : []),
  };
})();
