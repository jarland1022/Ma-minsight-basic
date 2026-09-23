import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api/client";
import AppLayout from "./layout/AppLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import EventsPage from "./pages/EventsPage";
import EventDetailPage from "./pages/EventDetailPage";
import TracePage from "./pages/TracePage";
import HumanReviewPage from "./pages/HumanReviewPage";
import DefenseAssetsPage from "./pages/DefenseAssetsPage";
import EvalPage from "./pages/EvalPage";
import SettingsPage from "./pages/SettingsPage";
import UserGuidePage from "./pages/UserGuidePage";
import PlaybooksPage from "./pages/PlaybooksPage";
import LicensePage from "./pages/LicensePage";

function PrivateRoute({ children }: { children: JSX.Element }) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="events/:id" element={<EventDetailPage />} />
          <Route path="investigations/:id/trace" element={<TracePage />} />
          <Route path="human-review" element={<HumanReviewPage />} />
          <Route path="guide" element={<UserGuidePage />} />
          <Route path="defense-assets" element={<DefenseAssetsPage />} />
          <Route path="playbooks" element={<PlaybooksPage />} />
          <Route path="eval" element={<EvalPage />} />
          <Route path="license" element={<LicensePage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
