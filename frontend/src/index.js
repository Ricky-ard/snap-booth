import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// SnapBooth is a dark-first product; force the shadcn `dark` palette.
document.documentElement.classList.add("dark");

// Register the offline-first service worker (only in production builds).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  });
}

// When the browser regains connectivity, ping the backend sync worker so
// completed sessions upload to the cloud without waiting for the next tick.
window.addEventListener("online", () => {
  if (navigator.serviceWorker?.controller) {
    navigator.serviceWorker.controller.postMessage({ type: "TRIGGER_SYNC" });
  } else {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/sync/trigger`, { method: "POST" }).catch(() => {});
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
