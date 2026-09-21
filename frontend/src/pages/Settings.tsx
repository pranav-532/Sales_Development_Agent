import { useState, type ReactNode } from "react";
import { Lock, Plus, Power, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
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
import { useControl } from "@/context/ControlContext";
import {
  CURRENT_USER_ID,
  useSettings,
  type Integration,
  type IntegrationStatus,
  type Role,
} from "@/context/SettingsContext";

const tabs = [
  { key: "integrations", label: "Integrations" },
  { key: "models", label: "Models and tools" },
  { key: "guardrails", label: "Guardrails" },
  { key: "knowledge", label: "Knowledge bases" },
  { key: "suppression", label: "Do-not-contact" },
  { key: "team", label: "Team and access" },
] as const;

type TabKey = (typeof tabs)[number]["key"];

const statusStyles: Record<IntegrationStatus, { label: string; cls: string }> = {
  connected: { label: "Connected", cls: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  disconnected: { label: "Not connected", cls: "border-stone-200 bg-stone-50 text-stone-600" },
  error: { label: "Needs attention", cls: "border-red-200 bg-red-50 text-red-700" },
};

const roleInfo: Record<Role, { label: string; desc: string }> = {
  admin: { label: "Admin", desc: "Everything, including settings, the kill switch and team access" },
  manager: { label: "Manager", desc: "Create and edit campaigns and prompts, pause and resume" },
  viewer: { label: "Viewer", desc: "Read-only access to dashboards and history" },
};

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function Pill({ cls, children }: { cls: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

function Panel({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-4">
        <div>
          <h2 className="font-semibold">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function SwitchRow({
  label,
  hint,
  checked,
  disabled,
  locked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  locked?: boolean;
  onChange: () => void;
}) {
  return (
    <li className="flex items-center gap-4 px-5 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm font-medium">
          {label}
          {locked && (
            <span className="inline-flex items-center gap-1 text-xs font-normal text-muted-foreground">
              <Lock className="h-3 w-3" />
              Always on
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground">{hint}</div>
      </div>
      <Switch checked={checked} disabled={disabled || locked} onCheckedChange={onChange} />
    </li>
  );
}

function NumberField({
  label,
  hint,
  value,
  min,
  max,
  onCommit,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  onCommit: (n: number) => void;
}) {
  const [text, setText] = useState(String(value));
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      <Input
        type="number"
        min={min}
        max={max}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const n = parseInt(e.target.value, 10);
          if (!Number.isNaN(n) && n >= min && n <= max) onCommit(n);
        }}
        onBlur={() => setText(String(value))}
        className="h-9 w-28"
      />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function ConnectDialog({ integration, onClose }: { integration: Integration; onClose: () => void }) {
  const { connectIntegration } = useSettings();
  const [account, setAccount] = useState(integration.account);
  const [key, setKey] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const errors = {
    account: account.trim() ? "" : "Enter the account or workspace",
    key: key.trim().length >= 4 ? "" : "Enter the API key or token",
  };

  const save = () => {
    setSubmitted(true);
    if (errors.account || errors.key) return;
    connectIntegration(integration.id, account, key);
    onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {integration.status === "disconnected" ? "Connect" : "Reconnect"} {integration.name}
          </DialogTitle>
          <DialogDescription>
            Keys go to the backend and are never kept in the browser. This demo keeps only the last
            4 characters to show a hint.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Account or workspace</label>
            <Input value={account} onChange={(e) => setAccount(e.target.value)} />
            {submitted && errors.account && <p className="text-xs text-red-600">{errors.account}</p>}
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">API key or token</label>
            <Input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
            />
            {submitted && errors.key && <p className="text-xs text-red-600">{errors.key}</p>}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save}>Save connection</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function IntegrationsTab() {
  const { integrations, disconnectIntegration } = useSettings();
  const [connectId, setConnectId] = useState<string | null>(null);
  const target = integrations.find((i) => i.id === connectId);
  const bad = integrations.filter((i) => i.status === "error").length;

  return (
    <div className="space-y-4">
      {bad > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {bad} integration needs attention. Agents that depend on it will fail until it is
          reconnected.
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {integrations.map((i) => {
          const s = statusStyles[i.status];
          return (
            <div key={i.id} className="flex flex-col rounded-xl border bg-card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium">{i.name}</div>
                  <div className="text-xs text-muted-foreground">{i.purpose}</div>
                </div>
                <Pill cls={s.cls}>{s.label}</Pill>
              </div>

              <dl className="mt-4 space-y-1.5 text-xs">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Account</dt>
                  <dd className="truncate text-right">{i.account || "-"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Key</dt>
                  <dd className="font-mono">{i.keyHint || "-"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Last sync</dt>
                  <dd>{i.lastSync}</dd>
                </div>
              </dl>

              {i.message && <p className="mt-3 text-xs text-red-700">{i.message}</p>}

              <div className="mt-auto flex gap-2 pt-4">
                <Button
                  size="sm"
                  variant={i.status === "connected" ? "outline" : "default"}
                  onClick={() => setConnectId(i.id)}
                >
                  {i.status === "disconnected" ? "Connect" : "Update key"}
                </Button>
                {i.status !== "disconnected" &&
                  (i.required ? (
                    <span className="self-center text-xs text-muted-foreground">Required</span>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => disconnectIntegration(i.id)}>
                      Disconnect
                    </Button>
                  ))}
              </div>
            </div>
          );
        })}
      </div>
      {target && <ConnectDialog key={target.id} integration={target} onClose={() => setConnectId(null)} />}
    </div>
  );
}

function ModelsTab() {
  const { models, routing, tools, setModelEnabled, setRouting, toggleTool } = useSettings();
  const usedBy = (id: string) => routing.filter((r) => r.modelId === id).length;
  const enabled = models.filter((m) => m.enabled);

  return (
    <div className="space-y-6">
      <Panel title="Available models" subtitle="Which models agents are allowed to use">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Model</TableHead>
              <TableHead>Best for</TableHead>
              <TableHead>Cost</TableHead>
              <TableHead>Speed</TableHead>
              <TableHead>Used by</TableHead>
              <TableHead className="pr-5 text-right">Enabled</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((m) => {
              const used = usedBy(m.id);
              return (
                <TableRow key={m.id}>
                  <TableCell className="pl-5">
                    <div className="font-medium">{m.name}</div>
                    <div className="text-xs text-muted-foreground">{m.provider}</div>
                  </TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">{m.note}</TableCell>
                  <TableCell className="font-mono">{m.cost}</TableCell>
                  <TableCell>{m.speed}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {used} {used === 1 ? "task" : "tasks"}
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    <span title={used > 0 ? "Reassign its tasks before disabling" : undefined}>
                      <Switch
                        checked={m.enabled}
                        disabled={used > 0}
                        onCheckedChange={(v) => setModelEnabled(m.id, v)}
                      />
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Panel>

      <Panel
        title="Model routing"
        subtitle="Use the smallest model that does the job well. This is the main lever on cost per prospect."
      >
        <ul className="divide-y">
          {routing.map((r) => (
            <li key={r.task} className="flex flex-wrap items-center gap-4 px-5 py-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{r.task}</div>
                <div className="text-xs text-muted-foreground">{r.hint}</div>
              </div>
              <Select value={r.modelId} onValueChange={(v) => setRouting(r.task, v)}>
                <SelectTrigger className="w-52">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {enabled.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name} ({m.cost})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Agent tools" subtitle="What agents are allowed to call">
        <ul className="divide-y">
          {tools.map((t) => (
            <SwitchRow
              key={t.id}
              label={t.name}
              hint={t.hint}
              checked={t.enabled}
              onChange={() => toggleTool(t.id)}
            />
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function GuardrailsTab() {
  const { killSwitch, setKillSwitch } = useControl();
  const { guardrails, toggleGuardrail, policies, setPolicies } = useSettings();

  return (
    <div className="space-y-6">
      <Panel title="Global kill switch" subtitle="Stops every autonomous external action on every campaign">
        <div className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <div className={`text-sm font-medium ${killSwitch ? "text-red-700" : ""}`}>
              {killSwitch ? "ON: all autonomous activity is stopped" : "OFF: campaigns run as configured"}
            </div>
            <p className="text-xs text-muted-foreground">
              Same switch as the top bar. Campaigns keep their own Live or Paused state underneath.
            </p>
          </div>
          <Button
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
        </div>
      </Panel>

      <Panel title="Platform guardrails" subtitle="Apply to every campaign, and campaigns cannot switch them off">
        <ul className="divide-y">
          {guardrails.map((g) => (
            <SwitchRow
              key={g.id}
              label={g.label}
              hint={g.hint}
              checked={g.enabled}
              locked={g.locked}
              onChange={() => toggleGuardrail(g.id)}
            />
          ))}
        </ul>
      </Panel>

      <Panel title="Sending policy" subtitle="Organisation-wide limits">
        <div className="grid gap-6 p-5 md:grid-cols-2">
          <NumberField
            label="Platform daily cap"
            hint="Maximum outreach actions per day across all campaigns"
            value={policies.dailyCap}
            min={1}
            max={100000}
            onCommit={(n) => setPolicies({ dailyCap: n })}
          />
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Sending window</label>
            <div className="flex items-center gap-2">
              <Select
                value={String(policies.windowStart)}
                onValueChange={(v) => {
                  const start = Number(v);
                  setPolicies({
                    windowStart: start,
                    windowEnd: Math.max(policies.windowEnd, start + 1),
                  });
                }}
              >
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.slice(0, 23).map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {h}:00
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground">to</span>
              <Select
                value={String(policies.windowEnd)}
                onValueChange={(v) => setPolicies({ windowEnd: Number(v) })}
              >
                <SelectTrigger className="w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOURS.filter((h) => h > policies.windowStart).map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {h}:00
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-muted-foreground">
              Agents send only inside this window, in the prospect's local time
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function KnowledgeTab() {
  const { knowledge, toggleKb, addKb, removeKb } = useSettings();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const taken = knowledge.some((k) => k.name.trim().toLowerCase() === name.trim().toLowerCase());
  const error = !name.trim() ? "Enter a name" : taken ? "A knowledge base with this name exists" : "";

  const close = () => {
    setAdding(false);
    setName("");
    setDesc("");
    setSubmitted(false);
  };

  const save = () => {
    setSubmitted(true);
    if (error) return;
    addKb(name, desc);
    close();
  };

  return (
    <Panel
      title="Shared knowledge bases"
      subtitle="Available to every campaign. Agents retrieve from these before writing anything customer-facing."
      action={
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add
        </Button>
      }
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="pl-5">Knowledge base</TableHead>
            <TableHead>Documents</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead>Enabled</TableHead>
            <TableHead className="w-12 pr-5" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {knowledge.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                No knowledge bases yet.
              </TableCell>
            </TableRow>
          )}
          {knowledge.map((k) => (
            <TableRow key={k.id}>
              <TableCell className="pl-5 whitespace-normal">
                <div className="font-medium">{k.name}</div>
                <div className="text-xs text-muted-foreground">{k.description}</div>
              </TableCell>
              <TableCell className="tabular-nums">{k.docs}</TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">{k.updated}</TableCell>
              <TableCell>
                <Switch checked={k.enabled} onCheckedChange={() => toggleKb(k.id)} />
              </TableCell>
              <TableCell className="pr-5 text-right">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8"
                  aria-label={`Remove ${k.name}`}
                  onClick={() => removeKb(k.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {adding && (
        <Dialog open onOpenChange={(o) => !o && close()}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add knowledge base</DialogTitle>
              <DialogDescription>
                This creates the entry. Documents are ingested and embedded by the RAG service.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
                {submitted && error && <p className="text-xs text-red-600">{error}</p>}
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Description</label>
                <Input value={desc} onChange={(e) => setDesc(e.target.value)} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={close}>
                Cancel
              </Button>
              <Button onClick={save}>Add</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </Panel>
  );
}

function SuppressionTab() {
  const { suppressed, addSuppressed, removeSuppressed } = useSettings();
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const rows = suppressed.filter(
    (s) => !q || s.value.includes(q) || s.reason.toLowerCase().includes(q)
  );

  const add = async () => {
    const err = await addSuppressed(value, reason);
    setError(err);
    if (!err) {
      setValue("");
      setReason("");
    }
  };

  return (
    <div className="space-y-6">
      <Panel
        title="Add to the do-not-contact list"
        subtitle="Applies to every campaign and cannot be overridden by any of them"
      >
        <div className="space-y-2 p-5">
          <div className="flex flex-wrap items-start gap-3">
            <Input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder="Email or domain, e.g. name@company.com or company.com"
              className="w-80"
            />
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
              placeholder="Reason (optional)"
              className="w-64"
            />
            <Button onClick={add}>
              <Plus className="mr-1.5 h-4 w-4" />
              Add
            </Button>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      </Panel>

      <div className="rounded-xl border bg-card">
        <div className="flex items-center justify-between gap-3 border-b px-5 py-3">
          <div>
            <h2 className="font-semibold">Suppressed contacts</h2>
            <p className="text-xs text-muted-foreground">{suppressed.length} on the list</p>
          </div>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search"
              className="h-9 pl-9"
            />
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Contact</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Added</TableHead>
              <TableHead className="w-12 pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  {suppressed.length === 0 ? "The list is empty." : "Nothing matches this search."}
                </TableCell>
              </TableRow>
            )}
            {rows.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="pl-5 font-medium">{s.value}</TableCell>
                <TableCell>
                  <Pill
                    cls={
                      s.type === "domain"
                        ? "border-violet-200 bg-violet-50 text-violet-700"
                        : "border-sky-200 bg-sky-50 text-sky-700"
                    }
                  >
                    {s.type === "domain" ? "Domain" : "Email"}
                  </Pill>
                </TableCell>
                <TableCell className="whitespace-normal text-muted-foreground">{s.reason}</TableCell>
                <TableCell className="whitespace-nowrap">
                  <div className="text-sm">{s.addedBy}</div>
                  <div className="text-xs text-muted-foreground">{s.addedAt}</div>
                </TableCell>
                <TableCell className="pr-5 text-right">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8"
                    aria-label={`Remove ${s.value}`}
                    onClick={() => removeSuppressed(s.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function TeamTab() {
  const { users, auth, setAuth, inviteUser, setUserRole, removeUser } = useSettings();
  const [inviting, setInviting] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("manager");
  const [error, setError] = useState("");

  const close = () => {
    setInviting(false);
    setName("");
    setEmail("");
    setRole("manager");
    setError("");
  };

  const invite = async () => {
    const err = await inviteUser(name, email, role);
    setError(err);
    if (!err) close();
  };

  return (
    <div className="space-y-6">
      <Panel title="Sign-in" subtitle="How people authenticate">
        <ul className="divide-y">
          <SwitchRow
            label="Require single sign-on"
            hint="Everyone signs in through the company identity provider"
            checked={auth.sso}
            onChange={() => setAuth({ sso: !auth.sso })}
          />
          <SwitchRow
            label="Require 2-step verification"
            hint="A second factor on every sign-in"
            checked={auth.mfa}
            onChange={() => setAuth({ mfa: !auth.mfa })}
          />
        </ul>
      </Panel>

      <Panel
        title="Team"
        subtitle="Who can use the control plane"
        action={
          <Button size="sm" onClick={() => setInviting(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Invite
          </Button>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-5">Person</TableHead>
              <TableHead>Role</TableHead>
              <TableHead className="w-12 pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => {
              const me = u.id === CURRENT_USER_ID;
              return (
                <TableRow key={u.id}>
                  <TableCell className="pl-5">
                    <div className="font-medium">
                      {u.name}
                      {me && <span className="ml-2 text-xs font-normal text-muted-foreground">You</span>}
                    </div>
                    <div className="text-xs text-muted-foreground">{u.email}</div>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={u.role}
                      disabled={me}
                      onValueChange={(v) => setUserRole(u.id, v as Role)}
                    >
                      <SelectTrigger className="w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.keys(roleInfo) as Role[]).map((r) => (
                          <SelectItem key={r} value={r}>
                            {roleInfo[r].label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="pr-5 text-right">
                    {!me && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        aria-label={`Remove ${u.name}`}
                        onClick={() => removeUser(u.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <ul className="space-y-1 border-t px-5 py-4 text-xs text-muted-foreground">
          {(Object.keys(roleInfo) as Role[]).map((r) => (
            <li key={r}>
              <span className="font-medium text-foreground">{roleInfo[r].label}:</span> {roleInfo[r].desc}
            </li>
          ))}
        </ul>
      </Panel>

      {inviting && (
        <Dialog open onOpenChange={(o) => !o && close()}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Invite a teammate</DialogTitle>
              <DialogDescription>They get access at the role you pick.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Email</label>
                <Input value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Role</label>
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(roleInfo) as Role[]).map((r) => (
                      <SelectItem key={r} value={r}>
                        {roleInfo[r].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {error && <p className="text-xs text-red-600">{error}</p>}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={close}>
                Cancel
              </Button>
              <Button onClick={invite}>Send invite</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

export default function Settings() {
  const [tab, setTab] = useState<TabKey>("integrations");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <div className="flex flex-wrap gap-6 border-b">
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

      {tab === "integrations" && <IntegrationsTab />}
      {tab === "models" && <ModelsTab />}
      {tab === "guardrails" && <GuardrailsTab />}
      {tab === "knowledge" && <KnowledgeTab />}
      {tab === "suppression" && <SuppressionTab />}
      {tab === "team" && <TeamTab />}
    </div>
  );
}