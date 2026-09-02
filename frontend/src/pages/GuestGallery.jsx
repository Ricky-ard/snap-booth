import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { Download, Share2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function GuestGallery() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [lead, setLead] = useState({ name: "", email: "" });
  const [gated, setGated] = useState(false);

  useEffect(() => {
    api.get(`/g/${token}`).then(r => {
      setData(r.data);
      setGated(!!r.data.event.lead_gate);
    }).catch(e => setErr(e.response?.status === 410 ? "This link has expired." : "Photos not found."));
  }, [token]);

  async function downloadAll() {
    window.open(`${process.env.REACT_APP_BACKEND_URL}/api/g/${token}/zip`, "_blank");
  }

  async function submitLead(e) {
    e.preventDefault();
    try {
      await api.post(`/g/${token}/lead`, lead);
      setGated(false);
    } catch { toast.error("Try again"); }
  }

  async function nativeShare() {
    if (navigator.share && data?.session.web_path) {
      try {
        await navigator.share({ title: data.event.name, url: window.location.href });
      } catch {}
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast.success("Link copied");
    }
  }

  if (err) return <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-8 text-center">{err}</div>;
  if (!data) return <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin" /></div>;

  const s = data.session;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="sticky top-0 z-10 backdrop-blur-xl bg-slate-950/70 border-b border-slate-800 px-4 py-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div>
            {data.event.logo_url && <img src={data.event.logo_url} className="h-8" alt="" />}
            <div className="text-sm font-bold" style={{color: data.event.color || "#f43f5e"}}>{data.event.name}</div>
            <div className="text-xs text-slate-400">{data.event.headline}</div>
          </div>
          <button onClick={nativeShare} data-testid="guest-gallery-share-button"
            className="h-11 px-4 rounded-full bg-white/10 border border-white/10 flex items-center gap-2">
            <Share2 className="w-4 h-4" /> Share
          </button>
        </div>
      </header>

      {gated ? (
        <div className="max-w-md mx-auto p-6">
          <div className="bg-slate-900 rounded-3xl p-6 border border-slate-800">
            <h2 className="text-xl font-bold mb-2">Enter your details to view</h2>
            <p className="text-slate-400 text-sm mb-4">The event host will use this to share more photos with you.</p>
            <form onSubmit={submitLead} className="space-y-3">
              <input value={lead.name} onChange={e => setLead({...lead, name: e.target.value})}
                placeholder="Name" required
                className="w-full h-12 rounded-xl bg-slate-800 border border-slate-700 px-4" />
              <input value={lead.email} onChange={e => setLead({...lead, email: e.target.value})}
                placeholder="Email" type="email" required
                className="w-full h-12 rounded-xl bg-slate-800 border border-slate-700 px-4" />
              <Button type="submit" className="w-full h-12 bg-rose-500 hover:bg-rose-600">Show my photos</Button>
            </form>
          </div>
        </div>
      ) : (
        <main className="max-w-lg mx-auto p-4 space-y-4">
          <div className="rounded-2xl overflow-hidden border border-slate-800 bg-slate-900">
            <img src={fileUrl(s.print_path)} alt="Your print" className="w-full" />
          </div>
          {(s.gif_path || s.mp4_path) && (
            <div data-testid="guest-gallery-boomerang" className="rounded-2xl overflow-hidden border border-fuchsia-500/40 bg-slate-900 relative">
              {s.mp4_path ? (
                <video src={fileUrl(s.mp4_path)} autoPlay loop muted playsInline className="w-full" />
              ) : (
                <img src={fileUrl(s.gif_path)} alt="Boomerang" className="w-full" />
              )}
              <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider bg-fuchsia-500 text-white">
                BOOMERANG · TAP TO SAVE
              </span>
              <div className="p-3 flex gap-2">
                {s.gif_path && (
                  <a href={fileUrl(s.gif_path)} download data-testid="guest-gallery-gif-download"
                     className="flex-1 h-11 rounded-xl bg-slate-800 hover:bg-slate-700 text-sm font-medium flex items-center justify-center gap-2">
                    <Download className="w-4 h-4" /> GIF
                  </a>
                )}
                {s.mp4_path && (
                  <a href={fileUrl(s.mp4_path)} download data-testid="guest-gallery-mp4-download"
                     className="flex-1 h-11 rounded-xl bg-slate-800 hover:bg-slate-700 text-sm font-medium flex items-center justify-center gap-2">
                    <Download className="w-4 h-4" /> MP4
                  </a>
                )}
              </div>
            </div>
          )}
          <Button onClick={downloadAll} data-testid="guest-gallery-download-all-button"
            className="w-full h-14 bg-rose-500 hover:bg-rose-600 text-white text-base font-bold">
            <Download className="w-5 h-5 mr-2" /> Download all as ZIP
          </Button>
          <div className="grid grid-cols-2 gap-3">
            {(s.raw_photos || []).filter(Boolean).map((p, i) => (
              <a key={i} href={fileUrl(p)} target="_blank" rel="noreferrer"
                 className="rounded-xl overflow-hidden border border-slate-800">
                <img src={fileUrl(p)} alt="" className="w-full aspect-square object-cover" />
              </a>
            ))}
          </div>
          <div className="text-center text-xs text-slate-500 pt-6 pb-10">
            {data.event.powered_by || "SnapBooth"}
          </div>
        </main>
      )}
    </div>
  );
}
