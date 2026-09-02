import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Sparkles, Volume2, VolumeX, RotateCcw, Check, Printer, Home, Loader2, Film } from "lucide-react";
import { toast } from "sonner";
import { api, fileUrl } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { paramsToCss } from "@/lib/filters";
import { beep, shutter, chime } from "@/lib/audio";
import { attachLutRenderer, loadStripImage } from "@/lib/webglLut";
import { Button } from "@/components/ui/button";

const STEPS = ["idle", "template", "filter", "countdown", "review", "processing", "delivery"];

export default function Kiosk() {
  const { t, lang, setLang } = useLang();
  const [bundle, setBundle] = useState(null);
  const [step, setStep] = useState("idle");
  const [template, setTemplate] = useState(null);
  const [preset, setPreset] = useState(null);
  const [session, setSession] = useState(null);
  const [shotIndex, setShotIndex] = useState(0);
  const [count, setCount] = useState(0);
  const [flash, setFlash] = useState(false);
  const [photos, setPhotos] = useState([]);
  const [finalized, setFinalized] = useState(null);
  const [muted, setMuted] = useState(false);
  const [copies, setCopies] = useState(1);
  const [pinOpen, setPinOpen] = useState(false);
  const [pin, setPin] = useState("");
  const [triple, setTriple] = useState([]);
  const [boomerang, setBoomerang] = useState(null); // {gif_path, mp4_path} | "capturing"
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const lutCanvasRef = useRef(null);
  const lutControllerRef = useRef(null);
  const idleTimer = useRef(null);

  // Load active event bundle
  useEffect(() => {
    api.get("/events/active").then(r => {
      setBundle(r.data);
      setMuted(!!r.data.event?.mute);
    }).catch(() => {});
  }, []);

  // Start webcam whenever we enter template/filter/countdown/review
  useEffect(() => {
    const need = ["filter", "countdown", "review"].includes(step);
    if (need && !streamRef.current) {
      navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, facingMode: "user" }, audio: false })
        .then(s => { streamRef.current = s; if (videoRef.current) videoRef.current.srcObject = s; })
        .catch(() => toast.error(t("camera_denied")));
    }
    if (step === "idle" && streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  }, [step, t]);

  // Attach WebGL LUT renderer when the picked preset has a .cube attached.
  useEffect(() => {
    // Tear down previous renderer whenever preset changes
    if (lutControllerRef.current) {
      lutControllerRef.current.stop();
      lutControllerRef.current = null;
    }
    if (!preset?.lut_path || !videoRef.current || !lutCanvasRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        const img = await loadStripImage(`${process.env.REACT_APP_BACKEND_URL}/api/presets/${preset.id}/lut.png`);
        if (cancelled) return;
        const size = preset.lut_size || 17;
        const ctl = attachLutRenderer(lutCanvasRef.current, videoRef.current, img, size);
        if (ctl) { ctl.setMirror(true); lutControllerRef.current = ctl; }
      } catch (e) {
        console.warn("LUT attach failed", e);
      }
    })();
    return () => { cancelled = true; };
  }, [preset]);

  // Reset idle timer on any interaction
  const resetIdle = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    if (step !== "idle") {
      const to = (bundle?.event?.idle_timeout || 60) * 1000;
      idleTimer.current = setTimeout(() => goIdle(), to);
    }
  }, [step, bundle]);

  useEffect(() => {
    resetIdle();
    return () => idleTimer.current && clearTimeout(idleTimer.current);
  }, [resetIdle]);

  function goIdle() {
    setStep("idle"); setTemplate(null); setPreset(null); setSession(null);
    setShotIndex(0); setPhotos([]); setFinalized(null); setCopies(1);
    setBoomerang(null);
  }

  // Triple-tap hidden admin gesture
  function onCornerTap() {
    const now = Date.now();
    const arr = [...triple, now].filter(t => now - t < 1500);
    setTriple(arr);
    if (arr.length >= 3) { setPinOpen(true); setTriple([]); }
  }

  async function submitPin() {
    try {
      await api.post("/auth/verify-pin", { pin });
      window.location.href = "/admin/login";
    } catch { toast.error("Wrong PIN"); }
    setPin("");
  }

  // Start a session after picking a template
  async function beginSession(tpl, prs) {
    try {
      const r = await api.post("/sessions/start", {
        event_id: bundle.event.id, template_id: tpl.id, preset_id: prs.id,
      });
      setSession(r.data); setShotIndex(0); setPhotos([]);
      setStep("countdown");
      runCountdown(0);
    } catch (e) { toast.error("Could not start session"); }
  }

  // Countdown then capture, for shot index n
  function runCountdown(n) {
    let c = 5;
    setCount(c);
    const iv = setInterval(() => {
      c -= 1;
      if (c <= 0) {
        clearInterval(iv);
        setCount(0);
        setFlash(true);
        shutter(muted);
        setTimeout(() => setFlash(false), 350);
        captureShot(n);
      } else {
        setCount(c);
        beep(800, 90, muted);
      }
    }, 1000);
  }

  async function captureShot(n) {
    const v = videoRef.current;
    if (!v) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth || 1280;
    canvas.height = v.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    // Mirror horizontally (front camera preview)
    ctx.translate(canvas.width, 0); ctx.scale(-1, 1);
    ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    try {
      await api.post("/sessions/photo", {
        session_id: session.id, slot_index: n, image_base64: dataUrl,
      });
      setPhotos(prev => { const c = [...prev]; c[n] = dataUrl; return c; });
    } catch { toast.error("Upload failed"); }

    // brief hold, then next shot or review
    setTimeout(() => {
      const total = template?.photo_count || 1;
      if (n + 1 < total) {
        setShotIndex(n + 1);
        runCountdown(n + 1);
      } else if (template?.is_boomerang) {
        captureBoomerang();
      } else {
        setStep("review");
      }
    }, 1500);
  }

  // Boomerang burst: 12 frames at 10fps -> POST to backend for GIF+MP4 encoding
  async function captureBoomerang() {
    setStep("boomerang");
    setBoomerang("capturing");
    beep(1200, 60, muted);
    const v = videoRef.current;
    if (!v) { setStep("review"); return; }
    const frames = [];
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth || 1280;
    canvas.height = v.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    for (let i = 0; i < 12; i++) {
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.translate(canvas.width, 0); ctx.scale(-1, 1);
      ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
      ctx.restore();
      frames.push(canvas.toDataURL("image/jpeg", 0.82));
      // 100ms between frames = 10 fps burst
      await new Promise((r) => setTimeout(r, 100));
    }
    beep(400, 100, muted);
    try {
      const r = await api.post("/sessions/boomerang", {
        session_id: session.id, frames, fps: 10,
      });
      setBoomerang(r.data);
      chime(muted);
    } catch (e) {
      console.warn("boomerang encode failed", e);
      toast.error("Boomerang failed — keeping your prints");
      setBoomerang(null);
    }
    setStep("review");
  }

  async function retake(n) {
    setShotIndex(n); setStep("countdown"); runCountdown(n);
  }

  async function finalize() {
    setStep("processing");
    try {
      const r = await api.post(`/sessions/${session.id}/finalize`);
      setFinalized(r.data);
      chime(muted);
      setStep("delivery");
    } catch (e) {
      toast.error("Could not compose print — returning to idle");
      setTimeout(goIdle, 3000);
    }
  }

  async function printNow() {
    try {
      await api.post(`/print/${session.id}?copies=${copies}`);
      toast.success(`Sent ${copies} copy${copies > 1 ? "ies" : ""} to printer`);
    } catch { toast.error("Print queue error"); }
  }

  if (!bundle) {
    return (
      <div className="kiosk-bg no-scroll flex items-center justify-center text-slate-300">
        <Loader2 className="w-8 h-8 animate-spin mr-3" /> Loading…
      </div>
    );
  }

  const ev = bundle.event;
  const cssFilter = preset ? paramsToCss(preset.params) : "none";

  return (
    <div className="kiosk-bg no-scroll relative select-none" onPointerDown={resetIdle}>
      {/* Hidden admin corner */}
      <div data-testid="kiosk-hidden-admin-area"
           className="fixed top-0 left-0 w-20 h-20 z-50"
           onClick={onCornerTap} />

      {/* Mute toggle top-right */}
      <button data-testid="kiosk-mute-toggle"
        onClick={() => setMuted(m => !m)}
        className="fixed top-4 right-4 z-40 w-16 h-16 rounded-full bg-white/10 backdrop-blur border border-white/20 flex items-center justify-center hover:bg-white/20">
        {muted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
      </button>

      {/* Language toggle */}
      <button data-testid="kiosk-language-toggle"
        onClick={() => setLang(lang === "en" ? "id" : "en")}
        className="fixed top-4 right-24 z-40 h-16 px-5 rounded-full bg-white/10 backdrop-blur border border-white/20 font-mono text-sm uppercase tracking-wider">
        {lang.toUpperCase()} · {lang === "en" ? "ID" : "EN"}
      </button>

      {/* Flash overlay */}
      {flash && <div className="animate-flash fixed inset-0 bg-white z-[100] pointer-events-none" />}

      <AnimatePresence mode="wait">
        {step === "idle" && (
          <motion.div key="idle" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            className="w-full h-screen flex flex-col items-center justify-center px-8">
            <motion.div initial={{y:20,opacity:0}} animate={{y:0,opacity:1}} transition={{delay:0.1}}
              className="text-center">
              {ev.logo_url && <img src={ev.logo_url} className="h-24 mx-auto mb-8" alt="" />}
              <div className="text-xs font-mono uppercase tracking-[0.4em] text-slate-400 mb-4">SNAPBOOTH · {ev.date}</div>
              <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight mb-3" style={{color: ev.color || "#f43f5e"}}>{ev.headline}</h1>
              <p className="text-lg text-slate-300 mb-16">{ev.client}</p>
            </motion.div>
            <motion.button data-testid="kiosk-attract-start-button"
              onClick={() => setStep(bundle.templates.length === 1 ? "filter" : "template")}
              initial={{scale:0.9}} animate={{scale:1}}
              className="animate-pulse-glow px-16 py-8 rounded-full bg-gradient-to-r from-amber-400 via-rose-500 to-fuchsia-600 text-white text-3xl font-black tracking-wide hover:scale-105 active:scale-95 transition-transform">
              {t("tap_to_start")}
            </motion.button>
            <p className="mt-16 text-slate-500 font-mono text-xs">TAP · SNAP · PRINT</p>
          </motion.div>
        )}

        {step === "template" && (
          <motion.div key="template" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            className="w-full h-screen flex flex-col p-12">
            <h2 className="text-3xl font-bold mb-8">{t("choose_template")}</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 flex-1 overflow-auto">
              {bundle.templates.map(tpl => (
                <button key={tpl.id} data-testid="kiosk-template-option-card"
                  onClick={() => { setTemplate(tpl); setStep("filter"); if (bundle.presets[0]) setPreset(bundle.presets[0]); }}
                  className="group bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col items-center hover:border-rose-500 hover:scale-[1.02] active:scale-95 transition-transform">
                  <div className="w-40 h-52 bg-slate-800 rounded-xl mb-4 relative overflow-hidden" style={{background: tpl.background_color || "#111"}}>
                    {(tpl.photo_slots || []).slice(0, 4).map((s, i) => (
                      <div key={i} className="absolute bg-slate-600 rounded" style={{
                        left: `${(s.x / (tpl.canvas?.width_px || 1200)) * 100}%`,
                        top: `${(s.y / (tpl.canvas?.height_px || 1800)) * 100}%`,
                        width: `${(s.width / (tpl.canvas?.width_px || 1200)) * 100}%`,
                        height: `${(s.height / (tpl.canvas?.height_px || 1800)) * 100}%`,
                      }} />
                    ))}
                  </div>
                  <div className="text-center">
                    <div className="font-bold text-lg">{tpl.name}</div>
                    <div className="text-slate-400 text-sm font-mono">{tpl.paper?.size} · {tpl.photo_count} photos</div>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {step === "filter" && (
          <motion.div key="filter" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            className="w-full h-screen relative">
            <video ref={videoRef} data-testid="kiosk-camera-live-feed"
              autoPlay playsInline muted
              className="w-full h-full object-cover"
              style={{transform:"scaleX(-1)", filter: cssFilter, visibility: preset?.lut_path ? "hidden" : "visible"}} />
            {preset?.lut_path && (
              <canvas ref={lutCanvasRef} data-testid="kiosk-lut-canvas"
                className="absolute inset-0 w-full h-full object-cover pointer-events-none" />
            )}
            <div className="absolute top-8 left-0 right-0 text-center">
              <h2 className="text-3xl font-bold">{t("choose_filter")}</h2>
            </div>
            <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/80 to-transparent">
              <div className="flex gap-3 overflow-x-auto pb-4 mb-6">
                {bundle.presets.map(p => (
                  <button key={p.id} data-testid="kiosk-filter-option-button"
                    onClick={() => setPreset(p)}
                    className={`flex-shrink-0 rounded-2xl border-2 transition-all p-2 ${preset?.id === p.id ? "border-rose-500 shadow-[0_0_25px_rgba(244,63,94,0.4)]" : "border-white/10"}`}>
                    <div className="w-20 h-20 rounded-xl bg-cover bg-center"
                      style={{backgroundImage:"url(https://images.unsplash.com/photo-1727764894973-28e7283a600c?w=200)", filter: paramsToCss(p.params)}} />
                    <div className="text-xs mt-2 font-medium">{p.name}</div>
                  </button>
                ))}
              </div>
              <div className="flex justify-center gap-4">
                <Button variant="outline" onClick={() => setStep("template")} className="h-16 px-8 text-base">Back</Button>
                <Button data-testid="kiosk-filter-confirm-button"
                  onClick={() => template && preset && beginSession(template, preset)}
                  className="h-16 px-12 text-lg font-bold bg-rose-500 hover:bg-rose-600">
                  <Camera className="w-5 h-5 mr-2" /> Start
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {step === "countdown" && (
          <motion.div key="countdown" initial={{opacity:0}} animate={{opacity:1}}
            className="w-full h-screen relative">
            <video ref={videoRef} autoPlay playsInline muted
              className="w-full h-full object-cover"
              style={{transform:"scaleX(-1)", filter: cssFilter, visibility: preset?.lut_path ? "hidden" : "visible"}} />
            {preset?.lut_path && (
              <canvas ref={lutCanvasRef} data-testid="kiosk-lut-canvas-countdown"
                className="absolute inset-0 w-full h-full object-cover pointer-events-none" />
            )}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <AnimatePresence mode="wait">
                <motion.div key={count} initial={{scale:0.3, opacity:0}} animate={{scale:1, opacity:1}} exit={{scale:1.5, opacity:0}}
                  transition={{type:"spring", stiffness:180, damping:14}}
                  data-testid="kiosk-countdown-display"
                  className="text-[16rem] font-black leading-none text-white drop-shadow-[0_0_40px_rgba(0,0,0,0.5)]">
                  {count > 0 ? count : ""}
                </motion.div>
              </AnimatePresence>
            </div>
            <div className="absolute top-8 left-0 right-0 text-center">
              <div className="inline-block px-6 py-3 rounded-full bg-black/50 backdrop-blur text-2xl font-bold tracking-widest">
                {t("get_ready")} — {t("shot_of", {n: shotIndex + 1, t: template?.photo_count || 1})}
              </div>
            </div>
          </motion.div>
        )}

        {step === "boomerang" && (
          <motion.div key="boom" initial={{opacity:0}} animate={{opacity:1}}
            className="w-full h-screen relative">
            <video ref={videoRef} autoPlay playsInline muted
              className="w-full h-full object-cover" style={{transform:"scaleX(-1)", filter: cssFilter}} />
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40">
              <Film className="w-24 h-24 text-fuchsia-400 mb-6 animate-pulse" />
              <div data-testid="kiosk-boomerang-status" className="text-4xl font-black tracking-tight text-white">
                {boomerang === "capturing" ? "HOLD IT — BOOMERANG!" : "Rendering your loop…"}
              </div>
              <div className="mt-4 text-sm font-mono uppercase tracking-widest text-slate-300">
                12 frames · 10 fps · ping-pong
              </div>
            </div>
          </motion.div>
        )}

        {step === "review" && (
          <motion.div key="review" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            className="w-full h-screen flex flex-col p-8">
            <h2 className="text-3xl font-bold mb-6 text-center">Review Your Shots</h2>
            <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6 overflow-auto">
              {photos.map((p, i) => (
                <div key={i} className="relative group rounded-2xl overflow-hidden border-2 border-white/10">
                  <img src={p} alt="" className="w-full h-full object-cover" />
                  <button data-testid="kiosk-retake-button" onClick={() => retake(i)}
                    className="absolute inset-x-3 bottom-3 h-14 rounded-xl bg-amber-500/95 hover:bg-amber-500 flex items-center justify-center gap-2 font-bold text-black">
                    <RotateCcw className="w-5 h-5" /> {t("retake")} #{i+1}
                  </button>
                </div>
              ))}
              {boomerang && boomerang !== "capturing" && boomerang.gif_path && (
                <div data-testid="kiosk-boomerang-preview" className="relative rounded-2xl overflow-hidden border-2 border-fuchsia-500/60 bg-black">
                  <img src={fileUrl(boomerang.gif_path)} alt="Boomerang" className="w-full h-full object-cover" />
                  <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-fuchsia-500 text-white flex items-center gap-1">
                    <Film className="w-3 h-3" /> BOOMERANG
                  </span>
                </div>
              )}
            </div>
            <Button data-testid="kiosk-confirm-print-button" onClick={finalize}
              className="h-20 text-2xl font-black bg-emerald-500 hover:bg-emerald-600 shadow-[0_0_35px_rgba(16,185,129,0.5)]">
              <Check className="w-6 h-6 mr-3" /> {t("looks_good")}
            </Button>
          </motion.div>
        )}

        {step === "processing" && (
          <motion.div key="proc" initial={{opacity:0}} animate={{opacity:1}}
            className="w-full h-screen flex flex-col items-center justify-center">
            <Sparkles className="w-24 h-24 text-rose-500 mb-8 animate-pulse" />
            <div className="text-3xl font-bold mb-4">{t("processing")}</div>
            <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          </motion.div>
        )}

        {step === "delivery" && finalized && (
          <motion.div key="del" initial={{opacity:0}} animate={{opacity:1}}
            className="w-full h-screen flex flex-col lg:flex-row items-center justify-center gap-12 p-12">
            <div className="flex-1 max-w-md">
              <img src={fileUrl(finalized.print_path)} alt=""
                className="w-full rounded-2xl shadow-2xl border border-white/10" />
            </div>
            <div className="flex-1 max-w-md text-center">
              <img data-testid="kiosk-qr-code-image"
                src={`${process.env.REACT_APP_BACKEND_URL}/api/qr/${finalized.qr_token}.png`}
                alt="QR"
                className="w-64 h-64 mx-auto rounded-2xl bg-white p-4" />
              <div className="mt-4 text-lg text-slate-300">{t("scan_qr")}</div>
              <div className="mt-2 text-xs font-mono text-slate-500 break-all">{finalized.guest_url}</div>

              <div className="mt-8 flex items-center justify-center gap-3">
                <label className="text-sm text-slate-400">{t("copies")}:</label>
                {[1,2,3,4].slice(0, ev.max_copies || 4).map(n => (
                  <button key={n} onClick={() => setCopies(n)}
                    className={`w-12 h-12 rounded-full font-bold ${copies===n ? "bg-rose-500" : "bg-white/10"}`}>{n}</button>
                ))}
              </div>
              <div className="mt-6 flex gap-4 justify-center">
                <Button data-testid="kiosk-print-again-button" onClick={printNow}
                  className="h-16 px-8 bg-sky-500 hover:bg-sky-600">
                  <Printer className="w-5 h-5 mr-2" /> {t("print_again")}
                </Button>
                <Button data-testid="kiosk-done-button" onClick={goIdle}
                  className="h-16 px-8 bg-emerald-500 hover:bg-emerald-600">
                  <Home className="w-5 h-5 mr-2" /> {t("done")}
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* PIN Modal */}
      {pinOpen && (
        <div className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center">
          <div className="bg-slate-900 rounded-3xl p-8 border border-white/10 w-96">
            <h3 className="text-xl font-bold mb-4">{t("admin_pin")}</h3>
            <input data-testid="kiosk-pin-input" type="password" inputMode="numeric" autoFocus
              value={pin} onChange={e => setPin(e.target.value)}
              onKeyDown={e => e.key === "Enter" && submitPin()}
              className="w-full h-14 rounded-xl bg-white/5 border border-white/10 text-white text-2xl text-center tracking-widest" />
            <div className="mt-4 flex gap-3">
              <Button variant="outline" onClick={() => { setPinOpen(false); setPin(""); }} className="flex-1 h-12">{t("cancel")}</Button>
              <Button onClick={submitPin} className="flex-1 h-12 bg-rose-500 hover:bg-rose-600">{t("ok")}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
