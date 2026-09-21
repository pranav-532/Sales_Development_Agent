import { useState, type KeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useControl } from "@/context/ControlContext";
import {
  AGENT_DEFS,
  APPROVAL_OPTIONS,
  CHANNEL_DEFS,
  ESCALATION_DEFS,
  OWNERS,
} from "@/lib/campaignDefaults";
import { cn } from "@/lib/utils";
import type { AgentKey, ApprovalMode, Campaign, Channel, EscalationKey } from "@/types";

interface FormState {
  name: string;
  description: string;
  owner: string;
  icp: string;
  geography: string;
  roles: string[];
  companyCriteria: string;
  exclusions: string;
  referenceProfiles: string;
  agents: Record<AgentKey, boolean>;
  qualifyThreshold: number;
  confidenceThreshold: number;
  approvalMode: ApprovalMode;
  escalateOn: EscalationKey[];
  channels: Record<Channel, { enabled: boolean; limit: string }>;
  repIds: string[];
  systemPrompt: string;
}

const buildInitial = (c?: Campaign): FormState => ({
  name: c?.name ?? "",
  description: c?.description ?? "",
  owner: c?.owner ?? OWNERS[0],
  icp: c?.icp ?? "",
  geography: c?.geography ?? "",
  roles: c?.targetRoles ?? [],
  companyCriteria: c?.companyCriteria ?? "",
  exclusions: c?.exclusions ?? "",
  referenceProfiles: c?.referenceProfiles ?? "",
  agents: Object.fromEntries(
    AGENT_DEFS.map((d) => [d.key, c ? (c.agents.find((a) => a.key === d.key)?.enabled ?? false) : true])
  ) as Record<AgentKey, boolean>,
  qualifyThreshold: c?.qualifyThreshold ?? 70,
  confidenceThreshold: c?.confidenceThreshold ?? 60,
  approvalMode: c?.approvalMode ?? "first_touch",
  escalateOn: c?.escalateOn ?? ["pricing", "human_request"],
  channels: Object.fromEntries(
    CHANNEL_DEFS.map((d) => {
      const ch = c?.channels.find((x) => x.channel === d.key);
      return [
        d.key,
        {
          enabled: c ? (ch?.enabled ?? false) : d.key === "linkedin" || d.key === "email",
          limit: String(ch && ch.dailyLimit > 0 ? ch.dailyLimit : d.defaultLimit),
        },
      ];
    })
  ) as Record<Channel, { enabled: boolean; limit: string }>,
  repIds: c?.repIds ?? [],
  systemPrompt: "",
});

const toLimit = (v: string) => {
  const n = parseInt(v, 10);
  return Number.isNaN(n) || n < 0 ? 0 : n;
};

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {error ? (
        <p className="text-xs text-red-600">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

function RangeField({
  label,
  hint,
  value,
  onChange,
  disabled,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (n: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">{label}</label>
        <span className="text-sm font-medium tabular-nums">{value}</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary"
      />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function FormBody({ campaign }: { campaign?: Campaign }) {
  const navigate = useNavigate();
  const { campaigns, killSwitch, prompts, addCampaign, updateCampaign, reps } = useControl();
  const isEdit = !!campaign;

  const [f, setF] = useState<FormState>(() => buildInitial(campaign));
  const [roleInput, setRoleInput] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setF((p) => ({ ...p, [key]: value }));

  const addRole = () => {
    const v = roleInput.trim().replace(/,$/, "").trim();
    if (v && !f.roles.some((r) => r.toLowerCase() === v.toLowerCase())) {
      set("roles", [...f.roles, v]);
    }
    setRoleInput("");
  };

  const onRoleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addRole();
    } else if (e.key === "Backspace" && !roleInput && f.roles.length) {
      set("roles", f.roles.slice(0, -1));
    }
  };

  const toggleEscalation = (key: EscalationKey) =>
    set(
      "escalateOn",
      f.escalateOn.includes(key) ? f.escalateOn.filter((k) => k !== key) : [...f.escalateOn, key]
    );

  const toggleRep = (id: string) =>
    set("repIds", f.repIds.includes(id) ? f.repIds.filter((r) => r !== id) : [...f.repIds, id]);

  const starterPrompt = () =>
    set(
      "systemPrompt",
      [
        `You are an SDR for our product, reaching ${
          f.roles.length ? f.roles.join(" and ") : "prospects"
        } in the ${f.icp.trim() || "target"} segment${
          f.geography.trim() ? ` in ${f.geography.trim()}` : ""
        }.`,
        "Lead with the problem the prospect is likely facing, and cite a relevant case study retrieved from the knowledge base.",
        "Never claim features, certifications or results we do not have.",
        f.escalateOn.includes("pricing") ? "Escalate pricing questions to a human rep." : "",
        "If the prospect asks to stop, add them to the do-not-contact list.",
      ]
        .filter(Boolean)
        .join("\n")
    );

  const nameTaken = campaigns.some(
    (x) => x.id !== campaign?.id && x.name.trim().toLowerCase() === f.name.trim().toLowerCase()
  );
  const errors = {
    name: !f.name.trim()
      ? "Give the campaign a name"
      : nameTaken
        ? "Another campaign already uses this name"
        : "",
    icp: !f.icp.trim() ? "Describe the ICP" : "",
  };
  const hasErrors = Boolean(errors.name || errors.icp);
  const show = (msg: string) => (submitted ? msg : "");

  const hasPrompt = campaign
    ? prompts.some((p) => p.campaignId === campaign.id && p.agentKey === "system" && p.isActive)
    : f.systemPrompt.trim().length > 0;

  const checks = [
    { ok: f.name.trim().length > 0 && !nameTaken, label: "Campaign has a unique name" },
    { ok: f.icp.trim().length > 0 && f.roles.length > 0, label: "ICP and target roles are defined" },
    { ok: CHANNEL_DEFS.some((d) => f.channels[d.key].enabled), label: "At least one channel is enabled" },
    { ok: AGENT_DEFS.some((d) => f.agents[d.key]), label: "At least one agent is enabled" },
    { ok: f.repIds.length > 0, label: "A rep is assigned to send under" },
    { ok: hasPrompt, label: "System prompt is set" },
  ];
  const ready = checks.every((c) => c.ok);

  const save = async (goLive: boolean) => {
    setSubmitted(true);
    if (hasErrors) return;

    const data = {
      name: f.name.trim(),
      description: f.description.trim(),
      owner: f.owner,
      icp: f.icp.trim(),
      geography: f.geography.trim(),
      targetRoles: f.roles,
      companyCriteria: f.companyCriteria.trim(),
      exclusions: f.exclusions.trim(),
      referenceProfiles: f.referenceProfiles.trim(),
      approvalMode: f.approvalMode,
      qualifyThreshold: f.qualifyThreshold,
      confidenceThreshold: f.confidenceThreshold,
      escalateOn: f.escalateOn,
      agents: AGENT_DEFS.map((d) => ({
        key: d.key,
        name: d.name,
        enabled: f.agents[d.key],
        paused: campaign?.agents.find((a) => a.key === d.key)?.paused ?? false,
      })),
      channels: CHANNEL_DEFS.map((d) => ({
        channel: d.key,
        enabled: f.channels[d.key].enabled,
        paused: campaign?.channels.find((ch) => ch.channel === d.key)?.paused ?? false,
        dailyLimit: toLimit(f.channels[d.key].limit),
      })),
      repIds: f.repIds,
    };

    if (campaign) {
      if (await updateCampaign(campaign.id, data)) navigate(`/campaigns/${campaign.id}`);
    } else {
      const id = await addCampaign(data, f.systemPrompt, goLive);
      if (id) navigate(`/campaigns/${id}`);
    }
  };

  return (
    <div className="space-y-6">
      <Link
        to={campaign ? `/campaigns/${campaign.id}` : "/campaigns"}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {campaign ? "Back to dashboard" : "All campaigns"}
      </Link>

      <h1 className="text-2xl font-semibold">
        {campaign ? `Edit ${campaign.name}` : "New campaign"}
      </h1>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Section title="Identity" subtitle="What this campaign is called and who owns it">
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <Field label="Campaign name" error={show(errors.name)}>
                <Input
                  value={f.name}
                  onChange={(e) => set("name", e.target.value)}
                  placeholder="e.g. UK Fintech CFOs"
                  aria-invalid={submitted && !!errors.name}
                />
              </Field>
              <Field label="Owner">
                <Select value={f.owner} onValueChange={(v) => set("owner", v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OWNERS.map((o) => (
                      <SelectItem key={o} value={o}>
                        {o}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <div className="md:col-span-2">
                <Field label="Description" hint="One or two lines on the goal of this campaign">
                  <Textarea
                    value={f.description}
                    onChange={(e) => set("description", e.target.value)}
                    className="min-h-[72px]"
                  />
                </Field>
              </div>
            </div>
          </Section>

          <Section title="Targeting" subtitle="Who the agents should look for, and who to leave alone">
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <Field label="ICP" error={show(errors.icp)} hint="Short label shown across the app">
                <Input
                  value={f.icp}
                  onChange={(e) => set("icp", e.target.value)}
                  placeholder="e.g. SaaS CTO"
                  aria-invalid={submitted && !!errors.icp}
                />
              </Field>
              <Field label="Geography">
                <Input
                  value={f.geography}
                  onChange={(e) => set("geography", e.target.value)}
                  placeholder="e.g. United States"
                />
              </Field>
              <div className="md:col-span-2">
                <Field label="Target roles" hint="Press Enter or comma to add a role">
                  <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border bg-transparent px-2 py-1.5">
                    {f.roles.map((r) => (
                      <span
                        key={r}
                        className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground"
                      >
                        {r}
                        <button
                          type="button"
                          onClick={() => set("roles", f.roles.filter((x) => x !== r))}
                          className="rounded-full hover:bg-black/10"
                          aria-label={`Remove ${r}`}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                    <input
                      value={roleInput}
                      onChange={(e) => setRoleInput(e.target.value)}
                      onKeyDown={onRoleKey}
                      onBlur={addRole}
                      placeholder={f.roles.length ? "" : "e.g. CTO"}
                      className="min-w-[120px] flex-1 bg-transparent px-1 py-0.5 text-sm outline-none"
                    />
                  </div>
                </Field>
              </div>
              <Field label="Company criteria" hint="Size, industry, funding stage, tech stack">
                <Textarea
                  value={f.companyCriteria}
                  onChange={(e) => set("companyCriteria", e.target.value)}
                  className="min-h-[96px]"
                />
              </Field>
              <Field label="Exclusion criteria" hint="Competitors, existing customers, regions to skip">
                <Textarea
                  value={f.exclusions}
                  onChange={(e) => set("exclusions", e.target.value)}
                  className="min-h-[96px]"
                />
              </Field>
              <div className="md:col-span-2">
                <Field
                  label="Reference profiles"
                  hint="Example prospects or companies that are a perfect fit. Agents use these to calibrate."
                >
                  <Textarea
                    value={f.referenceProfiles}
                    onChange={(e) => set("referenceProfiles", e.target.value)}
                    className="min-h-[80px]"
                  />
                </Field>
              </div>
            </div>
          </Section>

          <Section title="Agents and rules" subtitle="Which agents run, and when they must involve a human">
            <ul className="divide-y">
              {AGENT_DEFS.map((d) => (
                <li key={d.key} className="flex items-center gap-4 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{d.name}</div>
                    <div className="text-xs text-muted-foreground">{d.role}</div>
                  </div>
                  <Switch
                    checked={f.agents[d.key]}
                    onCheckedChange={(v) => set("agents", { ...f.agents, [d.key]: v })}
                  />
                </li>
              ))}
            </ul>
            <div className="grid gap-6 border-t p-5 md:grid-cols-2">
              <RangeField
                label="Minimum ICP fit score"
                hint="Prospects scoring below this are rejected by the ICP Fitment Agent"
                value={f.qualifyThreshold}
                onChange={(n) => set("qualifyThreshold", n)}
              />
              <RangeField
                label="Escalate below confidence"
                hint="If an agent is less sure than this, it hands the decision to a human"
                value={f.confidenceThreshold}
                onChange={(n) => set("confidenceThreshold", n)}
              />
              <div className="md:col-span-2">
                <Field label="Human approval">
                  <Select
                    value={f.approvalMode}
                    onValueChange={(v) => set("approvalMode", v as ApprovalMode)}
                  >
                    <SelectTrigger className="w-full md:w-96">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {APPROVAL_OPTIONS.map((o) => (
                        <SelectItem key={o.key} value={o.key}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
            </div>
            <div className="border-t">
              <div className="px-5 pt-4 text-sm font-medium">Always escalate to a human when</div>
              <ul className="divide-y">
                {ESCALATION_DEFS.map((d) => (
                  <li key={d.key} className="flex items-center gap-4 px-5 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm">{d.label}</div>
                      <div className="text-xs text-muted-foreground">{d.hint}</div>
                    </div>
                    <Switch
                      checked={f.escalateOn.includes(d.key)}
                      onCheckedChange={() => toggleEscalation(d.key)}
                    />
                  </li>
                ))}
              </ul>
            </div>
          </Section>

          <Section title="Channels" subtitle="Where the agents may reach prospects, and how much per day">
            <ul className="divide-y">
              {CHANNEL_DEFS.map((d) => {
                const ch = f.channels[d.key];
                return (
                  <li key={d.key} className="flex items-center gap-4 px-5 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{d.label}</div>
                      <div className="text-xs text-muted-foreground">{d.hint}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        value={ch.limit}
                        disabled={!ch.enabled}
                        onChange={(e) =>
                          set("channels", { ...f.channels, [d.key]: { ...ch, limit: e.target.value } })
                        }
                        className="h-9 w-20"
                      />
                      <span className="text-xs text-muted-foreground">per day</span>
                    </div>
                    <Switch
                      checked={ch.enabled}
                      onCheckedChange={(v) =>
                        set("channels", { ...f.channels, [d.key]: { ...ch, enabled: v } })
                      }
                    />
                  </li>
                );
              })}
            </ul>
          </Section>

          <Section title="Reps" subtitle="Whose identity the outreach is sent under">
            <ul className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
              {reps.map((r) => {
                const on = f.repIds.includes(r.id);
                const off = r.status === "offboarded";
                return (
                  <li key={r.id}>
                    <button
                      type="button"
                      disabled={off}
                      onClick={() => toggleRep(r.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                        on ? "border-primary bg-accent/50" : "hover:bg-muted",
                        off && "cursor-not-allowed opacity-50"
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                          on && "border-primary bg-primary text-primary-foreground"
                        )}
                      >
                        {on && <Check className="h-3 w-3" />}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{r.name}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {off ? "Offboarded" : r.workingHours}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Section>

          <Section
            title="System prompt"
            subtitle={
              isEdit
                ? "Prompts are versioned, so they are edited in the prompt manager"
                : "Saved as v1 and activated automatically"
            }
          >
            {campaign ? (
              <div className="flex flex-wrap items-center justify-between gap-3 p-5">
                <p className="text-sm text-muted-foreground">
                  {campaign.activePromptVersion > 0
                    ? `Version v${campaign.activePromptVersion} is active for this campaign.`
                    : "This campaign has no system prompt yet."}
                </p>
                <Button variant="outline" onClick={() => navigate(`/prompts?campaign=${campaign.id}`)}>
                  Open prompt manager
                </Button>
              </div>
            ) : (
              <div className="space-y-3 p-5">
                <Textarea
                  value={f.systemPrompt}
                  onChange={(e) => set("systemPrompt", e.target.value)}
                  placeholder="Tell the agents who they are, who they are talking to and what they must never do"
                  className="min-h-[160px] font-mono text-sm"
                />
                <Button variant="outline" size="sm" onClick={starterPrompt}>
                  <Sparkles className="mr-1.5 h-4 w-4" />
                  Fill a starter from the targeting above
                </Button>
              </div>
            )}
          </Section>
        </div>

        <aside className="space-y-4 self-start xl:sticky xl:top-0">
          <section className="rounded-xl border bg-card">
            <div className="border-b px-5 py-4">
              <h2 className="font-semibold">Readiness</h2>
              <p className="text-xs text-muted-foreground">
                Not needed to save a draft. All must pass to go live.
              </p>
            </div>
            <ul className="space-y-3 p-5">
              {checks.map((c) => (
                <li key={c.label} className="flex items-center gap-2 text-sm">
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                      c.ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {c.ok ? <Check className="h-3 w-3" /> : <span className="text-xs font-bold">!</span>}
                  </span>
                  <span className={c.ok ? "" : "text-amber-900"}>{c.label}</span>
                </li>
              ))}
            </ul>
          </section>

          {campaign?.status === "live" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              This campaign is Live. Saved changes apply from the agents' next action.
            </div>
          )}

          <div className="flex flex-col gap-2">
            {isEdit ? (
              <Button className="h-10" onClick={() => save(false)}>
                Save changes
              </Button>
            ) : (
              <>
                <Button className="h-10" onClick={() => save(false)}>
                  Create draft
                </Button>
                <Button
                  variant="outline"
                  className="h-10"
                  disabled={!ready || killSwitch}
                  onClick={() => save(true)}
                >
                  Create and go live
                </Button>
                {killSwitch && (
                  <p className="text-xs text-red-600">Release the global kill switch to go live.</p>
                )}
              </>
            )}
            <Button variant="ghost" onClick={() => navigate(campaign ? `/campaigns/${campaign.id}` : "/campaigns")}>
              Cancel
            </Button>
            {submitted && hasErrors && (
              <p className="text-xs text-red-600">Fix the highlighted fields to save.</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function CampaignForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { campaigns } = useControl();
  const campaign = id ? campaigns.find((c) => c.id === id) : undefined;

  if (id && !campaign) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Campaign not found</h1>
        <Button variant="outline" onClick={() => navigate("/campaigns")}>
          Back to campaigns
        </Button>
      </div>
    );
  }

  if (campaign && (campaign.status === "completed" || campaign.status === "archived")) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">{campaign.name}</h1>
        <p className="text-sm text-muted-foreground">
          This campaign is {campaign.status}, so its configuration is read-only. Restore it from the
          campaigns list to make changes.
        </p>
        <Button variant="outline" onClick={() => navigate(`/campaigns/${campaign.id}`)}>
          Back to dashboard
        </Button>
      </div>
    );
  }

  return <FormBody key={campaign?.id ?? "new"} campaign={campaign} />;
}