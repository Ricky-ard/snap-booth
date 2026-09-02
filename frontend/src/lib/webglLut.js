/* WebGL 3D LUT renderer for SnapBooth kiosk previews.

   Given a <video> element and a strip PNG URL from
   `/api/presets/{id}/lut.png` (N tall, N*N wide), this returns a controller
   that renders each frame into a <canvas>, sampling the LUT in a fragment
   shader using bilinear (r,g) + linear-blended blue slices — visually
   identical to the backend's trilinear print pipeline.

   Usage:
     const ctl = attachLutRenderer(canvasEl, videoEl, lutImgEl, lutSize);
     ctl.setLutSize(17);        // when swapping LUTs
     ctl.setMirror(true);       // horizontal mirror to match webcam preview
     ctl.stop();                // cleanup
*/

const VERT = `
attribute vec2 a_pos;
attribute vec2 a_uv;
varying vec2 v_uv;
uniform float u_mirror;
void main() {
  v_uv = vec2(mix(a_uv.x, 1.0 - a_uv.x, u_mirror), a_uv.y);
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FRAG = `
precision mediump float;
varying vec2 v_uv;
uniform sampler2D u_image;
uniform sampler2D u_lut;
uniform float u_lutSize;

vec3 applyLut(vec3 color) {
  float N = u_lutSize;
  // Blue slice index — do a linear blend of two neighbouring N x N blocks
  float bIdx = clamp(color.b, 0.0, 1.0) * (N - 1.0);
  float b0 = floor(bIdx);
  float b1 = min(b0 + 1.0, N - 1.0);
  float t  = bIdx - b0;

  // Strip is (N*N) wide, N tall.
  vec2 texSize = vec2(N * N, N);
  // half-pixel offsets so bilinear filter samples the correct texels
  float halfPx = 0.5 / texSize.x;
  float halfPy = 0.5 / texSize.y;

  // Within a block, r moves 0..N-1 across x, g moves 0..N-1 across y
  float rx0 = (b0 * N + color.r * (N - 1.0) + 0.5) / texSize.x;
  float rx1 = (b1 * N + color.r * (N - 1.0) + 0.5) / texSize.x;
  float gy  = (color.g * (N - 1.0) + 0.5) / texSize.y;

  vec3 s0 = texture2D(u_lut, vec2(rx0, gy)).rgb;
  vec3 s1 = texture2D(u_lut, vec2(rx1, gy)).rgb;
  return mix(s0, s1, t);
}

void main() {
  vec3 c = texture2D(u_image, v_uv).rgb;
  gl_FragColor = vec4(applyLut(c), 1.0);
}`;

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(s);
    gl.deleteShader(s);
    throw new Error(`shader compile: ${log}`);
  }
  return s;
}

export function attachLutRenderer(canvas, video, lutImage, lutSize = 17) {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, antialias: false });
  if (!gl) return null;

  const vs = compile(gl, gl.VERTEX_SHADER, VERT);
  const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
  const prog = gl.createProgram();
  gl.attachShader(prog, vs); gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`link: ${gl.getProgramInfoLog(prog)}`);
  }
  gl.useProgram(prog);

  // Fullscreen quad
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  // pos.x, pos.y, uv.x, uv.y  (uv.y flipped so texture is upright)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1, -1, 0, 1,
     1, -1, 1, 1,
    -1,  1, 0, 0,
    -1,  1, 0, 0,
     1, -1, 1, 1,
     1,  1, 1, 0,
  ]), gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(prog, "a_pos");
  const aUv  = gl.getAttribLocation(prog, "a_uv");
  gl.enableVertexAttribArray(aPos); gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 16, 0);
  gl.enableVertexAttribArray(aUv);  gl.vertexAttribPointer(aUv,  2, gl.FLOAT, false, 16, 8);

  const uImage   = gl.getUniformLocation(prog, "u_image");
  const uLut     = gl.getUniformLocation(prog, "u_lut");
  const uLutSize = gl.getUniformLocation(prog, "u_lutSize");
  const uMirror  = gl.getUniformLocation(prog, "u_mirror");

  // Video texture
  const texVideo = gl.createTexture();
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, texVideo);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

  // LUT strip texture
  const texLut = gl.createTexture();
  gl.activeTexture(gl.TEXTURE1);
  gl.bindTexture(gl.TEXTURE_2D, texLut);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

  function setLutImage(img, size) {
    lutSize = size || lutSize;
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, texLut);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
  }
  setLutImage(lutImage, lutSize);

  gl.uniform1i(uImage, 0);
  gl.uniform1i(uLut, 1);
  let mirror = 0;
  let running = true;

  function frame() {
    if (!running) return;
    if (video.readyState >= 2) {
      canvas.width  = video.videoWidth  || canvas.clientWidth  || 1280;
      canvas.height = video.videoHeight || canvas.clientHeight || 720;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texVideo);
      try {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, video);
      } catch (e) { /* video may be tainted mid-frame; skip */ }
      gl.uniform1f(uLutSize, lutSize);
      gl.uniform1f(uMirror, mirror);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    setLutImage,
    setLutSize: (n) => { lutSize = n; },
    setMirror: (m) => { mirror = m ? 1.0 : 0.0; },
    stop: () => { running = false; },
  };
}

/** Convenience: load a strip PNG then attach the renderer. */
export function loadStripImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}
