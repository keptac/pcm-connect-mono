import { Navigate, Route, Routes } from "react-router-dom";

import DashboardLayout from "./layouts/DashboardLayout";
import AdminPage from "./pages/AdminPage";
import AlumniConnectPage from "./pages/AlumniConnectPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import BroadcastsPage from "./pages/BroadcastsPage";
import CalendarPage from "./pages/CalendarPage";
import FundingPage from "./pages/FundingPage";
import LoginPage from "./pages/LoginPage";
import MarketplacePage from "./pages/MarketplacePage";
import MembersPage from "./pages/MembersPage";
import MessagesPage from "./pages/MessagesPage";
import MissionReportsPage from "./pages/MissionReportsPage";
import MyProfilePage from "./pages/MyProfilePage";
import OverviewPage from "./pages/OverviewPage";
import ProgramsPage from "./pages/ProgramsPage";
import SupportInfoPage from "./pages/SupportInfoPage";
import UpdatesPage from "./pages/UpdatesPage";
import UniversitiesPage from "./pages/UniversitiesPage";
import UsersPage from "./pages/UsersPage";
import { useAuthStore } from "./store/auth";

function HomeRoute() {
  const user = useAuthStore((state) => state.user);
  if (!user) return null;
  if (user.roles.includes("service_recovery")) {
    return <Navigate to="/team" replace />;
  }
  if (user.roles.includes("general_user")) {
    return <Navigate to="/marketplace" replace />;
  }
  return <OverviewPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<HomeRoute />} />
        <Route path="people" element={<MembersPage />} />
        <Route path="alumni-connect" element={<AlumniConnectPage />} />
        <Route path="my-profile" element={<MyProfilePage />} />
        <Route path="marketplace" element={<MarketplacePage />} />
        <Route path="programs" element={<ProgramsPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="broadcasts" element={<BroadcastsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="mission-reports" element={<MissionReportsPage />} />
        <Route path="updates" element={<UpdatesPage />} />
        <Route path="help" element={<SupportInfoPage variant="help" />} />
        <Route path="help/contact" element={<SupportInfoPage variant="contact" />} />
        <Route path="help/terms" element={<SupportInfoPage variant="terms" />} />
        <Route path="help/privacy" element={<SupportInfoPage variant="privacy" />} />
        <Route path="reports" element={<Navigate to="/updates" replace />} />
        <Route path="funding" element={<FundingPage />} />
        <Route path="universities" element={<UniversitiesPage />} />
        <Route path="team" element={<UsersPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="admin/audit-logs" element={<AuditLogsPage />} />

        <Route path="chapters" element={<Navigate to="/universities" replace />} />
        <Route path="members" element={<Navigate to="/people" replace />} />
        <Route path="reports/form" element={<Navigate to="/updates" replace />} />
        <Route path="reports/financial" element={<Navigate to="/funding" replace />} />
        <Route path="analytics" element={<Navigate to="/" replace />} />
        <Route path="admin/universities" element={<Navigate to="/universities" replace />} />
        <Route path="admin/programs" element={<Navigate to="/programs" replace />} />
        <Route path="admin/users" element={<Navigate to="/team" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
