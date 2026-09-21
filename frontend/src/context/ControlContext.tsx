import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type {
  AuditEntry,
  Campaign,
  CampaignStatus,
  NewCampaign,
  NewRep,
  PromptScope,
  PromptVersion,
  Rep,
} from "@/types";

interface ControlState {
  ready: boolean;
  loadError: string;
  reload: () => Promise<void>;
  error: string;
  clearError: () => void;

  campaigns: Campaign[];
  killSwitch: boolean;
  setKillSwitch: (on: boolean) => Promise<void>;
  setStatus: (id: string, status: CampaignStatus) => Promise<void>;
  duplicateCampaign: (id: string) => Promise<void>;
  addCampaign: (input: NewCampaign, systemPrompt: string, goLive: boolean) => Promise<string | null>;
  updateCampaign: (id: string, patch: Partial<Campaign>) => Promise<boolean>;
  toggleAgent: (id: string, agentKey: string) => Promise<void>;
  toggleChannel: (id: string, channel: string) => Promise<void>;

  prompts: PromptVersion[];
  audit: AuditEntry[];
  savePromptVersion: (
    campaignId: string,
    scope: PromptScope,
    content: string,
    note: string
  ) => Promise<number | null>;
  activatePromptVersion: (campaignId: string, scope: PromptScope, version: number) => Promise<void>;

  reps: Rep[];
  addRep: (input: NewRep) => Promise<string | null>;
  updateRep: (id: string, patch: Partial<Rep>) => Promise<void>;
  reactivateRep: (id: string) => Promise<void>;
  assignRep: (campaignId: string, repId: string) => Promise<void>;
  setRepCampaigns: (repId: string, campaignIds: string[]) => Promise<void>;
  offboardRep: (repId: string, replacements: Record<string, string>) => Promise<void>;
}

const ControlContext = createContext<ControlState | null>(null);

const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: "POST", body });

export function ControlProvider({ children }: { children: ReactNode }) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [reps, setReps] = useState<Rep[]>([]);
  const [killSwitch, setKillSwitchState] = useState(false);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    const [c, p, a, r, s] = await Promise.all([
      api<Campaign[]>("/campaigns"),
      api<PromptVersion[]>("/prompts"),
      api<AuditEntry[]>("/audit"),
      api<Rep[]>("/reps"),
      api<{ killSwitch: boolean }>("/control/state"),
    ]);
    setCampaigns(c);
    setPrompts(p);
    setAudit(a);
    setReps(r);
    setKillSwitchState(s.killSwitch);
  }, []);

  const reload = useCallback(async () => {
    try {
      await loadAll();
      setLoadError("");
      setReady(true);
    } catch (e) {
      setLoadError(errorText(e));
    }
  }, [loadAll]);

  const sync = useCallback(async () => {
    try {
      await loadAll();
    } catch {
      // keep the current data
    }
  }, [loadAll]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!ready) return;
    const timer = setInterval(async () => {
      if (document.hidden) return;
      try {
        const [c, s] = await Promise.all([
          api<Campaign[]>("/campaigns"),
          api<{ killSwitch: boolean }>("/control/state"),
        ]);
        setCampaigns(c);
        setKillSwitchState(s.killSwitch);
      } catch {
        // try again on the next tick
      }
    }, 15000);
    return () => clearInterval(timer);
  }, [ready]);

  async function run<T>(fn: () => Promise<T>): Promise<T | null> {
    try {
      setError("");
      return await fn();
    } catch (e) {
      setError(errorText(e));
      return null;
    }
  }

  const putCampaign = (c: Campaign) =>
    setCampaigns((prev) => prev.map((x) => (x.id === c.id ? c : x)));

  const setKillSwitch = async (on: boolean) => {
    const r = await run(() => post<{ killSwitch: boolean }>("/control/kill-switch", { on }));
    if (r) setKillSwitchState(r.killSwitch);
  };

  const setStatus = async (id: string, status: CampaignStatus) => {
    const c = await run(() => post<Campaign>(`/campaigns/${id}/status`, { status }));
    if (c) putCampaign(c);
  };

  const addCampaign = async (input: NewCampaign, systemPrompt: string, goLive: boolean) => {
    const c = await run(() => post<Campaign>("/campaigns", { ...input, systemPrompt, goLive }));
    if (!c) return null;
    await sync();
    return c.id;
  };

  const updateCampaign = async (id: string, patch: Partial<Campaign>) => {
    const c = await run(() => api<Campaign>(`/campaigns/${id}`, { method: "PATCH", body: patch }));
    if (c) putCampaign(c);
    return c !== null;
  };

  const duplicateCampaign = async (id: string) => {
    const c = await run(() => post<Campaign>(`/campaigns/${id}/duplicate`));
    if (c) await sync();
  };

  const toggleAgent = async (id: string, agentKey: string) => {
    const c = await run(() => post<Campaign>(`/campaigns/${id}/agents/${agentKey}/toggle`));
    if (c) putCampaign(c);
  };

  const toggleChannel = async (id: string, channel: string) => {
    const c = await run(() => post<Campaign>(`/campaigns/${id}/channels/${channel}/toggle`));
    if (c) putCampaign(c);
  };

  const savePromptVersion = async (
    campaignId: string,
    scope: PromptScope,
    content: string,
    note: string
  ) => {
    const p = await run(() =>
      post<PromptVersion>(`/campaigns/${campaignId}/prompts`, { scope, content, note })
    );
    if (!p) return null;
    await sync();
    return p.version;
  };

  const activatePromptVersion = async (campaignId: string, scope: PromptScope, version: number) => {
    const p = await run(() =>
      post<PromptVersion>(`/campaigns/${campaignId}/prompts/activate`, { scope, version })
    );
    if (p) await sync();
  };

  const addRep = async (input: NewRep) => {
    const r = await run(() => post<Rep>("/reps", input));
    if (!r) return null;
    await sync();
    return r.id;
  };

  const updateRep = async (id: string, patch: Partial<Rep>) => {
    const r = await run(() => api<Rep>(`/reps/${id}`, { method: "PATCH", body: patch }));
    if (r) await sync();
  };

  const reactivateRep = async (id: string) => {
    const r = await run(() => post<Rep>(`/reps/${id}/reactivate`));
    if (r) await sync();
  };

  const assignRep = async (campaignId: string, repId: string) => {
    const c = await run(() => post<Campaign>(`/campaigns/${campaignId}/reps/${repId}`));
    if (c) putCampaign(c);
  };

  const setRepCampaigns = async (repId: string, campaignIds: string[]) => {
    const r = await run(() =>
      api(`/reps/${repId}/campaigns`, { method: "PUT", body: { campaignIds } })
    );
    if (r) await sync();
  };

  const offboardRep = async (repId: string, replacements: Record<string, string>) => {
    const r = await run(() => post(`/reps/${repId}/offboard`, { replacements }));
    if (r) await sync();
  };

  return (
    <ControlContext.Provider
      value={{
        ready,
        loadError,
        reload,
        error,
        clearError: () => setError(""),
        campaigns,
        killSwitch,
        setKillSwitch,
        setStatus,
        duplicateCampaign,
        addCampaign,
        updateCampaign,
        toggleAgent,
        toggleChannel,
        prompts,
        audit,
        savePromptVersion,
        activatePromptVersion,
        reps,
        addRep,
        updateRep,
        reactivateRep,
        assignRep,
        setRepCampaigns,
        offboardRep,
      }}
    >
      {children}
    </ControlContext.Provider>
  );
}

export function useControl() {
  const ctx = useContext(ControlContext);
  if (!ctx) throw new Error("useControl must be used inside ControlProvider");
  return ctx;
}