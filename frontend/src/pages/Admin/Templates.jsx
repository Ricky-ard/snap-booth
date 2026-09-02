import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, Save } from "lucide-react";
import { toast } from "sonner";

const PAPER_SIZES = {
  "2x6": { w: 600, h: 1800 },
  "2x6_double": { w: 1200, h: 1800 },
  "4x6": { w: 1200, h: 1800 },
  "6x8": { w: 1800, h: 2400 },
  "square": { w: 1500, h: 1500 },
};

export default function AdminTemplates() {
  const [templates, setTemplates] = useState([]);
  const [sel, setSel] = useState(null);
  const load = () => api.get("/templates").then(r => setTemplates(r.data));
  useEffect(() => { load(); }, []);

  async function save() {
    await api.put(`/templates/${sel.id}`, sel);
    toast.success("Saved"); load();
  }
  async function create() {
    const r = await api.post("/templates", {
      name: "New Template", paper: {size: "4x6"}, canvas: {width_px: 1200, height_px: 1800},
      photo_count: 1, background_color: "#111827",
      photo_slots: [{x: 60, y: 60, width: 1080, height: 1500, corner_radius: 24}],
      text_layers: [], duplicate_on_sheet: false,
    });
    load(); setSel(r.data);
  }
  async function del(id) {
    if (!window.confirm("Delete template?")) return;
    await api.delete(`/templates/${id}`); setSel(null); load();
  }

  const updateSlot = (i, patch) => {
    const slots = sel.photo_slots.map((s, idx) => idx === i ? {...s, ...patch} : s);
    setSel({...sel, photo_slots: slots});
  };
  const addSlot = () => setSel({...sel, photo_slots: [...sel.photo_slots, {x:100, y:100, width:400, height:400, corner_radius:0}]});
  const delSlot = (i) => setSel({...sel, photo_slots: sel.photo_slots.filter((_, idx) => idx !== i), photo_count: Math.max(1, sel.photo_slots.length - 1)});

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Templates</div>
          <h1 className="text-3xl font-bold">Print Layout Designer</h1>
        </div>
        <Button data-testid="admin-create-template-btn" onClick={create} className="bg-rose-500 hover:bg-rose-600"><Plus className="w-4 h-4 mr-2" /> New Template</Button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3 space-y-2">
          {templates.map(t => (
            <button key={t.id} onClick={() => setSel({...t})}
              className={`w-full text-left p-3 rounded-xl border ${sel?.id === t.id ? "bg-rose-500/10 border-rose-500" : "bg-[#161B22] border-slate-800"}`}>
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-slate-400 font-mono">{t.paper?.size} · {t.photo_count} slots</div>
            </button>
          ))}
        </div>

        <div className="col-span-9">
          {sel ? (
            <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <input value={sel.name} onChange={e => setSel({...sel, name: e.target.value})} className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3" />
                <select value={sel.paper?.size} onChange={e => {
                  const size = e.target.value;
                  const {w, h} = PAPER_SIZES[size];
                  setSel({...sel, paper: {...(sel.paper||{}), size}, canvas: {width_px: w, height_px: h}});
                }} className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3">
                  {Object.keys(PAPER_SIZES).map(k => <option key={k}>{k}</option>)}
                </select>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!sel.duplicate_on_sheet} onChange={e => setSel({...sel, duplicate_on_sheet: e.target.checked})} />
                  Duplicate strip on sheet (2x 2x6 strips on one 4x6)
                </label>
                <input type="color" value={sel.background_color || "#111827"} onChange={e => setSel({...sel, background_color: e.target.value})} className="h-11 rounded-xl bg-slate-900 border border-slate-800" />
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="text-xs font-mono uppercase text-slate-500 mb-2">Preview</div>
                  <SlotCanvas sel={sel} />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs font-mono uppercase text-slate-500">Photo Slots</div>
                    <Button size="sm" onClick={addSlot} className="bg-slate-700 hover:bg-slate-600 h-8">
                      <Plus className="w-3 h-3 mr-1" /> Add slot
                    </Button>
                  </div>
                  <div className="space-y-2 max-h-96 overflow-auto">
                    {sel.photo_slots.map((s, i) => (
                      <div key={i} className="grid grid-cols-5 gap-2 p-2 rounded-xl bg-slate-900 border border-slate-800">
                        <input type="number" value={s.x} onChange={e => updateSlot(i, {x: +e.target.value})} className="h-8 rounded bg-slate-800 px-2 text-xs" placeholder="x" />
                        <input type="number" value={s.y} onChange={e => updateSlot(i, {y: +e.target.value})} className="h-8 rounded bg-slate-800 px-2 text-xs" placeholder="y" />
                        <input type="number" value={s.width} onChange={e => updateSlot(i, {width: +e.target.value})} className="h-8 rounded bg-slate-800 px-2 text-xs" placeholder="w" />
                        <input type="number" value={s.height} onChange={e => updateSlot(i, {height: +e.target.value})} className="h-8 rounded bg-slate-800 px-2 text-xs" placeholder="h" />
                        <button onClick={() => delSlot(i)} className="h-8 rounded bg-rose-500/20 hover:bg-rose-500/40 flex items-center justify-center">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 flex items-center gap-2">
                    <label className="text-sm text-slate-400">Photos captured:</label>
                    <input type="number" min="1" max="8" value={sel.photo_count} onChange={e => setSel({...sel, photo_count: +e.target.value})} className="h-9 w-20 rounded bg-slate-800 px-2" />
                  </div>
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button data-testid="admin-template-save-btn" onClick={save} className="bg-emerald-500 hover:bg-emerald-600"><Save className="w-4 h-4 mr-2" />Save</Button>
                <Button variant="outline" onClick={() => del(sel.id)} className="border-rose-500/50 text-rose-300"><Trash2 className="w-4 h-4 mr-2" />Delete</Button>
              </div>
            </div>
          ) : (
            <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-16 text-center text-slate-400">
              Select a template to edit
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SlotCanvas({ sel }) {
  const cw = sel.canvas?.width_px || 1200;
  const ch = sel.canvas?.height_px || 1800;
  const scale = 340 / Math.max(cw, ch);
  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700"
      style={{width: cw*scale, height: ch*scale, background: sel.background_color || "#111"}}>
      {(sel.photo_slots || []).map((s, i) => (
        <div key={i} className="absolute bg-slate-500/60 border border-white/30 flex items-center justify-center text-xs font-mono" style={{
          left: s.x*scale, top: s.y*scale, width: s.width*scale, height: s.height*scale,
          borderRadius: (s.corner_radius || 0)*scale,
        }}>{i+1}</div>
      ))}
      {sel.duplicate_on_sheet && (
        <div className="absolute inset-y-0 left-1/2 w-px bg-white/40 border-l border-dashed" />
      )}
    </div>
  );
}
