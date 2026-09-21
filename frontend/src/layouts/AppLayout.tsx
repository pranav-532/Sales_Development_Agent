import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  FileText,
  GitMerge,
  LayoutDashboard,
  PanelLeftClose,
  Power,
  Search,
  Users,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useControl } from "@/context/ControlContext";
import { useConflicts } from "@/context/ConflictContext";
import { Settings } from "lucide-react";

const nav = [
  { to: "/campaigns", label: "Campaigns", icon: LayoutDashboard },
  { to: "/prompts", label: "Prompts", icon: FileText },
  { to: "/reps", label: "Reps", icon: Users },
  { to: "/conflicts", label: "Conflicts", icon: GitMerge },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function AppLayout() {
  const { campaigns, killSwitch, setKillSwitch, error, clearError } = useControl();
  const { openCount } = useConflicts();
  const [collapsed, setCollapsed] = useState(true);
  const liveCount = campaigns.filter((c) => c.status === "live").length;
  const pausedCount = campaigns.filter((c) => c.status === "paused").length;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r bg-card transition-all duration-200",
          collapsed ? "w-16" : "w-60"
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b px-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Open sidebar" : "Close sidebar"}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"
          >
            <Zap className="h-5 w-5" />
          </button>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-sm font-semibold">Reachwell</div>
                <div className="text-xs text-muted-foreground">Control plane</div>
              </div>
              <button
                onClick={() => setCollapsed(true)}
                title="Close sidebar"
                className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </>
          )}
        </div>

        <nav className="flex-1 space-y-1 p-2">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={label}
              className={({ isActive }) =>
                cn(
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  collapsed && "justify-center px-0",
                  isActive && "bg-primary font-medium text-primary-foreground hover:bg-primary hover:text-primary-foreground"
                )
              }
            >
              <span className="relative flex shrink-0">
                <Icon className="h-5 w-5" />
                {to === "/conflicts" && openCount > 0 && collapsed && (
                  <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-card" />
                )}
              </span>
              {!collapsed && <span className="truncate">{label}</span>}
              {!collapsed && to === "/conflicts" && openCount > 0 && (
                <span className="ml-auto rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  {openCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-4 border-b bg-card px-6">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search campaigns, prospects..." className="h-9 pl-9" />
          </div>

          <div className="ml-auto flex items-center gap-3">
            <span
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium",
                killSwitch
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {killSwitch ? "All activity stopped" : `${liveCount} live · ${pausedCount} paused`}
            </span>
            <Button
              size="sm"
              variant={killSwitch ? "outline" : "default"}
              className={
                killSwitch
                  ? "border-red-600 text-red-600 hover:bg-red-50"
                  : "bg-red-600 text-white hover:bg-red-700"
              }
              onClick={() => setKillSwitch(!killSwitch)}
            >
              <Power className="mr-1.5 h-4 w-4" />
              {killSwitch ? "Release kill switch" : "Global kill switch"}
            </Button>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
              AM
            </div>
          </div>
        </header>

        {killSwitch && (
          <div className="bg-red-600 px-6 py-2 text-sm text-white">
            Global kill switch is ON. No agent can take external actions on any campaign.
          </div>
        )}

        {error && (
          <div className="flex items-center justify-between gap-4 bg-amber-100 px-6 py-2 text-sm text-amber-900">
            <span>{error}</span>
            <button onClick={clearError} className="text-xs font-medium underline">
              Dismiss
            </button>
          </div>
        )}

        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}