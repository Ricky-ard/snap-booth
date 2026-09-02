import { useEffect, useState } from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Camera, LayoutGrid, Sliders, Cpu, Images, LogOut, Play, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/admin", label: "Dashboard", icon: LayoutGrid, testid: "admin-nav-dashboard-link", end: true },
  { to: "/admin/events", label: "Events", icon: Calendar, testid: "admin-nav-events-link" },
  { to: "/admin/templates", label: "Templates", icon: LayoutGrid, testid: "admin-nav-templates-link" },
  { to: "/admin/filters", label: "Filters", icon: Sliders, testid: "admin-nav-filters-link" },
  { to: "/admin/hardware", label: "Hardware", icon: Cpu, testid: "admin-nav-hardware-link" },
  { to: "/admin/gallery", label: "Gallery", icon: Images, testid: "admin-nav-gallery-link" },
];

export default function AdminLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const [ok, setOk] = useState(false);

  useEffect(() => {
    api.get("/auth/me").then(() => setOk(true)).catch(() => nav("/admin/login"));
  }, [nav]);

  async function logout() {
    await api.post("/auth/logout");
    localStorage.removeItem("sb_token");
    nav("/admin/login");
  }

  if (!ok) return <div className="min-h-screen bg-[#090C10]" />;

  return (
    <div className="min-h-screen bg-[#090C10] text-slate-100 flex">
      <aside className="w-64 bg-[#0C1017] border-r border-slate-800 flex flex-col">
        <div className="px-6 py-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500 to-fuchsia-600 flex items-center justify-center">
              <Camera className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold">SnapBooth</div>
              <div className="text-xs text-slate-400 font-mono">OPERATOR</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(n => {
            const active = n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to);
            return (
              <Link key={n.to} to={n.to} data-testid={n.testid}
                className={`flex items-center gap-3 px-3 py-3 rounded-xl text-sm ${active ? "bg-rose-500/15 text-rose-300 border border-rose-500/30" : "text-slate-300 hover:bg-white/5"}`}>
                <n.icon className="w-4 h-4" /> {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-slate-800 space-y-2">
          <Button data-testid="admin-kiosk-launcher-button"
            onClick={() => window.open("/kiosk", "_blank")}
            className="w-full h-11 bg-rose-500 hover:bg-rose-600">
            <Play className="w-4 h-4 mr-2" /> Launch Kiosk
          </Button>
          <Button variant="outline" onClick={logout} className="w-full h-10 border-slate-700">
            <LogOut className="w-4 h-4 mr-2" /> Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto"><Outlet /></main>
    </div>
  );
}
