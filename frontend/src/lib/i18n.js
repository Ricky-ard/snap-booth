import { create } from "zustand";

const dict = {
  en: {
    tap_to_start: "TAP TO START",
    choose_template: "Choose a Print Layout",
    choose_filter: "Choose a Style",
    get_ready: "GET READY",
    shot_of: "Shot {n} of {t}",
    retake: "Retake",
    looks_good: "Looks Good",
    processing: "Composing your print…",
    scan_qr: "Scan to get your photos",
    print_again: "Print Again",
    done: "Done",
    session_active_none: "No active event. Ask the operator to activate one from the dashboard.",
    starting_camera: "Starting camera…",
    camera_denied: "Camera permission denied. Allow camera to use the booth.",
    admin_pin: "Enter Admin PIN",
    ok: "OK",
    cancel: "Cancel",
    copies: "Copies",
  },
  id: {
    tap_to_start: "SENTUH UNTUK MULAI",
    choose_template: "Pilih Tata Letak Cetak",
    choose_filter: "Pilih Gaya Foto",
    get_ready: "BERSIAPLAH",
    shot_of: "Foto ke-{n} dari {t}",
    retake: "Foto Ulang",
    looks_good: "Sudah Bagus",
    processing: "Menyusun cetakan…",
    scan_qr: "Pindai untuk unduh foto",
    print_again: "Cetak Lagi",
    done: "Selesai",
    session_active_none: "Belum ada event aktif. Aktifkan dari dasbor.",
    starting_camera: "Menghidupkan kamera…",
    camera_denied: "Izin kamera ditolak.",
    admin_pin: "Masukkan PIN Admin",
    ok: "OK",
    cancel: "Batal",
    copies: "Salinan",
  },
};

export const useLang = create((set, get) => ({
  lang: localStorage.getItem("sb_lang") || "en",
  setLang: (l) => {
    localStorage.setItem("sb_lang", l);
    set({ lang: l });
  },
  t: (key, vars) => {
    const l = get().lang;
    let s = (dict[l] && dict[l][key]) || dict.en[key] || key;
    if (vars) Object.entries(vars).forEach(([k, v]) => { s = s.replace(`{${k}}`, v); });
    return s;
  },
}));
