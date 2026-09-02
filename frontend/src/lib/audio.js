let ctx;
function ac() { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); return ctx; }

export function beep(freq = 800, ms = 100, muted = false) {
  if (muted) return;
  try {
    const c = ac();
    const o = c.createOscillator();
    const g = c.createGain();
    o.frequency.value = freq;
    o.type = "sine";
    g.gain.setValueAtTime(0.18, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + ms / 1000);
    o.connect(g); g.connect(c.destination);
    o.start();
    o.stop(c.currentTime + ms / 1000);
  } catch {}
}

export function shutter(muted = false) {
  if (muted) return;
  try {
    const c = ac();
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = "square";
    o.frequency.setValueAtTime(1400, c.currentTime);
    o.frequency.exponentialRampToValueAtTime(80, c.currentTime + 0.12);
    g.gain.setValueAtTime(0.25, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.15);
    o.connect(g); g.connect(c.destination);
    o.start(); o.stop(c.currentTime + 0.16);
  } catch {}
}

export function chime(muted = false) {
  if (muted) return;
  try {
    const c = ac();
    [523, 659, 784].forEach((f, i) => {
      const o = c.createOscillator();
      const g = c.createGain();
      o.frequency.value = f;
      g.gain.setValueAtTime(0.001, c.currentTime + i * 0.08);
      g.gain.exponentialRampToValueAtTime(0.2, c.currentTime + i * 0.08 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + i * 0.08 + 0.35);
      o.connect(g); g.connect(c.destination);
      o.start(c.currentTime + i * 0.08);
      o.stop(c.currentTime + i * 0.08 + 0.4);
    });
  } catch {}
}
