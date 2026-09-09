/* Jarvis — rastreamento de mão (MediaPipe Hands, roda 100% local).
   handtrack.js só DETECTA e guarda os 21 pontos por mão.
   O desenho (esqueleto neon) fica no camera.js, que é dono do canvas. */
window.jarvisHands = (() => {
  "use strict";

  let hands = null, running = false, ready = false, busy = false;
  let latest = { hands: [], t: 0 };

  function dbg(m) {
    const a = window.pywebview && window.pywebview.api;
    if (a && a.log) a.log("hands: " + m);
  }

  async function ensure() {
    if (hands) return hands;
    if (typeof Hands === "undefined") { dbg("lib Hands não carregou"); return null; }
    hands = new Hands({ locateFile: (f) => "lib/mp_hands/" + f });
    hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 0,          // 0 = lite (rápido) · 1 = full (preciso)
      minDetectionConfidence: 0.7,
      minTrackingConfidence: 0.5,
      selfieMode: false,
    });
    let _logAt = 0;
    hands.onResults((res) => {
      const arr = res.multiHandLandmarks || [];
      let hs = arr.map((lm, i) => ({
        landmarks: lm,
        handed: (res.multiHandedness && res.multiHandedness[i]) ? res.multiHandedness[i].label : "?",
        score: (res.multiHandedness && res.multiHandedness[i]) ? res.multiHandedness[i].score : 1,
        gesture: window.jarvisGestures ? window.jarvisGestures.classify(lm) : null,
      }));
      // MediaPipe às vezes acha 2 mãos onde só tem 1 — junta as que têm o pulso
      // quase no mesmo lugar, mantendo a mais confiante.
      if (hs.length === 2) {
        const d = Math.hypot(hs[0].landmarks[0].x - hs[1].landmarks[0].x,
                             hs[0].landmarks[0].y - hs[1].landmarks[0].y);
        if (d < 0.13) hs = [hs[0].score >= hs[1].score ? hs[0] : hs[1]];
      }
      const now = performance.now();
      if (now - _logAt > 4000) { _logAt = now; dbg("rastreando " + hs.length + " mão(s)"); }
      latest = { hands: hs, t: now };
      busy = false;
    });
    try {
      await hands.initialize();
      ready = true;
      dbg("inicializado (modelo lite)");
    } catch (e) {
      dbg("initialize falhou: " + e.message);
    }
    return hands;
  }

  async function start() { running = true; await ensure(); }
  function stop() { running = false; busy = false; latest = { hands: [], t: 0 }; }

  async function feed(video) {
    if (!running || !ready || busy || !video || !video.videoWidth) return;
    busy = true;
    try {
      await hands.send({ image: video });
    } catch (e) {
      busy = false;
      dbg("send erro: " + e.message);
    }
  }

  return {
    start, stop, feed,
    results: () => latest,
    isReady: () => ready,
    CONNECTIONS: () => (typeof HAND_CONNECTIONS !== "undefined" ? HAND_CONNECTIONS : []),
  };
})();
