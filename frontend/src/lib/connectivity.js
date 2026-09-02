import { useEffect, useState } from "react";

/** Track online/offline via the browser and a periodic backend health probe.
    The event laptop is usually online-on-LAN even when the internet is down,
    so we distinguish the two: `lan` = backend reachable, `cloud` = navigator.onLine.
*/
export function useConnectivity() {
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [lan, setLan] = useState(true);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    let alive = true;
    const probe = async () => {
      try {
        const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/`, { cache: "no-store" });
        if (alive) setLan(r.ok);
      } catch { if (alive) setLan(false); }
    };
    probe();
    const iv = setInterval(probe, 15000);
    return () => { alive = false; window.removeEventListener("online", on); window.removeEventListener("offline", off); clearInterval(iv); };
  }, []);

  return { online, lan };
}
