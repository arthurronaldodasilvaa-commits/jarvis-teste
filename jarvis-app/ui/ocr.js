/* Jarvis — OCR (tesseract.js, tudo local). Lê texto da câmera ou de um print.
   Ativado por control.scan === "ocr". Devolve o texto via api.scan_result("ocr", txt). */
window.jarvisOcr = (() => {
  "use strict";
  const B = "lib/tess";
  let worker = null, loading = false, failed = false, busy = false, lastReq = "";

  const api = () => (window.pywebview && window.pywebview.api) || null;
  const dbg = (m) => { const a = api(); if (a && a.log) a.log("ocr: " + m); };
  const flash = (m) => { if (window.jarvisVision_setflash) window.jarvisVision_setflash(m); };

  async function ensureWorker() {
    if (worker || failed) return worker;
    if (loading) { while (loading) await new Promise((r) => setTimeout(r, 100)); return worker; }
    if (typeof Tesseract === "undefined") { failed = true; dbg("tesseract.js não carregou"); return null; }
    loading = true;
    try {
      worker = await Tesseract.createWorker("por", 1, {
        workerPath: B + "/worker.min.js",
        corePath: B + "/tesseract-core-simd.wasm.js",
        langPath: B,
        gzip: true,
        cacheMethod: "none",
      });
      dbg("worker pronto");
    } catch (e) { failed = true; dbg("falha: " + (e && e.message)); }
    finally { loading = false; }
    return worker;
  }

  async function run(source, rotulo) {
    if (busy) return;
    busy = true;
    flash("👁 lendo o texto…");
    try {
      const w = await ensureWorker();
      if (!w) { report("", "erro"); return; }
      const { data } = await w.recognize(source);
      let txt = (data && data.text || "").replace(/\s*\n\s*/g, "\n").replace(/[ \t]{2,}/g, " ").trim();
      if (txt.length < 2) { report("", "vazio"); return; }
      report(txt, rotulo || "câmera");
    } catch (e) {
      dbg("recognize erro: " + (e && e.message));
      report("", "erro");
    } finally { busy = false; }
  }

  function report(txt, rotulo) {
    const a = api();
    if (a && a.scan_result) a.scan_result("ocr", txt);
    flash(txt ? "✓ " + txt.slice(0, 40) : ("ocr: " + rotulo));
  }

  return {
    async fromVideo(video) { if (video && video.videoWidth) await run(video, "câmera"); },
    onControl(s) {
      if (s && s.scan === "ocr" && s.scan !== lastReq) {
        lastReq = "ocr";
        ensureWorker();
        const v = document.getElementById("cam");
        // dá 1 frame pra câmera estabilizar
        setTimeout(() => { if (v && v.videoWidth) run(v, "câmera"); }, 350);
      } else if (!s || s.scan !== "ocr") { lastReq = ""; }
    },
    // usado por "lê o texto do print": app manda um dataURL
    async fromDataURL(url) { await run(url, "imagem"); },
    _state: () => ({ ready: !!worker, failed, busy }),
  };
})();
