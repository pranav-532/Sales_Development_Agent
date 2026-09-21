import type { Channel } from "@/types";

export interface Touch {
  campaignId: string;
  channel: Channel;
  daysAgo: number;
}

export interface Prospect {
  id: string;
  name: string;
  title: string;
  company: string;
  email: string;
  campaignIds: string[];
  touches: Touch[];
  suppressed: boolean;
}

export type IssueKey = "suppressed" | "duplicate" | "overlap" | "frequency" | "instructions";
export type Severity = "high" | "medium" | "low";

export interface Issue {
  key: IssueKey;
  label: string;
  detail: string;
  severity: Severity;
}

export type ResolutionAction = "owner" | "cooldown" | "dnc" | "allow";

export interface Resolution {
  action: ResolutionAction;
  ownerId?: string | null;
  days?: number | null;
  note: string;
  by: string;
  time: string;
  prevCampaignIds: string[];
}

export interface Rules {
  maxTouches: number;
  duplicateWindow: number;
}

export interface ConflictItem {
  prospect: Prospect;
  issues: Issue[];
  severity: Severity;
  activeCampaignIds: string[];
  recentTouches: number;
  recommended: { action: ResolutionAction; ownerId?: string };
}

export const CHANNEL_LABEL: Record<Channel, string> = {
  linkedin: "LinkedIn",
  email: "Email",
  sms: "SMS",
  voice: "Voice",
};