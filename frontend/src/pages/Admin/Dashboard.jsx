import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Camera, Printer, Clock, Image as ImageIcon, Wifi } from "lucide-react";

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

  useEffect(() => {
    api.get("/stats").then(r => setStats(r.data));
    api.get("/hardware/status").then(r => setHw(r.data));
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
        <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-widest mb-3">
            <Camera className="w-4 h-4" /> Hardware
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-slate-400 text-xs">Camera</div><div>{hw?.camera_source || "…"}</div></div>
            <div><div className="text-slate-400 text-xs">Printer</div><div>{hw?.printer_driver || "…"}</div></div>
            <div><div className="text-slate-400 text-xs">Booth Bridge</div>
              <div className={hw?.bridge?.connected ? "text-emerald-400" : "text-amber-400"}>
                {hw?.bridge?.connected ? "Connected" : "Not detected — using webcam + mock"}
              </div>
            </div>
            <div><div className="text-slate-400 text-xs">Disk free</div><div>{hw?.storage_free_gb} GB</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}
