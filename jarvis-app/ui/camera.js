/* Jarvis — visão da câmera + detecção de movimento.
   window.jarvisCam.start(hint) / .stop() / .active()
   Chamado pelo hologram.js quando state.view muda pra "camera". */
window.jarvisCam = (() => {
  "use strict";

  const video = document.getElementById("cam");
  const fx = document.getElementById("cam-fx");
  const fxctx = fx.getContext("2d");
  const label = document.getElementById("cam-label");
  const motionBar = document.getElementById("cam-motion");

  // canvas pequeno só pra fazer a conta do diff (rápido)
  const W = 128, H = 96;
  const small = document.createElement("canvas");
  small.width = W; small.height = H;
  const sctx = small.getContext("2d", { willReadFrequently: true });

  let stream = null, raf = 0, prev = null, motionLevel = 0;
  const opt = { overlay: true, fade: 0.10, sensitivity: 1.0 };

  function configure(o) {
    if (!o) return;
    if (typeof o.motion_overlay === "boolean") opt.overlay = o.motion_overlay;
    if (typeof o.motion_fade === "number") opt.fade = Math.max(0.02, Math.min(0.9, o.motion_fade));
    if (typeof o.motion_sensitivity === "number") opt.sensitivity = o.motion_sensitivity || 1;
  }

  function dbg(m) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.log) api.log("cam: " + m);
  }

  function resize() { fx.width = innerWidth; fx.height = innerHeight; }
  addEventListener("resize", () => { if (stream) resize(); });

  async function pickDevice(hint) {
    // precisa de 1 getUserMedia antes pra os labels aparecerem
    try {
      const t = await navigator.mediaDevices.getUserMedia({ video: true });
      t.getTracks().forEach((x) => x.stop());
    } catch (e) { /* segue */ }
    const cams = (await navigator.mediaDevices.enumerateDevices())
      .filter((d) => d.kind === "videoinput");
    const h = (hint || "").toLowerCase();
    const match = cams.find((d) => d.label.toLowerCase().includes(h));
    return match || cams[0] || null;
  }

  async function start(hint) {
    if (stream) return;
    label.textContent = "Conectando…";
    dbg("start hint=" + hint + " | mediaDevices=" + !!navigator.mediaDevices);
    let dev;
    try {
      dev = await pickDevice(hint);
      dbg("device escolhido: " + (dev ? dev.label || "(sem label)" : "NENHUM"));
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
    try { await video.play(); } catch (e) { dbg("play() falhou: " + e.message); }
    const name = (dev && dev.label) ? dev.label.replace(/\s*\(.*?\)\s*/g, "").trim() : "Câmera";
    label.textContent = name;
    dbg("stream OK, video " + video.videoWidth + "x" + video.videoHeight);
    if (window.jarvisHands) window.jarvisHands.start();
    resize();
    prev = null;
    loop();
  }

  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
    if (window.jarvisHands) window.jarvisHands.stop();
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    video.srcObject = null;
    prev = null;
    fxctx.clearRect(0, 0, fx.width, fx.height);
    if (motionBar) motionBar.style.transform = "scaleX(0)";
  }

  // mapeia ponto normalizado (0..1 do frame) -> pixel na tela (object-fit: cover)
  function coverMap(nx, ny) {
    const vW = video.videoWidth, vH = video.videoHeight;
    const va = vW / vH, ca = fx.width / fx.height;
    let scale, offX = 0, offY = 0;
    if (va > ca) { scale = fx.height / vH; offX = (fx.width - vW * scale) / 2; }
    else { scale = fx.width / vW; offY = (fx.height - vH * scale) / 2; }
    return [nx * vW * scale + offX, ny * vH * scale + offY];
  }

  const TIPS = new Set([4, 8, 12, 16, 20]);

  function drawHands() {
    const r = window.jarvisHands && window.jarvisHands.results();
    if (!r || !r.hands.length) return;
    const conns = window.jarvisHands.CONNECTIONS();
    fxctx.globalCompositeOperation = "lighter";
    for (const h of r.hands) {
      const lm = h.landmarks;
      // ossos
      fxctx.lineWidth = 2.5;
      fxctx.strokeStyle = "rgba(90,224,255,0.85)";
      fxctx.shadowColor = "rgba(90,224,255,0.9)";
      fxctx.shadowBlur = 8;
      for (const [a, b] of conns) {
        const p = coverMap(lm[a].x, lm[a].y), q = coverMap(lm[b].x, lm[b].y);
        fxctx.beginPath(); fxctx.moveTo(p[0], p[1]); fxctx.lineTo(q[0], q[1]); fxctx.stroke();
      }
      // juntas
      for (let i = 0; i < lm.length; i++) {
        const [x, y] = coverMap(lm[i].x, lm[i].y);
        const rad = TIPS.has(i) ? 6 : 3.2;
        fxctx.beginPath();
        fxctx.fillStyle = TIPS.has(i) ? "rgba(180,245,255,0.95)" : "rgba(120,230,255,0.8)";
        fxctx.arc(x, y, rad, 0, Math.PI * 2);
        fxctx.fill();
      }
    }
    fxctx.shadowBlur = 0;
    fxctx.globalCompositeOperation = "source-over";
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    if (!video.videoWidth) return;

    sctx.drawImage(video, 0, 0, W, H);
    const cur = sctx.getImageData(0, 0, W, H);

    // esmaece o rastro anterior (não apaga de vez -> o movimento "fica")
    fxctx.globalCompositeOperation = "destination-out";
    fxctx.fillStyle = "rgba(0,0,0," + opt.fade + ")";
    fxctx.fillRect(0, 0, fx.width, fx.height);

    let energy = 0;
    if (prev && opt.overlay) {
      const sx = fx.width / W, sy = fx.height / H;
      const cd = cur.data, pd = prev.data;
      const thr = 42 / opt.sensitivity;
      fxctx.globalCompositeOperation = "lighter";
      for (let y = 0; y < H; y += 2) {
        for (let x = 0; x < W; x += 2) {
          const i = (y * W + x) * 4;
          const diff =
            Math.abs(cd[i] - pd[i]) +
            Math.abs(cd[i + 1] - pd[i + 1]) +
            Math.abs(cd[i + 2] - pd[i + 2]);
          if (diff > thr) {
            energy += diff;
            const a = Math.min(0.6, (diff / 420) * opt.sensitivity);
            fxctx.fillStyle = "rgba(120,232,255," + a + ")";
            fxctx.fillRect(x * sx - sx * 1.5, y * sy - sy * 1.5, sx * 4, sy * 4);
          }
        }
      }
    } else if (prev) {
      // overlay desligado: ainda medimos o movimento pra barra
      const cd = cur.data, pd = prev.data;
      for (let i = 0; i < cd.length; i += 16) {
        energy += Math.abs(cd[i] - pd[i]);
      }
      energy *= 4;
    }
    fxctx.globalCompositeOperation = "source-over";
    prev = cur;

    // rastreamento de mão
    if (window.jarvisHands) {
      window.jarvisHands.feed(video);   // assíncrono, não bloqueia
      drawHands();
    }

    const lvl = Math.min(1, energy / 110000);
    motionLevel += (lvl - motionLevel) * 0.35;
    if (motionBar) motionBar.style.transform = "scaleX(" + motionLevel.toFixed(3) + ")";
  }

  return {
    start, stop, configure,
    active: () => !!stream,
    motion: () => motionLevel,
  };
})();
