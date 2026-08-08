import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { DomainBadge, OutcomeBadge, StatusBadge } from "../components/Badges";

const STATUS_FILTERS = ["", "APPROVAL_PENDING", "RESOLVE", "ESCALATE"];

export default function LiveQueue() {
  const [statusFilter, setStatusFilter] = useState("");
  const { data: cases, loading } = usePolling(() => api.listCases({ status: statusFilter || undefined, limit: 50 }), 4000);

  const [customerRef, setCustomerRef] = useState("cus_tok_1000");
  const [text, setText] = useState("My refund for order #ORD-4471 hasn't come through yet, please check.");
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function createAndProcess(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLastResult(null);
    try {
      const ingressed = await api.ingressTicket({ customer_ref: customerRef, text });
      const processed = await api.processEvent(ingressed.event_id);
      setLastResult(`Case ${processed.case_id} -> ${processed.status}`);
    } catch (err: any) {
      setLastResult(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Create a ticket (demo ingress)</h2>
        <form onSubmit={createAndProcess} className="flex flex-col gap-2 sm:flex-row">
          <input value={customerRef} onChange={(e) => setCustomerRef(e.target.value)} placeholder="customer_ref"
                 className="w-40 rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="ticket text"
                 className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <button type="submit" disabled={submitting}
                  className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
            {submitting ? "Processing..." : "Submit & Process"}
          </button>
        </form>
        {lastResult && <p className="mt-2 text-xs text-slate-500">{lastResult}</p>}
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Live Queue</h1>
        <div className="flex gap-1">
          {STATUS_FILTERS.map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)}
                    className={`rounded-md px-3 py-1 text-xs font-medium ${statusFilter === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {s || "All"}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Case</th>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Outcome</th>
              <th className="px-4 py-2">Triage stage</th>
              <th className="px-4 py-2">Cost (₹)</th>
              <th className="px-4 py-2">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(cases || []).map((c) => (
              <tr key={c.case_id} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-mono text-xs">
                  <Link to={`/cases/${c.case_id}`} className="text-sky-600 hover:underline">{c.case_id.slice(0, 18)}...</Link>
                  <span className="ml-2 text-slate-400">{c.customer_ref}</span>
                </td>
                <td className="px-4 py-2"><DomainBadge domain={c.domain} /></td>
                <td className="px-4 py-2"><StatusBadge status={c.status} /></td>
                <td className="px-4 py-2">{c.risk_decision?.outcome ? <OutcomeBadge outcome={c.risk_decision.outcome} /> : "—"}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{c.triage_stage || "—"}</td>
                <td className="px-4 py-2 text-xs">{Number(c.cost_inr).toFixed(4)}</td>
                <td className="px-4 py-2 text-xs text-slate-400">{new Date(c.updated_at).toLocaleTimeString()}</td>
              </tr>
            ))}
            {!loading && (cases || []).length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">No cases yet — submit a ticket above.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
