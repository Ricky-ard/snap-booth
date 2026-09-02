import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { paramsToCss } from "@/lib/filters";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

const SAMPLE = "https://images.unsplash.com/photo-1727764894973-28e7283a600c?w=400";

export default function AdminFilters() {
  const [presets, setPresets] = useState([]);
  const load = () => api.get("/presets").then(r => setPresets(r.data));
  useEffect(() => { load(); }, []);

  async function toggle(p) {
    await api.put(`/presets/${p.id}`, {enabled: !p.enabled});
    load();
  }
  async function updateParam(p, k, v) {
    const params = {...p.params, [k]: v};
    await api.put(`/presets/${p.id}`, {params});
    load();
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Filters</div>
        <h1 className="text-3xl font-bold">Filter Presets</h1>
        <p className="text-sm text-slate-400 mt-1">Preview matches the print math — WebGL/CSS front + Pillow back.</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {presets.map(p => (
          <div key={p.id} data-testid="admin-filter-card" className="bg-[#161B22] border border-slate-800 rounded-2xl p-4">
            <div className="rounded-xl overflow-hidden bg-slate-800 aspect-square mb-3">
              <img src={SAMPLE} alt="" className="w-full h-full object-cover" style={{filter: paramsToCss(p.params)}} />
            </div>
            <div className="flex items-center justify-between mb-2">
              <div className="font-bold">{p.name}</div>
              <Switch checked={p.enabled} onCheckedChange={() => toggle(p)} />
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs font-mono text-slate-400">
              {Object.entries(p.params).filter(([_,v]) => v !== 0).slice(0, 6).map(([k,v]) => (
                <div key={k}>{k}: {v}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
