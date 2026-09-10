/* Jarvis — reconhecimento facial (face-api.js, tudo local).
   camera.js chama window.jarvisFace.tick(video) por frame; a checagem pesada
   roda no máx. a cada ~1,4 s. hologram.js passa o control em onControl(state).

   - reconhece quem está na câmera -> api.face_seen(nome | "desconhecido" | "")
   - "aprende meu rosto": daemon manda control.face_enroll=<nome>; captura ~6
     descritores e chama api.face_save(nome, descritores)
*/
window.jarvisFace = (() => {
  "use strict";

  const P = "lib/face-api";
  let ready = false, loading = false, failed = false;
  let enrolled = [];                 // [{name, descriptors:[Float32Array]}]
  let lastCheck = 0;
  let current = null, stableFrames = 0, reported = null;
  let enrollTag = "", enrollName = "", enrollGrab = [];

  const api = () => (window.pywebview && window.pywebview.api) || null;
  const dbg = (m) => { const a = api(); if (a && a.log) a.log("face: " + m); };

  async function ensureLoaded() {
    if (ready || loading || failed) return;
    if (typeof faceapi === "undefined") { failed = true; dbg("face-api.js não carregou"); return; }
    loading = true;
    try {
      await faceapi.nets.tinyFaceDetector.loadFromUri(P);
      await faceapi.nets.faceLandmark68Net.loadFromUri(P);
      await faceapi.nets.faceRecognitionNet.loadFromUri(P);
      const a = api();
      const db = a && a.face_db ? await a.face_db() : {};
      enrolled = Object.entries(db || {}).map(([name, descs]) => ({
        name,
        descriptors: (descs || []).map((d) => new Float32Array(d)),
      }));
      ready = true;
      dbg("pronto — " + enrolled.length + " rosto(s) conhecido(s)");
    } catch (e) {
      failed = true; dbg("falha ao carregar: " + (e && e.message));
    } finally { loading = false; }
  }

  const OPT = () => new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 });
  const THRESH = 0.52;              // distância euclidiana máx. p/ ser "a mesma pessoa"

  function identify(descriptor) {
    let who = "desconhecido", best = THRESH;
    for (const e of enrolled) {
      for (const d of e.descriptors) {
        const dist = faceapi.euclideanDistance(descriptor, d);
        if (dist < best) { best = dist; who = e.name; }
      }
    }
    return who;
  }

  async function tick(video) {
    if (failed || !video || !video.videoWidth) return;
    if (!ready) { ensureLoaded(); return; }
    const now = performance.now();
    if (now - lastCheck < (enrollName ? 450 : 1400)) return;
    lastCheck = now;

    let det;
    try {
      det = await faceapi.detectSingleFace(video, OPT())
        .withFaceLandmarks().withFaceDescriptor();
    } catch (e) { return; }

    // ---- enrollment em andamento ----
    if (enrollName) {
      if (det) {
        enrollGrab.push(Array.from(det.descriptor));
        dbg("capturei " + enrollGrab.length + "/6 pro " + enrollName);
        if (enrollGrab.length >= 6) {
          const a = api();
          if (a && a.face_save) {
            await a.face_save(enrollName, enrollGrab);
            enrolled = enrolled.filter((e) => e.name !== enrollName);
            enrolled.push({ name: enrollName, descriptors: enrollGrab.map((d) => new Float32Array(d)) });
          }
          enrollName = ""; enrollGrab = [];
          if (a && a.face_seen) a.face_seen("__enrolled__");
        }
      }
      return;
    }

    // ---- reconhecimento normal ----
    const who = det ? identify(det.descriptor) : "";
    if (who === current) { stableFrames++; } else { current = who; stableFrames = 1; }
    // só avisa o daemon depois de 2 checagens seguidas iguais (evita flicker)
    if (stableFrames === 2 && who !== reported) {
      reported = who;
      const a = api();
      if (a && a.face_seen) a.face_seen(who);
    }
  }

  return {
    tick,
    reset() {                    // câmera fechou: some com o "quem está aí"
      current = null; reported = null; stableFrames = 0;
      enrollName = ""; enrollGrab = [];
      const a = api();
      if (a && a.face_seen) a.face_seen("");
    },
    onControl(s) {
      if (s && s.face_enroll && s.face_enroll !== enrollTag) {
        enrollTag = s.face_enroll;
        enrollName = String(s.face_enroll).split("|")[0].toLowerCase().slice(0, 30);
        enrollGrab = [];
        ensureLoaded();
        dbg("modo cadastro: " + enrollName);
      }
    },
    known: () => enrolled.map((e) => e.name),
    _state: () => ({ ready, failed, current: reported, enrolling: enrollName }),
  };
})();
