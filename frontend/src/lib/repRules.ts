import type { Campaign, CampaignStatus, Rep } from "@/types";

export const OPEN_STATUSES: CampaignStatus[] = ["draft", "live", "paused"];

export const isOpen = (c: Campaign) => OPEN_STATUSES.includes(c.status);

export const TIMEZONES = ["EST", "PST", "GMT", "CET", "IST"];

export function missingChannels(c: Campaign, r: Rep) {
  return c.channels
    .filter((ch) => ch.enabled && !r.channels.includes(ch.channel))
    .map((ch) => ch.channel);
}

export function parseHours(s: string) {
  const m = s.match(/^(\d{1,2}):00 to (\d{1,2}):00 (\w+)$/);
  return m
    ? { start: Number(m[1]), end: Number(m[2]), tz: m[3] }
    : { start: 9, end: 18, tz: "EST" };
}

export const formatHours = (start: number, end: number, tz: string) =>
  `${start}:00 to ${end}:00 ${tz}`;