import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../lib/api";
import { usePolling } from "../lib/usePolling";
import { DomainBadge, OutcomeBadge, StatusBadge, TierBadge } from "../components/Badges";

function JsonBlock({ value }: { value: unknown }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1">
      <button onClick={() => setOpen((o) => !o)} className="text-xs text-sky-600 hover:underline">
        {open ? "hide raw JSON" : "show raw JSON"}
      </button>
      {open && (
        <pre className="mt-1 max-h-64 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  );
}

function TimelineNode({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="relative pb-6 pl-8">
      <span className="absolute left-0 top-1 h-3 w-3 rounded-full border-2 border-slate-900 bg-white" />
      <span className="absolute left-[5px] top-4 h-full w-px bg-slate-200" />
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {subtitle && <span className="text-xs text-slate-400">{subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

export default function CaseTrace() {
  const { caseId } = useParams<{ caseId: string }>();
  const { data: kase } = usePolling(() => api.getCase(caseId!), 4000);
  const [auditExport, setAuditExport] = useState<any>(null);

  async function loadAuditExport() {
    const result = await api.auditExport(caseId!);
    setAuditExport(result);
  }

  if (!kase) return <p className="text-sm text-slate-400">Loading case...</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/queue" className="text-xs text-sky-600 hover:underline">&larr; back to queue</Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-sm text-slate-500">{kase.case_id}</h1>
          <DomainBadge domain={kase.domain} />
          <StatusBadge status={kase.status} />
          {kase.risk_decision?.tier && <TierBadge tier={kase.risk_decision.tier} />}
          {kase.risk_decision?.outcome && <OutcomeBadge outcome={kase.risk_decision.outcome} />}
        </div>
        {kase.error && <p className="mt-2 text-sm text-rose-600">{kase.error}</p>}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-bold uppercase tracking-wide text-slate-500">Agent Trace</h2>

          <TimelineNode title="Triage" subtitle={kase.triage_stage}>
            <p className="text-xs text-slate-500">Cheap-first cascade decided the route at this stage — the whole cost story.</p>
          </TimelineNode>

          <TimelineNode title="Observations" subtitle={`${kase.observations?.length || 0} tool call(s)`}>
            {(kase.observations || []).map((obs: any, i: number) => (
              <div key={i} className="mt-1 rounded-md bg-slate-50 p-2 text-xs">
                <span className="font-mono font-medium">{obs.tool}</span>
                <JsonBlock value={obs.result} />
              </div>
            ))}
          </TimelineNode>

          <TimelineNode title="Proposal(s)" subtitle={`${kase.proposals?.length || 0} (revisions: ${kase.revisions})`}>
            {(kase.proposals || []).map((p: any, i: number) => (
              <div key={i} className="mt-1 rounded-md border border-slate-200 p-2 text-xs">
                <div className="font-medium">{p.action_type} — by {p.proposed_by}</div>
                <div className="mt-1 text-slate-500">{p.reasoning}</div>
                <JsonBlock value={p} />
              </div>
            ))}
          </TimelineNode>

          <TimelineNode title="Self-Verify">
            {kase.verifier_report?.verdict && (
              <div className="mt-1">
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
                  {kase.verifier_report.verdict}
                </span>
                <JsonBlock value={kase.verifier_report} />
              </div>
            )}
          </TimelineNode>

          <TimelineNode title="Risk Decision">
            {kase.risk_decision?.reason_plain && (
              <>
                <p className="mt-1 text-xs text-slate-600">{kase.risk_decision.reason_plain}</p>
                <p className="mt-1 text-xs text-slate-400">matched rules: {(kase.risk_decision.matched_rules || []).join(", ")}</p>
                <JsonBlock value={kase.risk_decision} />
              </>
            )}
          </TimelineNode>

          <TimelineNode title="Outcome" subtitle={kase.status}>
            <p className="text-xs text-slate-500">Final state — see Live Queue for the full list.</p>
          </TimelineNode>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">Cost</h2>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Tokens in</dt><dd>{kase.cost_tokens_in}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Tokens out</dt><dd>{kase.cost_tokens_out}</dd></div>
              <div className="flex justify-between font-semibold"><dt>Total (₹)</dt><dd>{Number(kase.cost_inr).toFixed(4)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Tool calls used</dt><dd>{kase.tool_calls_used} / {kase.max_tool_calls}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Revisions</dt><dd>{kase.revisions} / {kase.max_revisions}</dd></div>
            </dl>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">Auditor Mode</h2>
            <button onClick={loadAuditExport} className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800">
              Export signed audit trail
            </button>
            {auditExport && (
              <div className="mt-3 text-xs">
                <p>Decisions: {auditExport.decision_count}</p>
                <p>Ledger integrity: {auditExport.ledger_integrity?.valid ? "✅ valid" : "❌ broken"}</p>
                <p className="truncate text-slate-400">signature: {auditExport.signature}</p>
                <JsonBlock value={auditExport} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
