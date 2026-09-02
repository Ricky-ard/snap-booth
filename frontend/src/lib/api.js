import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Also try Authorization bearer from localStorage (for third-party cookie fallback)
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("sb_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const fileUrl = (rel) => (rel ? `${API}/files/${rel}` : "");
