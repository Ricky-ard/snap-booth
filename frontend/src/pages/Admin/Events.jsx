import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Plus, Check, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function AdminEvents() {
  const [events, setEvents] = useState([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", client: "", headline: "Say Cheese!", color: "#f43f5e" });

  const load = () => api.get("/events").then(r => setEvents(r.data));
  useEffect(() => { load(); }, []);

  async function activate(id) {
    await api.post(`/events/${id}/activate`);
    toast.success("Event activated"); load();
  }
  async function del(id) {
    if (!window.confirm("Delete event?")) return;
    await api.delete(`/events/${id}`); load();
  }
  async function create(e) {
    e.preventDefault();
    await api.post("/events", form);
    setCreating(false); setForm({ name: "", client: "", headline: "Say Cheese!", color: "#f43f5e" }); load();
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest text-slate-500">Events</div>
          <h1 className="text-3xl font-bold">Manage Events</h1>
        </div>
        <Button data-testid="admin-create-event-btn" onClick={() => setCreating(true)} className="bg-rose-500 hover:bg-rose-600">
          <Plus className="w-4 h-4 mr-2" /> New Event
        </Button>
      </div>

      {creating && (
        <form onSubmit={create} className="mb-6 bg-[#161B22] border border-slate-800 rounded-2xl p-6 grid grid-cols-2 gap-4">
          <input required value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Event name" className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3" />
          <input value={form.client} onChange={e => setForm({...form, client: e.target.value})} placeholder="Client / couple" className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3" />
          <input value={form.headline} onChange={e => setForm({...form, headline: e.target.value})} placeholder="Headline" className="h-11 rounded-xl bg-slate-900 border border-slate-800 px-3" />
          <input type="color" value={form.color} onChange={e => setForm({...form, color: e.target.value})} className="h-11 rounded-xl bg-slate-900 border border-slate-800" />
          <div className="col-span-2 flex gap-3">
            <Button type="submit" className="bg-rose-500 hover:bg-rose-600">Create</Button>
            <Button type="button" variant="outline" className="border-slate-700" onClick={() => setCreating(false)}>Cancel</Button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {events.map(ev => (
          <div key={ev.id} data-testid="admin-event-card" className={`bg-[#161B22] border rounded-2xl p-5 ${ev.active ? "border-rose-500" : "border-slate-800"}`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-mono uppercase text-slate-500">{ev.date}</div>
                <div className="text-xl font-bold" style={{color: ev.color}}>{ev.name}</div>
                <div className="text-sm text-slate-400">{ev.client}</div>
              </div>
              {ev.active && <span className="text-xs px-2 py-1 rounded-full bg-rose-500/20 text-rose-300 font-bold">ACTIVE</span>}
            </div>
            <div className="mt-4 flex gap-2">
              {!ev.active && <Button data-testid="admin-event-activate-btn" onClick={() => activate(ev.id)} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
                <Check className="w-3 h-3 mr-1" /> Activate
              </Button>}
              <Button size="sm" variant="outline" className="border-slate-700" onClick={() => del(ev.id)}>
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
