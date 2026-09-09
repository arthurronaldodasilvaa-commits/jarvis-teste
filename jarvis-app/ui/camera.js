/* Jarvis — visão da câmera + esqueleto da mão (sem detector de movimento).
   window.jarvisCam.start(hint) / .stop() / .configure() / .coverMap() */
window.jarvisCam = (() => {
  "use strict";

  const video = document.getElementById("cam");
  const fx = document.getElementById("cam-fx");
  const fxctx = fx.getContext("2d");
  const label = document.getElementById("cam-label");

  let stream = null, raf = 0;
  const opt = { skeleton: true };

  function configure(o) {
    if (o && typeof o.hand_skeleton === "boolean") opt.skeleton = o.hand_skeleton;
  }
  function dbg(m) {
    const a = window.pywebview && window.pywebview.api;
    if (a && a.log) a.log("cam: " + m);
  }

  function resize() { fx.width = innerWidth; fx.height = innerHeight; }
  addEventListener("resize", () => { if (stream) resize(); });

  async function pickDevice(hint) {
    try {
      const t = await navigator.mediaDevices.getUserMedia({ video: true });
      t.getTracks().forEach((x) => x.stop());
    } catch (e) { /* segue */ }
    const cams = (await navigator.mediaDevices.enumerateDevices())
      .filter((d) => d.kind === "videoinput");
    const h = (hint || "").toLowerCase();
    return cams.find((d) => d.label.toLowerCase().includes(h)) || cams[0] || null;
  }

  async function start(hint) {
    if (stream) return;
    label.textContent = "Conectando…";
    let dev;
    try {
      dev = await pickDevice(hint);
      dbg("device: " + (dev ? dev.label || "(sem label)" : "NENHUM"));
      stream = await navigator.mediaDevices.getUserMedia({
        video: dev
          ? { deviceId: { exact: dev.deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
          : { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (err) {
      label.textContent = "Câmera indisponível";
      dbg("ERRO getUserMedia: " + err.name + " - " + err.message);
      return;
    }
    video.srcObject = stream;
    try { await video.play(); } catch (e) { dbg("play(): " + e.message); }
    label.textContent = (dev && dev.label ? dev.label.replace(/\s*\(.*?\)\s*/g, "").trim() : "Câmera");
    dbg("stream OK " + video.videoWidth + "x" + video.videoHeight);
    if (window.jarvisHands) window.jarvisHands.start();
    resize();
    loop();
  }

  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
    if (window.jarvisHands) window.jarvisHands.stop();
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    video.srcObject = null;
    fxctx.clearRect(0, 0, fx.width, fx.height);
  }

  // ponto normalizado (0..1 do frame) -> pixel na tela (object-fit: cover)
  function coverMap(nx, ny) {
    const vW = video.videoWidth || 1280, vH = video.videoHeight || 720;
    const va = vW / vH, ca = fx.width / fx.height;
    let scale, offX = 0, offY = 0;
    if (va > ca) { scale = fx.height / vH; offX = (fx.width - vW * scale) / 2; }
    else { scale = fx.width / vW; offY = (fx.height - vH * scale) / 2; }
    return [nx * vW * scale + offX, ny * vH * scale + offY];
  }

  const TIPS = new Set([4, 8, 12, 16, 20]);

  // o canvas é espelhado (CSS scaleX -1) — pra texto sair legível, desenha invertido
  function mirrorText(txt, x, y) {
    fxctx.save();
    fxctx.translate(x, y);
    fxctx.scale(-1, 1);
    fxctx.fillText(txt, 0, 0);
    fxctx.restore();
  }

  function drawHands() {
    const r = window.jarvisHands && window.jarvisHands.results();
    if (!r || !r.hands.length) return;
    const conns = window.jarvisHands.CONNECTIONS();
    fxctx.globalCompositeOperation = "lighter";
    for (const h of r.hands) {
      const lm = h.landmarks;
      const sel = h.role === "selector";
      const col = sel ? "255,190,90" : "90,224,255";
      fxctx.lineWidth = 2.4;
      fxctx.strokeStyle = "rgba(" + col + ",0.85)";
      fxctx.shadowColor = "rgba(" + col + ",0.9)";
      fxctx.shadowBlur = 8;
      for (const [a, b] of conns) {
        const p = coverMap(lm[a].x, lm[a].y), q = coverMap(lm[b].x, lm[b].y);
        fxctx.beginPath(); fxctx.moveTo(p[0], p[1]); fxctx.lineTo(q[0], q[1]); fxctx.stroke();
      }
      for (let i = 0; i < lm.length; i++) {
        const [x, y] = coverMap(lm[i].x, lm[i].y);
        fxctx.beginPath();
        fxctx.fillStyle = "rgba(" + (TIPS.has(i) ? "200,245,255" : "120,230,255") + ",0.9)";
        fxctx.arc(x, y, TIPS.has(i) ? 6 : 3.2, 0, Math.PI * 2);
        fxctx.fill();
      }
      const g = h.gesture;
      if (g && g.name && g.name !== "?") {
        const [wx, wy] = coverMap(lm[0].x, lm[0].y);
        fxctx.shadowBlur = 6;
        fxctx.fillStyle = "rgba(" + col + ",0.95)";
        fxctx.font = "600 13px Segoe UI, monospace";
        fxctx.textAlign = "center";
        mirrorText(window.jarvisGestures.label(g.name), wx, wy + 32);
        if (g.pinch > 0.2 && g.pinchAt) {
          const [px, py] = coverMap(g.pinchAt.x, g.pinchAt.y);
          fxctx.strokeStyle = "rgba(200,245,255," + (0.35 + 0.5 * g.pinch) + ")";
          fxctx.lineWidth = 2;
          fxctx.beginPath();
          fxctx.arc(px, py, 13 + 9 * (1 - g.pinch), 0, Math.PI * 2);
          fxctx.stroke();
        }
      }
    }
    fxctx.shadowBlur = 0;
    fxctx.textAlign = "left";
    fxctx.globalCompositeOperation = "source-over";
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    if (!video.videoWidth) return;
    fxctx.clearRect(0, 0, fx.width, fx.height);
    try {
      if (window.jarvisHands) window.jarvisHands.feed(video);
      if (opt.skeleton) drawHands();
      if (window.jarvisVision) {
        window.jarvisVision.tick(window.jarvisHands && window.jarvisHands.results(), video);
        const fm = window.jarvisVision_flash && window.jarvisVision_flash();
        if (fm) {
          fxctx.save(); fxctx.font = "600 18px Segoe UI, monospace";
          fxctx.fillStyle = "rgba(124,228,255,0.95)"; fxctx.textAlign = "center";
          fxctx.shadowColor = "rgba(124,228,255,0.9)"; fxctx.shadowBlur = 10;
          mirrorText(fm, fx.width / 2, 64);
          fxctx.restore();
        }
      }
    } catch (e) { dbg("loop erro: " + (e && e.message)); }
  }

  return {
    start, stop, configure, coverMap,
    active: () => !!stream,
    videoAspect: () => (video.videoWidth ? video.videoWidth / video.videoHeight : 16 / 9),
  };
})();
