const STATUS_COLORS: Record<string, string> = {
  INTAKE: "bg-slate-200 text-slate-700",
  CONTEXT_GATHER: "bg-slate-200 text-slate-700",
  PLAN: "bg-slate-200 text-slate-700",
  ACT: "bg-slate-200 text-slate-700",
  SELF_VERIFY: "bg-indigo-100 text-indigo-700",
  RISK_GATE: "bg-indigo-100 text-indigo-700",
  APPROVAL_PENDING: "bg-amber-100 text-amber-700",
  EXECUTE: "bg-sky-100 text-sky-700",
  RESOLVE: "bg-emerald-100 text-emerald-700",
  ESCALATE: "bg-rose-100 text-rose-700",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[status] || "bg-slate-200 text-slate-700"}`}>
      {status}
    </span>
  );
}

const TIER_COLORS: Record<string, string> = {
  T0: "bg-tier0/10 text-tier0",
  T1: "bg-tier1/10 text-tier1",
  T2: "bg-tier2/10 text-tier2",
  T3: "bg-tier3/10 text-tier3",
};

export function TierBadge({ tier }: { tier: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${TIER_COLORS[tier] || "bg-slate-200 text-slate-700"}`}>
      {tier}
    </span>
  );
}

const OUTCOME_COLORS: Record<string, string> = {
  AUTO_EXECUTE: "bg-emerald-100 text-emerald-700",
  NEEDS_APPROVAL: "bg-amber-100 text-amber-700",
  DUAL_APPROVAL: "bg-orange-100 text-orange-700",
  ESCALATE: "bg-rose-100 text-rose-700",
  DENY: "bg-rose-100 text-rose-700",
};

export function OutcomeBadge({ outcome }: { outcome: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${OUTCOME_COLORS[outcome] || "bg-slate-200 text-slate-700"}`}>
      {outcome}
    </span>
  );
}

export function DomainBadge({ domain }: { domain: string }) {
  return <span className="inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{domain}</span>;
}
