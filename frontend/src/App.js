import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Kiosk from "@/pages/Kiosk";
import GuestGallery from "@/pages/GuestGallery";
import AdminLogin from "@/pages/Admin/Login";
import AdminLayout from "@/pages/Admin/Layout";
import AdminDashboard from "@/pages/Admin/Dashboard";
import AdminEvents from "@/pages/Admin/Events";
import AdminTemplates from "@/pages/Admin/Templates";
import AdminFilters from "@/pages/Admin/Filters";
import AdminHardware from "@/pages/Admin/Hardware";
import AdminGallery from "@/pages/Admin/Gallery";
import "@/App.css";

function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" richColors closeButton />
      <Routes>
        <Route path="/" element={<Navigate to="/kiosk" replace />} />
        <Route path="/kiosk" element={<Kiosk />} />
        <Route path="/g/:token" element={<GuestGallery />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="events" element={<AdminEvents />} />
          <Route path="templates" element={<AdminTemplates />} />
          <Route path="filters" element={<AdminFilters />} />
          <Route path="hardware" element={<AdminHardware />} />
          <Route path="gallery" element={<AdminGallery />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
