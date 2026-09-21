import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Archive,
  ArchiveRestore,
  CalendarCheck,
  CheckCircle2,
  Copy,
  Megaphone,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  Plus,
  Search,
  Send,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { useControl } from "@/context/ControlContext";
import type { CampaignStatus } from "@/types";

type Filter = "all" | CampaignStatus;

const tabs: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "live", label: "Live" },
  { key: "paused", label: "Paused" },
  { key: "draft", label: "Draft" },
  { key: "completed", label: "Completed" },
  { key: "archived", label: "Archived" },
];

function StatCard({
  label,
  value,
  sub,
  icon,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-5">
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${tone}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold leading-tight">{value}</div>
        <div className="text-xs text-muted-foreground">{sub}</div>
      </div>
    </div>
  );
}

export default function Campaigns() {
  const { campaigns, killSwitch, setStatus, duplicateCampaign, reps: allReps } = useControl();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const live = campaigns.filter((c) => c.status === "live").length;
  const prospects = campaigns.reduce((s, c) => s + c.funnel.discovered, 0);
  const outreach = campaigns.reduce((s, c) => s + c.outreachCount, 0);
  const meetings = campaigns.reduce((s, c) => s + c.meetings, 0);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return campaigns.filter((c) => {
      const okStatus = filter === "all" ? c.status !== "archived" : c.status === filter;
      const okQuery =
        !q ||
        c.name.toLowerCase().includes(q) ||
        c.icp.toLowerCase().includes(q) ||
        c.owner.toLowerCase().includes(q);
      return okStatus && okQuery;
    });
  }, [campaigns, filter, query]);

  const countFor = (key: Filter) =>
    key === "all"
      ? campaigns.filter((c) => c.status !== "archived").length
      : campaigns.filter((c) => c.status === key).length;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <h1 className="text-2xl font-semibold">Campaigns</h1>
        <Button onClick={() => navigate("/campaigns/new")}>
          <Plus className="mr-1.5 h-4 w-4" />
          New campaign
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Live campaigns"
          value={String(live)}
          sub={`of ${campaigns.length} total`}
          icon={<Megaphone className="h-6 w-6 text-orange-600" />}
          tone="bg-orange-100"
        />
        <StatCard
          label="Prospects discovered"
          value={prospects.toLocaleString()}
          sub="across all campaigns"
          icon={<Users className="h-6 w-6 text-emerald-600" />}
          tone="bg-emerald-100"
        />
        <StatCard
          label="Outreach sent"
          value={outreach.toLocaleString()}
          sub="all channels"
          icon={<Send className="h-6 w-6 text-sky-600" />}
          tone="bg-sky-100"
        />
        <StatCard
          label="Meetings booked"
          value={meetings.toLocaleString()}
          sub="across all campaigns"
          icon={<CalendarCheck className="h-6 w-6 text-violet-600" />}
          tone="bg-violet-100"
        />
      </div>

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
                <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-xs">
                  {countFor(t.key)}
                </span>
              </button>
            ))}
          </div>
          <div className="relative mb-3 w-64">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, ICP or owner"
              className="h-9 pl-9"
            />
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Campaign</TableHead>
              <TableHead>ICP</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Prospects</TableHead>
              <TableHead className="text-right">Outreach</TableHead>
              <TableHead className="pr-6 text-right">Meetings</TableHead>
              <TableHead className="pl-10">Reps</TableHead>
              <TableHead className="pr-5">
                <div className="flex justify-end">
                  <div className="w-[9.5rem] text-center">Control</div>
                </div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                  No campaigns match this filter.
                </TableCell>
              </TableRow>
            )}
            {rows.map((c) => {
              const reps = allReps.filter((r) => c.repIds.includes(r.id));
              const canComplete = c.status === "live" || c.status === "paused";
              const canArchive = c.status !== "archived";

              return (
                <TableRow
                  key={c.id}
                  onClick={() => navigate(`/campaigns/${c.id}`)}
                  className={`cursor-pointer ${c.status === "paused" ? "bg-amber-50/50" : ""}`}
                >
                  <TableCell className="pl-5">
                    <div className="font-medium">{c.name}</div>
                    <div className="text-xs text-muted-foreground">Owner: {c.owner}</div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">{c.icp}</div>
                    <div className="text-xs text-muted-foreground">{c.geography}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={c.status} halted={killSwitch} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {c.funnel.discovered.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {c.outreachCount.toLocaleString()}
                  </TableCell>
                  <TableCell className="pr-6 text-right tabular-nums">{c.meetings}</TableCell>
                  <TableCell className="pl-10">
                    {reps.length === 0 ? (
                      <span className="text-xs text-muted-foreground">Unassigned</span>
                    ) : (
                      <div className="flex -space-x-2">
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
                  </TableCell>
                  <TableCell className="pr-5">
                    <div className="flex justify-end">
                      <div className="flex w-[9.5rem] items-center gap-2">
                        {c.status === "live" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-28"
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatus(c.id, "paused");
                            }}
                          >
                            <Pause className="mr-1.5 h-3.5 w-3.5" />
                            Pause
                          </Button>
                        )}
                        {c.status === "paused" && (
                          <Button
                            size="sm"
                            className="w-28"
                            disabled={killSwitch}
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatus(c.id, "live");
                            }}
                          >
                            <Play className="mr-1.5 h-3.5 w-3.5" />
                            Resume
                          </Button>
                        )}
                        {c.status === "draft" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-28"
                            disabled={killSwitch}
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatus(c.id, "live");
                            }}
                          >
                            <Play className="mr-1.5 h-3.5 w-3.5" />
                            Activate
                          </Button>
                        )}
                        {c.status === "archived" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-28"
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatus(c.id, "completed");
                            }}
                          >
                            <ArchiveRestore className="mr-1.5 h-3.5 w-3.5" />
                            Restore
                          </Button>
                        )}
                        {c.status === "completed" && <div className="w-28" />}

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                            {c.status !== "archived" && (
                              <DropdownMenuItem
                                onSelect={() => navigate(`/campaigns/${c.id}/edit`)}
                              >
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onSelect={() => duplicateCampaign(c.id)}>
                              <Copy className="mr-2 h-4 w-4" />
                              Duplicate
                            </DropdownMenuItem>
                            {(canComplete || canArchive) && <DropdownMenuSeparator />}
                            {canComplete && (
                              <DropdownMenuItem onSelect={() => setStatus(c.id, "completed")}>
                                <CheckCircle2 className="mr-2 h-4 w-4" />
                                Complete
                              </DropdownMenuItem>
                            )}
                            {canArchive && (
                              <DropdownMenuItem onSelect={() => setStatus(c.id, "archived")}>
                                <Archive className="mr-2 h-4 w-4" />
                                Archive
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}