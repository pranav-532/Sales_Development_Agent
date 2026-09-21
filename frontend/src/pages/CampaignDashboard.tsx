import type { ReactNode } from "react";
import RunCampaignPanel from "@/components/RunCampaignPanel";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarCheck,
  Check,
  CheckCircle2,
  FileText,
  Info,
  MessageSquare,
  Pause,
  Pencil,
  Play,
  Send,
  Users,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import { useControl } from "@/context/ControlContext";
import { useCampaignData } from "@/hooks/useCampaignData";
import type { ActivityStatus, AgentKey, Channel, Funnel } from "@/types";

const channelLabels: Record<Channel, string> = {
  linkedin: "LinkedIn",
  email: "Email",
  sms: "SMS",
  voice: "Voice calls",
};

const agentRole: Record<AgentKey, string> = {
  icp_fitment: "Qualifies or rejects prospects",
  research: "Builds prospect context",
  strategy: "Decides when, where and how",
  personalisation: "Writes contextual outreach",
  conversation: "Reads replies, picks next step",
  voice: "Runs and qualifies calls",
  followup: "Times follow-ups, knows when to stop",
};

const stages: { key: keyof Funnel; label: string }[] = [
  { key: "discovered", label: "Discovered" },
  { key: "researched", label: "Researched" },
  { key: "qualified", label: "Qualified" },
  { key: "contacted", label: "Contacted" },
  { key: "engaged", label: "Engaged" },
  { key: "meeting", label: "Meeting" },
  { key: "opportunity", label: "Opportunity" },
];

const activityStyles: Record<ActivityStatus, { label: string; cls: string }> = {
  completed: { label: "Completed", cls: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  failed: { label: "Failed", cls: "border-red-200 bg-red-50 text-red-700" },
  pending_approval: { label: "Needs approval", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  escalated: { label: "Escalated", cls: "border-violet-200 bg-violet-50 text-violet-700" },
    approved: { label: "Approved", cls: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  rejected: { label: "Rejected", cls: "border-stone-200 bg-stone-50 text-stone-600" },
};

const stateStyles: Record<string, string> = {
  Running: "border-emerald-200 bg-emerald-50 text-emerald-700",
  Paused: "border-amber-200 bg-amber-50 text-amber-800",
  Idle: "border-slate-200 bg-slate-50 text-slate-600",
  "Not enabled": "border-stone-200 bg-stone-50 text-stone-500",
};

const pct = (n: number, d: number) => (d ? `${((n / d) * 100).toFixed(1)}%` : "0%");

function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex flex-col rounded-xl border bg-card ${className}`}>
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Pill({ cls, children }: { cls: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

function FunnelChart({ funnel }: { funnel: Funnel }) {
  const total = funnel.discovered;
  const widths = stages.map((s) => {
    const v = funnel[s.key];
    return v > 0 ? Math.max(Math.sqrt(v / total) * 100, 10) : 0;
  });

  return (
    <div className="space-y-0.5">
      {stages.map((s, i) => {
        const value = funnel[s.key];
        const prev = i === 0 ? null : funnel[stages[i - 1].key];
        const w = widths[i];
        const next = i < stages.length - 1 ? widths[i + 1] : w * 0.8;
        const topInset = (100 - w) / 2;
        const bottomInset = (100 - next) / 2;
        const clip = `polygon(${topInset}% 0, ${100 - topInset}% 0, ${100 - bottomInset}% 100%, ${bottomInset}% 100%)`;

        return (
          <div key={s.key} className="grid grid-cols-[84px_1fr_88px] items-center gap-3">
            <div className="text-sm">{s.label}</div>
            <div
              className="h-9 bg-primary transition-all duration-500"
              style={{ clipPath: clip, opacity: 1 - i * 0.1 }}
            />
            <div className="text-right">
              <div className="text-sm font-medium tabular-nums">{value.toLocaleString()}</div>
              {prev !== null && (
                <div className="text-[11px] tabular-nums text-muted-foreground">
                  {pct(value, prev)}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DonutChart({
  positive,
  neutral,
  negative,
}: {
  positive: number;
  neutral: number;
  negative: number;
}) {
  const total = positive + neutral + negative;
  const cx = 160;
  const cy = 95;
  const r = 58;
  const sw = 18;
  const capDeg = (sw / 2 / r) * (180 / Math.PI);
  const gapDeg = 5;

  const point = (deg: number, radius: number) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + radius * Math.sin(rad), y: cy - radius * Math.cos(rad) };
  };
  const arc = (from: number, to: number) => {
    const a = point(from, r);
    const b = point(to, r);
    const large = to - from > 180 ? 1 : 0;
    return `M ${a.x} ${a.y} A ${r} ${r} 0 ${large} 1 ${b.x} ${b.y}`;
  };

  const raw = [
    { label: "Positive", value: positive, color: "#10b981" },
    { label: "Neutral", value: neutral, color: "#cbd5e1" },
    { label: "Negative", value: negative, color: "#f87171" },
  ];
  const visible = raw.filter((s) => s.value > 0);
  let start = 0;
  const segments = visible.map((s) => {
    const sweep = (s.value / total) * 360;
    const seg = { ...s, start, end: start + sweep, mid: start + sweep / 2 };
    start += sweep;
    return seg;
  });
  const pad = segments.length > 1 ? capDeg + gapDeg / 2 : 0;

  return (
    <div className="flex flex-col items-center gap-4">
      <svg viewBox="0 0 320 190" className="w-full max-w-xs">
        {total === 0 && (
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="currentColor"
            strokeWidth={sw}
            className="text-muted"
          />
        )}

        {segments.length === 1 && (
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={segments[0].color}
            strokeWidth={sw}
          />
        )}

        {segments.length > 1 &&
          segments.map((s) => {
            const from = s.start + pad;
            const to = Math.max(s.end - pad, from + 0.01);
            return (
              <path
                key={s.label}
                d={arc(from, to)}
                fill="none"
                stroke={s.color}
                strokeWidth={sw}
                strokeLinecap="round"
              />
            );
          })}

        {segments.map((s) => {
          const p = point(s.mid, r);
          const e = point(s.mid, r + sw / 2 + 14);
          const side = Math.sin((s.mid * Math.PI) / 180) >= 0 ? 1 : -1;
          const h = e.x + side * 14;
          return (
            <g key={`label-${s.label}`}>
              <polyline
                points={`${p.x},${p.y} ${e.x},${e.y} ${h},${e.y}`}
                fill="none"
                stroke={s.color}
                strokeWidth={1.5}
              />
              <circle cx={p.x} cy={p.y} r={3.5} fill={s.color} stroke="white" strokeWidth={1.5} />
              <text
                x={h + side * 5}
                y={e.y}
                textAnchor={side > 0 ? "start" : "end"}
                dominantBaseline="middle"
                fontSize="12"
                fill="currentColor"
                className="text-foreground"
              >
                {pct(s.value, total)}
              </text>
            </g>
          );
        })}

        <text
          x={cx}
          y={cy + 2}
          textAnchor="middle"
          fontSize="22"
          fontWeight="600"
          fill="currentColor"
          className="text-foreground"
        >
          {total > 0 ? pct(positive, total) : "0"}
        </text>
        <text
          x={cx}
          y={cy + 20}
          textAnchor="middle"
          fontSize="11"
          fill="currentColor"
          opacity={0.6}
          className="text-foreground"
        >
          {total > 0 ? "positive" : "replies"}
        </text>
      </svg>

      <div className="flex w-full items-center justify-center gap-5">
        {raw.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5 text-sm">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
            <span>{s.label}</span>
            <span className="tabular-nums text-muted-foreground">{s.value}</span>
          </div>
        ))}
      </div>
      <div className="text-xs text-muted-foreground">{total} replies in total</div>
    </div>
  );
}

export default function CampaignDashboard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { campaigns, killSwitch, setStatus, toggleAgent, toggleChannel, reps: allReps } = useControl();
  const data = useCampaignData(id);

  const c = campaigns.find((x) => x.id === id);

  if (!c) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Campaign not found</h1>
        <Button variant="outline" onClick={() => navigate("/campaigns")}>
          Back to campaigns
        </Button>
      </div>
    );
  }

  const { stats, decide } = data;
  const events = data.events.filter((e) => e.campaignId === c.id);
  const running = c.status === "live" && !killSwitch;
  const editable = c.status !== "completed" && c.status !== "archived";
  const reps = allReps.filter((r) => c.repIds.includes(r.id));
  const activeChannels = c.channels.filter((ch) => ch.enabled && !ch.paused);

  const pending = events.filter((e) => e.status === "pending_approval").length;
  const escalations = events.filter((e) => e.status === "escalated").length;
  const { positive, negative, neutral } = stats.outcomes;
  const activeWorkflows = running ? stats.workflows.active : 0;

  const attention = events
    .filter((e) => e.status === "pending_approval" || e.status === "escalated" || e.status === "failed")
    .slice(0, 5);

  const steps = stages
    .slice(1)
    .map((s, i) => {
      const prev = c.funnel[stages[i].key];
      return {
        from: stages[i].label,
        to: s.label,
        prev,
        rate: prev ? c.funnel[s.key] / prev : 0,
      };
    })
    .filter((s) => s.prev > 0);
  const weakest =
    steps.length > 0 ? steps.reduce((a, b) => (b.rate < a.rate ? b : a)) : null;

  const checklist = [
    { ok: !!c.icp && c.targetRoles.length > 0, label: "ICP and target roles are defined" },
    { ok: c.channels.some((ch) => ch.enabled), label: "At least one channel is enabled" },
    { ok: c.agents.some((a) => a.enabled), label: "Agents are enabled" },
    { ok: c.repIds.length > 0, label: "A rep is assigned to send under" },
    { ok: c.activePromptVersion > 0, label: `Prompt version v${c.activePromptVersion} is active` },
  ];

  let banner: { cls: string; text: string } | null = null;
  if (killSwitch && c.status === "live") {
    banner = {
      cls: "border-red-200 bg-red-50 text-red-800",
      text: "The global kill switch is ON. This campaign is Live, but no agent can take any external action until the switch is released.",
    };
  } else if (c.status === "paused") {
    banner = {
      cls: "border-amber-200 bg-amber-50 text-amber-900",
      text: "This campaign is paused. All autonomous execution has stopped and no new outreach will fire. Prospect and conversation data is kept, and you can resume any time.",
    };
  } else if (c.status === "draft") {
    banner = {
      cls: "border-slate-200 bg-slate-50 text-slate-700",
      text: "Draft campaigns cannot send autonomous outreach. Review the checklist below, then activate.",
    };
  } else if (c.status === "completed") {
    banner = {
      cls: "border-sky-200 bg-sky-50 text-sky-800",
      text: "This campaign is completed. Agents are stopped and the full history and analytics stay available.",
    };
  } else if (c.status === "archived") {
    banner = {
      cls: "border-stone-200 bg-stone-50 text-stone-700",
      text: "This campaign is archived and read-only. Restore it from the campaigns list to make changes.",
    };
  }

  const rowState = (enabled: boolean, paused: boolean) =>
    !enabled ? "Not enabled" : paused ? "Paused" : running ? "Running" : "Idle";

  return (
    <div className="space-y-6">
      <Link
        to="/campaigns"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        All campaigns
      </Link>

      <div className="rounded-xl border bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold">{c.name}</h1>
              <StatusBadge status={c.status} halted={killSwitch} />
            </div>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{c.description}</p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => navigate(`/prompts?campaign=${c.id}`)}>
              <FileText className="mr-1.5 h-4 w-4" />
              Prompts
            </Button>
            {editable && (
              <Button variant="outline" onClick={() => navigate(`/campaigns/${c.id}/edit`)}>
                <Pencil className="mr-1.5 h-4 w-4" />
                Edit
              </Button>
            )}
            {c.status === "live" && (
              <Button
                size="lg"
                className="h-11 bg-red-400 px-6 text-white hover:bg-red-500"
                onClick={() => setStatus(c.id, "paused")}
              >
                <Pause className="mr-2 h-4 w-4" />
                Pause campaign
              </Button>
            )}
            {c.status === "paused" && (
              <Button
                size="lg"
                className="h-11 px-6"
                disabled={killSwitch}
                onClick={() => setStatus(c.id, "live")}
              >
                <Play className="mr-2 h-4 w-4" />
                Resume campaign
              </Button>
            )}
            {c.status === "draft" && (
              <Button
                size="lg"
                className="h-11 px-6"
                disabled={killSwitch}
                onClick={() => setStatus(c.id, "live")}
              >
                <Play className="mr-2 h-4 w-4" />
                Activate campaign
              </Button>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t pt-5 text-sm md:grid-cols-3 xl:grid-cols-6">
          <div>
            <div className="text-xs text-muted-foreground">Owner</div>
            <div className="font-medium">{c.owner}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">ICP</div>
            <div className="font-medium">{c.icp}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Geography</div>
            <div className="font-medium">{c.geography}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Target roles</div>
            <div className="font-medium">{c.targetRoles.join(", ")}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Active channels</div>
            <div className="font-medium">
              {activeChannels.length
                ? activeChannels.map((ch) => channelLabels[ch.channel]).join(", ")
                : "None"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Reps</div>
            {reps.length === 0 ? (
              <div className="text-muted-foreground">Unassigned</div>
            ) : (
              <div className="mt-0.5 flex -space-x-2">
                {reps.map((r) => (
                  <span
                    key={r.id}
                    title={r.name}
                    className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-card bg-accent text-[10px] font-semibold text-accent-foreground"
                  >
                    {r.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <RunCampaignPanel />
      {banner && (
        <div className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${banner.cls}`}>
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{banner.text}</span>
        </div>
      )}

      {c.status === "draft" && (
        <Panel title="Before you activate" subtitle="Checked against this campaign's configuration">
          <ul className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {checklist.map((item) => (
              <li key={item.label} className="flex items-center gap-2 text-sm">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full ${
                    item.ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {item.ok ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <span className="text-xs font-bold">!</span>
                  )}
                </span>
                <span className={item.ok ? "" : "text-amber-900"}>{item.label}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Prospects discovered"
          value={c.funnel.discovered.toLocaleString()}
          sub={`${c.funnel.qualified.toLocaleString()} qualified`}
          icon={<Users className="h-6 w-6 text-emerald-600" />}
          tone="bg-emerald-100"
        />
        <StatCard
          label="Outreach sent"
          value={c.outreachCount.toLocaleString()}
          sub={`${stats.followups} follow-ups`}
          icon={<Send className="h-6 w-6 text-sky-600" />}
          tone="bg-sky-100"
        />
        <StatCard
          label="Reply rate"
          value={pct(c.funnel.engaged, c.funnel.contacted)}
          sub={`${c.funnel.engaged} engaged of ${c.funnel.contacted} contacted`}
          icon={<MessageSquare className="h-6 w-6 text-orange-600" />}
          tone="bg-orange-100"
        />
        <StatCard
          label="Meetings booked"
          value={String(c.meetings)}
          sub={`${pct(c.meetings, c.funnel.contacted)} of contacted`}
          icon={<CalendarCheck className="h-6 w-6 text-violet-600" />}
          tone="bg-violet-100"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Prospect funnel" subtitle="Percentage is conversion from the previous stage">
          {c.funnel.discovered === 0 ? (
            <div className="p-10 text-center text-sm text-muted-foreground">
              No prospects yet. They will appear here once the campaign goes live.
            </div>
          ) : (
            <>
              <div className="p-5">
                <FunnelChart funnel={c.funnel} />
              </div>
              <div className="mt-auto space-y-1 border-t px-5 py-3 text-xs text-muted-foreground">
                {weakest && (
                  <div>
                    Weakest step:{" "}
                    <span className="font-medium text-foreground">
                      {weakest.from} to {weakest.to}
                    </span>{" "}
                    ({(weakest.rate * 100).toFixed(1)}% convert)
                  </div>
                )}
                <div>
                  Overall:{" "}
                  <span className="font-medium text-foreground">
                    {pct(c.funnel.opportunity, c.funnel.discovered)}
                  </span>{" "}
                  of discovered prospects become opportunities
                </div>
                <div>Shape is scaled so small stages stay visible. Exact counts are on the right.</div>
              </div>
            </>
          )}
        </Panel>

        <Panel title="Outcomes" subtitle="Reply sentiment and conversion">
          <div className="space-y-5 p-5">
            <DonutChart positive={positive} neutral={neutral} negative={negative} />
            <dl className="space-y-3 border-t pt-4 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Positive reply rate</dt>
                <dd className="font-medium tabular-nums">{pct(positive, c.funnel.contacted)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Meeting rate</dt>
                <dd className="font-medium tabular-nums">{pct(c.meetings, c.funnel.contacted)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Qualified opportunities</dt>
                <dd className="font-medium tabular-nums">{c.funnel.opportunity}</dd>
              </div>
            </dl>
          </div>
        </Panel>

        <Panel title="Needs attention" subtitle="Approvals, escalations and failures">
          {attention.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-10 text-center text-sm text-muted-foreground">
              <CheckCircle2 className="h-8 w-8 text-emerald-500" />
              All clear. Nothing needs a human right now.
            </div>
          ) : (
            <ul className="divide-y">
              {attention.map((e) => {
                const agent = c.agents.find((a) => a.key === e.agentKey);
                const style = activityStyles[e.status];
                return (
                  <li key={e.id} className="space-y-1.5 px-5 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-sm">{e.action}</div>
                      <Pill cls={style.cls}>{style.label}</Pill>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {agent?.name ?? e.agentKey} · {e.time}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Channels" subtitle="Outreach activity and channel pause">
          <ul className="divide-y">
            {c.channels.map((ch) => {
              const state = rowState(ch.enabled, ch.paused);
              return (
                <li key={ch.channel} className="flex items-center gap-3 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{channelLabels[ch.channel]}</div>
                    <div className="text-xs text-muted-foreground">
                      {stats.outreach[ch.channel].toLocaleString()} sent
                      {ch.enabled ? `, limit ${ch.dailyLimit}/day` : ""}
                    </div>
                  </div>
                  <Pill cls={stateStyles[state]}>{state}</Pill>
                  <Switch
                    checked={ch.enabled && !ch.paused}
                    disabled={!ch.enabled || !editable}
                    onCheckedChange={() => toggleChannel(c.id, ch.channel)}
                  />
                </li>
              );
            })}
            <li className="flex items-center justify-between px-5 py-3 text-sm">
              <span className="text-muted-foreground">Follow-ups sent</span>
              <span className="font-medium tabular-nums">{stats.followups}</span>
            </li>
          </ul>
        </Panel>

        <Panel title="Agents" subtitle="Pause one agent, the rest keep going">
          <ul className="divide-y">
            {c.agents.map((a) => {
              const state = rowState(a.enabled, a.paused);
              return (
                <li key={a.key} className="flex items-center gap-3 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{a.name}</div>
                    <div className="truncate text-xs text-muted-foreground">{agentRole[a.key]}</div>
                  </div>
                  <Pill cls={stateStyles[state]}>{state}</Pill>
                  <Switch
                    checked={a.enabled && !a.paused}
                    disabled={!a.enabled || !editable}
                    onCheckedChange={() => toggleAgent(c.id, a.key)}
                  />
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel title="Agent workflows" subtitle="Live execution status">
          <div className="grid grid-cols-3 divide-x border-b">
            <div className="p-4 text-center">
              <div className="text-2xl font-semibold tabular-nums">{activeWorkflows}</div>
              <div className="text-xs text-muted-foreground">Active</div>
            </div>
            <div className="p-4 text-center">
              <div className="text-2xl font-semibold tabular-nums">{stats.workflows.completed}</div>
              <div className="text-xs text-muted-foreground">Completed</div>
            </div>
            <div className="p-4 text-center">
              <div className="text-2xl font-semibold tabular-nums text-red-600">
                {stats.workflows.failed}
              </div>
              <div className="text-xs text-muted-foreground">Failed</div>
            </div>
          </div>
          <dl className="space-y-3 p-5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Pending approvals</dt>
              <dd className="font-medium tabular-nums">{pending}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Escalations to reps</dt>
              <dd className="font-medium tabular-nums">{escalations}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Active prompt version</dt>
              <dd className="font-medium">v{c.activePromptVersion}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Last updated</dt>
              <dd className="font-medium">{c.updatedAt}</dd>
            </div>
          </dl>
        </Panel>
      </div>

      <Panel
        title="Agent activity"
        subtitle="Each action records the prompt version that was active, so any outcome can be traced to its configuration"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">When</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Prompt</TableHead>
              <TableHead className="pr-5">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  No agent activity yet.
                </TableCell>
              </TableRow>
            )}
            {events.map((e) => {
              const agent = c.agents.find((a) => a.key === e.agentKey);
              const style = activityStyles[e.status];
              return (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap pl-5 text-muted-foreground">
                    {e.time}
                  </TableCell>
                  <TableCell className="whitespace-nowrap font-medium">
                    {agent?.name ?? e.agentKey}
                  </TableCell>
                  <TableCell className="max-w-md whitespace-normal">{e.action}</TableCell>
                  <TableCell>{e.channel ? channelLabels[e.channel] : "-"}</TableCell>
                  <TableCell>
                    <Pill
                      cls={
                        e.promptVersion === c.activePromptVersion
                          ? "border-orange-200 bg-orange-50 text-orange-700"
                          : "border-stone-200 bg-stone-50 text-stone-600"
                      }
                    >
                      v{e.promptVersion}
                    </Pill>
                  </TableCell>
                  <TableCell className="pr-5">
                    {e.status === "pending_approval" ? (
                      <div className="flex items-center gap-2">
                        <Button size="sm" onClick={() => void decide(e.id, "approved")}>
                          <Check className="mr-1 h-3.5 w-3.5" />
                          Approve
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => void decide(e.id, "rejected")}>
                          <X className="mr-1 h-3.5 w-3.5" />
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <Pill cls={style.cls}>{style.label}</Pill>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Panel>
    </div>
  );
}