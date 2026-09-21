import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActivityEvent, CampaignStats } from "@/types";

export const EMPTY_STATS: CampaignStats = {
  outreach: { linkedin: 0, email: 0, sms: 0, voice: 0 },
  followups: 0,
  outcomes: { positive: 0, negative: 0, neutral: 0 },
  workflows: { active: 0, completed: 0, failed: 0 },
};

export function useCampaignData(campaignId: string | undefined) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [stats, setStats] = useState<CampaignStats>(EMPTY_STATS);

  const load = useCallback(async () => {
    if (!campaignId) return;
    try {
      const [e, s] = await Promise.all([
        api<ActivityEvent[]>(`/campaigns/${campaignId}/activity`),
        api<CampaignStats>(`/campaigns/${campaignId}/stats`),
      ]);
      setEvents(e);
      setStats(s);
    } catch {
      // keep showing the last data, the next refresh will try again
    }
  }, [campaignId]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const decide = async (eventId: string, decision: "approved" | "rejected") => {
    try {
      await api(`/activity/${eventId}/decision`, { method: "POST", body: { decision } });
    } catch {
      // already decided elsewhere, the reload below shows the current state
    }
    await load();
  };

  return { events, stats, reload: load, decide };
}