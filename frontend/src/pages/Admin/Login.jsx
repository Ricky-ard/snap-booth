import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Camera, Lock } from "lucide-react";
import { toast } from "sonner";

export default function AdminLogin() {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post("/auth/login", { password });
      if (r.data.token) localStorage.setItem("sb_token", r.data.token);
      nav("/admin");
    } catch { toast.error("Wrong password"); }
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-[#0A0D14] flex items-center justify-center p-6">
      <form onSubmit={submit} className="w-96 bg-[#161B22] border border-slate-800 rounded-3xl p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-rose-500 to-fuchsia-600 flex items-center justify-center">
            <Camera className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="font-mono text-xs uppercase tracking-widest text-slate-400">SnapBooth</div>
            <div className="text-xl font-bold text-white">Operator Sign-in</div>
          </div>
        </div>
        <label className="block text-sm text-slate-400 mb-2">Password</label>
        <div className="relative mb-6">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input data-testid="admin-login-password"
            type="password" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full h-12 rounded-xl bg-slate-900 border border-slate-800 pl-10 pr-4 text-white" required />
        </div>
        <Button data-testid="admin-login-submit"
          type="submit" disabled={loading}
          className="w-full h-12 bg-rose-500 hover:bg-rose-600">
          {loading ? "Signing in..." : "Sign in"}
        </Button>
        <p className="text-xs text-slate-500 mt-4 font-mono">default: snapbooth · pin: 1234</p>
      </form>
    </div>
  );
}
