import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  Gauge,
  Layers,
  MoreHorizontal,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  TriangleAlert,
  UserCheck,
  UserMinus,
  UserX,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { CHANNEL_DEFS } from "@/lib/campaignDefaults";
import { TIMEZONES, formatHours, isOpen, missingChannels, parseHours } from "@/lib/repRules";
import { cn } from "@/lib/utils";
import type { Campaign, Channel, Rep } from "@/types";

const channelLabels: Record<Channel, string> = {
  linkedin: "LinkedIn",
  email: "Email",
  sms: "SMS",
  voice: "Voice",
};

const initials = (name: string) =>
  name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function Warn({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-1.5 text-xs text-amber-800">
      <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

function RepFormDialog({ rep, onClose }: { rep?: Rep; onClose: () => void }) {
  const { reps, addRep, updateRep } = useControl();
  const init = parseHours(rep?.workingHours ?? "");

  const [name, setName] = useState(rep?.name ?? "");
  const [email, setEmail] = useState(rep?.email ?? "");
  const [limit, setLimit] = useState(String(rep?.dailyLimit ?? 50));
  const [start, setStart] = useState(init.start);
  const [end, setEnd] = useState(init.end);
  const [tz, setTz] = useState(init.tz);
  const [channels, setChannels] = useState<Channel[]>(rep?.channels ?? ["email"]);
  const [submitted, setSubmitted] = useState(false);

  const limitNum = parseInt(limit, 10);
  const emailTaken = reps.some(
    (r) => r.id !== rep?.id && r.email.toLowerCase() === email.trim().toLowerCase()
  );
  const errors = {
    name: name.trim() ? "" : "Enter a name",
    email: !/^\S+@\S+\.\S+$/.test(email.trim())
      ? "Enter a valid email"
      : emailTaken
        ? "Another rep uses this email"
        : "",
    limit: Number.isNaN(limitNum) || limitNum < 1 ? "Enter a limit of at least 1" : "",
    hours: end > start ? "" : "End time must be after start time",
    channels: channels.length ? "" : "Pick at least one channel",
  };
  const hasErrors = Object.values(errors).some(Boolean);
  const show = (m: string) => (submitted ? m : "");

  const toggleChannel = (c: Channel) =>
    setChannels((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const save = () => {
    setSubmitted(true);
    if (hasErrors) return;
    const data = {
      name: name.trim(),
      email: email.trim(),
      dailyLimit: limitNum,
      workingHours: formatHours(start, end, tz),
      channels,
    };
    if (rep) updateRep(rep.id, data);
    else addRep(data);
    onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{rep ? "Edit rep" : "Add rep"}</DialogTitle>
          <DialogDescription>
            Limits and hours apply across every campaign this rep is assigned to.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" error={show(errors.name)}>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Email" error={show(errors.email)}>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
          </div>

          <Field label="Daily activity limit" error={show(errors.limit)}>
            <Input
              type="number"
              min={1}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className="w-32"
            />
          </Field>

          <Field label="Working hours" error={show(errors.hours)}>
            <div className="flex flex-wrap items-center gap-2">
              <Select value={String(start)} onValueChange={(v) => setStart(Number(v))}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {h}:00
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground">to</span>
              <Select value={String(end)} onValueChange={(v) => setEnd(Number(v))}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {h}:00
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={tz} onValueChange={setTz}>
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </Field>

          <Field label="Channels this rep can use" error={show(errors.channels)}>
            <div className="grid grid-cols-2 gap-2">
              {CHANNEL_DEFS.map((d) => {
                const on = channels.includes(d.key);
                return (
                  <button
                    key={d.key}
                    type="button"
                    onClick={() => toggleChannel(d.key)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                      on ? "border-primary bg-accent/50" : "hover:bg-muted"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                        on && "border-primary bg-primary text-primary-foreground"
                      )}
                    >
                      {on && <Check className="h-3 w-3" />}
                    </span>
                    {d.label}
                  </button>
                );
              })}
            </div>
          </Field>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save}>{rep ? "Save changes" : "Add rep"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssignDialog({ rep, onClose }: { rep: Rep; onClose: () => void }) {
  const { campaigns, setRepCampaigns } = useControl();
  const open = campaigns.filter(isOpen);
  const [sel, setSel] = useState<string[]>(
    open.filter((c) => c.repIds.includes(rep.id)).map((c) => c.id)
  );

  const toggle = (id: string) =>
    setSel((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const stranded = open.filter(
    (c) =>
      c.status !== "draft" && c.repIds.length === 1 && c.repIds[0] === rep.id && !sel.includes(c.id)
  );
  const gaps = open
    .filter((c) => sel.includes(c.id))
    .map((c) => ({ c, missing: missingChannels(c, rep) }))
    .filter((x) => x.missing.length > 0);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Assign campaigns to {rep.name}</DialogTitle>
          <DialogDescription>
            Completed and archived campaigns are not listed, and keep their history unchanged.
          </DialogDescription>
        </DialogHeader>

        {open.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No open campaigns.</p>
        ) : (
          <ul className="space-y-2">
            {open.map((c) => {
              const on = sel.includes(c.id);
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => toggle(c.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                      on ? "border-primary bg-accent/50" : "hover:bg-muted"
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
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{c.name}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {c.icp} · {c.geography}
                      </span>
                    </span>
                    <StatusBadge status={c.status} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {(stranded.length > 0 || gaps.length > 0) && (
          <div className="space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 p-3">
            {stranded.map((c) => (
              <Warn key={c.id}>{c.name} would have no rep left to send under.</Warn>
            ))}
            {gaps.map(({ c, missing }) => (
              <Warn key={c.id}>
                {rep.name} cannot use {missing.map((m) => channelLabels[m]).join(", ")}, which{" "}
                {c.name} has enabled.
              </Warn>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              setRepCampaigns(rep.id, sel);
              onClose();
            }}
          >
            Save assignments
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OffboardDialog({ rep, onClose }: { rep: Rep; onClose: () => void }) {
  const { reps, campaigns, offboardRep } = useControl();
  const affected = campaigns.filter((c) => isOpen(c) && c.repIds.includes(rep.id));
  const candidates = reps.filter((r) => r.status === "active" && r.id !== rep.id);

  const [choice, setChoice] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      affected.map((c) => [c.id, candidates.find((r) => !c.repIds.includes(r.id))?.id ?? "none"])
    )
  );

  const rows = affected.map((c) => {
    const chosen = choice[c.id] ?? "none";
    const cand = candidates.find((r) => r.id === chosen);
    const remaining = c.repIds.filter((id) => id !== rep.id).length + (cand ? 1 : 0);
    return {
      c,
      chosen,
      missing: cand ? missingChannels(c, cand) : [],
      uncovered: c.status !== "draft" && remaining === 0,
    };
  });
  const uncoveredCount = rows.filter((r) => r.uncovered).length;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Offboard {rep.name}?</DialogTitle>
          <DialogDescription>
            {affected.length === 0
              ? "This rep is not assigned to any open campaign, so nothing else is affected."
              : `${affected.length} open ${affected.length === 1 ? "campaign is" : "campaigns are"} affected. Pick a replacement for each one.`}
          </DialogDescription>
        </DialogHeader>

        {rows.length > 0 && (
          <ul className="divide-y rounded-lg border px-4">
            {rows.map(({ c, chosen, missing, uncovered }) => (
              <li key={c.id} className="space-y-2 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-sm font-medium">{c.name}</span>
                    <StatusBadge status={c.status} />
                  </div>
                  <Select
                    value={chosen}
                    onValueChange={(v) => setChoice((p) => ({ ...p, [c.id]: v }))}
                  >
                    <SelectTrigger className="w-52">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Leave without a rep</SelectItem>
                      {candidates
                        .filter((r) => !c.repIds.includes(r.id))
                        .map((r) => (
                          <SelectItem key={r.id} value={r.id}>
                            {r.name}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                {uncovered && (
                  <Warn>
                    {c.name} is {c.status} and would have no rep. It will show up under "Needs a rep".
                  </Warn>
                )}
                {missing.length > 0 && (
                  <Warn>
                    The replacement cannot use {missing.map((m) => channelLabels[m]).join(", ")}, which
                    this campaign has enabled.
                  </Warn>
                )}
              </li>
            ))}
          </ul>
        )}

        {uncoveredCount > 0 && (
          <p className="text-xs text-muted-foreground">
            Campaigns without a rep are not paused automatically. Assign someone from the Reps page.
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="bg-red-600 text-white hover:bg-red-700"
            onClick={() => {
              offboardRep(rep.id, choice);
              onClose();
            }}
          >
            Offboard {rep.name.split(" ")[0]}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssignRow({ campaign }: { campaign: Campaign }) {
  const { reps, assignRep } = useControl();
  const options = reps.filter((r) => r.status === "active");
  const [pick, setPick] = useState(options[0]?.id ?? "");

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <Link to={`/campaigns/${campaign.id}`} className="truncate text-sm font-medium hover:underline">
          {campaign.name}
        </Link>
        <StatusBadge status={campaign.status} />
      </div>
      {options.length === 0 ? (
        <span className="text-xs text-muted-foreground">Add an active rep first</span>
      ) : (
        <div className="flex items-center gap-2">
          <Select value={pick} onValueChange={setPick}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" disabled={!pick} onClick={() => assignRep(campaign.id, pick)}>
            Assign
          </Button>
        </div>
      )}
    </li>
  );
}

type Filter = "all" | "active" | "offboarded";

export default function Reps() {
  const { reps, campaigns, reactivateRep } = useControl();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [formId, setFormId] = useState<string | "new" | null>(null);
  const [assignId, setAssignId] = useState<string | null>(null);
  const [offboardId, setOffboardId] = useState<string | null>(null);

  const activeIds = new Set(reps.filter((r) => r.status === "active").map((r) => r.id));
  const activeCount = activeIds.size;
  const offboardedCount = reps.length - activeCount;
  const capacity = reps.filter((r) => r.status === "active").reduce((s, r) => s + r.dailyLimit, 0);
  const needsRep = campaigns.filter(
    (c) =>
      (c.status === "live" || c.status === "paused") && !c.repIds.some((id) => activeIds.has(id))
  );

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return reps.filter(
      (r) =>
        (filter === "all" || r.status === filter) &&
        (!q || r.name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q))
    );
  }, [reps, filter, query]);

  const tabs: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All", count: reps.length },
    { key: "active", label: "Active", count: activeCount },
    { key: "offboarded", label: "Offboarded", count: offboardedCount },
  ];

  const formRep = formId && formId !== "new" ? reps.find((r) => r.id === formId) : undefined;
  const assignRepObj = assignId ? reps.find((r) => r.id === assignId) : undefined;
  const offboardRepObj = offboardId ? reps.find((r) => r.id === offboardId) : undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <h1 className="text-2xl font-semibold">Reps</h1>
        <Button onClick={() => setFormId("new")}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add rep
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Active reps"
          value={String(activeCount)}
          sub={`of ${reps.length} total`}
          icon={<UserCheck className="h-6 w-6 text-emerald-600" />}
          tone="bg-emerald-100"
        />
        <StatCard
          label="Offboarded"
          value={String(offboardedCount)}
          sub="no longer sending"
          icon={<UserX className="h-6 w-6 text-stone-600" />}
          tone="bg-stone-100"
        />
        <StatCard
          label="Campaigns needing a rep"
          value={String(needsRep.length)}
          sub="Live or Paused, no active rep"
          icon={<TriangleAlert className="h-6 w-6 text-amber-600" />}
          tone="bg-amber-100"
        />
        <StatCard
          label="Daily capacity"
          value={capacity.toLocaleString()}
          sub="activities across active reps"
          icon={<Gauge className="h-6 w-6 text-sky-600" />}
          tone="bg-sky-100"
        />
      </div>

      {needsRep.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-card">
          <div className="border-b border-amber-200 bg-amber-50 px-5 py-3">
            <h2 className="flex items-center gap-2 font-semibold text-amber-900">
              <TriangleAlert className="h-4 w-4" />
              Needs a rep
            </h2>
            <p className="text-xs text-amber-900/80">
              These campaigns have no active rep to send under. Assign one to continue.
            </p>
          </div>
          <ul className="divide-y">
            {needsRep.map((c) => (
              <AssignRow key={c.id} campaign={c} />
            ))}
          </ul>
        </section>
      )}

      <div className="rounded-xl border bg-card">
        <div className="flex items-center justify-between gap-3 border-b px-5 pt-3">
          <div className="flex gap-6">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={`-mb-px border-b-2 pb-3 text-sm ${
                  filter === t.key
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
              placeholder="Search name or email"
              className="h-9 pl-9"
            />
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Rep</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Campaigns</TableHead>
              <TableHead>Daily limit</TableHead>
              <TableHead>Working hours</TableHead>
              <TableHead>Channels</TableHead>
              <TableHead className="w-16 pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  No reps match this filter.
                </TableCell>
              </TableRow>
            )}
            {rows.map((r) => {
              const off = r.status === "offboarded";
              const mine = campaigns.filter((c) => isOpen(c) && c.repIds.includes(r.id));
              return (
                <TableRow key={r.id} className={off ? "opacity-60" : ""}>
                  <TableCell className="pl-5">
                    <div className="flex items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                        {initials(r.name)}
                      </span>
                      <div>
                        <div className="font-medium">{r.name}</div>
                        <div className="text-xs text-muted-foreground">{r.email}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                        off
                          ? "border-stone-200 bg-stone-50 text-stone-600"
                          : "border-emerald-200 bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      {off ? "Offboarded" : "Active"}
                    </span>
                  </TableCell>
                  <TableCell>
                    {mine.length === 0 ? (
                      <span className="text-xs text-muted-foreground">None</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {mine.map((c) => (
                          <Link
                            key={c.id}
                            to={`/campaigns/${c.id}`}
                            className="rounded-full border bg-muted/50 px-2.5 py-0.5 text-xs hover:bg-muted"
                          >
                            {c.name}
                          </Link>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums">{r.dailyLimit}/day</TableCell>
                  <TableCell className="whitespace-nowrap">{r.workingHours}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1.5">
                      {r.channels.map((ch) => (
                        <span
                          key={ch}
                          className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {channelLabels[ch]}
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="icon" variant="ghost" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {!off && (
                          <>
                            <DropdownMenuItem onSelect={() => setFormId(r.id)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit details
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => setAssignId(r.id)}>
                              <Layers className="mr-2 h-4 w-4" />
                              Assign campaigns
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onSelect={() => setOffboardId(r.id)}>
                              <UserMinus className="mr-2 h-4 w-4" />
                              Offboard
                            </DropdownMenuItem>
                          </>
                        )}
                        {off && (
                          <DropdownMenuItem onSelect={() => reactivateRep(r.id)}>
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Reactivate
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {formId && (formId === "new" || formRep) && (
        <RepFormDialog key={formId} rep={formRep} onClose={() => setFormId(null)} />
      )}
      {assignRepObj && (
        <AssignDialog key={assignRepObj.id} rep={assignRepObj} onClose={() => setAssignId(null)} />
      )}
      {offboardRepObj && (
        <OffboardDialog
          key={offboardRepObj.id}
          rep={offboardRepObj}
          onClose={() => setOffboardId(null)}
        />
      )}
    </div>
  );
}