import type { AgentKey, ApprovalMode, Channel, EscalationKey } from "@/types";

export const OWNERS = ["Aarav Mehta", "Priya Nair"];

export const AGENT_DEFS: { key: AgentKey; name: string; role: string }[] = [
  { key: "icp_fitment", name: "ICP Fitment Agent", role: "Qualifies or rejects prospects against the ICP" },
  { key: "research", name: "Lead Research Agent", role: "Researches companies and people, builds context" },
  { key: "strategy", name: "Outreach Strategy Agent", role: "Decides whether, when, where and how to contact" },
  { key: "personalisation", name: "Personalisation Agent", role: "Writes contextual outreach from prospect context" },
  { key: "conversation", name: "Conversation Agent", role: "Reads replies and decides the next action" },
  { key: "voice", name: "Voice SDR Agent", role: "Runs calls, handles objections, escalates" },
  { key: "followup", name: "Follow-up Agent", role: "Times follow-ups and knows when to stop" },
];

export const CHANNEL_DEFS: { key: Channel; label: string; hint: string; defaultLimit: number }[] = [
  { key: "linkedin", label: "LinkedIn", hint: "Connection requests and messages", defaultLimit: 40 },
  { key: "email", label: "Email", hint: "Cold outreach and follow-ups", defaultLimit: 100 },
  { key: "sms", label: "SMS", hint: "Short messages after a first touch", defaultLimit: 30 },
  { key: "voice", label: "Voice calls", hint: "Outbound calls by the Voice SDR Agent", defaultLimit: 15 },
];

export const ESCALATION_DEFS: { key: EscalationKey; label: string; hint: string }[] = [
  { key: "pricing", label: "Pricing or contract questions", hint: "Hand to a human rep instead of answering" },
  { key: "human_request", label: "Prospect asks for a human", hint: "Transfer the conversation right away" },
  { key: "objection", label: "Legal, security or compliance objection", hint: "Needs an approved answer from a person" },
];

export const APPROVAL_OPTIONS: { key: ApprovalMode; label: string }[] = [
  { key: "none", label: "No approval, agents send on their own" },
  { key: "first_touch", label: "Approve the first message to each prospect" },
  { key: "all", label: "Approve every outgoing message" },
];