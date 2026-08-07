import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function BarRow({ label, count, max, colorClass }: { label: string; count: number; max: number; colorClass: string }) {
  const pct = max > 0 ? Math.max(4, (count / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="w-32 shrink-0 text-xs text-slate-500">{label}</span>
      <div className="h-4 flex-1 rounded bg-slate-100">
        <div className={`h-4 rounded ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-medium">{count}</span>
    </div>
  );
}

export default function CostDashboard() {
  const { data } = usePolling(() => api.dashboardSummary(), 5000);
  if (!data) return <p className="text-sm text-slate-400">Loading...</p>;

  const maxStatus = Math.max(1, ...Object.values(data.by_status || {}) as number[]);
  const maxDomain = Math.max(1, ...Object.values(data.by_domain || {}) as number[]);
  const maxStage = Math.max(1, ...Object.values(data.by_route_stage || {}) as number[]);
  const tierColors: Record<string, string> = { T0: "bg-tier0", T1: "bg-tier1", T2: "bg-tier2", T3: "bg-tier3" };

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold">Impact &amp; Cost Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="Total Cases" value={String(data.total_cases)} />
        <StatTile label="Auto-Resolution Rate" value={`${data.auto_resolution_rate_pct}%`} hint="resolved with zero human touch" />
        <StatTile label="Approval Override Rate" value={`${data.approval_override_rate_pct}%`} hint="rejected or sent back" />
        <StatTile label="Blended Cost / Decision" value={`₹${data.blended_cost_per_decision_inr}`}
                   hint={`vs ₹${data.naive_all_frontier_cost_per_decision_inr} all-frontier baseline`} />
      </div>

      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
        Measured <strong>{data.cost_savings_pct}%</strong> cost reduction vs. an all-frontier-model baseline, from real
        traffic through this demo instance — not an assumption. Total blended spend so far: ₹{data.total_blended_cost_inr}.
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Case Status</h2>
          {Object.entries(data.by_status || {}).map(([k, v]) => (
            <BarRow key={k} label={k} count={v as number} max={maxStatus} colorClass="bg-slate-700" />
          ))}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Cases by Domain</h2>
          {Object.entries(data.by_domain || {}).map(([k, v]) => (
            <BarRow key={k} label={k} count={v as number} max={maxDomain} colorClass="bg-sky-600" />
          ))}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Triage Route Stage</h2>
          <p className="mb-2 text-xs text-slate-400">This is the whole cost-cascade story: how much volume each stage disposed of.</p>
          {Object.entries(data.by_route_stage || {}).map(([k, v]) => (
            <BarRow key={k} label={k} count={v as number} max={maxStage} colorClass="bg-indigo-600" />
          ))}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Cost by Risk Tier</h2>
          <table className="w-full text-xs">
            <thead className="text-left text-slate-400"><tr><th className="pb-1">Tier</th><th className="pb-1">Cases</th><th className="pb-1">Total ₹</th></tr></thead>
            <tbody>
              {Object.entries(data.by_tier || {}).map(([tier, stats]: [string, any]) => (
                <tr key={tier} className="border-t border-slate-100">
                  <td className="py-1"><span className={`inline-block h-2 w-2 rounded-full ${tierColors[tier] || "bg-slate-400"} mr-2`} />{tier}</td>
                  <td className="py-1">{stats.count}</td>
                  <td className="py-1">{stats.total_cost_inr.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
