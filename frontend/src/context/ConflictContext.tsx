import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { useControl } from "@/context/ControlContext";
import type {
  ConflictItem,
  Prospect,
  Resolution,
  ResolutionAction,
  Rules,
} from "@/lib/conflicts";

export interface ResolvedItem {
  prospect: Prospect;
  resolution: Resolution;
  activeCampaignIds: string[];
}

interface Payload {
  monitored: number;
  rules: Rules;
  open: ConflictItem[];
  resolved: ResolvedItem[];
}

interface ConflictState {
  monitored: number;
  rules: Rules;
  setRules: (r: Rules) => Promise<void>;
  open: ConflictItem[];
  openCount: number;
  resolved: ResolvedItem[];
  resolve: (
    prospectId: string,
    action: ResolutionAction,
    opts: { ownerId?: string; days?: number; note: string }
  ) => Promise<string>;
  reopen: (prospectId: string) => Promise<void>;
}

const EMPTY: Payload = {
  monitored: 0,
  rules: { maxTouches: 3, duplicateWindow: 3 },
  open: [],
  resolved: [],
};

const ConflictContext = createContext<ConflictState | null>(null);

export function ConflictProvider({ children }: { children: ReactNode }) {
  const { campaigns } = useControl();
  const [data, setData] = useState<Payload>(EMPTY);

  const load = useCallback(async () => {
    try {
      setData(await api<Payload>("/conflicts"));
    } catch {
      // keep the last data, the next refresh tries again
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, campaigns]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const setRules = async (r: Rules) => {
    try {
      setData(await api<Payload>("/conflicts/rules", { method: "PUT", body: r }));
    } catch {
      // out-of-range values are rejected, the last valid rules stay
    }
  };

  const resolve: ConflictState["resolve"] = async (prospectId, action, opts) => {
    try {
      setData(
        await api<Payload>(`/conflicts/${prospectId}/resolve`, {
          method: "POST",
          body: { action, ownerId: opts.ownerId, days: opts.days, note: opts.note },
        })
      );
      return "";
    } catch (e) {
      return e instanceof Error ? e.message : "Something went wrong";
    }
  };

  const reopen = async (prospectId: string) => {
    try {
      setData(await api<Payload>(`/conflicts/${prospectId}/reopen`, { method: "POST" }));
    } catch {
      await load();
    }
  };

  return (
    <ConflictContext.Provider
      value={{
        monitored: data.monitored,
        rules: data.rules,
        setRules,
        open: data.open,
        openCount: data.open.length,
        resolved: data.resolved,
        resolve,
        reopen,
      }}
    >
      {children}
    </ConflictContext.Provider>
  );
}

export function useConflicts() {
  const ctx = useContext(ConflictContext);
  if (!ctx) throw new Error("useConflicts must be used inside ConflictProvider");
  return ctx;
}