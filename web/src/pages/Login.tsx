import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

const DEMO_ACCOUNTS = [
  ["viewer1", "viewer"], ["ops1", "ops_agent"], ["approver_alice", "approver"],
  ["approver_bob", "approver"], ["supervisor1", "supervisor"], ["auditor1", "auditor"],
];

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("approver_alice");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/queue" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate("/queue");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-bold">🏦 Agentic FinOps Console</h1>
        <p className="mb-6 text-sm text-slate-500">Sign in to view cases, approvals, and cost.</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)}
                   className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </div>
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <button type="submit" disabled={loading}
                  className="w-full rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <div className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-400">
          <p className="mb-1 font-medium text-slate-500">Demo accounts (password: demo1234)</p>
          {DEMO_ACCOUNTS.map(([u, role]) => (
            <div key={u} className="flex justify-between">
              <span>{u}</span>
              <span>{role}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
