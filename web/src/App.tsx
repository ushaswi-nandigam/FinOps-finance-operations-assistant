import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
import LiveQueue from "./pages/LiveQueue";
import CaseTrace from "./pages/CaseTrace";
import Approvals from "./pages/Approvals";
import CostDashboard from "./pages/CostDashboard";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="text-lg font-bold">🏦 FinOps Console</span>
            <nav className="flex gap-1">
              <NavLink to="/queue" className={navLinkClass}>Live Queue</NavLink>
              <NavLink to="/approvals" className={navLinkClass}>Approvals</NavLink>
              <NavLink to="/dashboard" className={navLinkClass}>Cost Dashboard</NavLink>
            </nav>
          </div>
          {user && (
            <div className="flex items-center gap-3 text-sm text-slate-600">
              <span>
                {user.username} <span className="text-slate-400">({user.role})</span>
              </span>
              <button onClick={logout} className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100">
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/queue" element={<RequireAuth><LiveQueue /></RequireAuth>} />
      <Route path="/cases/:caseId" element={<RequireAuth><CaseTrace /></RequireAuth>} />
      <Route path="/approvals" element={<RequireAuth><Approvals /></RequireAuth>} />
      <Route path="/dashboard" element={<RequireAuth><CostDashboard /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/queue" replace />} />
    </Routes>
  );
}
