import type { CampaignStatus } from "@/types";
import { cn } from "@/lib/utils";

const styles: Record<CampaignStatus, { label: string; box: string; dot: string }> = {
  live: { label: "Live", box: "border-emerald-200 bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  paused: { label: "Paused", box: "border-amber-200 bg-amber-50 text-amber-800", dot: "bg-amber-500" },
  draft: { label: "Draft", box: "border-slate-200 bg-slate-50 text-slate-600", dot: "bg-slate-400" },
  completed: { label: "Completed", box: "border-sky-200 bg-sky-50 text-sky-700", dot: "bg-sky-500" },
  archived: { label: "Archived", box: "border-stone-200 bg-stone-50 text-stone-600", dot: "bg-stone-400" },
};

export default function StatusBadge({
  status,
  halted = false,
}: {
  status: CampaignStatus;
  halted?: boolean;
}) {
  const s = styles[status];
  const stopped = halted && status === "live";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        stopped ? "border-red-200 bg-red-50 text-red-700" : s.box
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          stopped ? "bg-red-500" : s.dot,
          status === "live" && !stopped && "animate-pulse"
        )}
      />
      {stopped ? "Live (halted)" : s.label}
    </span>
  );
}