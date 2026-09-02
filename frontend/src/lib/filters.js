// Convert a backend filter params JSON into a CSS filter string.
// The visual math is deliberately close to the Pillow backend so preview ≈ print.
export function paramsToCss(p = {}) {
  const brightness = 1 + (p.brightness || 0) / 100 + (p.exposure || 0) / 100;
  const contrast = 1 + (p.contrast || 0) / 100;
  const saturate = Math.max(0, 1 + (p.saturation || 0) / 100);
  const hueRot = (p.tint || 0) * 0.4;
  const sepia = p.temperature > 20 && p.saturation <= -50 ? 0.6 : 0;
  const blur = Math.max(0, (p.skinSmooth || 0) / 60);
  return `brightness(${brightness.toFixed(2)}) contrast(${contrast.toFixed(2)}) saturate(${saturate.toFixed(2)}) hue-rotate(${hueRot.toFixed(1)}deg) sepia(${sepia.toFixed(2)}) blur(${blur.toFixed(1)}px)`;
}

// Optional overlay for grain/vignette that CSS filter can't do cleanly.
export function paramsToOverlayStyle(p = {}) {
  const vignette = (p.vignette || 0) / 100;
  const fade = (p.fade || 0) / 100;
  return {
    boxShadow: vignette > 0 ? `inset 0 0 ${120 * vignette}px ${60 * vignette}px rgba(0,0,0,${0.6 * vignette})` : "none",
    background: fade > 0 ? `rgba(255,255,255,${0.15 * fade})` : "transparent",
  };
}
