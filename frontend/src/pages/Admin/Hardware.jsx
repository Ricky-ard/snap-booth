import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Camera, Printer, HardDrive, Wifi, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

function Badge({ ok, children }) {
  return <span className={`px-2 py-1 rounded-full text-xs font-bold ${ok ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"}`}>{children}</span>;
}

export default function AdminHardware() {
  const [hw, setHw] = useState(null);
  const [queue, setQueue] = useState([]);
  const load = () => Promise.all([
    api.get("/hardware/status").then(r => setHw(r.data)),
    api.get("/print/queue").then(r => setQueue(r.data)).catch(() => {}),
  ]);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Diagnostics</div>
          <h1 className="text-3xl font-bold">Hardware</h1>
        </div>
        <Button onClick={load} variant="outline" className="border-slate-700"><RefreshCw className="w-4 h-4 mr-2" />Refresh</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card icon={Camera} title="Camera">
          <div className="flex items-center justify-between">
            <span data-testid="hardware-camera-status-badge">
              <Badge ok={hw?.camera_source === "bridge"}>{hw?.camera_source || "…"}</Badge>
            </span>
            <span className="font-mono text-xs text-slate-400">{hw?.bridge?.camera?.model || "browser webcam"}</span>
          </div>
        </Card>
        <Card icon={Printer} title="Printer">
          <div className="flex items-center justify-between">
            <span data-testid="hardware-printer-status-badge">
              <Badge ok={hw?.printer_driver === "bridge"}>{hw?.printer_driver || "…"}</Badge>
            </span>
            <span className="font-mono text-xs text-slate-400">{hw?.bridge?.printer?.name || "mock driver"}</span>
          </div>
          <div className="mt-3 text-sm text-slate-300">
            <div>State: <span className="font-mono">{hw?.bridge?.printer?.state || (hw?.printer_driver === "mock" ? "mock-ready" : "…")}</span></div>
            <div>Media remaining: <span className="font-mono">{hw?.bridge?.printer?.media_remaining ?? "n/a"}</span></div>
            <div data-testid="hardware-paper-gauge-bar" className="mt-2 h-2 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-rose-500 transition-all" style={{width: `${Math.min(100, (hw?.bridge?.printer?.media_remaining || 0) / 4)}%`}} />
            </div>
          </div>
        </Card>
        <Card icon={Wifi} title="Booth Bridge">
          <Badge ok={hw?.bridge?.connected}>{hw?.bridge?.connected ? "Connected" : "Not detected"}</Badge>
          <div className="mt-2 text-xs text-slate-400 font-mono">{hw?.bridge?.url}</div>
          {!hw?.bridge?.connected && (
            <div className="mt-3 text-xs text-slate-400">
              Run the bridge locally: <span className="font-mono">./booth-bridge/start.sh</span>
            </div>
          )}
          <div className="mt-3 text-sm">
            LAN IP: <span className="font-mono text-emerald-300">{hw?.lan_ip}</span>
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Guest QR resolves to <span className="font-mono">http://{hw?.lan_ip}:3000/g/…</span>
          </div>
        </Card>
        <Card icon={HardDrive} title="Storage">
          <div className="text-sm">
            {hw?.storage_free_gb} GB free of {hw?.storage_total_gb} GB
          </div>
        </Card>
      </div>

      <div className="mt-8">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500 mb-2">Print Queue</div>
        <div className="bg-[#161B22] border border-slate-800 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/50">
              <tr><th className="text-left p-3">Job</th><th className="text-left p-3">Driver</th><th className="text-left p-3">State</th><th className="text-left p-3">Copies</th><th className="text-left p-3">Created</th></tr>
            </thead>
            <tbody>
              {queue.length === 0 && <tr><td colSpan="5" className="p-6 text-center text-slate-500">No jobs yet</td></tr>}
              {queue.map(j => (
                <tr key={j.id} className="border-t border-slate-800">
                  <td className="p-3 font-mono text-xs">{j.id.slice(0,8)}</td>
                  <td className="p-3">{j.driver}</td>
                  <td className="p-3"><Badge ok={j.state === "done"}>{j.state}</Badge></td>
                  <td className="p-3">{j.copies}</td>
                  <td className="p-3 text-xs text-slate-400 font-mono">{new Date(j.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Card({ icon: Icon, title, children }) {
  return (
    <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-5">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-widest mb-3">
        <Icon className="w-4 h-4" /> {title}
      </div>
      {children}
    </div>
  );
}
