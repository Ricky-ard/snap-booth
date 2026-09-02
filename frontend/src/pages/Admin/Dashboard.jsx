import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Camera, Printer, Clock, Image as ImageIcon, Wifi, Cloud, CloudOff } from "lucide-react";

function Stat({ label, value, unit, icon: Icon, color = "rose" }) {
  return (
    <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-widest">
        <Icon className={`w-4 h-4 text-${color}-400`} /> {label}
      </div>
      <div className="mt-3 text-4xl font-black">{value}<span className="text-lg text-slate-400 ml-1">{unit}</span></div>
    </div>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [hw, setHw] = useState(null);
  const [sync, setSync] = useState(null);

  useEffect(() => {
    const load = () => {
      api.get("/stats").then(r => setStats(r.data));
      api.get("/hardware/status").then(r => setHw(r.data));
      api.get("/sync/status").then(r => setSync(r.data));
    };
    load();
    const iv = setInterval(load, 6000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="p-8">
      <div className="mb-8">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Command Center</div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat label="Sessions today" value={stats?.today_sessions ?? "—"} icon={ImageIcon} color="rose" />
        <Stat label="Prints today" value={stats?.prints_today ?? "—"} icon={Printer} color="sky" />
        <Stat label="Photos captured" value={stats?.photos_captured ?? "—"} icon={Camera} color="fuchsia" />
        <Stat label="Avg session" value={stats?.avg_session_seconds ?? "—"} unit="s" icon={Clock} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-widest mb-3">
            <Wifi className="w-4 h-4" /> Network
          </div>
          <div className="text-2xl font-mono">{hw?.lan_ip || "…"}</div>
          <div className="text-sm text-slate-400 mt-1">
            Guests scan a QR that points to <span className="font-mono">http://{hw?.lan_ip}:3000/g/…</span>
          </div>
        </div>

        <div data-testid="admin-cloud-sync-card" className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-widest mb-3">
            {sync?.online ? <Cloud className="w-4 h-4 text-emerald-400" /> : <CloudOff className="w-4 h-4 text-amber-400" />}
            Cloud Sync
          </div>
          <div className="flex items-center gap-3 text-sm mb-2">
            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${sync?.online ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"}`}>
              {sync?.online ? "Online" : "Offline"}
            </span>
            <span className="font-mono text-xs text-slate-400">driver: {sync?.driver || "—"}</span>
            <span className="font-mono text-xs text-slate-400">worker: {sync?.running ? "running" : "stopped"}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-slate-400 text-xs">Pending upload</div><div data-testid="admin-sync-pending" className="text-2xl font-black">{sync?.pending ?? "—"}</div></div>
            <div><div className="text-slate-400 text-xs">Synced total</div><div data-testid="admin-sync-synced" className="text-2xl font-black text-emerald-400">{sync?.synced ?? "—"}</div></div>
          </div>
          <div className="mt-3 text-xs font-mono text-slate-500">
            Last run: {sync?.stats?.last_run || "never"} · Last success: {sync?.stats?.last_success || "—"}
          </div>
          {!sync?.online && (
            <p className="mt-3 text-xs text-amber-300/80">
              Sessions queue locally and upload automatically when the internet comes back.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
