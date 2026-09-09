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
    resize();
    prev = null;
    loop();
  }

  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    video.srcObject = null;
    prev = null;
    fxctx.clearRect(0, 0, fx.width, fx.height);
    if (motionBar) motionBar.style.transform = "scaleX(0)";
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
