from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    icp: Mapped[str] = mapped_column(String)
    geography: Mapped[str] = mapped_column(String, default="")
    target_roles: Mapped[list] = mapped_column(JSON, default=list)
    company_criteria: Mapped[str] = mapped_column(Text, default="")
    exclusions: Mapped[str] = mapped_column(Text, default="")
    reference_profiles: Mapped[str] = mapped_column(Text, default="")
    approval_mode: Mapped[str] = mapped_column(String, default="first_touch")
    qualify_threshold: Mapped[int] = mapped_column(Integer, default=70)
    confidence_threshold: Mapped[int] = mapped_column(Integer, default=60)
    escalate_on: Mapped[list] = mapped_column(JSON, default=list)
    agents: Mapped[list] = mapped_column(JSON, default=list)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    rep_ids: Mapped[list] = mapped_column(JSON, default=list)
    funnel: Mapped[dict] = mapped_column(JSON, default=dict)
    outreach_count: Mapped[int] = mapped_column(Integer, default=0)
    meetings: Mapped[int] = mapped_column(Integer, default=0)
    active_prompt_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    pipeline_config: Mapped[dict] = mapped_column(JSON, default=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "status": self.status,
            "icp": self.icp,
            "geography": self.geography,
            "targetRoles": self.target_roles,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "activePromptVersion": self.active_prompt_version,
            "agents": self.agents,
            "channels": self.channels,
            "funnel": self.funnel,
            "outreachCount": self.outreach_count,
            "meetings": self.meetings,
            "repIds": self.rep_ids,
            "companyCriteria": self.company_criteria,
            "exclusions": self.exclusions,
            "referenceProfiles": self.reference_profiles,
            "approvalMode": self.approval_mode,
            "qualifyThreshold": self.qualify_threshold,
            "confidenceThreshold": self.confidence_threshold,
            "escalateOn": self.escalate_on,
            "pipelineConfig": self.pipeline_config,
        }


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    agent_key: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String, default="")


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    prospect_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    ref_id: Mapped[str | None] = mapped_column(String, nullable=True)    
    agent_key: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, default="decision")  # decision | send
    status: Mapped[str] = mapped_column(String, default="completed")
    prompt_version: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String, default="local")  # local | dronahq
    mode: Mapped[str] = mapped_column(String, default="sandbox")  # live | sandbox
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Suppression(Base):
    __tablename__ = "suppressions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, unique=True)
    type: Mapped[str] = mapped_column(String)  # email | domain
    reason: Mapped[str] = mapped_column(String, default="")
    added_by: Mapped[str] = mapped_column(String, default="")
    added_at: Mapped[str] = mapped_column(String, default="")


class GlobalState(Base):
    __tablename__ = "global_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)

class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    scope: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)  # created | activated | rolled_back
    version: Mapped[int] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(String)
    time: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(String, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "campaignId": self.campaign_id,
            "scope": self.scope,
            "action": self.action,
            "version": self.version,
            "author": self.author,
            "time": self.time,
            "note": self.note,
        }


class Rep(Base):
    __tablename__ = "reps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="active")
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    working_hours: Mapped[str] = mapped_column(String, default="9:00 to 18:00 EST")
    channels: Mapped[list] = mapped_column(JSON, default=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "dailyLimit": self.daily_limit,
            "workingHours": self.working_hours,
            "channels": self.channels,
        }


class CampaignStats(Base):
    __tablename__ = "campaign_stats"

    campaign_id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    company: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    campaign_ids: Mapped[list] = mapped_column(JSON, default=list)
    touches: Mapped[list] = mapped_column(JSON, default=list)


class ConflictResolution(Base):
    __tablename__ = "conflict_resolutions"

    prospect_id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String)  # owner | cooldown | dnc | allow
    owner_id: Mapped[str | None] = mapped_column(String, nullable=True)
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String, default="")
    by: Mapped[str] = mapped_column(String)
    time: Mapped[str] = mapped_column(String)
    prev_campaign_ids: Mapped[list] = mapped_column(JSON, default=list)
    added_suppression_id: Mapped[str | None] = mapped_column(String, nullable=True)

class CampaignProspect(Base):
    __tablename__ = "campaign_prospects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    company: Mapped[str] = mapped_column(String, default="")
    domain: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    linkedin_url: Mapped[str] = mapped_column(String, default="")
    location: Mapped[str] = mapped_column(String, default="")
    industry: Mapped[str] = mapped_column(String, default="")
    company_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String, default="")
    facts: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String, default="DISCOVERED", index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icp: Mapped[dict] = mapped_column(JSON, default=dict)
    research: Mapped[dict] = mapped_column(JSON, default=dict)
    strategy: Mapped[dict] = mapped_column(JSON, default=dict)
    message: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self, full: bool = False) -> dict:
        d = {
            "id": self.id,
            "campaignId": self.campaign_id,
            "name": self.name,
            "title": self.title,
            "company": self.company,
            "domain": self.domain,
            "email": self.email,
            "location": self.location,
            "industry": self.industry,
            "companySize": self.company_size,
            "source": self.source,
            "state": self.state,
            "score": self.score,
            "error": self.error,
            "updatedAt": self.updated_at.isoformat(),
        }
        if full:
            d.update(
                facts=self.facts, icp=self.icp, research=self.research,
                strategy=self.strategy, message=self.message,
            )
        return d


class AgentJob(Base):
    __tablename__ = "agent_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    prospect_id: Mapped[str] = mapped_column(String, index=True)
    agent: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)  # queued|running|done|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kb: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    audience: Mapped[list] = mapped_column(JSON, default=list)  # ["*"] or campaign ids

class ProspectMessage(Base):
    __tablename__ = "prospect_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    prospect_id: Mapped[str] = mapped_column(String, index=True)
    direction: Mapped[str] = mapped_column(String)  # out | in
    channel: Mapped[str] = mapped_column(String, default="email")
    kind: Mapped[str] = mapped_column(String, default="message")  # first_touch | followup | reply | inbound | call
    subject: Mapped[str] = mapped_column(String, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="sandbox")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "campaignId": self.campaign_id, "prospectId": self.prospect_id,
            "direction": self.direction, "channel": self.channel, "kind": self.kind,
            "subject": self.subject, "body": self.body, "status": self.status,
            "meta": {k: v for k, v in (self.meta or {}).items() if k != "claim"},
            "createdAt": self.created_at.isoformat(),
        }