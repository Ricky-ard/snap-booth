import { useEffect, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Trash2, Printer, ExternalLink, Download, Cloud, CloudOff, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function AdminGallery() {
  const [sessions, setSessions] = useState([]);
  const [sel, setSel] = useState(null);
  const load = () => api.get("/sessions").then(r => setSessions(r.data));
  useEffect(() => { load(); const iv = setInterval(load, 8000); return () => clearInterval(iv); }, []);

  async function reprint(s) {
    await api.post(`/print/${s.id}?copies=1`); toast.success("Sent to print queue");
  }
  async function del(id) {
    if (!window.confirm("Delete session?")) return;
    await api.delete(`/sessions/${id}`); setSel(null); load();
  }
  async function retrySync(id) {
    await api.post(`/sync/${id}/retry`);
    toast.success("Queued for cloud sync");
    load();
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Gallery</div>
        <h1 className="text-3xl font-bold">Session History</h1>
      </div>
      {sessions.length === 0 && (
        <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
          No sessions yet. Try the kiosk!
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {sessions.map(s => (
          <button key={s.id} onClick={() => setSel(s)}
            data-testid="admin-gallery-session-card"
            className="rounded-xl overflow-hidden border border-slate-800 hover:border-rose-500 bg-[#161B22] relative">
            {s.web_path ? (
              <img src={fileUrl(s.web_path)} alt="" className="w-full aspect-[3/4] object-cover" />
            ) : (
              <div className="w-full aspect-[3/4] bg-slate-800 flex items-center justify-center text-slate-500 text-sm">In progress</div>
            )}
            <span data-testid="admin-gallery-sync-badge"
              className={`absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-mono uppercase tracking-widest flex items-center gap-1 ${
                s.synced_to_cloud ? "bg-emerald-500/85 text-white" : "bg-amber-500/85 text-black"
              }`} title={s.cloud_url || s.last_sync_error || "queued for upload"}>
              {s.synced_to_cloud ? <Cloud className="w-2.5 h-2.5" /> : <CloudOff className="w-2.5 h-2.5" />}
              {s.synced_to_cloud ? "synced" : "pending"}
            </span>
            <div className="p-2 text-xs">
              <div className="font-mono text-slate-400">{new Date(s.started_at).toLocaleString()}</div>
              <div className="text-slate-300">{s.copies_printed} print{s.copies_printed !== 1 ? "s" : ""}</div>
            </div>
          </button>
        ))}
      </div>

      {sel && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" onClick={() => setSel(null)}>
          <div className="bg-[#161B22] rounded-3xl border border-slate-800 max-w-3xl w-full p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="text-xs font-mono uppercase text-slate-500">Session</div>
                <div className="font-bold">{new Date(sel.started_at).toLocaleString()}</div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => reprint(sel)} className="bg-sky-500 hover:bg-sky-600"><Printer className="w-4 h-4 mr-1"/>Re-print</Button>
                {!sel.synced_to_cloud && (
                  <Button size="sm" data-testid="admin-gallery-retry-sync-btn" onClick={() => retrySync(sel.id)} className="bg-amber-500 hover:bg-amber-600 text-black">
                    <RefreshCw className="w-4 h-4 mr-1"/>Retry sync
                  </Button>
                )}
                <Button size="sm" variant="outline" className="border-slate-700" asChild><a href={`/g/${sel.qr_token}`} target="_blank" rel="noreferrer"><ExternalLink className="w-4 h-4 mr-1"/>Open QR</a></Button>
                <a className="text-xs" href={`${process.env.REACT_APP_BACKEND_URL}/api/g/${sel.qr_token}/zip`}><Button size="sm" variant="outline" className="border-slate-700"><Download className="w-4 h-4 mr-1"/>ZIP</Button></a>
                <Button size="sm" variant="outline" className="border-rose-500/50 text-rose-300" onClick={() => del(sel.id)}><Trash2 className="w-4 h-4"/></Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                {sel.print_path && <img src={fileUrl(sel.print_path)} alt="" className="w-full rounded-xl border border-slate-800" />}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(sel.photo_paths || []).filter(Boolean).map((p, i) => (
                  <img key={i} src={fileUrl(p)} alt="" className="rounded-lg border border-slate-800" />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
