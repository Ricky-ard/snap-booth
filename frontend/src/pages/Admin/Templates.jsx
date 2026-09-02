import { useEffect, useMemo, useRef, useState } from "react";
import { api, fileUrl, API } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Plus, Trash2, Save, Copy, Upload, Grid3x3, Image as ImageIcon, Move, Maximize2 } from "lucide-react";
import { toast } from "sonner";

const PAPER_SIZES = {
  "2x6":        { w: 600,  h: 1800 },
  "2x6_double": { w: 1200, h: 1800 },
  "4x6":        { w: 1200, h: 1800 },
  "6x8":        { w: 1800, h: 2400 },
  "square":     { w: 1500, h: 1500 },
};

const DEFAULT_SLOT = { x: 100, y: 100, width: 400, height: 400, corner_radius: 0 };
const HANDLE_SIZE = 14;

export default function AdminTemplates() {
  const [templates, setTemplates] = useState([]);
  const [sel, setSel] = useState(null);
  const [snap, setSnap] = useState(true);
  const [snapSize, setSnapSize] = useState(20);
  const [showGrid, setShowGrid] = useState(true);
  const [activeSlot, setActiveSlot] = useState(0);
  const overlayInput = useRef(null);
  const backgroundInput = useRef(null);

  const load = () => api.get("/templates").then(r => setTemplates(r.data));
  useEffect(() => { load(); }, []);

  async function create() {
    const r = await api.post("/templates", {
      name: "New Template",
      paper: { size: "4x6" },
      canvas: { width_px: 1200, height_px: 1800 },
      photo_count: 1,
      background_color: "#111827",
      photo_slots: [{ ...DEFAULT_SLOT, x: 60, y: 60, width: 1080, height: 1500, corner_radius: 24 }],
      text_layers: [],
      duplicate_on_sheet: false,
    });
    await load();
    setSel(r.data);
    setActiveSlot(0);
  }

  async function save() {
    if (!sel) return;
    await api.put(`/templates/${sel.id}`, sel);
    toast.success("Template saved");
    load();
  }

  async function duplicate() {
    if (!sel) return;
    const copy = { ...sel, name: `${sel.name} (copy)` };
    delete copy.id;
    const r = await api.post("/templates", copy);
    await load();
    setSel(r.data);
    toast.success("Duplicated");
  }

  async function del(id) {
    if (!window.confirm("Delete this template?")) return;
    await api.delete(`/templates/${id}`);
    setSel(null);
    load();
  }

  async function uploadAsset(kind, file) {
    if (!file) return null;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post(`/uploads/${kind}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return r.data.path;
    } catch (e) {
      toast.error(`Upload failed: ${e.response?.data?.detail || e.message}`);
      return null;
    }
  }

  async function onUploadOverlay(e) {
    const path = await uploadAsset("overlay", e.target.files?.[0]);
    if (path) setSel({ ...sel, overlay_image: path });
    e.target.value = "";
  }

  async function onUploadBackground(e) {
    const path = await uploadAsset("background", e.target.files?.[0]);
    if (path) setSel({ ...sel, background_image: path });
    e.target.value = "";
  }

  function updateSlot(i, patch) {
    const slots = sel.photo_slots.map((s, idx) => (idx === i ? { ...s, ...patch } : s));
    setSel({ ...sel, photo_slots: slots });
  }

  function addSlot() {
    const slots = [...sel.photo_slots, { ...DEFAULT_SLOT }];
    setSel({ ...sel, photo_slots: slots, photo_count: Math.max(slots.length, sel.photo_count || 1) });
    setActiveSlot(slots.length - 1);
  }

  function duplicateSlot(i) {
    const s = sel.photo_slots[i];
    const clone = { ...s, x: s.x + 40, y: s.y + 40 };
    const slots = [...sel.photo_slots, clone];
    setSel({ ...sel, photo_slots: slots });
    setActiveSlot(slots.length - 1);
  }

  function deleteSlot(i) {
    const slots = sel.photo_slots.filter((_, idx) => idx !== i);
    setSel({
      ...sel,
      photo_slots: slots,
      photo_count: Math.max(1, Math.min(sel.photo_count || 1, slots.length)),
    });
    setActiveSlot((s) => Math.max(0, Math.min(s, slots.length - 1)));
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Templates</div>
          <h1 className="text-3xl font-bold">Print Layout Designer</h1>
        </div>
        <Button data-testid="admin-create-template-btn" onClick={create} className="bg-rose-500 hover:bg-rose-600">
          <Plus className="w-4 h-4 mr-2" /> New Template
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3 space-y-2">
          {templates.map((t) => (
            <button
              key={t.id}
              data-testid="admin-template-list-item"
              onClick={() => { setSel({ ...t }); setActiveSlot(0); }}
              className={`w-full text-left p-3 rounded-xl border transition-colors ${
                sel?.id === t.id ? "bg-rose-500/10 border-rose-500" : "bg-[#161B22] border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-slate-400 font-mono">
                {t.paper?.size} · {t.photo_slots?.length ?? 0} slots
              </div>
            </button>
          ))}
        </div>

        <div className="col-span-9">
          {sel ? (
            <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-6">
              {/* --- Header controls --- */}
              <div className="grid grid-cols-4 gap-3 mb-4">
                <input
                  value={sel.name}
                  onChange={(e) => setSel({ ...sel, name: e.target.value })}
                  className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3 text-white col-span-2"
                />
                <select
                  value={sel.paper?.size}
                  onChange={(e) => {
                    const size = e.target.value;
                    const { w, h } = PAPER_SIZES[size];
                    setSel({ ...sel, paper: { ...(sel.paper || {}), size }, canvas: { width_px: w, height_px: h } });
                  }}
                  className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3 text-white"
                >
                  {Object.keys(PAPER_SIZES).map((k) => <option key={k}>{k}</option>)}
                </select>
                <input
                  type="color"
                  value={sel.background_color || "#111827"}
                  onChange={(e) => setSel({ ...sel, background_color: e.target.value })}
                  className="h-11 rounded-xl bg-slate-900 border border-slate-800"
                />
              </div>

              <div className="grid grid-cols-12 gap-6">
                {/* --- Editor Canvas --- */}
                <div className="col-span-8">
                  <div className="flex items-center gap-3 mb-2 text-xs font-mono uppercase text-slate-500">
                    <Move className="w-3 h-3" />
                    Drag slots · Handle to resize · Shift+drag = move without snap
                  </div>
                  <SlotEditor
                    template={sel}
                    activeSlot={activeSlot}
                    onActiveSlot={setActiveSlot}
                    onChangeSlot={updateSlot}
                    snap={snap ? snapSize : 0}
                    showGrid={showGrid}
                  />
                  <div className="mt-3 flex items-center gap-4 text-sm">
                    <label className="flex items-center gap-2">
                      <Switch checked={snap} onCheckedChange={setSnap} data-testid="admin-template-snap-toggle" />
                      <span>Snap to grid</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <Grid3x3 className="w-3 h-3 text-slate-500" />
                      <input
                        type="number"
                        min="4" max="200" step="4"
                        value={snapSize}
                        onChange={(e) => setSnapSize(Math.max(4, +e.target.value || 20))}
                        className="w-16 h-8 rounded bg-slate-900 border border-slate-800 px-2 text-xs"
                      />
                      <span className="text-xs text-slate-500">px</span>
                    </div>
                    <label className="flex items-center gap-2">
                      <Switch checked={showGrid} onCheckedChange={setShowGrid} />
                      <span>Show grid</span>
                    </label>
                    <label className="flex items-center gap-2 ml-auto">
                      <input
                        type="checkbox"
                        checked={!!sel.duplicate_on_sheet}
                        onChange={(e) => setSel({ ...sel, duplicate_on_sheet: e.target.checked })}
                      />
                      <span className="text-xs">Duplicate strip on 4x6 sheet</span>
                    </label>
                  </div>
                </div>

                {/* --- Right rail: assets + slot inspector --- */}
                <div className="col-span-4 space-y-4">
                  <AssetRow
                    label="Overlay PNG (over photos)"
                    path={sel.overlay_image}
                    onUpload={() => overlayInput.current?.click()}
                    onClear={() => setSel({ ...sel, overlay_image: null })}
                  />
                  <AssetRow
                    label="Background image (under photos)"
                    path={sel.background_image}
                    onUpload={() => backgroundInput.current?.click()}
                    onClear={() => setSel({ ...sel, background_image: null })}
                  />
                  <input ref={overlayInput} type="file" accept="image/png,image/webp" hidden onChange={onUploadOverlay} data-testid="admin-template-overlay-input" />
                  <input ref={backgroundInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={onUploadBackground} />

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-xs font-mono uppercase text-slate-500">Photo Slots</div>
                      <Button size="sm" onClick={addSlot} className="bg-slate-700 hover:bg-slate-600 h-8">
                        <Plus className="w-3 h-3 mr-1" /> Add
                      </Button>
                    </div>
                    <div className="space-y-2 max-h-72 overflow-auto pr-1">
                      {sel.photo_slots.map((s, i) => (
                        <SlotRow
                          key={i}
                          i={i}
                          slot={s}
                          active={activeSlot === i}
                          onSelect={() => setActiveSlot(i)}
                          onChange={(patch) => updateSlot(i, patch)}
                          onDuplicate={() => duplicateSlot(i)}
                          onDelete={() => deleteSlot(i)}
                        />
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                    <label className="text-sm text-slate-400">Photos captured:</label>
                    <input
                      type="number" min="1" max="8"
                      value={sel.photo_count}
                      onChange={(e) => setSel({ ...sel, photo_count: +e.target.value })}
                      className="h-9 w-16 rounded bg-slate-900 border border-slate-800 px-2 text-white"
                    />
                    <span className="text-xs text-slate-500">shots</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button data-testid="admin-template-save-btn" onClick={save} className="bg-emerald-500 hover:bg-emerald-600">
                  <Save className="w-4 h-4 mr-2" /> Save
                </Button>
                <Button variant="outline" onClick={duplicate} className="border-slate-700">
                  <Copy className="w-4 h-4 mr-2" /> Duplicate
                </Button>
                <Button variant="outline" onClick={() => del(sel.id)} className="border-rose-500/50 text-rose-300">
                  <Trash2 className="w-4 h-4 mr-2" /> Delete
                </Button>
              </div>
            </div>
          ) : (
            <div className="bg-[#161B22] border border-slate-800 rounded-2xl p-16 text-center text-slate-400">
              Select a template on the left or create a new one to start designing.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// -----------------------------------------------------------------------
// Slot Editor Canvas
// -----------------------------------------------------------------------
function SlotEditor({ template, activeSlot, onActiveSlot, onChangeSlot, snap, showGrid }) {
  const cw = template.canvas?.width_px || 1200;
  const ch = template.canvas?.height_px || 1800;

  const containerRef = useRef(null);
  const [displayW, setDisplayW] = useState(600);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setDisplayW(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const maxH = 620;
  // Fit canvas keeping aspect ratio inside displayW × maxH
  const scale = Math.min(displayW / cw, maxH / ch);
  const viewW = cw * scale;
  const viewH = ch * scale;

  const snapVal = (v) => (snap > 0 ? Math.round(v / snap) * snap : Math.round(v));

  const [drag, setDrag] = useState(null); // { i, mode: 'move'|'resize', startX, startY, orig, shift }

  function onPointerDown(e, i, mode) {
    if (e.button !== 0 && e.pointerType !== "touch") return;
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    onActiveSlot(i);
    setDrag({
      i, mode,
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...template.photo_slots[i] },
      shift: e.shiftKey,
    });
  }

  function onPointerMove(e) {
    if (!drag) return;
    const dx = (e.clientX - drag.startX) / scale;
    const dy = (e.clientY - drag.startY) / scale;
    const s = drag.orig;
    const bypass = e.shiftKey || drag.shift;
    const doSnap = (v) => (bypass ? Math.round(v) : snapVal(v));
    if (drag.mode === "move") {
      const nx = Math.max(0, Math.min(cw - s.width, doSnap(s.x + dx)));
      const ny = Math.max(0, Math.min(ch - s.height, doSnap(s.y + dy)));
      onChangeSlot(drag.i, { x: nx, y: ny });
    } else if (drag.mode === "resize") {
      const nw = Math.max(40, Math.min(cw - s.x, doSnap(s.width + dx)));
      const nh = Math.max(40, Math.min(ch - s.y, doSnap(s.height + dy)));
      onChangeSlot(drag.i, { width: nw, height: nh });
    }
  }

  function onPointerUp() {
    setDrag(null);
  }

  const overlayUrl = template.overlay_image ? fileUrl(template.overlay_image) : null;
  const backgroundUrl = template.background_image ? fileUrl(template.background_image) : null;

  return (
    <div ref={containerRef} className="w-full">
      <div className="mx-auto rounded-xl overflow-hidden border border-slate-700 relative select-none touch-none"
           style={{
             width: viewW, height: viewH,
             background: template.background_color || "#111",
           }}
           data-testid="admin-template-canvas"
           onPointerMove={onPointerMove}
           onPointerUp={onPointerUp}
           onPointerCancel={onPointerUp}
           onPointerLeave={onPointerUp}
      >
        {/* Background image (under photos) */}
        {backgroundUrl && (
          <img src={backgroundUrl} alt="" className="absolute inset-0 w-full h-full object-cover pointer-events-none" />
        )}

        {/* Grid */}
        {showGrid && snap > 0 && (
          <svg className="absolute inset-0 pointer-events-none" width={viewW} height={viewH}>
            <defs>
              <pattern id="p-grid" x="0" y="0" width={snap * scale} height={snap * scale} patternUnits="userSpaceOnUse">
                <path d={`M ${snap * scale} 0 L 0 0 0 ${snap * scale}`} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width={viewW} height={viewH} fill="url(#p-grid)" />
          </svg>
        )}

        {/* Slots (below overlay) */}
        {(template.photo_slots || []).map((s, i) => {
          const active = i === activeSlot;
          return (
            <div
              key={i}
              data-testid={`admin-template-slot-${i}`}
              onPointerDown={(e) => onPointerDown(e, i, "move")}
              className={`absolute cursor-move ${
                active ? "ring-2 ring-rose-500" : "ring-1 ring-white/40 hover:ring-white/70"
              }`}
              style={{
                left: s.x * scale,
                top: s.y * scale,
                width: s.width * scale,
                height: s.height * scale,
                background: active ? "rgba(244,63,94,0.22)" : "rgba(148,163,184,0.35)",
                borderRadius: (s.corner_radius || 0) * scale,
                touchAction: "none",
              }}
            >
              <div className="absolute inset-0 flex items-center justify-center text-white font-mono text-xs font-bold pointer-events-none">
                {i + 1}
              </div>
              {active && (
                <>
                  <div className="absolute -top-6 left-0 text-[10px] font-mono bg-black/80 px-1.5 py-0.5 rounded pointer-events-none">
                    {Math.round(s.x)},{Math.round(s.y)} · {Math.round(s.width)}×{Math.round(s.height)}
                  </div>
                  <div
                    data-testid={`admin-template-slot-${i}-resize`}
                    onPointerDown={(e) => onPointerDown(e, i, "resize")}
                    className="absolute bg-rose-500 hover:bg-rose-400 rounded-sm cursor-nwse-resize flex items-center justify-center"
                    style={{
                      width: HANDLE_SIZE, height: HANDLE_SIZE,
                      right: -HANDLE_SIZE / 2, bottom: -HANDLE_SIZE / 2,
                      touchAction: "none",
                    }}
                  >
                    <Maximize2 className="w-2.5 h-2.5 text-white" />
                  </div>
                </>
              )}
            </div>
          );
        })}

        {/* Overlay PNG (above photos) — semi-transparent so slots stay visible */}
        {overlayUrl && (
          <img src={overlayUrl} alt="" className="absolute inset-0 w-full h-full object-cover pointer-events-none" style={{ opacity: 0.65 }} />
        )}

        {/* Cut line for duplicate strip layout */}
        {template.duplicate_on_sheet && (
          <div className="absolute inset-y-0 left-1/2 border-l border-dashed border-white/60 pointer-events-none" />
        )}
      </div>
      <div className="mt-1 text-center text-[11px] font-mono text-slate-500">
        Canvas · {cw} × {ch}px @ 300 DPI · shown at {Math.round(scale * 100)}%
      </div>
    </div>
  );
}


// -----------------------------------------------------------------------
// Slot list row (numeric inputs + actions)
// -----------------------------------------------------------------------
function SlotRow({ i, slot, active, onSelect, onChange, onDuplicate, onDelete }) {
  return (
    <div
      onClick={onSelect}
      className={`rounded-xl border p-2 cursor-pointer ${
        active ? "bg-rose-500/10 border-rose-500" : "bg-slate-900 border-slate-800 hover:border-slate-700"
      }`}
    >
      <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
        <span>Slot #{i + 1}</span>
        <div className="flex gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onDuplicate(); }}
            className="h-6 w-6 rounded bg-slate-800 hover:bg-slate-700 flex items-center justify-center"
            title="Duplicate slot"
          >
            <Copy className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="h-6 w-6 rounded bg-rose-500/20 hover:bg-rose-500/40 flex items-center justify-center"
            title="Delete slot"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-1">
        <LabeledNum label="X" value={slot.x} onChange={(v) => onChange({ x: v })} />
        <LabeledNum label="Y" value={slot.y} onChange={(v) => onChange({ y: v })} />
        <LabeledNum label="W" value={slot.width} onChange={(v) => onChange({ width: v })} />
        <LabeledNum label="H" value={slot.height} onChange={(v) => onChange({ height: v })} />
      </div>
      <div className="mt-1">
        <LabeledNum label="Corner radius" value={slot.corner_radius || 0} onChange={(v) => onChange({ corner_radius: v })} />
      </div>
    </div>
  );
}

function LabeledNum({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="block text-[9px] uppercase tracking-widest text-slate-500 font-mono">{label}</span>
      <input
        type="number"
        value={Math.round(value)}
        onChange={(e) => onChange(+e.target.value || 0)}
        onClick={(e) => e.stopPropagation()}
        className="w-full h-7 rounded bg-slate-800 border border-slate-700 px-1.5 text-xs text-white"
      />
    </label>
  );
}


// -----------------------------------------------------------------------
// Uploaded asset row
// -----------------------------------------------------------------------
function AssetRow({ label, path, onUpload, onClear }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-mono uppercase text-slate-500">{label}</div>
        {path && (
          <button onClick={onClear} className="text-xs text-rose-300 hover:text-rose-200">clear</button>
        )}
      </div>
      {path ? (
        <div className="flex items-center gap-3">
          <img src={fileUrl(path)} alt="" className="w-14 h-14 rounded-lg object-cover border border-slate-800 bg-slate-800" />
          <div className="flex-1 min-w-0">
            <div className="text-xs font-mono text-slate-300 truncate">{path}</div>
            <Button size="sm" onClick={onUpload} className="mt-1 h-7 bg-slate-700 hover:bg-slate-600">
              <Upload className="w-3 h-3 mr-1" /> Replace
            </Button>
          </div>
        </div>
      ) : (
        <button
          onClick={onUpload}
          className="w-full h-20 rounded-lg border-2 border-dashed border-slate-700 hover:border-rose-500 flex flex-col items-center justify-center text-slate-400 hover:text-rose-300 text-xs transition-colors"
        >
          <ImageIcon className="w-4 h-4 mb-1" />
          Upload PNG
        </button>
      )}
    </div>
  );
}
