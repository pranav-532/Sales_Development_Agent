import { useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ChevronDown, Play, RotateCcw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import StatusBadge from "@/components/StatusBadge";
import { useControl } from "@/context/ControlContext";
import { useCampaignData } from "@/hooks/useCampaignData";
import { cn } from "@/lib/utils";
import type { AuditAction, Campaign, CampaignStatus, PromptScope } from "@/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const auditStyles: Record<AuditAction, { label: string; cls: string }> = {
  created: { label: "Created", cls: "border-sky-200 bg-sky-50 text-sky-700" },
  activated: { label: "Activated", cls: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  rolled_back: { label: "Rolled back", cls: "border-amber-200 bg-amber-50 text-amber-800" },
};

type Part = { type: "same" | "add" | "del"; text: string };

function diffWords(a: string, b: string): Part[] {
  const x = a.split(/(\s+)/).filter(Boolean);
  const y = b.split(/(\s+)/).filter(Boolean);
  const n = x.length;
  const m = y.length;
  const dp = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: Part[] = [];
  const push = (type: Part["type"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.type === type) last.text += text;
    else out.push({ type, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) {
      push("same", x[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push("del", x[i]);
      i++;
    } else {
      push("add", y[j]);
      j++;
    }
  }
  while (i < n) push("del", x[i++]);
  while (j < m) push("add", y[j++]);
  return out;
}

const countWords = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

function Pill({ cls, children }: { cls: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

const tabs = [
  { key: "versions", label: "Versions" },
  { key: "compare", label: "Compare" },
  { key: "audit", label: "Audit trail" },
] as const;

function ScopeEditor({
  campaign,
  scope,
  scopeName,
}: {
  campaign: Campaign;
  scope: PromptScope;
  scopeName: string;
}) {
  const { prompts, audit, savePromptVersion, activatePromptVersion } = useControl();
  const { events } = useCampaignData(campaign.id);

  const versions = prompts
    .filter((p) => p.campaignId === campaign.id && p.agentKey === scope)
    .sort((a, b) => b.version - a.version);
  const active = versions.find((v) => v.isActive);
  const latest = versions[0];
  const toDefault = active?.version ?? latest?.version ?? null;
  const fromDefault =
    versions.find((v) => toDefault !== null && v.version < toDefault)?.version ?? toDefault;

  const [tab, setTab] = useState<(typeof tabs)[number]["key"]>("versions");
  const [selected, setSelected] = useState<number | null>(active?.version ?? latest?.version ?? null);
  const [draft, setDraft] = useState(active?.content ?? latest?.content ?? "");
  const [note, setNote] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cmpFrom, setCmpFrom] = useState<number | null>(fromDefault);
  const [cmpTo, setCmpTo] = useState<number | null>(toDefault);
  const [auditAll, setAuditAll] = useState(false);

  const selectedVersion = versions.find((v) => v.version === selected) ?? null;
  const editable = campaign.status !== "completed" && campaign.status !== "archived";
  const isLive = campaign.status === "live";

  const trimmed = draft.trim();
  const changed = trimmed !== (selectedVersion?.content ?? "");
  const dirty = selectedVersion ? draft !== selectedVersion.content : trimmed.length > 0;
  const canSave = editable && trimmed.length > 0 && changed;
  const canActivate = editable && !!selectedVersion && !selectedVersion.isActive && !dirty;
  const isRollback = !!active && !!selectedVersion && selectedVersion.version < active.version;

  const nameOf = (s: PromptScope) =>
    s === "system" ? "System prompt" : campaign.agents.find((a) => a.key === s)?.name ?? s;

  const usedCount = (version: number) =>
    events.filter((e) => e.campaignId === campaign.id && e.promptVersion === version).length;

  const pick = (v: { version: number; content: string }) => {
    setSelected(v.version);
    setDraft(v.content);
    setNote("");
  };

  const handleSave = async () => {
    const version = await savePromptVersion(campaign.id, scope, trimmed, note.trim());
    if (version === null) return;
    setSelected(version);
    setDraft(trimmed);
    setNote("");
  };

  const doActivate = () => {
    if (!selectedVersion) return;
    activatePromptVersion(campaign.id, scope, selectedVersion.version);
    setConfirmOpen(false);
  };

  const fromV = versions.find((v) => v.version === cmpFrom);
  const toV = versions.find((v) => v.version === cmpTo);
  const parts = fromV && toV ? diffWords(fromV.content, toV.content) : [];
  const added = countWords(parts.filter((p) => p.type === "add").map((p) => p.text).join(" "));
  const removed = countWords(parts.filter((p) => p.type === "del").map((p) => p.text).join(" "));

  const auditRows = audit.filter(
    (a) => a.campaignId === campaign.id && (auditAll || a.scope === scope)
  );

  let hint = "Unsaved edits are discarded when you switch version.";
  if (!editable) hint = `This campaign is ${campaign.status}, so prompts are read-only.`;
  else if (versions.length === 0)
    hint = "No prompt yet. Write one and save it as v1. It is activated automatically.";
  else if (selectedVersion && !selectedVersion.isActive && dirty)
    hint = "Save your edits as a new version before activating.";

  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">{scopeName}</h2>
        <p className="text-xs text-muted-foreground">
          {active ? `v${active.version} is active` : "No active version"}
        </p>
      </div>

      <div className="flex gap-6 border-b px-5 pt-3">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 pb-3 text-sm ${
              tab === t.key
                ? "border-primary font-medium text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-5">
        {tab === "versions" && (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[260px_1fr]">
            <div className="max-h-[440px] space-y-2 overflow-y-auto">
              {versions.length === 0 && (
                <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                  No versions yet
                </div>
              )}
              {versions.map((v) => (
                <button
                  key={v.id}
                  onClick={() => pick(v)}
                  className={cn(
                    "w-full rounded-lg border p-3 text-left transition-colors",
                    selected === v.version ? "border-primary bg-accent/50" : "hover:bg-muted"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">v{v.version}</span>
                    {v.isActive && (
                      <Pill cls="border-emerald-200 bg-emerald-50 text-emerald-700">Active</Pill>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {v.author} · {v.createdAt}
                  </div>
                  {v.note && <div className="mt-1 text-xs">{v.note}</div>}
                  {scope === "system" && (
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      Used in {usedCount(v.version)} logged actions
                    </div>
                  )}
                </button>
              ))}
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">
                  {selectedVersion
                    ? `v${selectedVersion.version}${selectedVersion.isActive ? " (active)" : ""}`
                    : "New prompt"}
                </div>
                <div className="text-xs text-muted-foreground">{countWords(draft)} words</div>
              </div>
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                readOnly={!editable}
                placeholder="Write the prompt here"
                className="min-h-[260px] font-mono text-sm"
              />
              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={!editable}
                placeholder="What changed? (shown in history)"
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="max-w-md text-xs text-muted-foreground">{hint}</p>
                <div className="flex gap-2">
                  {selectedVersion && !selectedVersion.isActive && (
                    <Button
                      variant="outline"
                      disabled={!canActivate}
                      onClick={() => (isLive ? setConfirmOpen(true) : doActivate())}
                    >
                      {isRollback ? (
                        <RotateCcw className="mr-1.5 h-4 w-4" />
                      ) : (
                        <Play className="mr-1.5 h-4 w-4" />
                      )}
                      {isRollback ? "Roll back to" : "Activate"} v{selectedVersion.version}
                    </Button>
                  )}
                  <Button disabled={!canSave} onClick={handleSave}>
                    <Save className="mr-1.5 h-4 w-4" />
                    Save as new version
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "compare" &&
          (versions.length < 2 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Save at least two versions to compare them.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="text-muted-foreground">Compare</span>
                <Select
                  value={cmpFrom !== null ? String(cmpFrom) : undefined}
                  onValueChange={(v) => setCmpFrom(Number(v))}
                >
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {versions.map((v) => (
                      <SelectItem key={v.id} value={String(v.version)}>
                        v{v.version}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-muted-foreground">with</span>
                <Select
                  value={cmpTo !== null ? String(cmpTo) : undefined}
                  onValueChange={(v) => setCmpTo(Number(v))}
                >
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {versions.map((v) => (
                      <SelectItem key={v.id} value={String(v.version)}>
                        v{v.version}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {fromV && toV && cmpFrom !== cmpTo && (
                  <span className="text-xs text-muted-foreground">
                    <span className="text-emerald-700">+{added} words</span>
                    {" · "}
                    <span className="text-red-700">-{removed} words</span>
                  </span>
                )}
              </div>

              {cmpFrom === cmpTo ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  Pick two different versions.
                </div>
              ) : (
                <div className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm leading-relaxed">
                  {parts.map((p, i) => (
                    <span
                      key={i}
                      className={
                        p.type === "add"
                          ? "bg-emerald-100 text-emerald-800"
                          : p.type === "del"
                            ? "bg-red-100 text-red-800 line-through"
                            : ""
                      }
                    >
                      {p.text}
                    </span>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Green was added in the second version. Red with a strikethrough was removed from the first.
              </p>
            </div>
          ))}

        {tab === "audit" && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={auditAll ? "outline" : "default"}
                onClick={() => setAuditAll(false)}
              >
                This prompt
              </Button>
              <Button
                size="sm"
                variant={auditAll ? "default" : "outline"}
                onClick={() => setAuditAll(true)}
              >
                All prompts in campaign
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-0">When</TableHead>
                  <TableHead>Prompt</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>By</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditRows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                      No changes recorded yet.
                    </TableCell>
                  </TableRow>
                )}
                {auditRows.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="whitespace-nowrap pl-0 text-muted-foreground">{a.time}</TableCell>
                    <TableCell className="whitespace-nowrap">{nameOf(a.scope)}</TableCell>
                    <TableCell>
                      <Pill cls={auditStyles[a.action].cls}>{auditStyles[a.action].label}</Pill>
                    </TableCell>
                    <TableCell>v{a.version}</TableCell>
                    <TableCell className="whitespace-nowrap">{a.author}</TableCell>
                    <TableCell className="whitespace-normal text-muted-foreground">{a.note || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {selectedVersion && (
        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {isRollback ? "Roll back" : "Activate"} {scopeName} v{selectedVersion.version}?
              </DialogTitle>
              <DialogDescription>
                {campaign.name} is Live. Agents will use this version from their next action. Other
                campaigns are not affected.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button onClick={doActivate}>Confirm</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </section>
  );
}

const statusMoves: Record<CampaignStatus, { to: CampaignStatus; label: string }[]> = {
  draft: [
    { to: "live", label: "Activate (Live)" },
    { to: "archived", label: "Archive" },
  ],
  live: [
    { to: "paused", label: "Pause" },
    { to: "completed", label: "Complete" },
    { to: "archived", label: "Archive" },
  ],
  paused: [
    { to: "live", label: "Resume (Live)" },
    { to: "completed", label: "Complete" },
    { to: "archived", label: "Archive" },
  ],
  completed: [{ to: "archived", label: "Archive" }],
  archived: [{ to: "completed", label: "Restore" }],
};

export default function PromptManager() {
  const { campaigns, killSwitch, prompts, setStatus  } = useControl();
  const [params, setParams] = useSearchParams();
  const [scope, setScope] = useState<PromptScope>("system");

  const c = campaigns.find((x) => x.id === params.get("campaign")) ?? campaigns[0];
  if (!c) return <div className="text-muted-foreground">No campaigns yet.</div>;

  const scopes: { key: PromptScope; name: string; hint: string }[] = [
    { key: "system", name: "Campaign system prompt", hint: "Applies to every agent" },
    ...c.agents.map((a) => ({
      key: a.key as PromptScope,
      name: a.name,
      hint: a.enabled ? "Agent prompt" : "Agent not enabled",
    })),
  ];
  const current = scopes.find((s) => s.key === scope) ?? scopes[0];

  const activeOf = (key: PromptScope) =>
    prompts.find((p) => p.campaignId === c.id && p.agentKey === key && p.isActive);

  return (
    <div className="space-y-6">
      {params.get("campaign") && (
        <Link
            to={`/campaigns/${c.id}`}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
            <ArrowLeft className="h-4 w-4" />
            Back to dashboard
        </Link>
      )}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold">Prompt manager</h1>
        <div className="flex items-center gap-3">
            <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline" className="h-9 gap-2 px-3">
                <StatusBadge status={c.status} halted={killSwitch} />
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                {statusMoves[c.status].map((m) => (
                <DropdownMenuItem
                    key={m.to}
                    disabled={m.to === "live" && killSwitch}
                    onSelect={() => setStatus(c.id, m.to)}
                >
                    {m.label}
                </DropdownMenuItem>
                ))}
            </DropdownMenuContent>
            </DropdownMenu>
            <Select
            value={c.id}
            onValueChange={(v) => {
                setParams({ campaign: v });
                setScope("system");
            }}
            >
            <SelectTrigger className="w-64">
                <SelectValue />
            </SelectTrigger>
            <SelectContent>
                {campaigns.map((x) => (
                <SelectItem key={x.id} value={x.id}>
                    {x.name}
                </SelectItem>
                ))}
            </SelectContent>
            </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[280px_1fr]">
        <section className="self-start rounded-xl border bg-card">
          <div className="border-b px-5 py-4">
            <h2 className="font-semibold">Prompts</h2>
            <p className="text-xs text-muted-foreground">One system prompt plus one per agent</p>
          </div>
          <ul className="p-2">
            {scopes.map((s) => {
              const a = activeOf(s.key);
              return (
                <li key={s.key}>
                  <button
                    onClick={() => setScope(s.key)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left transition-colors",
                      scope === s.key ? "bg-accent" : "hover:bg-muted"
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">{s.name}</div>
                      <div className="truncate text-xs text-muted-foreground">{s.hint}</div>
                    </div>
                    {a ? (
                      <Pill cls="border-orange-200 bg-orange-50 text-orange-700">v{a.version}</Pill>
                    ) : (
                      <Pill cls="border-stone-200 bg-stone-50 text-stone-500">Not set</Pill>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        <ScopeEditor
          key={`${c.id}:${scope}`}
          campaign={c}
          scope={current.key}
          scopeName={current.name}
        />
      </div>
    </div>
  );
}