import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import DocumentsPage from "./pages/DocumentsPage.jsx";
import AdminUsers from "./pages/AdminUsers.jsx";
import AdminSettings from "./pages/AdminSettings.jsx";

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<DocumentsPage />} />
      <Route path="/admin/users" element={<AdminUsers />} />
      <Route path="/admin/settings" element={<AdminSettings />} />
    </Routes>
  </BrowserRouter>
);
