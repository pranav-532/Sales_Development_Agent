import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";

export type IntegrationStatus = "connected" | "disconnected" | "error";

export interface Integration {
  id: string;
  name: string;
  purpose: string;
  status: IntegrationStatus;
  account: string;
  keyHint: string;
  lastSync: string;
  required: boolean;
  message?: string;
}

export interface ModelDef {
  id: string;
  name: string;
  provider: string;
  note: string;
  cost: "$" | "$$" | "$$$";
  speed: string;
  enabled: boolean;
}

export interface RoutingRule {
  task: string;
  hint: string;
  modelId: string;
}

export interface ToolDef {
  id: string;
  name: string;
  hint: string;
  enabled: boolean;
}

export interface Guardrail {
  id: string;
  label: string;
  hint: string;
  enabled: boolean;
  locked?: boolean;
}

export interface Policies {
  dailyCap: number;
  windowStart: number;
  windowEnd: number;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  docs: number;
  updated: string;
  enabled: boolean;
}

export interface Suppressed {
  id: string;
  value: string;
  type: "email" | "domain";
  reason: string;
  addedBy: string;
  addedAt: string;
}

export type Role = "admin" | "manager" | "viewer";

export interface TeamUser {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export const CURRENT_USER_ID = "u1";

interface SettingsData {
  integrations: Integration[];
  models: ModelDef[];
  routing: RoutingRule[];
  tools: ToolDef[];
  guardrails: Guardrail[];
  policies: Policies;
  knowledge: KnowledgeBase[];
  users: TeamUser[];
  auth: { sso: boolean; mfa: boolean };
}

interface SettingsState extends SettingsData {
  suppressed: Suppressed[];

  connectIntegration: (id: string, account: string, key: string) => Promise<void>;
  disconnectIntegration: (id: string) => Promise<void>;

  setModelEnabled: (id: string, on: boolean) => Promise<void>;
  setRouting: (task: string, modelId: string) => Promise<void>;
  toggleTool: (id: string) => Promise<void>;

  toggleGuardrail: (id: string) => Promise<void>;
  setPolicies: (patch: Partial<Policies>) => Promise<void>;

  toggleKb: (id: string) => Promise<void>;
  addKb: (name: string, description: string) => Promise<void>;
  removeKb: (id: string) => Promise<void>;

  addSuppressed: (value: string, reason: string) => Promise<string>;
  removeSuppressed: (id: string) => Promise<void>;

  setAuth: (patch: Partial<{ sso: boolean; mfa: boolean }>) => Promise<void>;
  inviteUser: (name: string, email: string, role: Role) => Promise<string>;
  setUserRole: (id: string, role: Role) => Promise<void>;
  removeUser: (id: string) => Promise<void>;
}

const EMPTY: SettingsData = {
  integrations: [],
  models: [],
  routing: [],
  tools: [],
  guardrails: [],
  policies: { dailyCap: 500, windowStart: 8, windowEnd: 20 },
  knowledge: [],
  users: [],
  auth: { sso: true, mfa: false },
};

const SettingsContext = createContext<SettingsState | null>(null);

const put = (path: string, body: unknown) => api(path, { method: "PUT", body });
const post = (path: string, body?: unknown) => api(path, { method: "POST", body });
const del = (path: string) => api(path, { method: "DELETE" });

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<SettingsData>(EMPTY);
  const [suppressed, setSuppressed] = useState<Suppressed[]>([]);

  const load = useCallback(async () => {
    try {
      const [s, sup] = await Promise.all([
        api<SettingsData>("/settings"),
        api<Suppressed[]>("/suppressions"),
      ]);
      setData(s);
      setSuppressed(sup);
    } catch {
      // keep the last data
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function mutate(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch {
      // rejected changes are simply not applied, the reload shows the real state
    }
    await load();
  }

  async function mutateWithMessage(fn: () => Promise<unknown>): Promise<string> {
    try {
      await fn();
      await load();
      return "";
    } catch (e) {
      return e instanceof Error ? e.message : "Something went wrong";
    }
  }

  const value: SettingsState = {
    ...data,
    suppressed,

    connectIntegration: (id, account, key) =>
      mutate(() => post(`/settings/integrations/${id}/connect`, { account, key })),
    disconnectIntegration: (id) => mutate(() => post(`/settings/integrations/${id}/disconnect`)),

    setModelEnabled: (id, on) => mutate(() => put(`/settings/models/${id}`, { enabled: on })),
    setRouting: (task, modelId) => mutate(() => put("/settings/routing", { task, modelId })),
    toggleTool: (id) => {
      const t = data.tools.find((x) => x.id === id);
      return mutate(() => put(`/settings/tools/${id}`, { enabled: !t?.enabled }));
    },

    toggleGuardrail: (id) => {
      const g = data.guardrails.find((x) => x.id === id);
      return mutate(() => put(`/settings/guardrails/${id}`, { enabled: !g?.enabled }));
    },
    setPolicies: (patch) => mutate(() => put("/settings/policies", patch)),

    toggleKb: (id) => {
      const k = data.knowledge.find((x) => x.id === id);
      return mutate(() => put(`/settings/knowledge/${id}`, { enabled: !k?.enabled }));
    },
    addKb: (name, description) =>
      mutate(() => post("/settings/knowledge", { name, description })),
    removeKb: (id) => mutate(() => del(`/settings/knowledge/${id}`)),

    addSuppressed: (v, reason) =>
      mutateWithMessage(() => post("/suppressions", { value: v, reason })),
    removeSuppressed: (id) => mutate(() => del(`/suppressions/${id}`)),

    setAuth: (patch) => mutate(() => put("/settings/auth", patch)),
    inviteUser: async (name, email, role) => {
      if (!name.trim()) return "Enter a name";
      return mutateWithMessage(() => post("/settings/users", { name, email, role }));
    },
    setUserRole: (id, role) => mutate(() => put(`/settings/users/${id}/role`, { role })),
    removeUser: (id) => mutate(() => del(`/settings/users/${id}`)),
  };

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used inside SettingsProvider");
  return ctx;
}