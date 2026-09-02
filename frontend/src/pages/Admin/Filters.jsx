import { useEffect, useRef, useState } from "react";
import { api, fileUrl, API } from "@/lib/api";
import { paramsToCss } from "@/lib/filters";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Upload, Trash2 } from "lucide-react";

const SAMPLE = "https://images.unsplash.com/photo-1727764894973-28e7283a600c?w=400";

export default function AdminFilters() {
  const [presets, setPresets] = useState([]);
  const load = () => api.get("/presets").then(r => setPresets(r.data));
  useEffect(() => { load(); }, []);

  async function toggle(p) {
    await api.put(`/presets/${p.id}`, { enabled: !p.enabled });
    load();
  }

  async function uploadLut(p, file) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/presets/${p.id}/lut`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`LUT attached to ${p.name}`);
      load();
    } catch (e) {
      toast.error(`Upload failed: ${e.response?.data?.detail || e.message}`);
    }
  }

  async function removeLut(p) {
    if (!window.confirm(`Remove the LUT from ${p.name}?`)) return;
    await api.delete(`/presets/${p.id}/lut`);
    load();
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Filters</div>
        <h1 className="text-3xl font-bold">Filter Presets</h1>
        <p className="text-sm text-slate-400 mt-1">
          Preview matches the print math. Attach a <span className="font-mono">.cube</span> 3D LUT to any preset — WebGL for the kiosk, trilinear for the print.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {presets.map(p => (
          <div key={p.id} data-testid="admin-filter-card" className="bg-[#161B22] border border-slate-800 rounded-2xl p-4">
            <div className="rounded-xl overflow-hidden bg-slate-800 aspect-square mb-3 relative">
              <img src={SAMPLE} alt="" className="w-full h-full object-cover" style={{ filter: paramsToCss(p.params) }} />
              {p.lut_path && (
                <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-fuchsia-500/90 text-white">
                  LUT · {p.lut_size || "?"}³
                </span>
              )}
            </div>
            <div className="flex items-center justify-between mb-2">
              <div className="font-bold">{p.name}</div>
              <Switch checked={p.enabled} onCheckedChange={() => toggle(p)} />
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs font-mono text-slate-400">
              {Object.entries(p.params || {}).filter(([_, v]) => v !== 0).slice(0, 6).map(([k, v]) => (
                <div key={k}>{k}: {v}</div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-slate-800 flex items-center gap-2">
              <label className="flex-1">
                <input type="file" accept=".cube" hidden
                  data-testid={`admin-filter-lut-input-${p.id}`}
                  onChange={(e) => { uploadLut(p, e.target.files?.[0]); e.target.value = ""; }} />
                <span className="inline-flex items-center gap-1 h-8 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs cursor-pointer">
                  <Upload className="w-3 h-3" /> {p.lut_path ? "Replace .cube" : "Add .cube"}
                </span>
              </label>
              {p.lut_path && (
                <button onClick={() => removeLut(p)} data-testid={`admin-filter-lut-remove-${p.id}`}
                  className="h-8 w-8 rounded-lg bg-rose-500/20 hover:bg-rose-500/40 flex items-center justify-center">
                  <Trash2 className="w-3 h-3 text-rose-300" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
