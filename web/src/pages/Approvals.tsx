import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { useAuth } from "../lib/auth";
import { TierBadge } from "../components/Badges";

export default function Approvals() {
  const { user } = useAuth();
  const { data: approvals, refresh } = usePolling(() => api.listApprovals(), 4000);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reasonById, setReasonById] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  async function decide(approvalId: string, decision: "approve" | "reject" | "send_back") {
    setBusyId(approvalId);
    setMessage(null);
    try {
      const reason = reasonById[approvalId] || (decision === "approve" ? "Looks correct, approving." : "Not justified.");
      const result = await api.decideApproval(approvalId, { approver_id: user!.username, decision, reason });
      setMessage(`${decision.toUpperCase()} recorded. Case is now ${result.case?.status}.`);
      await refresh();
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Approval Inbox</h1>
        <p className="text-xs text-slate-400">Signed in as <span className="font-medium">{user?.username}</span> — the maker can never also be the checker for the same proposal (enforced in the database).</p>
      </div>
      {message && <div className="rounded-md bg-slate-100 px-3 py-2 text-sm">{message}</div>}

      <div className="space-y-3">
        {(approvals || []).map((a) => (
          <div key={a.approval_id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <TierBadge tier={a.tier || "T2"} />
                <span className="font-mono text-xs text-slate-400">slot {a.slot_no} · {a.case_domain}</span>
                <Link to={`/cases/${a.case_id}`} className="text-xs text-sky-600 hover:underline">view case &rarr;</Link>
              </div>
              <span className="text-xs text-slate-400">SLA: {new Date(a.sla_deadline).toLocaleString()}</span>
            </div>

            {a.proposal && (
              <div className="mt-3">
                <p className="text-sm font-semibold">
                  {a.proposal.action_type}
                  {a.proposal.args?.amount_inr ? ` — ₹${Number(a.proposal.args.amount_inr).toLocaleString()}` : ""}
                </p>
                <p className="mt-1 text-xs text-slate-600">{a.proposal.reasoning}</p>
                <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
                  {(a.proposal.evidence || []).map((e: any, i: number) => (
                    <li key={i}>evidence: {e.type} — {e.ref}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                placeholder="reason (required to reject)"
                value={reasonById[a.approval_id] || ""}
                onChange={(e) => setReasonById((prev) => ({ ...prev, [a.approval_id]: e.target.value }))}
                className="flex-1 min-w-[200px] rounded-md border border-slate-300 px-3 py-1.5 text-xs"
              />
              <button disabled={busyId === a.approval_id} onClick={() => decide(a.approval_id, "approve")}
                      className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
                Approve
              </button>
              <button disabled={busyId === a.approval_id} onClick={() => decide(a.approval_id, "reject")}
                      className="rounded-md bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50">
                Reject
              </button>
              <button disabled={busyId === a.approval_id} onClick={() => decide(a.approval_id, "send_back")}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50">
                Send back
              </button>
            </div>
          </div>
        ))}
        {(approvals || []).length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
            No pending approvals right now.
          </div>
        )}
      </div>
    </div>
  );
}
