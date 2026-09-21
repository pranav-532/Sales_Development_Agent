import os
import random

FIRST = ["Sarah", "Daniel", "Priya", "Marcus", "Elena", "Kenji", "Amara", "Lucas", "Nadia", "Owen",
         "Isabel", "Rahul", "Chloe", "Mateo", "Hana", "Victor", "Zara", "Ethan", "Leila", "Jonas"]
LAST = ["Sharma", "Whitfield", "Okafor", "Lindqvist", "Moreau", "Tanaka", "Alvarez", "Novak", "Bennett", "Rao",
        "Fischer", "Costa", "Haddad", "Petrov", "Nguyen", "Mehta", "Larsen", "Khan", "Duarte", "Iyer"]
PRE = ["Cloud", "Nimbus", "Vector", "Bright", "Stack", "Pulse", "Orbit", "Lumen", "Quanta", "Helix", "Nova", "Ember", "Atlas", "Prism", "Tandem"]
SUF = ["Flow", "Labs", "Works", "Systems", "Loop", "Base", "Forge", "Grid", "Deck", "Path"]
OFF_TITLES = ["Marketing Manager", "HR Business Partner", "Sales Director", "Product Designer", "Recruiter"]
OFF_PLACES = ["Brazil", "Germany", "Australia", "Singapore"]
SIGNALS = [
    "Most internal admin work still runs on hand-built scripts and spreadsheets.",
    "Recently hired three platform engineers.",
    "Core product runs on Postgres with a REST API.",
    "Engineering team is fielding a growing queue of internal tooling requests.",
    "Publicly announced a push to cut manual operations work.",
    "Uses several disconnected internal dashboards.",
    "Compliance and audit reporting is handled manually.",
    "Support team reviews calls by hand.",
]


class DemoSource:
    """Fictional dataset for the demo. A real source (for example Apollo) implements the same fetch()."""

    name = "demo-dataset"

    def fetch(self, campaign, cfg: dict, offset: int, count: int) -> list[dict]:
        if offset >= 2000:
            return []
        roles = campaign.target_roles or ["CTO"]
        industries = cfg.get("industries") or [campaign.icp]
        lo = int(cfg.get("companySizeMin") or 50)
        hi = int(cfg.get("companySizeMax") or 1000)
        inboxes = [i.strip() for i in os.getenv("DEMO_INBOXES", "").split(",") if "@" in i]
        out = []
        for idx in range(offset, offset + count):
            r = random.Random(f"{campaign.id}:{idx}")
            title = r.choice(roles)
            size = r.randint(max(lo, 1), max(hi, lo + 1))
            place = campaign.geography or "United States"
            kind = r.random()
            if kind < 0.62:
                pass
            elif kind < 0.74:
                title = r.choice(OFF_TITLES)
            elif kind < 0.86:
                size = max(5, lo // 4) if r.random() < 0.5 else hi * 4
            elif kind < 0.94:
                place = r.choice(OFF_PLACES)
            else:
                size = None  # missing information on purpose
            company = r.choice(PRE) + r.choice(SUF)
            industry = r.choice(industries)
            first, last = FIRST[idx % len(FIRST)], LAST[(idx // len(FIRST)) % len(LAST)]
            email = ""
            if inboxes:
                local, domain = inboxes[idx % len(inboxes)].split("@", 1)
                email = f"{local}+{campaign.id}-{idx}@{domain}"
            facts = [f"{company} is a {industry} company" + (f" with about {size} employees." if size else ".")]
            facts += r.sample(SIGNALS, 2)
            out.append({
                "name": f"{first} {last}",
                "title": title,
                "company": company,
                "domain": f"{company.lower()}.example",
                "email": email,
                "linkedin_url": "",
                "location": place,
                "industry": industry,
                "company_size": size,
                "source": self.name,
                "facts": facts,
            })
        return out


def get_source() -> DemoSource:
    return DemoSource()