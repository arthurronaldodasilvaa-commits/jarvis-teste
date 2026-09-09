/* Jarvis — classifica gestos a partir dos 21 pontos da mão (MediaPipe). */
window.jarvisGestures = (() => {
  "use strict";

  const D = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
  const mid = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: ((a.z || 0) + (b.z || 0)) / 2 });

  // dedo esticado = ponta mais longe do pulso que a junta do meio (PIP)
  function ext(lm, tip, pip) {
    return D(lm[tip], lm[0]) > D(lm[pip], lm[0]) * 1.06;
  }

  function classify(lm) {
    if (!lm || lm.length < 21) return { name: "?", pinch: 0 };

    const idx = ext(lm, 8, 6);
    const mdl = ext(lm, 12, 10);
    const rng = ext(lm, 16, 14);
    const pky = ext(lm, 20, 18);
    const thumbOut = D(lm[4], lm[17]) > D(lm[3], lm[17]) * 1.05;

    // pinça: ponta do polegar encosta na ponta do indicador
    const pd = D(lm[4], lm[8]);
    const pinch = pd < 0.055 ? 1 : (pd < 0.11 ? (0.11 - pd) / 0.055 : 0);
    const pinchAt = mid(lm[4], lm[8]);

    let name;
    if (pinch >= 1) name = "pinca";
    else if (!idx && !mdl && !rng && !pky) name = "punho";
    else if (idx && mdl && rng && pky) name = "palma";
    else if (idx && !mdl && !rng && !pky) name = "apontar";
    else if (idx && mdl && !rng && !pky) name = "paz";
    else name = "mao";

    return { name, pinch, pinchAt, fingers: { idx, mdl, rng, pky, thumbOut } };
  }

  const PT = { pinca: "PINÇA", punho: "PUNHO", palma: "PALMA", apontar: "APONTAR", paz: "PAZ", mao: "MÃO", "?": "" };
  const label = (n) => PT[n] || n.toUpperCase();

  return { classify, label };
})();
