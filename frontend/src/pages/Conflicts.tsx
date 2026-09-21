import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  CheckCircle2,
  RotateCcw,
  Search,
  ShieldAlert,
  TriangleAlert,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import StatCard from "@/components/StatCard";
import { useControl } from "@/context/ControlContext";
import { useConflicts } from "@/context/ConflictContext";
import {
  CHANNEL_LABEL,
  type ConflictItem,
  type IssueKey,
  type Prospect,
  type Resolution,
  type ResolutionAction,
  type Severity,
} from "@/lib/conflicts";
import { cn } from "@/lib/utils";

const issueStyles: Record<IssueKey, string> = {
  suppressed: "border-red-200 bg-red-50 text-red-700",
  duplicate: "border-orange-200 bg-orange-50 text-orange-700",
  overlap: "border-violet-200 bg-violet-50 text-violet-700",
  frequency: "border-amber-200 bg-amber-50 text-amber-800",
  instructions: "border-sky-200 bg-sky-50 text-sky-700",
};

const severityStyles: Record<Severity, { label: string; cls: string }> = {
  high: { label: "High", cls: "border-red-200 bg-red-50 text-red-700" },
  medium: { label: "Medium", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  low: { label: "Low", cls: "border-slate-200 bg-slate-50 text-slate-600" },
};

function Pill({ cls, children }: { cls: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

const when = (d: number) => (d === 0 ? "today" : d === 1 ? "1 day ago" : `${d} days ago`);

function RuleInput({
  label,
  hint,
  value,
  onCommit,
}: {
  label: string;
  hint: string;
  value: number;
  onCommit: (n: number) => void;
}) {
  const [text, setText] = useState(String(value));
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      <Input
        type="number"
        min={1}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const n = parseInt(e.target.value, 10);
          if (!Number.isNaN(n) && n >= 1) onCommit(n);
        }}
        onBlur={() => setText(String(value))}
        className="h-9 w-24"
      />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function ReviewDialog({ item, onClose }: { item: ConflictItem; onClose: () => void }) {
  const { campaigns } = useControl();
  const { resolve } = useConflicts();
  const { prospect: p, issues } = item;
  const active = item.activeCampaignIds;
  const rec = item.recommended;
  const suppressed = issues.some((i) => i.key === "suppressed");
  const multi = active.length > 1;
  const nameOf = (id: string) => campaigns.find((c) => c.id === id)?.name ?? "Unknown campaign";

  const [action, setAction] = useState<ResolutionAction>(rec.action);
  const [ownerId, setOwnerId] = useState(rec.ownerId ?? active[0] ?? "");
  const [days, setDays] = useState("7");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const options: { key: ResolutionAction; title: string; desc: string; show: boolean }[] = [
    {
      key: "owner",
      title: "Assign to one campaign",
      desc: "Only the chosen campaign keeps contacting this prospect. The others stop.",
      show: multi && !suppressed,
    },
    {
      key: "cooldown",
      title: multi ? "Take turns" : "Cool down",
      desc: multi
        ? `Campaigns contact this prospect one at a time, at least ${days} days apart.`
        : `Pause all outreach to this prospect for ${days} days.`,
      show: !suppressed,
    },
    {
      key: "dnc",
      title: suppressed ? "Stop all active campaigns" : "Do not contact",
      desc: suppressed
        ? "This prospect is on the global do-not-contact list, so every active campaign must stop. This cannot be overridden here."
        : "Add to the global do-not-contact list and stop every active campaign.",
      show: true,
    },
    {
      key: "allow",
      title: "Allow as is",
      desc: "Accept this situation. The decision is logged and it will not be flagged again.",
      show: !suppressed,
    },
  ];

  const touches = [...p.touches].sort((a, b) => a.daysAgo - b.daysAgo);

  const apply = async () => {
    const msg = await resolve(p.id, action, {
      ownerId: action === "owner" ? ownerId : undefined,
      days: action === "cooldown" ? Number(days) : undefined,
      note: note.trim(),
    });
    if (msg) setError(msg);
    else onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{p.name}</DialogTitle>
          <DialogDescription>
            {p.title} at {p.company}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="space-y-2">
            <div className="text-sm font-medium">What we found</div>
            <ul className="space-y-2">
              {issues.map((i, idx) => (
                <li key={`${i.key}-${idx}`} className="flex items-start gap-3 rounded-lg border p-3">
                  <Pill cls={issueStyles[i.key]}>{i.label}</Pill>
                  <span className="text-sm text-muted-foreground">{i.detail}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Recent touches</div>
            <ul className="max-h-36 divide-y overflow-y-auto rounded-lg border text-sm">
              {touches.map((t, i) => (
                <li key={i} className="flex items-center justify-between gap-3 px-3 py-2">
                  <span className="truncate">{nameOf(t.campaignId)}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {CHANNEL_LABEL[t.channel]} · {when(t.daysAgo)}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Resolution</div>
            <ul className="space-y-2">
              {options
                .filter((o) => o.show)
                .map((o) => {
                  const on = action === o.key;
                  return (
                    <li key={o.key}>
                      <button
                        type="button"
                        onClick={() => setAction(o.key)}
                        className={cn(
                          "flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors",
                          on ? "border-primary bg-accent/50" : "hover:bg-muted"
                        )}
                      >
                        <span
                          className={cn(
                            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                            on && "border-primary bg-primary text-primary-foreground"
                          )}
                        >
                          {on && <Check className="h-3 w-3" />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            <span className="text-sm font-medium">{o.title}</span>
                            {rec.action === o.key && (
                              <Pill cls="border-orange-200 bg-orange-50 text-orange-700">
                                Recommended
                              </Pill>
                            )}
                          </span>
                          <span className="block text-xs text-muted-foreground">{o.desc}</span>
                        </span>
                      </button>

                      {on && o.key === "owner" && (
                        <div className="mt-2 flex items-center gap-2 pl-8 text-sm">
                          <span className="text-muted-foreground">Keep in</span>
                          <Select value={ownerId} onValueChange={setOwnerId}>
                            <SelectTrigger className="w-60">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {active.map((id) => (
                                <SelectItem key={id} value={id}>
                                  {nameOf(id)} (
                                  {p.touches.filter((t) => t.campaignId === id).length} touches)
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      )}

                      {on && o.key === "cooldown" && (
                        <div className="mt-2 flex items-center gap-2 pl-8 text-sm">
                          <span className="text-muted-foreground">For</span>
                          <Select value={days} onValueChange={setDays}>
                            <SelectTrigger className="w-28">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="3">3 days</SelectItem>
                              <SelectItem value="7">7 days</SelectItem>
                              <SelectItem value="14">14 days</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                    </li>
                  );
                })}
            </ul>
          </div>

          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note (shown in the resolved list)"
          />
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={action === "owner" && !ownerId} onClick={apply}>
            Apply resolution
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type Tab = "open" | "resolved";

export default function Conflicts() {
  const { campaigns } = useControl();
  const { monitored, rules, setRules, open, resolved, reopen } = useConflicts();
  const [tab, setTab] = useState<Tab>("open");
  const [query, setQuery] = useState("");
  const [reviewId, setReviewId] = useState<string | null>(null);

  const nameOf = (id: string) => campaigns.find((c) => c.id === id)?.name ?? "Unknown campaign";

  const q = query.trim().toLowerCase();
  const match = (p: Prospect) =>
    !q || p.name.toLowerCase().includes(q) || p.company.toLowerCase().includes(q);

  const openRows = useMemo(() => open.filter((i) => match(i.prospect)), [open, q]);
  const resolvedRows = useMemo(() => resolved.filter((r) => match(r.prospect)), [resolved, q]);

  const highCount = open.filter((i) => i.severity === "high").length;
  const overlapCount = open.filter((i) => i.issues.some((x) => x.key === "overlap")).length;
  const reviewItem = reviewId ? open.find((i) => i.prospect.id === reviewId) : undefined;

  const describe = (r: Resolution) => {
    const base =
      r.action === "owner"
        ? `Kept in ${nameOf(r.ownerId ?? "")}, removed from the others`
        : r.action === "cooldown"
          ? `Cool-down of ${r.days} days between touches`
          : r.action === "dnc"
            ? "Added to do-not-contact, removed from active campaigns"
            : "Allowed as is";
    return base;
  };

  const chips = (ids: string[]) =>
    ids.length === 0 ? (
      <span className="text-xs text-muted-foreground">None</span>
    ) : (
      <div className="flex flex-wrap gap-1.5">
        {ids.map((id) => (
          <Link
            key={id}
            to={`/campaigns/${id}`}
            className="rounded-full border bg-muted/50 px-2.5 py-0.5 text-xs hover:bg-muted"
          >
            {nameOf(id)}
          </Link>
        ))}
      </div>
    );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Conflicts</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Open conflicts"
          value={String(open.length)}
          sub={`across ${monitored} prospects monitored`}
          icon={<TriangleAlert className="h-6 w-6 text-amber-600" />}
          tone="bg-amber-100"
        />
        <StatCard
          label="Need action now"
          value={String(highCount)}
          sub="high severity"
          icon={<ShieldAlert className="h-6 w-6 text-red-600" />}
          tone="bg-red-100"
        />
        <StatCard
          label="In multiple campaigns"
          value={String(overlapCount)}
          sub="targeted by 2 or more at once"
          icon={<Users className="h-6 w-6 text-violet-600" />}
          tone="bg-violet-100"
        />
        <StatCard
          label="Resolved"
          value={String(resolved.length)}
          sub="decisions on record"
          icon={<CheckCircle2 className="h-6 w-6 text-emerald-600" />}
          tone="bg-emerald-100"
        />
      </div>

      <section className="rounded-xl border bg-card">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Contact rules</h2>
          <p className="text-xs text-muted-foreground">
            Apply to every campaign. Changing a rule re-checks all prospects straight away.
          </p>
        </div>
        <div className="grid gap-5 p-5 md:grid-cols-2">
          <RuleInput
            label="Max touches per prospect, per 7 days"
            hint="More than this across all campaigns counts as too many touches"
            value={rules.maxTouches}
            onCommit={(n) => setRules({ ...rules, maxTouches: n })}
          />
          <RuleInput
            label="Duplicate outreach window (days)"
            hint="Two campaigns using the same channel within this window is a duplicate"
            value={rules.duplicateWindow}
            onCommit={(n) => setRules({ ...rules, duplicateWindow: n })}
          />
        </div>
      </section>

      <div className="rounded-xl border bg-card">
        <div className="flex items-center justify-between gap-3 border-b px-5 pt-3">
          <div className="flex gap-6">
            {(
              [
                { key: "open", label: "Open", count: open.length },
                { key: "resolved", label: "Resolved", count: resolved.length },
              ] as const
            ).map((t) => (
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
                <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-xs">{t.count}</span>
              </button>
            ))}
          </div>
          <div className="relative mb-3 w-64">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search prospect or company"
              className="h-9 pl-9"
            />
          </div>
        </div>

        {tab === "open" ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-5">Prospect</TableHead>
                <TableHead>Campaigns</TableHead>
                <TableHead>Issues</TableHead>
                <TableHead>Touches (7d)</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead className="pr-5 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {openRows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                    <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-emerald-500" />
                    {open.length === 0
                      ? "All clear. No prospect is being contacted in conflicting ways."
                      : "No conflicts match this search."}
                  </TableCell>
                </TableRow>
              )}
              {openRows.map(({ prospect: p, issues, severity, activeCampaignIds: activeIds, recentTouches }) => (
                <TableRow key={p.id} className="cursor-pointer" onClick={() => setReviewId(p.id)}>
                  <TableCell className="pl-5">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.title} · {p.company}
                    </div>
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {chips(activeIds)}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1.5">
                      {issues.map((i, idx) => (
                        <Pill key={`${i.key}-${idx}`} cls={issueStyles[i.key]}>
                          {i.label}
                        </Pill>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="tabular-nums">{recentTouches}</TableCell>
                  <TableCell>
                    <Pill cls={severityStyles[severity].cls}>{severityStyles[severity].label}</Pill>
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        setReviewId(p.id);
                      }}
                    >
                      Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-5">Prospect</TableHead>
                <TableHead>Active in</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>By</TableHead>
                <TableHead className="pr-5 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {resolvedRows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                    {resolved.length === 0
                      ? "No conflicts resolved yet."
                      : "No resolved conflicts match this search."}
                  </TableCell>
                </TableRow>
              )}
              {resolvedRows.map(({ prospect: p, resolution: r, activeCampaignIds: activeIds }) => (
                <TableRow key={p.id}>
                  <TableCell className="pl-5">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.title} · {p.company}
                    </div>
                  </TableCell>
                  <TableCell>{chips(activeIds)}</TableCell>
                  <TableCell className="whitespace-normal">
                    <div className="text-sm">{describe(r)}</div>
                    {r.note && <div className="text-xs text-muted-foreground">{r.note}</div>}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <div className="text-sm">{r.by}</div>
                    <div className="text-xs text-muted-foreground">{r.time}</div>
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    <Button size="sm" variant="outline" onClick={() => reopen(p.id)}>
                      <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      Reopen
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {reviewItem && (
        <ReviewDialog key={reviewItem.prospect.id} item={reviewItem} onClose={() => setReviewId(null)} />
      )}
    </div>
  );
}