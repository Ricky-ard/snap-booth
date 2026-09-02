import { create } from "zustand";

/** Shared kiosk state — critically holds the ONE MediaStream for a whole session.
    The <video> element is mounted once in Kiosk.jsx and stays mounted from the
    filter picker through the last capture, so the live feed is visible behind
    every step of the flow (including the countdown overlay).
*/
export const useKiosk = create((set, get) => ({
  stream: null,
  error: null,
  _starting: null,

  /** Idempotent: returns the same stream on repeat calls; concurrent callers
      await the in-flight getUserMedia. Never call getUserMedia elsewhere. */
  async acquire() {
    const s = get().stream;
    if (s && s.getTracks().some((t) => t.readyState === "live")) return s;
    if (get()._starting) return get()._starting;

    const promise = navigator.mediaDevices
      .getUserMedia({ video: { width: 1280, height: 720, facingMode: "user" }, audio: false })
      .then((stream) => { set({ stream, _starting: null, error: null }); return stream; })
      .catch((err) => { set({ _starting: null, error: err }); throw err; });

    set({ _starting: promise });
    return promise;
  },

  /** Stop tracks + clear. Called only when returning to idle. */
  release() {
    const s = get().stream;
    if (s) {
      try { s.getTracks().forEach((t) => t.stop()); } catch {}
    }
    set({ stream: null, _starting: null });
  },
}));
